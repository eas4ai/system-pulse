//! Opt-in latest rendered snapshot evidence. One worker owns serialization and I/O.
//! `accepted_unix_ns` and the raw snapshot never change during elapsed stale updates.
//! `render_revision` orders publications, including same-snapshot stale transitions.
//! `rendered_at_collector_ms` is the collector-clock coordinate used to age samples;
//! it describes presentation evaluation time, never a new source capture.
use crate::{meters, workspace::Data};
use serde::Serialize;
use std::{
    path::PathBuf,
    sync::{Arc, Condvar, Mutex},
    thread::JoinHandle,
};
use system_pulse_collectors::Snapshot;
use system_pulse_model::Sample;

#[derive(Serialize)]
pub(crate) struct Rendered {
    monitor_id: String,
    sensor_id: Option<String>,
    process_identity: Option<system_pulse_collectors::ProcessIdentity>,
    element_id: String,
    label: String,
    sample: Option<Sample>,
}
pub(crate) struct Record {
    snapshot: Arc<Snapshot>,
    accepted_unix_ns: u64,
    render_revision: u64,
    rendered_at_collector_ms: u64,
    rendered: Vec<Rendered>,
}
impl Record {
    pub(crate) fn new(
        snapshot: Arc<Snapshot>,
        accepted_unix_ns: u64,
        render_revision: u64,
        rendered_at_collector_ms: u64,
        data: &Data,
    ) -> Self {
        let mut rendered = Vec::new();
        for monitor in &data.catalog {
            rendered.push(Rendered {
                monitor_id: monitor.id.clone(),
                sensor_id: Some(monitor.summary.clone()),
                process_identity: None,
                element_id: format!("{}:summary", monitor.id),
                label: meters::summary(monitor, &data.history),
                sample: meters::summary_sample(monitor, &data.history),
            });
            for sensor in &monitor.sensors {
                let sample = data
                    .history
                    .latest(&monitor.id, &sensor.id)
                    .cloned()
                    .unwrap_or_else(|| {
                        crate::live::missing(
                            sensor.quantity,
                            sensor.unit,
                            "Sensor or device absent",
                            0,
                        )
                    });
                rendered.push(Rendered {
                    monitor_id: monitor.id.clone(),
                    sensor_id: Some(sensor.id.clone()),
                    process_identity: None,
                    element_id: format!("{}:value:{}", monitor.id, sensor.id),
                    label: meters::sensor_label(monitor, sensor, &sample),
                    sample: Some(sample),
                });
            }
        }
        for process in &data.processes {
            for (column, label) in process.cells.iter().enumerate() {
                rendered.push(Rendered {
                    monitor_id: "processes".into(),
                    sensor_id: None,
                    process_identity: Some(process.identity.clone()),
                    element_id: format!(
                        "process:{}:{}:cell:{column}",
                        process.identity.pid, process.identity.start_time_ticks
                    ),
                    label: label.clone(),
                    sample: None,
                });
            }
        }
        Self {
            snapshot,
            accepted_unix_ns,
            render_revision,
            rendered_at_collector_ms,
            rendered,
        }
    }
}
#[derive(Default)]
struct State {
    latest: Option<Record>,
    stopping: bool,
    error: Option<String>,
}
struct Shared {
    state: Mutex<State>,
    wake: Condvar,
}
pub(crate) struct Writer {
    shared: Arc<Shared>,
    worker: Option<JoinHandle<()>>,
}
impl Writer {
    pub(crate) fn from_env() -> Result<Option<Self>, String> {
        std::env::var_os("SYSTEM_PULSE_DIAGNOSTICS_PATH")
            .map(|path| Self::start(path.into()))
            .transpose()
    }
    pub(crate) fn start(path: PathBuf) -> Result<Self, String> {
        let shared = Arc::new(Shared {
            state: Mutex::new(State::default()),
            wake: Condvar::new(),
        });
        let worker_shared = shared.clone();
        let worker = std::thread::Builder::new().name("pulse-diagnostics".into()).spawn(move || {
            let storage = crate::storage::Storage::default();
            loop {
                let record = {
                    let mut state = worker_shared.state.lock().unwrap_or_else(|p| p.into_inner());
                    while state.latest.is_none() && !state.stopping { state = worker_shared.wake.wait(state).unwrap_or_else(|p| p.into_inner()); }
                    match state.latest.take() { Some(record) => record, None => break }
                };
                let json = serde_json::to_string(&serde_json::json!({ "schema_version": 1, "application_pid": std::process::id(), "accepted_unix_ns": record.accepted_unix_ns, "render_revision": record.render_revision, "rendered_at_collector_ms": record.rendered_at_collector_ms, "snapshot": record.snapshot.as_ref(), "rendered": record.rendered }));
                let result = json.map_err(|e| format!("Serialize snapshot diagnostics: {e}"))
                    .and_then(|json| storage.write_diagnostic(&path, record.render_revision, &json));
                if let Err(error) = result {
                    eprintln!("{error}");
                    worker_shared.state.lock().unwrap_or_else(|p| p.into_inner()).error = Some(error);
                }
            }
        }).map_err(|e| format!("Start snapshot diagnostic writer: {e}"))?;
        Ok(Self {
            shared,
            worker: Some(worker),
        })
    }
    pub(crate) fn submit(&self, record: Record) {
        self.shared
            .state
            .lock()
            .unwrap_or_else(|p| p.into_inner())
            .latest = Some(record);
        self.shared.wake.notify_one();
    }
    pub(crate) fn take_error(&self) -> Option<String> {
        self.shared
            .state
            .lock()
            .unwrap_or_else(|p| p.into_inner())
            .error
            .take()
    }
}
impl Drop for Writer {
    fn drop(&mut self) {
        self.shared
            .state
            .lock()
            .unwrap_or_else(|p| p.into_inner())
            .stopping = true;
        self.shared.wake.notify_one();
        if let Some(worker) = self.worker.take() {
            if worker.join().is_err() {
                eprintln!("Snapshot diagnostic worker panicked");
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn latest_writer_is_atomic_bounded_and_reports_failure() {
        let dir = std::env::temp_dir().join(format!("pulse-diagnostic-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join("latest.json");
        let writer = Writer::start(path.clone()).unwrap();
        for sequence in 1..=20 {
            writer.submit(Record {
                snapshot: Arc::new(Snapshot {
                    sequence,
                    ..Snapshot::default()
                }),
                accepted_unix_ns: sequence,
                render_revision: sequence,
                rendered_at_collector_ms: sequence,
                rendered: vec![],
            });
        }
        drop(writer);
        let record: serde_json::Value =
            serde_json::from_str(&std::fs::read_to_string(&path).unwrap()).unwrap();
        assert_eq!(record["snapshot"]["sequence"], 20);
        assert_eq!(record["application_pid"], std::process::id());
        assert_eq!(std::fs::read_dir(&dir).unwrap().count(), 1);
        std::fs::remove_file(path).unwrap();
        std::fs::remove_dir(dir).unwrap();
    }
    #[test]
    fn failed_diagnostic_write_is_reported() {
        let dir =
            std::env::temp_dir().join(format!("pulse-diagnostic-failure-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let writer = Writer::start(dir.clone()).unwrap();
        writer.submit(Record {
            snapshot: Arc::new(Snapshot {
                sequence: 1,
                ..Snapshot::default()
            }),
            accepted_unix_ns: 1,
            render_revision: 1,
            rendered_at_collector_ms: 1,
            rendered: vec![],
        });
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(2);
        let error = loop {
            if let Some(error) = writer.take_error() {
                break error;
            }
            assert!(
                std::time::Instant::now() < deadline,
                "writer did not report failure"
            );
            std::thread::sleep(std::time::Duration::from_millis(5));
        };
        assert!(error.contains("Save"));
        drop(writer);
        std::fs::remove_dir(dir).unwrap();
    }
    #[test]
    fn diagnostic_snapshot_size_is_independent_of_configuration_limit() {
        let dir =
            std::env::temp_dir().join(format!("pulse-large-diagnostic-{}", std::process::id()));
        let path = dir.join("latest.json");
        let writer = Writer::start(path.clone()).unwrap();
        let title = "x".repeat(system_pulse_model::MAX_CONFIGURATION_BYTES + 1);
        writer.submit(Record {
            snapshot: Arc::new(Snapshot {
                sequence: 1,
                monitors: vec![system_pulse_collectors::MonitorDescriptor {
                    id: "cpu:host".into(),
                    title,
                    kind: system_pulse_collectors::MonitorKind::Cpu,
                    summary_sensor_id: "cpu:host/usage".into(),
                }],
                ..Snapshot::default()
            }),
            accepted_unix_ns: 1,
            render_revision: 1,
            rendered_at_collector_ms: 1,
            rendered: vec![],
        });
        drop(writer);
        let record: serde_json::Value =
            serde_json::from_str(&std::fs::read_to_string(&path).unwrap()).unwrap();
        assert_eq!(
            record["snapshot"]["monitors"][0]["title"]
                .as_str()
                .unwrap()
                .len(),
            system_pulse_model::MAX_CONFIGURATION_BYTES + 1
        );
        assert_eq!(std::fs::read_dir(&dir).unwrap().count(), 1);
        std::fs::remove_file(path).unwrap();
        std::fs::remove_dir(dir).unwrap();
    }
}
