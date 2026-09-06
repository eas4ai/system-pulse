use std::collections::{BTreeMap, BTreeSet};
use system_pulse_collectors::{self as collectors, Availability, ProcessIdentity, Snapshot};
use system_pulse_model::{
    HistoryStore, MonitorDescriptor as Monitor, PhysicalUnit, Quantity, ReadingStatus, Sample,
    SensorDescriptor as Sensor, Workspace,
};

#[cfg(test)]
mod gpu_tests;

pub(crate) fn presentations() -> Vec<Monitor> {
    vec![
        Monitor {
            id: "processes".into(),
            title: "Processes".into(),
            summary: "count".into(),
            sensors: vec![],
        },
        Monitor {
            id: "settings".into(),
            title: "Settings".into(),
            summary: String::new(),
            sensors: vec![],
        },
    ]
}
pub(crate) fn catalog(workspace: &Workspace) -> Vec<Monitor> {
    let mut monitors = workspace.monitors.clone();
    for (id, panel) in &workspace.panels {
        monitors.entry(id.clone()).or_insert_with(|| Monitor {
            id: id.clone(),
            title: format!("Unavailable device · {id}"),
            summary: String::new(),
            sensors: panel
                .sensors
                .keys()
                .map(|id| Sensor {
                    id: id.clone(),
                    title: id.clone(),
                    quantity: Quantity::Scalar,
                    unit: PhysicalUnit::Count,
                })
                .collect(),
        });
    }
    for monitor in presentations() {
        monitors.insert(monitor.id.clone(), monitor);
    }
    let mut monitors: Vec<_> = monitors.into_values().collect();
    monitors.sort_by_key(|m| {
        (
            match m.id.as_str() {
                "cpu:host" => 0,
                "memory:host" => 1,
                "processes" => 3,
                "settings" => 4,
                _ => 2,
            },
            m.id.clone(),
        )
    });
    monitors
}
pub(crate) fn discover(workspace: &mut Workspace, monitors: &[Monitor]) {
    for monitor in monitors {
        let panel = workspace.panel_mut(&monitor.id);
        for sensor in &monitor.sensors {
            panel.sensor_mut(&sensor.id);
        }
        workspace
            .monitors
            .insert(monitor.id.clone(), monitor.clone());
    }
}
pub(crate) fn physical(
    kind: &collectors::SensorKind,
    unit: &collectors::Unit,
) -> (Quantity, PhysicalUnit) {
    use collectors::{SensorKind as K, Unit as U};
    let quantity = match kind {
        K::Percentage => Quantity::Percentage,
        K::Capacity => Quantity::Capacity,
        K::Rate | K::Fan => Quantity::Rate,
        K::Temperature => Quantity::Temperature,
        K::Counter => Quantity::Counter,
        K::Frequency => Quantity::Frequency,
        K::Power => Quantity::Power,
        K::Duration => Quantity::Duration,
        K::Scalar => Quantity::Scalar,
    };
    let unit = match unit {
        U::Percent => PhysicalUnit::Percent,
        U::Bytes => PhysicalUnit::Bytes,
        U::BytesPerSecond => PhysicalUnit::BytesPerSecond,
        U::Celsius => PhysicalUnit::Celsius,
        U::Hertz => PhysicalUnit::Hertz,
        U::Watts => PhysicalUnit::Watts,
        U::Rpm => PhysicalUnit::Rpm,
        U::Count => PhysicalUnit::Count,
        U::CountPerSecond => PhysicalUnit::CountPerSecond,
        U::Milliseconds => PhysicalUnit::Milliseconds,
        U::Seconds => PhysicalUnit::Seconds,
        U::Load => PhysicalUnit::Load,
    };
    // NVML intended fan speed is a percentage, while tachometers are RPM rates.
    (
        if unit == PhysicalUnit::Percent {
            Quantity::Percentage
        } else {
            quantity
        },
        unit,
    )
}
pub(crate) fn convert(
    sensor: &collectors::SensorDescriptor,
    reading: &collectors::Reading,
    at_ms: u64,
) -> Sample {
    let (quantity, unit) = physical(&sensor.kind, &sensor.unit);
    convert_value(quantity, unit, reading, at_ms)
}
pub(crate) fn convert_value(
    quantity: Quantity,
    unit: PhysicalUnit,
    reading: &collectors::Reading,
    at_ms: u64,
) -> Sample {
    let observed_ms = reading
        .observations
        .iter()
        .map(|o| o.captured_ns / 1_000_000)
        .max()
        .unwrap_or(at_ms);
    let mut reason = reading.reason.clone();
    if reading.availability == Availability::Available {
        if let Some(value) = reading.value {
            match Sample::measured(observed_ms, quantity, value, reading.total, unit) {
                Ok(mut sample) => {
                    sample.reason = reason;
                    return sample;
                }
                Err(error) => reason = Some(error),
            }
        } else {
            reason = Some("Source reported available without a value".into());
        }
    }
    let status = match reading.availability {
        Availability::Available | Availability::Failed => ReadingStatus::Failed,
        Availability::WarmingUp => ReadingStatus::WarmingUp,
        Availability::Unavailable => ReadingStatus::Unavailable,
    };
    Sample {
        // This is the outcome of this capture, not a new measurement of any
        // retained raw operand. Successful values keep their source time above.
        at_ms,
        quantity,
        value: None,
        total: None,
        text: String::new(),
        unit: unit.symbol().into(),
        status,
        reason,
    }
}
pub(crate) fn missing(quantity: Quantity, unit: PhysicalUnit, reason: &str, at_ms: u64) -> Sample {
    Sample {
        at_ms,
        quantity,
        value: None,
        total: None,
        text: String::new(),
        unit: unit.symbol().into(),
        status: ReadingStatus::Unavailable,
        reason: Some(reason.into()),
    }
}
pub(crate) fn census(snapshot: &Snapshot) -> Sample {
    if let Some(reading) = snapshot
        .readings
        .iter()
        .find(|r| r.sensor_id == "cpu:host/processes")
    {
        return convert_value(
            Quantity::Counter,
            PhysicalUnit::Count,
            reading,
            snapshot.capture_finished_ns / 1_000_000,
        );
    }
    let failed = snapshot
        .diagnostics
        .iter()
        .find(|d| d.backend == "linux-processes" && d.availability == Availability::Failed);
    let mut sample = missing(
        Quantity::Counter,
        PhysicalUnit::Count,
        failed.map_or("Process census unavailable", |d| d.reason.as_str()),
        snapshot.capture_finished_ns / 1_000_000,
    );
    if failed.is_some() {
        sample.status = ReadingStatus::Failed;
    }
    sample
}
#[derive(Default)]
pub(crate) struct LiveState {
    pub(crate) sequence: Option<u64>,
}
impl LiveState {
    pub(crate) fn accept(
        &mut self,
        snapshot: &Snapshot,
        workspace: &mut Workspace,
        history: &mut HistoryStore,
        now_ms: u64,
        interval_ms: u64,
    ) -> Result<(), String> {
        if self
            .sequence
            .is_some_and(|previous| snapshot.sequence <= previous)
        {
            return Err("Snapshot sequence did not advance".into());
        }
        let mut sensors: BTreeMap<String, Vec<Sensor>> = BTreeMap::new();
        for descriptor in &snapshot.sensors {
            let (quantity, unit) = physical(&descriptor.kind, &descriptor.unit);
            sensors
                .entry(descriptor.monitor_id.clone())
                .or_default()
                .push(Sensor {
                    id: descriptor.id.clone(),
                    title: descriptor.title.clone(),
                    quantity,
                    unit,
                });
        }
        let monitors: Vec<_> = snapshot
            .monitors
            .iter()
            .map(|m| {
                let title = if m.kind == collectors::MonitorKind::Gpu
                    && snapshot
                        .monitors
                        .iter()
                        .filter(|other| other.title == m.title)
                        .count()
                        > 1
                {
                    format!("{} · {}", m.title, m.id)
                } else {
                    m.title.clone()
                };
                let mut rows = sensors.remove(&m.id).unwrap_or_default();
                // Retain known absent sensor labels and choices without retaining their histories.
                if let Some(old) = workspace.monitors.get(&m.id) {
                    for sensor in &old.sensors {
                        if !rows.iter().any(|s| s.id == sensor.id) {
                            rows.push(sensor.clone());
                        }
                    }
                }
                Monitor {
                    id: m.id.clone(),
                    title,
                    summary: m.summary_sensor_id.clone(),
                    sensors: rows,
                }
            })
            .collect();
        discover(workspace, &monitors);
        discover(workspace, &presentations());
        let at_ms = snapshot.capture_finished_ns / 1_000_000;
        let readings: BTreeMap<_, _> = snapshot
            .readings
            .iter()
            .map(|r| (r.sensor_id.as_str(), r))
            .collect();
        let mut present = BTreeSet::new();
        // A repeated native observation may arrive inside a fresh snapshot.
        // Age the retained value without manufacturing another history point.
        history.mark_stale(now_ms, interval_ms.saturating_mul(2));
        for sensor in &snapshot.sensors {
            let mut sample = readings.get(sensor.id.as_str()).map_or_else(
                || {
                    let (q, u) = physical(&sensor.kind, &sensor.unit);
                    missing(q, u, "Sensor reading missing from snapshot", at_ms)
                },
                |reading| convert(sensor, reading, at_ms),
            );
            if sample.status == ReadingStatus::Current
                && now_ms.saturating_sub(sample.at_ms) > interval_ms.saturating_mul(2)
            {
                sample.status = ReadingStatus::Stale;
            }
            present.insert((sensor.monitor_id.clone(), sensor.id.clone()));
            if history
                .latest(&sensor.monitor_id, &sensor.id)
                .is_some_and(|previous| sample.at_ms <= previous.at_ms)
            {
                continue;
            }
            history.push(&sensor.monitor_id, &sensor.id, sample)?;
        }
        let mut count = census(snapshot);
        if count.status == ReadingStatus::Current
            && now_ms.saturating_sub(count.at_ms) > interval_ms.saturating_mul(2)
        {
            count.status = ReadingStatus::Stale;
        }
        if history
            .latest("processes", "count")
            .is_none_or(|previous| count.at_ms > previous.at_ms)
        {
            history.push("processes", "count", count)?;
        }
        present.insert(("processes".into(), "count".into()));
        history.retain_keys(&present);
        self.sequence = Some(snapshot.sequence);
        Ok(())
    }
}
pub(crate) fn reconcile_selection(
    selected: &mut Option<ProcessIdentity>,
    identities: &[ProcessIdentity],
) {
    if selected.as_ref().is_some_and(|id| !identities.contains(id)) {
        *selected = None;
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use system_pulse_collectors::{
        Availability, Reading, SensorDescriptor, SensorKind, Snapshot, Unit,
    };
    fn reading(value: Option<f64>, availability: Availability) -> Reading {
        Reading {
            sensor_id: "cpu:host/usage".into(),
            value,
            total: None,
            availability,
            reason: Some("test reason".into()),
            observations: vec![],
        }
    }
    #[test]
    fn failed_and_delayed_values_keep_status_and_reason() {
        let descriptor = SensorDescriptor {
            id: "cpu:host/usage".into(),
            monitor_id: "cpu:host".into(),
            title: "Usage".into(),
            kind: SensorKind::Percentage,
            unit: Unit::Percent,
            source: "test".into(),
            scope: "host".into(),
            scale: None,
        };
        let failed = convert(&descriptor, &reading(None, Availability::Failed), 1000);
        assert_eq!(failed.status, system_pulse_model::ReadingStatus::Failed);
        assert_eq!(failed.reason.as_deref(), Some("test reason"));
        assert!(failed.value.is_none());
        let mut snapshot = Snapshot {
            sequence: 1,
            capture_finished_ns: 1_000_000_000,
            ..Snapshot::default()
        };
        snapshot.sensors.push(descriptor);
        snapshot
            .readings
            .push(reading(Some(34.), Availability::Available));
        let mut state = LiveState::default();
        let mut workspace = Workspace::new(serde_json::json!({}));
        let mut history = HistoryStore::new(10).unwrap();
        state
            .accept(&snapshot, &mut workspace, &mut history, 4000, 1000)
            .unwrap();
        assert_eq!(
            history.latest("cpu:host", "cpu:host/usage").unwrap().status,
            ReadingStatus::Stale
        );
        assert!(
            state
                .accept(&snapshot, &mut workspace, &mut history, 4000, 1000)
                .is_err()
        );
        assert_eq!(
            history.samples("cpu:host", "cpu:host/usage").unwrap().len(),
            1
        );
    }
    #[test]
    fn census_failure_is_not_zero_and_readable_rows_are_separate() {
        let mut snapshot = Snapshot::default();
        snapshot
            .diagnostics
            .push(system_pulse_collectors::BackendDiagnostic {
                backend: "linux-processes".into(),
                availability: Availability::Failed,
                reason: "denied".into(),
            });
        let sample = census(&snapshot);
        assert_eq!(sample.status, ReadingStatus::Failed);
        assert!(sample.value.is_none());
        snapshot.readings.push(Reading {
            sensor_id: "cpu:host/processes".into(),
            ..reading(Some(1200.), Availability::Available)
        });
        assert_eq!(census(&snapshot).value, Some(1200.));
    }
    #[test]
    fn selection_survives_reordering_but_not_exit_or_pid_reuse() {
        use system_pulse_collectors::ProcessIdentity;
        let first = ProcessIdentity {
            pid: 12,
            start_time_ticks: 1,
        };
        let second = ProcessIdentity {
            pid: 13,
            start_time_ticks: 2,
        };
        let mut selected = Some(first.clone());
        reconcile_selection(&mut selected, &[second.clone(), first.clone()]);
        assert_eq!(selected, Some(first));
        reconcile_selection(
            &mut selected,
            &[
                ProcessIdentity {
                    pid: 12,
                    start_time_ticks: 3,
                },
                second,
            ],
        );
        assert_eq!(selected, None);
        reconcile_selection(&mut selected, &[]);
        assert_eq!(selected, None);
    }
    #[test]
    fn restored_absent_metadata_and_discovery_preserve_user_choices() {
        let mut workspace = Workspace::new(serde_json::json!({}));
        workspace.panel_mut("amdgpu:stable").collapsed = true;
        let before = catalog(&workspace);
        assert!(
            before
                .iter()
                .any(|m| m.id == "amdgpu:stable" && m.title.contains("amdgpu:stable"))
        );
        let snapshot = Snapshot {
            sequence: 1,
            monitors: vec![system_pulse_collectors::MonitorDescriptor {
                id: "amdgpu:stable".into(),
                title: "GPU".into(),
                kind: system_pulse_collectors::MonitorKind::Gpu,
                summary_sensor_id: "amdgpu:stable/usage".into(),
            }],
            ..Snapshot::default()
        };
        LiveState::default()
            .accept(
                &snapshot,
                &mut workspace,
                &mut HistoryStore::new(2).unwrap(),
                0,
                1000,
            )
            .unwrap();
        assert!(workspace.panels["amdgpu:stable"].collapsed);
        assert!(
            catalog(&workspace)
                .iter()
                .any(|m| m.id == "amdgpu:stable" && m.title.contains("GPU"))
        );
    }
}

pub(crate) fn is_fixture_id(id: &str) -> bool {
    matches!(
        id,
        "cpu"
            | "memory"
            | "gpu:fixture-a"
            | "gpu:fixture-b"
            | "volume:fixture-home"
            | "interface:fixture-lan"
    ) || id.contains(":fixture-")
}

#[derive(Clone)]
pub(crate) struct ProcessView {
    pub(crate) identity: ProcessIdentity,
    pub(crate) cells: Vec<String>,
    pub(crate) numeric: [Option<f64>; 5],
}
pub(crate) const PROCESS_COLUMNS: [&str; 8] = [
    "PID",
    "Name",
    "CPU (one core)",
    "Memory",
    "Read I/O",
    "Write I/O",
    "Threads",
    "User",
];
pub(crate) const PROCESS_WIDTHS: [f32; 8] = [85., 240., 200., 180., 320., 320., 160., 240.];
pub(crate) fn process_views(
    snapshot: &Snapshot,
    now_ms: u64,
    threshold_ms: u64,
) -> Vec<ProcessView> {
    snapshot
        .processes
        .iter()
        .map(|process| {
            let numeric = [
                (
                    &process.cpu_percent,
                    Quantity::Percentage,
                    PhysicalUnit::Percent,
                ),
                (
                    &process.memory_bytes,
                    Quantity::Capacity,
                    PhysicalUnit::Bytes,
                ),
                (
                    &process.read_bytes_per_second,
                    Quantity::Rate,
                    PhysicalUnit::BytesPerSecond,
                ),
                (
                    &process.write_bytes_per_second,
                    Quantity::Rate,
                    PhysicalUnit::BytesPerSecond,
                ),
                (&process.threads, Quantity::Counter, PhysicalUnit::Count),
            ];
            let mut cells = vec![process.identity.pid.to_string(), process.name.clone()];
            let sort_values = numeric.map(|(reading, _, _)| {
                (reading.availability == collectors::Availability::Available)
                    .then_some(reading.value)
                    .flatten()
                    .filter(|value| value.is_finite())
            });
            cells.extend(numeric.map(|(reading, quantity, unit)| {
                let mut sample = convert_value(
                    quantity,
                    unit,
                    reading,
                    snapshot.capture_finished_ns / 1_000_000,
                );
                if now_ms.saturating_sub(sample.at_ms) > threshold_ms
                    && sample.status == ReadingStatus::Current
                {
                    sample.status = ReadingStatus::Stale;
                }
                crate::meters::value(Some(&sample))
            }));
            cells.push(process.user.clone().unwrap_or_else(|| {
                format!(
                    "Unavailable · {}",
                    process.user_reason.as_deref().unwrap_or("User unavailable")
                )
            }));
            ProcessView {
                identity: process.identity.clone(),
                cells,
                numeric: sort_values,
            }
        })
        .collect()
}

/// Estimate collector time from the bracketed wall-clock anchor; the delivery
/// clock thereafter advances monotonically even if the host wall clock changes.
pub(crate) fn collector_now_ms(snapshot: &Snapshot, unix_ns: u64) -> u64 {
    snapshot
        .clock_anchor
        .as_ref()
        .map_or(snapshot.capture_finished_ns / 1_000_000, |anchor| {
            anchor
                .monotonic_after_ns
                .saturating_add(unix_ns.saturating_sub(anchor.unix_ns))
                / 1_000_000
        })
}
pub(crate) fn unix_ns() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map_or(0, |d| u64::try_from(d.as_nanos()).unwrap_or(u64::MAX))
}

#[cfg(test)]
mod observation_tests {
    use super::*;
    #[test]
    fn stale_source_in_slow_snapshot_does_not_become_current_at_delivery() {
        let reading = collectors::Reading {
            sensor_id: "cpu:host/usage".into(),
            value: Some(25.),
            total: None,
            availability: Availability::Available,
            reason: None,
            observations: vec![collectors::RawObservation {
                source: "proc".into(),
                captured_ns: 1_000_000_000,
                read_started_ns: Some(900_000_000),
                integers: BTreeMap::new(),
                decimals: BTreeMap::new(),
            }],
        };
        let sample = convert_value(Quantity::Percentage, PhysicalUnit::Percent, &reading, 5000);
        assert_eq!(sample.at_ms, 1000);
    }
    #[test]
    fn process_columns_preserve_full_denied_reasons_with_horizontal_access() {
        let mut cells = vec![String::new(); 8];
        cells[4] = "Unavailable · Permission denied: ".repeat(12);
        let row = ProcessView {
            identity: ProcessIdentity {
                pid: 1,
                start_time_ticks: 1,
            },
            cells,
            numeric: [None; 5],
        };
        let widths = process_widths(std::slice::from_ref(&row));
        assert!(widths[4] >= row.cells[4].chars().count() as f32 * 8.);
    }
}

pub(crate) fn process_widths(rows: &[ProcessView]) -> [f32; 8] {
    let mut widths = PROCESS_WIDTHS;
    for row in rows {
        for (index, text) in row.cells.iter().enumerate().take(8) {
            widths[index] = widths[index].max(text.chars().count() as f32 * 8. + 24.);
        }
    }
    widths
}
