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

#[path = "diagnostic_timing.rs"]
pub(crate) mod timing;
use timing::{Clock, History, Timing, bounded_error};

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
    latest: Option<(Record, Option<Timing>)>,
    stopping: bool,
    error: Option<String>,
    history: Option<History>,
}
struct Shared {
    state: Mutex<State>,
    wake: Condvar,
}
pub(crate) struct Writer {
    shared: Arc<Shared>,
    worker: Option<JoinHandle<()>>,
    clock: Option<Arc<Clock>>,
}
impl Writer {
    pub(crate) fn from_env() -> Result<Option<Self>, String> {
        std::env::var_os("SYSTEM_PULSE_DIAGNOSTICS_PATH")
            .map(|path| {
                if std::env::var_os("SYSTEM_PULSE_DIAGNOSTICS_TRACE").is_some_and(|v| v == "1") {
                    Self::start_with_trace(path.into(), true)
                } else {
                    Self::start(path.into())
                }
            })
            .transpose()
    }
    pub(crate) fn start(path: PathBuf) -> Result<Self, String> {
        Self::start_with_trace(path, false)
    }
    pub(crate) fn start_with_trace(path: PathBuf, trace: bool) -> Result<Self, String> {
        let clock = trace.then(|| Arc::new(Clock::new()));
        let shared = Arc::new(Shared {
            state: Mutex::new(State {
                history: trace.then(History::default),
                ..State::default()
            }),
            wake: Condvar::new(),
        });
        let worker_shared = shared.clone();
        let worker = std::thread::Builder::new()
            .name("pulse-diagnostics".into())
            .spawn(move || run_worker(worker_shared, path))
            .map_err(|e| format!("Start snapshot diagnostic writer: {e}"))?;
        Ok(Self {
            shared,
            worker: Some(worker),
            clock,
        })
    }
    pub(crate) fn timestamp(&self) -> Option<u64> {
        self.clock.as_ref().map(|clock| clock.now())
    }
    pub(crate) fn submit(&self, record: Record) {
        self.submit_timed(record, None, None);
    }
    pub(crate) fn submit_timed(
        &self,
        record: Record,
        model: Option<(u64, u64)>,
        construction_started: Option<u64>,
    ) {
        let timing = self.clock.as_ref().map(|clock| {
            let mut timing = Timing::new(
                clock.clone(),
                record.snapshot.sequence,
                record.render_revision,
                record.accepted_unix_ns,
            );
            if let Some((started, completed)) = model {
                timing.stages.acceptance_started_ns = Some(started);
                timing.stages.model_completed_ns = Some(completed);
            }
            timing.stages.construction_started_ns = construction_started;
            if construction_started.is_some() {
                timing.stages.construction_completed_ns = Some(clock.now());
            }
            timing.stages.submission_started_ns = Some(clock.now());
            timing
        });
        let mut state = self.shared.state.lock().unwrap_or_else(|p| p.into_inner());
        let overwritten = state
            .latest
            .as_ref()
            .map(|(record, _)| record.render_revision);
        if let Some(timing) = &timing {
            if let Some(history) = &mut state.history {
                history.submit(timing.clone(), overwritten);
            }
        }
        state.latest = Some((record, timing));
        // The slot is installed. Stamp before releasing the lock so dequeue
        // cannot precede observed submission completion.
        if let Some((_, Some(timing))) = &mut state.latest {
            timing.stages.submission_completed_ns = Some(timing.clock.now());
            let completed = timing.stages.submission_completed_ns;
            if let Some(history) = &mut state.history {
                if let Some(record) = history.records.back_mut() {
                    record.stages.submission_completed_ns = completed;
                }
            }
        }
        drop(state);
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

#[derive(Serialize)]
struct Publication<'a> {
    schema_version: u32,
    application_pid: u32,
    accepted_unix_ns: u64,
    render_revision: u64,
    rendered_at_collector_ms: u64,
    snapshot: &'a Snapshot,
    rendered: &'a [Rendered],
}

fn publish(
    storage: &crate::storage::Storage,
    path: &std::path::Path,
    record: &Record,
    mut timing: Option<&mut Timing>,
) -> Result<(), String> {
    if let Some(t) = &mut timing {
        t.stages.serialization_started_ns = Some(t.clock.now());
    }
    let json = serde_json::to_string(&Publication {
        schema_version: 1,
        application_pid: std::process::id(),
        accepted_unix_ns: record.accepted_unix_ns,
        render_revision: record.render_revision,
        rendered_at_collector_ms: record.rendered_at_collector_ms,
        snapshot: record.snapshot.as_ref(),
        rendered: &record.rendered,
    })
    .map_err(|e| format!("Serialize snapshot diagnostics: {e}"))?;
    if let Some(t) = &mut timing {
        t.stages.serialization_completed_ns = Some(t.clock.now());
        t.bytes = Some(json.len() as u64);
    }
    match timing {
        Some(timing) => storage.write_diagnostic_timed(path, record.render_revision, &json, timing),
        None => storage.write_diagnostic(path, record.render_revision, &json),
    }
}

fn run_worker(shared: Arc<Shared>, path: PathBuf) {
    let storage = crate::storage::Storage::default();
    loop {
        let (record, mut timing) = {
            let mut state = shared.state.lock().unwrap_or_else(|p| p.into_inner());
            while state.latest.is_none() && !state.stopping {
                state = shared.wake.wait(state).unwrap_or_else(|p| p.into_inner());
            }
            let Some((record, mut timing)) = state.latest.take() else {
                break;
            };
            if let Some(t) = &mut timing {
                t.stages.dequeue_ns = Some(t.clock.now());
                t.outcome = "dequeued";
                if let Some(history) = &mut state.history {
                    history.dequeued = history.dequeued.saturating_add(1);
                    history.update(t.clone());
                }
            }
            (record, timing)
        };
        let result = publish(&storage, &path, &record, timing.as_mut());
        if let Err(error) = &result {
            eprintln!("{error}");
            shared.state.lock().unwrap_or_else(|p| p.into_inner()).error = Some(error.clone());
        }
        if let Some(mut timing) = timing {
            timing.outcome = if result.is_err() {
                "failed"
            } else if timing.stages.rename_completed_ns.is_some() {
                "published"
            } else {
                "skipped_older_revision"
            };
            timing.primary_error = result.as_ref().err().map(|e| bounded_error(e));
            let clock = timing.clock.clone();
            let history = {
                let mut state = shared.state.lock().unwrap_or_else(|p| p.into_inner());
                let history = state.history.as_mut().expect("traced writer has history");
                history.update(timing);
                history.clone()
            };
            let sidecar = serde_json::to_string(&serde_json::json!({
                "schema_version": 1, "instrumented": true, "capacity": timing::CAPACITY,
                "clock": clock.as_ref(), "history": history,
                "coverage": "History captured after a worker attempt; pending entries and interrupted later stages may be incomplete. Null means unobserved, never zero-duration completion."
            }));
            let result = sidecar.map_err(|e| e.to_string()).and_then(|json| {
                storage.write_diagnostic(
                    &path.with_extension("publication-timing.json"),
                    record.render_revision,
                    &json,
                )
            });
            if let Err(error) = result {
                let error = bounded_error(&error);
                let mut state = shared.state.lock().unwrap_or_else(|p| p.into_inner());
                let history = state.history.as_mut().expect("traced writer has history");
                let first_error = (history.sidecar_errors == 0).then(|| error.clone());
                history.sidecar_errors = history.sidecar_errors.saturating_add(1);
                history.last_sidecar_error = Some(error);
                drop(state);
                if let Some(error) = first_error {
                    eprintln!("Publication timing sidecar: {error}");
                }
            }
        }
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

    fn empty_record(sequence: u64) -> Record {
        Record {
            snapshot: Arc::new(Snapshot {
                sequence,
                ..Snapshot::default()
            }),
            accepted_unix_ns: 123,
            render_revision: sequence,
            rendered_at_collector_ms: 1,
            rendered: vec![],
        }
    }

    #[test]
    fn direct_publication_preserves_decoded_snapshot_and_rendered_labels() {
        use system_pulse_collectors::{
            Availability, ProcessIdentity, ProcessRow, RawObservation, Reading,
        };
        let reading = Reading {
            sensor_id: "cpu:host/usage".into(),
            value: Some(12.3456789),
            total: None,
            availability: Availability::Available,
            reason: Some("quoted \"value\"\nµ".into()),
            observations: vec![RawObservation {
                source: "counter".into(),
                captured_ns: u64::MAX,
                read_started_ns: None,
                integers: [("ticks".into(), u64::MAX)].into(),
                decimals: [("invalid".into(), f64::NAN)].into(),
            }],
        };
        let identity = ProcessIdentity {
            pid: 42,
            start_time_ticks: u64::MAX,
        };
        let mut record = empty_record(7);
        let snapshot = Arc::make_mut(&mut record.snapshot);
        snapshot.readings.push(reading.clone());
        snapshot.processes.push(ProcessRow {
            identity: identity.clone(),
            name: "editor\n日本語".into(),
            user: None,
            user_reason: Some("unavailable".into()),
            cpu_percent: reading.clone(),
            memory_bytes: reading.clone(),
            read_bytes_per_second: reading.clone(),
            write_bytes_per_second: reading.clone(),
            threads: reading,
        });
        record.rendered.push(Rendered {
            monitor_id: "processes".into(),
            sensor_id: None,
            process_identity: Some(identity),
            element_id: "process:42".into(),
            label: "editor\n日本語".into(),
            sample: None,
        });
        let expected = serde_json::to_value(Publication {
            schema_version: 1,
            application_pid: std::process::id(),
            accepted_unix_ns: record.accepted_unix_ns,
            render_revision: record.render_revision,
            rendered_at_collector_ms: record.rendered_at_collector_ms,
            snapshot: &record.snapshot,
            rendered: &record.rendered,
        })
        .unwrap();
        let dir = std::env::temp_dir().join(format!("pulse-direct-json-{}", std::process::id()));
        let path = dir.join("latest.json");
        publish(&crate::storage::Storage::default(), &path, &record, None).unwrap();
        let actual: serde_json::Value =
            serde_json::from_slice(&std::fs::read(&path).unwrap()).unwrap();
        assert_eq!(actual, expected);
        assert_eq!(
            actual["snapshot"]["readings"][0]["observations"][0]["integers"]["ticks"],
            u64::MAX
        );
        assert!(
            actual["snapshot"]["readings"][0]["observations"][0]["decimals"]["invalid"].is_null()
        );
        std::fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn timing_history_is_fixed_capacity_and_accounts_for_latest_slot_overwrites() {
        let writer = Writer {
            shared: Arc::new(Shared {
                state: Mutex::new(State {
                    history: Some(History::default()),
                    ..State::default()
                }),
                wake: Condvar::new(),
            }),
            worker: None,
            clock: Some(Arc::new(Clock::new())),
        };
        for sequence in 1..=70 {
            writer.submit(empty_record(sequence));
        }
        let state = writer.shared.state.lock().unwrap();
        let history = state.history.as_ref().unwrap();
        assert_eq!(history.records.len(), 64);
        assert_eq!(history.submitted, 70);
        assert_eq!(history.dequeued, 0);
        assert_eq!(history.overwritten_before_dequeue, 69);
        assert_eq!(history.evicted, 6);
        assert_eq!(history.records.front().unwrap().sequence, 7);
        assert_eq!(state.latest.as_ref().unwrap().0.snapshot.sequence, 70);
        assert!(history.records.iter().take(63).all(|r| r.outcome == "overwritten_before_dequeue" && r.stages.dequeue_ns.is_none()));
        assert_eq!(history.records.back().unwrap().outcome, "submitted");
        let mut cloned = history.clone();
        cloned.update(Timing::new(writer.clock.as_ref().unwrap().clone(), 1, 1, 1));
        assert_eq!(cloned.records.len(), 64);
        assert_eq!(cloned.records.front().unwrap().sequence, 7);
    }

    #[test]
    fn trace_errors_are_bounded_utf8_and_explicit_about_truncation() {
        let error = bounded_error(&"💥".repeat(300));
        assert!(error.len() <= 512);
        assert!(error.ends_with(" [truncated]"));
        assert_eq!(bounded_error("short error"), "short error");
    }

    #[test]
    fn sidecar_failure_never_replaces_the_primary_error_or_leaves_temporary_files() {
        let dir =
            std::env::temp_dir().join(format!("pulse-timing-both-errors-{}", std::process::id()));
        let path = dir.join("latest.json");
        std::fs::create_dir_all(&path).unwrap();
        std::fs::create_dir_all(path.with_extension("publication-timing.json")).unwrap();
        let writer = Writer::start_with_trace(path.clone(), true).unwrap();
        let shared = writer.shared.clone();
        writer.submit(empty_record(1));
        drop(writer);
        let state = shared.state.lock().unwrap();
        let primary = state.error.as_ref().unwrap();
        assert!(primary.contains("Save") && primary.contains("latest.json"));
        assert!(!primary.contains("publication-timing"));
        let history = state.history.as_ref().unwrap();
        assert_eq!(history.sidecar_errors, 1);
        assert!(
            history
                .last_sidecar_error
                .as_ref()
                .unwrap()
                .contains("publication-timing")
        );
        assert!(history.records[0].stages.rename_completed_ns.is_none());
        assert_eq!(std::fs::read_dir(&dir).unwrap().count(), 2);
        std::fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn repeated_sidecar_failures_report_once_and_recover() {
        const CHILD: &str = "SYSTEM_PULSE_TIMING_ERROR_TEST_CHILD";
        if std::env::var_os(CHILD).is_none() {
            // Capture the real worker's stderr without replacing its reporting path.
            let output = std::process::Command::new(std::env::current_exe().unwrap())
                .args([
                    "--exact",
                    "diagnostics::tests::repeated_sidecar_failures_report_once_and_recover",
                    "--nocapture",
                ])
                .env(CHILD, "1")
                .output()
                .unwrap();
            let stderr = String::from_utf8(output.stderr).unwrap();
            assert!(output.status.success(), "child regression failed: {stderr}");
            assert_eq!(
                stderr.matches("Publication timing sidecar:").count(),
                1,
                "{stderr}"
            );
            return;
        }

        let dir = std::env::temp_dir().join(format!(
            "pulse-timing-repeated-error-{}",
            std::process::id()
        ));
        let path = dir.join("latest.json");
        let sidecar = path.with_extension("publication-timing.json");
        std::fs::create_dir_all(&sidecar).unwrap();
        let writer = Writer::start_with_trace(path.clone(), true).unwrap();
        let shared = writer.shared.clone();
        for sequence in 1..=3 {
            writer.submit(empty_record(sequence));
            let deadline = std::time::Instant::now() + std::time::Duration::from_secs(2);
            while shared
                .state
                .lock()
                .unwrap()
                .history
                .as_ref()
                .unwrap()
                .sidecar_errors
                != sequence
            {
                assert!(
                    std::time::Instant::now() < deadline,
                    "sidecar failure not observed"
                );
                std::thread::sleep(std::time::Duration::from_millis(5));
            }
            assert!(
                writer.take_error().is_none(),
                "trace error became a primary failure"
            );
            let primary: serde_json::Value =
                serde_json::from_slice(&std::fs::read(&path).unwrap()).unwrap();
            assert_eq!(primary["render_revision"], sequence);
        }
        let last_error = shared
            .state
            .lock()
            .unwrap()
            .history
            .as_ref()
            .unwrap()
            .last_sidecar_error
            .clone()
            .unwrap();
        std::fs::remove_dir(&sidecar).unwrap();
        writer.submit(empty_record(4));
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(2);
        while !sidecar.is_file() {
            assert!(
                std::time::Instant::now() < deadline,
                "sidecar did not recover"
            );
            std::thread::sleep(std::time::Duration::from_millis(5));
        }
        let recovered: serde_json::Value =
            serde_json::from_slice(&std::fs::read(&sidecar).unwrap()).unwrap();
        assert_eq!(recovered["history"]["sidecar_errors"], 3);
        assert_eq!(recovered["history"]["last_sidecar_error"], last_error);
        assert!(writer.take_error().is_none());

        // A subsequent primary failure must still reach the original error channel.
        std::fs::remove_file(&path).unwrap();
        std::fs::create_dir(&path).unwrap();
        writer.submit(empty_record(5));
        drop(writer);
        let state = shared.state.lock().unwrap();
        let primary = state.error.as_ref().unwrap();
        assert!(primary.contains("latest.json") && !primary.contains("publication-timing"));
        let retained: serde_json::Value =
            serde_json::from_slice(&std::fs::read(&sidecar).unwrap()).unwrap();
        assert_eq!(retained["history"]["sidecar_errors"], 3);
        assert_eq!(retained["history"]["last_sidecar_error"], last_error);
        assert_eq!(retained["history"]["records"][4]["primary_error"], *primary);
        assert_eq!(std::fs::read_dir(&dir).unwrap().count(), 2);
        std::fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn failed_temp_creation_and_revision_skip_do_not_invent_write_completion() {
        let dir = std::env::temp_dir().join(format!("pulse-timing-partial-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join("latest.json");
        let temp = path.with_extension(format!("{}.tmp", std::process::id()));
        std::fs::create_dir_all(&temp).unwrap();
        let storage = crate::storage::Storage::default();
        let clock = Arc::new(Clock::new());
        let mut timing = Timing::new(clock.clone(), 1, 1, 123);
        assert!(publish(&storage, &path, &empty_record(1), Some(&mut timing)).is_err());
        assert!(timing.stages.temp_write_started_ns.is_some());
        assert!(timing.stages.temp_write_completed_ns.is_none());
        assert!(timing.stages.rename_started_ns.is_none());
        assert!(timing.trace_error.as_ref().unwrap().contains("cleanup"));
        std::fs::remove_dir(&temp).unwrap();
        storage.write_diagnostic(&path, 3, "newer").unwrap();
        let mut timing = Timing::new(clock, 2, 2, 123);
        publish(&storage, &path, &empty_record(2), Some(&mut timing)).unwrap();
        assert!(timing.stages.temp_write_started_ns.is_none());
        assert!(timing.stages.rename_completed_ns.is_none());
        assert_eq!(std::fs::read_to_string(path).unwrap(), "newer");
        std::fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn traced_publication_orders_worker_stages_and_identifies_the_replaced_inode() {
        let dir = std::env::temp_dir().join(format!("pulse-timing-order-{}", std::process::id()));
        let path = dir.join("latest.json");
        let writer = Writer::start_with_trace(path.clone(), true).unwrap();
        writer.submit(empty_record(1));
        drop(writer);
        let sidecar: serde_json::Value = serde_json::from_slice(
            &std::fs::read(path.with_extension("publication-timing.json")).unwrap(),
        )
        .unwrap();
        let record = &sidecar["history"]["records"][0];
        assert_eq!(record["sequence"], 1);
        assert_eq!(record["render_revision"], 1);
        assert_eq!(record["accepted_unix_ns"], 123);
        assert_eq!(record["outcome"], "published");
        assert_eq!(sidecar["clock"]["application_pid"], std::process::id());
        assert!(sidecar["clock"]["session_id"].as_str().unwrap().len() < 100);
        let stages = &record["stages"];
        let ordered = [
            "submission_started_ns",
            "submission_completed_ns",
            "dequeue_ns",
            "serialization_started_ns",
            "serialization_completed_ns",
            "temp_write_started_ns",
            "temp_write_completed_ns",
            "rename_started_ns",
            "rename_completed_ns",
        ];
        let times: Vec<_> = ordered
            .iter()
            .map(|key| stages[key].as_u64().unwrap())
            .collect();
        assert!(times.windows(2).all(|pair| pair[0] <= pair[1]));
        assert!(stages["json_conversion_started_ns"].is_null());
        assert!(stages["json_conversion_completed_ns"].is_null());
        assert!(
            stages["acceptance_started_ns"].is_null(),
            "unobserved model stages stay absent"
        );
        assert_eq!(
            record["bytes"].as_u64().unwrap(),
            std::fs::metadata(&path).unwrap().len()
        );
        #[cfg(unix)]
        {
            use std::os::unix::fs::MetadataExt;
            let metadata = std::fs::metadata(&path).unwrap();
            assert_eq!(record["temp_device"], metadata.dev());
            assert_eq!(record["temp_inode"], metadata.ino());
        }
        assert_eq!(std::fs::read_dir(&dir).unwrap().count(), 2);
        std::fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn traced_rename_failure_has_no_invented_completion_and_keeps_primary_error() {
        let dir = std::env::temp_dir().join(format!("pulse-timing-failure-{}", std::process::id()));
        let path = dir.join("latest.json");
        std::fs::create_dir_all(&path).unwrap();
        std::fs::write(path.join("original"), "preserve").unwrap();
        let writer = Writer::start_with_trace(path.clone(), true).unwrap();
        writer.submit(empty_record(1));
        drop(writer);
        let sidecar: serde_json::Value = serde_json::from_slice(
            &std::fs::read(path.with_extension("publication-timing.json")).unwrap(),
        )
        .unwrap();
        let record = &sidecar["history"]["records"][0];
        assert_eq!(record["outcome"], "failed");
        assert!(record["primary_error"].as_str().unwrap().contains("Save"));
        assert!(record["stages"]["rename_started_ns"].is_u64());
        assert!(record["stages"]["rename_completed_ns"].is_null());
        assert_eq!(
            std::fs::read_to_string(path.join("original")).unwrap(),
            "preserve"
        );
        assert_eq!(std::fs::read_dir(&dir).unwrap().count(), 2);
        std::fs::remove_dir_all(dir).unwrap();
    }
    #[test]
    fn latest_writer_is_atomic_bounded_and_reports_failure() {
        let dir = std::env::temp_dir().join(format!("pulse-diagnostic-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join("latest.json");
        let writer = Writer::start(path.clone()).unwrap();
        assert!(writer.timestamp().is_none());
        assert!(writer.shared.state.lock().unwrap().history.is_none());
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
