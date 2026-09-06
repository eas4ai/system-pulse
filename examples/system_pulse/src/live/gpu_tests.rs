//! Snapshot-boundary integration cases. These inputs model the descriptors emitted
//! by the native adapters; native source validation remains in collector tests.
use super::*;
use collectors::{MonitorKind, RawObservation, Reading, SensorDescriptor, SensorKind, Unit};
use system_pulse_model::{Meter, Session};

const INTEL: &str = "intel-pci:0000:00:02.0";
const APPLE: &str = "gpu:apple:IODeviceTree:/arm-io/sgx@4000000";
const GIB: f64 = 1_073_741_824.;

fn memory(
    monitor: &str,
    suffix: &str,
    title: &str,
    kind: SensorKind,
    source: &str,
) -> SensorDescriptor {
    SensorDescriptor {
        id: format!("{monitor}/{suffix}"),
        monitor_id: monitor.into(),
        title: title.into(),
        kind,
        unit: Unit::Bytes,
        source: source.into(),
        scope: monitor.into(),
        scale: None,
    }
}

fn descriptors() -> Vec<SensorDescriptor> {
    let mut sensors = vec![
        memory(
            INTEL,
            "shared-region-0",
            "GPU shared region 0 allocation",
            SensorKind::Counter,
            "DRM xe MEM_REGIONS (bytes)",
        ),
        memory(
            INTEL,
            "local-region-3",
            "VRAM region 3 allocation",
            SensorKind::Capacity,
            "DRM xe MEM_REGIONS (bytes)",
        ),
        memory(
            APPLE,
            "shared-allocated",
            "GPU shared allocation",
            SensorKind::Scalar,
            "IOKit/PerformanceStatistics/Alloc system memory;bytes",
        ),
        memory(
            APPLE,
            "shared-in-use",
            "GPU shared memory in use",
            SensorKind::Scalar,
            "IOKit/PerformanceStatistics/In use system memory;bytes",
        ),
        memory(
            "amdgpu:physical-uuid",
            "vram",
            "VRAM",
            SensorKind::Capacity,
            "amdgpu sysfs",
        ),
        memory(
            "nvidia:GPU-one",
            "vram",
            "VRAM",
            SensorKind::Capacity,
            "NVML memory_info v2",
        ),
    ];
    sensors[0].scope = "This device's TTM system-memory region allocation; not total system RAM or unique resident process memory".into();
    sensors[1].scope =
        "Dedicated device-local VRAM region; estimate of allocation, not visible-client sum".into();
    for sensor in &mut sensors[2..4] {
        sensor.scope =
            format!("{APPLE}; hasUnifiedMemory=true; GPU shared memory; no capacity total");
    }
    sensors
}

fn snapshot(sequence: u64, at_ms: u64, sensors: Vec<SensorDescriptor>) -> Snapshot {
    let monitors = sensors
        .iter()
        .map(|s| s.monitor_id.clone())
        .collect::<BTreeSet<_>>()
        .into_iter()
        .map(|id| collectors::MonitorDescriptor {
            summary_sensor_id: sensors
                .iter()
                .find(|s| s.monitor_id == id)
                .unwrap()
                .id
                .clone(),
            id,
            title: "GPU".into(),
            kind: MonitorKind::Gpu,
        })
        .collect();
    let readings = sensors
        .iter()
        .map(|s| Reading {
            sensor_id: s.id.clone(),
            value: Some(GIB),
            total: (s.kind == SensorKind::Capacity).then_some(4. * GIB),
            availability: Availability::Available,
            reason: None,
            observations: vec![RawObservation {
                source: s.source.clone(),
                captured_ns: at_ms * 1_000_000,
                read_started_ns: Some(at_ms.saturating_sub(1) * 1_000_000),
                integers: BTreeMap::new(),
                decimals: BTreeMap::new(),
            }],
        })
        .collect();
    Snapshot {
        sequence,
        capture_started_ns: at_ms * 1_000_000,
        capture_finished_ns: at_ms * 1_000_000,
        monitors,
        sensors,
        readings,
        ..Snapshot::default()
    }
}

fn label(workspace: &Workspace, history: &HistoryStore, source: &SensorDescriptor) -> String {
    let monitor = &workspace.monitors[&source.monitor_id];
    let sensor = monitor.sensors.iter().find(|s| s.id == source.id).unwrap();
    crate::meters::sensor_label(
        monitor,
        sensor,
        history.latest(&monitor.id, &sensor.id).unwrap(),
    )
}

#[test]
fn gpu_memory_preserves_quantity_labels_and_capacity_compatibility() {
    let snapshot = snapshot(1, 1000, descriptors());
    let mut workspace = Workspace::new(serde_json::json!({}));
    let mut history = HistoryStore::new(2).unwrap();
    LiveState::default()
        .accept(&snapshot, &mut workspace, &mut history, 1000, 1000)
        .unwrap();
    for source in &snapshot.sensors {
        let sample = history.latest(&source.monitor_id, &source.id).unwrap();
        let sensor = workspace.monitors[&source.monitor_id]
            .sensors
            .iter()
            .find(|s| s.id == source.id)
            .unwrap();
        let expected = match source.kind {
            SensorKind::Counter => Quantity::Counter,
            SensorKind::Scalar => Quantity::Scalar,
            SensorKind::Capacity => Quantity::Capacity,
            _ => unreachable!(),
        };
        assert_eq!(sample.quantity, expected);
        assert_eq!(sensor.quantity, expected);
        assert_eq!(sensor.unit, PhysicalUnit::Bytes);
        assert_eq!(sample.value, Some(GIB));
        assert_eq!(sample.status, ReadingStatus::Current);
        let visible = label(&workspace, &history, source);
        assert!(visible.contains(&source.title));
        if expected == Quantity::Capacity {
            assert_eq!(sample.total, Some(4. * GIB));
            assert_eq!(sample.capacity_ratio(), Some(0.25));
            assert_eq!(expected.compatible(Meter::Bar), Meter::Bar);
            assert!(visible.contains("1.0 / 4.0 GiB"));
        } else {
            assert_eq!(sample.total, None);
            assert_eq!(sample.capacity_ratio(), None);
            assert_eq!(expected.compatible(Meter::Bar), Meter::Number);
            assert_eq!(expected.compatible(Meter::Sparkline), Meter::Sparkline);
            assert!(visible.contains("1.0 GiB"));
            assert!(!visible.contains("VRAM"));
            assert!(!sample.text.contains('/'));
        }
    }
}

#[test]
fn gpu_unknown_or_zero_total_never_borrows_ram_or_process_capacity() {
    for total in [None, Some(0.)] {
        let mut snapshot = snapshot(1, 1000, descriptors());
        for reading in &mut snapshot.readings {
            if reading.total.is_some() {
                reading.total = total;
            }
        }
        let ram = memory("memory:host", "ram", "RAM", SensorKind::Capacity, "sysinfo");
        snapshot.sensors.push(ram.clone());
        snapshot.readings.push(Reading {
            sensor_id: ram.id.clone(),
            value: Some(16. * GIB),
            total: Some(32. * GIB),
            ..snapshot.readings[0].clone()
        });
        snapshot.monitors.push(collectors::MonitorDescriptor {
            id: ram.monitor_id.clone(),
            title: "Memory".into(),
            kind: MonitorKind::Memory,
            summary_sensor_id: ram.id.clone(),
        });
        let process_memory = Reading {
            sensor_id: "process:42:7/memory".into(),
            value: Some(2. * GIB),
            total: None,
            ..snapshot.readings[0].clone()
        };
        let unrelated = Reading {
            value: None,
            availability: Availability::Unavailable,
            reason: Some("Not exercised by this memory test".into()),
            ..process_memory.clone()
        };
        snapshot.processes.push(collectors::ProcessRow {
            identity: ProcessIdentity {
                pid: 42,
                start_time_ticks: 7,
            },
            name: "workload".into(),
            user: Some("test".into()),
            user_reason: None,
            cpu_percent: unrelated.clone(),
            memory_bytes: process_memory,
            read_bytes_per_second: unrelated.clone(),
            write_bytes_per_second: unrelated.clone(),
            threads: unrelated,
        });
        let mut workspace = Workspace::new(serde_json::json!({}));
        let mut history = HistoryStore::new(2).unwrap();
        LiveState::default()
            .accept(&snapshot, &mut workspace, &mut history, 1000, 1000)
            .unwrap();
        for source in snapshot
            .sensors
            .iter()
            .filter(|s| s.monitor_id != "memory:host")
        {
            let sample = history.latest(&source.monitor_id, &source.id).unwrap();
            assert_eq!(
                sample.total,
                if source.kind == SensorKind::Capacity {
                    total
                } else {
                    None
                }
            );
            assert_eq!(sample.capacity_ratio(), None);
            assert_eq!(sample.value, Some(GIB));
            assert!(label(&workspace, &history, source).contains(&source.title));
        }
        let sample = history.latest("memory:host", &ram.id).unwrap();
        assert_eq!(sample.quantity, Quantity::Capacity);
        assert_eq!(sample.capacity_ratio(), Some(0.5));
        assert!(label(&workspace, &history, &ram).contains("Memory · RAM · 16.0 / 32.0 GiB"));
        assert_eq!(process_views(&snapshot, 1000, 2000)[0].cells[3], "2.0 GiB");
        assert_eq!(PROCESS_COLUMNS[3], "Memory");
    }
}

#[test]
fn gpu_same_name_devices_with_colliding_suffixes_have_distinct_labels() {
    let sensors = [APPLE, "gpu:apple:IODeviceTree:/arm-io-1/sgx@4000000"].map(|id| {
        memory(
            id,
            "shared-allocated",
            "GPU shared allocation",
            SensorKind::Scalar,
            "IOKit/PerformanceStatistics/Alloc system memory;bytes",
        )
    });
    let snapshot = snapshot(1, 1000, sensors.to_vec());
    let mut workspace = Workspace::new(serde_json::json!({}));
    let mut history = HistoryStore::new(2).unwrap();
    LiveState::default()
        .accept(&snapshot, &mut workspace, &mut history, 1000, 1000)
        .unwrap();
    assert_ne!(
        label(&workspace, &history, &sensors[0]),
        label(&workspace, &history, &sensors[1])
    );
}

#[test]
fn gpu_mixed_vendor_choices_and_metadata_survive_restore_absence_and_reorder() {
    let mut snapshot = snapshot(1, 1000, descriptors());
    let mut workspace = Workspace::new(serde_json::json!({"layout": "split"}));
    let mut history = HistoryStore::new(2).unwrap();
    let mut live = LiveState::default();
    live.accept(&snapshot, &mut workspace, &mut history, 1000, 1000)
        .unwrap();
    for (index, source) in snapshot.sensors.iter().enumerate() {
        let panel = workspace.panel_mut(&source.monitor_id);
        panel.collapsed = true;
        let sensor = panel.sensor_mut(&source.id);
        sensor.meter = if index % 2 == 0 {
            Meter::Bar
        } else {
            Meter::Sparkline
        };
        sensor.visible = index % 2 == 0;
        sensor.collapsed = index % 2 != 0;
        sensor.order = 12 - index as u32;
    }
    let expected = workspace.clone();
    let json = Session {
        workspace,
        rejected: None,
    }
    .autosave_json()
    .unwrap();
    let mut session = Session::restore(&json, Workspace::new(serde_json::json!({})), |dock| {
        assert_eq!(dock, &serde_json::json!({"layout": "split"}));
        Ok(())
    });
    assert!(session.rejected.is_none());
    assert_eq!(session.workspace, expected);
    live.accept(
        &Snapshot {
            sequence: 2,
            capture_finished_ns: 2_000_000_000,
            ..Snapshot::default()
        },
        &mut session.workspace,
        &mut history,
        2000,
        1000,
    )
    .unwrap();
    assert_eq!(history.series_count(), 1); // Only the process census remains.
    for source in &snapshot.sensors {
        let monitor = &session.workspace.monitors[&source.monitor_id];
        let missing = crate::meters::summary_sample(monitor, &history).unwrap();
        assert_eq!(missing.status, ReadingStatus::Unavailable);
        assert_eq!(missing.value, None);
        assert_eq!(missing.unit, "B");
        assert!(crate::meters::summary(monitor, &history).contains("Sensor or device absent"));
    }
    snapshot.sequence = 3;
    snapshot.sensors.reverse();
    snapshot.monitors.reverse();
    snapshot.readings.reverse();
    for reading in &mut snapshot.readings {
        reading.observations[0].captured_ns = 3_000_000_000;
    }
    snapshot.capture_finished_ns = 3_000_000_000;
    live.accept(&snapshot, &mut session.workspace, &mut history, 3000, 1000)
        .unwrap();
    assert_eq!(session.workspace.panels, expected.panels);
    assert_eq!(history.series_count(), snapshot.sensors.len() + 1);
    for source in &snapshot.sensors {
        let monitor = &session.workspace.monitors[&source.monitor_id];
        let descriptor = monitor.sensors.iter().find(|s| s.id == source.id).unwrap();
        let saved = session.workspace.panels[&source.monitor_id].sensors[&source.id].meter;
        if source.kind != SensorKind::Capacity && saved == Meter::Bar {
            assert_eq!(descriptor.quantity.compatible(saved), Meter::Number);
            assert_eq!(saved, Meter::Bar);
        }
        assert!(label(&session.workspace, &history, source).contains(&source.title));
    }
}

#[test]
fn gpu_cached_source_does_not_abort_fresh_fields_or_refresh_old_memory() {
    let mut snapshot = snapshot(1, 1000, descriptors());
    let mut workspace = Workspace::new(serde_json::json!({}));
    let mut history = HistoryStore::new(2).unwrap();
    let mut live = LiveState::default();
    live.accept(&snapshot, &mut workspace, &mut history, 1000, 1000)
        .unwrap();
    snapshot.sequence = 2;
    snapshot.capture_finished_ns = 5_000_000_000;
    // Apple native values repeat an old capture while every other adapter is fresh.
    for reading in &mut snapshot.readings {
        if !reading.sensor_id.starts_with(APPLE) {
            reading.observations[0].captured_ns = 5_000_000_000;
        }
    }
    live.accept(&snapshot, &mut workspace, &mut history, 5000, 1000)
        .unwrap();
    for source in &snapshot.sensors {
        let sample = history.latest(&source.monitor_id, &source.id).unwrap();
        if source.monitor_id == APPLE {
            assert_eq!(sample.status, ReadingStatus::Stale);
            assert_eq!(sample.at_ms, 1000);
            assert_eq!(sample.chart_value(), None);
            assert_eq!(history.samples(APPLE, &source.id).unwrap().len(), 1);
            assert!(label(&workspace, &history, source).contains("Stale"));
        } else {
            assert_eq!(sample.status, ReadingStatus::Current);
            assert_eq!(sample.at_ms, 5000);
        }
    }
    snapshot.sequence = 3;
    snapshot.capture_finished_ns = 6_000_000_000;
    for reading in &mut snapshot.readings {
        reading.observations[0].read_started_ns = Some(499_000_000);
        reading.observations[0].captured_ns = if reading.sensor_id.starts_with(APPLE) {
            500_000_000 // Even an older native capture cannot move history backward.
        } else {
            6_000_000_000
        };
    }
    live.accept(&snapshot, &mut workspace, &mut history, 6000, 1000)
        .unwrap();
    for source in &snapshot.sensors {
        let sample = history.latest(&source.monitor_id, &source.id).unwrap();
        assert_eq!(
            sample.at_ms,
            if source.monitor_id == APPLE {
                1000
            } else {
                6000
            }
        );
        assert_eq!(
            sample.status,
            if source.monitor_id == APPLE {
                ReadingStatus::Stale
            } else {
                ReadingStatus::Current
            }
        );
        assert!(
            history
                .samples(&source.monitor_id, &source.id)
                .unwrap()
                .len()
                <= 2
        );
    }
}

#[test]
fn gpu_failed_cached_values_are_explicit_and_recover_independently() {
    let mut snapshot = snapshot(1, 1000, descriptors());
    let mut workspace = Workspace::new(serde_json::json!({}));
    let mut history = HistoryStore::new(2).unwrap();
    let mut live = LiveState::default();
    live.accept(&snapshot, &mut workspace, &mut history, 1000, 1000)
        .unwrap();
    for (sequence, availability, expected) in [
        (2, Availability::Failed, ReadingStatus::Failed),
        (3, Availability::Unavailable, ReadingStatus::Unavailable),
        (4, Availability::WarmingUp, ReadingStatus::WarmingUp),
        // A retry that repeats the old measured operand cannot erase the newer outcome.
        (5, Availability::Available, ReadingStatus::WarmingUp),
        (6, Availability::Available, ReadingStatus::Current),
    ] {
        snapshot.sequence = sequence;
        snapshot.capture_finished_ns = sequence * 1_000_000_000;
        for reading in &mut snapshot.readings {
            reading.observations[0].captured_ns = sequence * 1_000_000_000;
            if reading.sensor_id.ends_with("shared-allocated") {
                reading.availability = availability.clone();
                reading.reason = Some("native memory query outcome".into());
                // Deliberately retain the old operand: unsuccessful outcomes must discard it.
                if availability != Availability::Available || sequence == 5 {
                    reading.observations[0].captured_ns = 1_000_000_000;
                }
            }
        }
        live.accept(
            &snapshot,
            &mut workspace,
            &mut history,
            sequence * 1000,
            1000,
        )
        .unwrap();
        let id = format!("{APPLE}/shared-allocated");
        let sample = history.latest(APPLE, &id).unwrap();
        assert_eq!(sample.status, expected);
        assert_eq!(
            sample.value,
            (expected == ReadingStatus::Current).then_some(GIB)
        );
        assert_eq!(sample.quantity, Quantity::Scalar);
        assert_eq!(sample.total, None);
        assert_eq!(
            sample.at_ms,
            if sequence == 5 { 4000 } else { sequence * 1000 }
        );
        let source = snapshot.sensors.iter().find(|s| s.id == id).unwrap();
        assert!(label(&workspace, &history, source).contains("native memory query outcome"));
        assert_eq!(
            history
                .latest(APPLE, &format!("{APPLE}/shared-in-use"))
                .unwrap()
                .status,
            ReadingStatus::Current
        );
        assert!(history.samples(APPLE, &id).unwrap().len() <= 2);
    }
}

#[test]
fn gpu_fresh_snapshot_survives_repeated_host_census_observation() {
    let mut snapshot = snapshot(1, 1000, descriptors());
    snapshot.readings.push(Reading {
        sensor_id: "cpu:host/processes".into(),
        value: Some(42.),
        total: None,
        ..snapshot.readings[0].clone()
    });
    let mut workspace = Workspace::new(serde_json::json!({}));
    let mut history = HistoryStore::new(2).unwrap();
    let mut live = LiveState::default();
    live.accept(&snapshot, &mut workspace, &mut history, 1000, 1000)
        .unwrap();
    snapshot.sequence = 2;
    snapshot.capture_finished_ns = 5_000_000_000;
    for reading in &mut snapshot.readings {
        if reading.sensor_id != "cpu:host/processes" {
            reading.observations[0].captured_ns = 5_000_000_000;
        }
    }
    live.accept(&snapshot, &mut workspace, &mut history, 5000, 1000)
        .unwrap();
    assert_eq!(live.sequence, Some(2));
    let census = history.latest("processes", "count").unwrap();
    assert_eq!(census.status, ReadingStatus::Stale);
    assert_eq!(census.at_ms, 1000);
    assert_eq!(history.samples("processes", "count").unwrap().len(), 1);
    for source in &snapshot.sensors {
        let sample = history.latest(&source.monitor_id, &source.id).unwrap();
        assert_eq!(sample.status, ReadingStatus::Current);
        assert_eq!(sample.at_ms, 5000);
    }
    snapshot.sequence = 3;
    snapshot.capture_finished_ns = 6_000_000_000;
    for reading in &mut snapshot.readings {
        if reading.sensor_id == "cpu:host/processes" {
            reading.availability = Availability::Failed;
            reading.reason = Some("Process census query failed".into());
        } else {
            reading.observations[0].captured_ns = 6_000_000_000;
        }
    }
    live.accept(&snapshot, &mut workspace, &mut history, 6000, 1000)
        .unwrap();
    let census = history.latest("processes", "count").unwrap();
    assert_eq!(census.status, ReadingStatus::Failed);
    assert_eq!(census.value, None);
    assert_eq!(census.at_ms, 6000);
    assert_eq!(census.quantity, Quantity::Counter);
    assert_eq!(history.samples("processes", "count").unwrap().len(), 2);
    assert!(
        crate::meters::value(Some(census)).contains("Failed · count · Process census query failed")
    );
}
