//! Collector-shaped input for the tabbed screen tests. Never compiled into the application.
use system_pulse_collectors::{
    Availability, MonitorDescriptor, MonitorKind, ProcessIdentity, ProcessRow, Reading,
    SensorDescriptor, SensorKind, Snapshot, Unit,
};

pub(super) const GPU_A: &str = "gpu:pci:0000:01:00.0";
pub(super) const GPU_B: &str = "gpu:pci:0000:02:00.0";

fn reading(id: &str, value: f64) -> Reading {
    Reading {
        sensor_id: id.into(),
        value: Some(value),
        total: None,
        availability: Availability::Available,
        reason: None,
        observations: vec![],
    }
}

fn monitor(snapshot: &mut Snapshot, id: &str, title: &str, kind: MonitorKind, summary: &str) {
    snapshot.monitors.push(MonitorDescriptor {
        id: id.into(),
        title: title.into(),
        kind,
        summary_sensor_id: format!("{id}/{summary}"),
    });
}

fn sensor(
    snapshot: &mut Snapshot,
    monitor: &str,
    suffix: &str,
    title: &str,
    physical: (SensorKind, Unit),
    value: f64,
    total: Option<f64>,
) {
    let id = format!("{monitor}/{suffix}");
    snapshot.sensors.push(SensorDescriptor {
        id: id.clone(),
        monitor_id: monitor.into(),
        title: title.into(),
        kind: physical.0,
        unit: physical.1,
        source: "deterministic screen regression fixture".into(),
        scope: format!("Measured channel on {monitor}"),
        scale: None,
    });
    let mut value = reading(&id, value);
    value.total = total;
    snapshot.readings.push(value);
}

pub(super) fn snapshot(sequence: u64) -> Snapshot {
    use MonitorKind as M;
    use SensorKind as K;
    use Unit as U;
    let mut snapshot = Snapshot {
        sequence,
        capture_started_ns: sequence * 1_000_000_000,
        capture_finished_ns: sequence * 1_000_000_000,
        ..Snapshot::default()
    };
    let phase = (sequence % 4) as f64;
    monitor(&mut snapshot, "cpu:host", "Host CPU", M::Cpu, "usage");
    sensor(
        &mut snapshot,
        "cpu:host",
        "usage",
        "CPU usage",
        (K::Percentage, U::Percent),
        28. + phase * 5.,
        None,
    );
    for core in 0..4 {
        sensor(
            &mut snapshot,
            "cpu:host",
            &format!("core-{core}-usage"),
            &format!("CPU {core}"),
            (K::Percentage, U::Percent),
            core as f64 * 17. + phase,
            None,
        );
        sensor(
            &mut snapshot,
            "cpu:host",
            &format!("core-{core}-frequency"),
            &format!("Core {core} clock"),
            (K::Frequency, U::Hertz),
            3_200_000_000.,
            None,
        );
    }
    sensor(
        &mut snapshot,
        "cpu:host",
        "processes",
        "Processes",
        (K::Counter, U::Count),
        2.,
        None,
    );
    sensor(
        &mut snapshot,
        "cpu:host",
        "power",
        "CPU package power",
        (K::Power, U::Watts),
        42. + phase,
        None,
    );
    sensor(
        &mut snapshot,
        "cpu:host",
        "temperature",
        "CPU package temperature",
        (K::Temperature, U::Celsius),
        61. + phase,
        None,
    );
    monitor(
        &mut snapshot,
        "memory:host",
        "Physical memory",
        M::Memory,
        "used",
    );
    for (suffix, title, gib) in [
        ("used", "Used memory", 12.),
        ("available", "Available memory", 20.),
        ("cache", "Cached memory", 4.),
        ("swap", "Swap used", 0.),
    ] {
        sensor(
            &mut snapshot,
            "memory:host",
            suffix,
            title,
            (K::Capacity, U::Bytes),
            gib * 1024_f64.powi(3),
            Some(32. * 1024_f64.powi(3)),
        );
    }
    for (gpu, usage) in [(GPU_A, 73.), (GPU_B, 0.)] {
        // Identical product labels deliberately require stable PCI identity.
        monitor(&mut snapshot, gpu, "Discrete GPU", M::Gpu, "usage");
        sensor(
            &mut snapshot,
            gpu,
            "usage",
            "GPU utilization",
            (K::Percentage, U::Percent),
            usage,
            None,
        );
        sensor(
            &mut snapshot,
            gpu,
            "memory",
            "Dedicated memory",
            (K::Capacity, U::Bytes),
            4. * 1024_f64.powi(3),
            Some(16. * 1024_f64.powi(3)),
        );
        sensor(
            &mut snapshot,
            gpu,
            "power",
            "Board power",
            (K::Power, U::Watts),
            usage * 2.,
            None,
        );
        sensor(
            &mut snapshot,
            gpu,
            "temperature",
            "GPU temperature",
            (K::Temperature, U::Celsius),
            45. + phase,
            None,
        );
    }
    monitor(
        &mut snapshot,
        "volume:root",
        "Root filesystem",
        M::Volume,
        "capacity",
    );
    sensor(
        &mut snapshot,
        "volume:root",
        "capacity",
        "Filesystem used",
        (K::Capacity, U::Bytes),
        250e9,
        Some(1e12),
    );
    monitor(&mut snapshot, "network:eth0", "Ethernet", M::Network, "rx");
    for (device, first, second) in [
        ("volume:root", "read", "write"),
        ("network:eth0", "rx", "tx"),
    ] {
        sensor(
            &mut snapshot,
            device,
            first,
            "Receive / read",
            (K::Rate, U::BytesPerSecond),
            12e6 + phase * 1e6,
            None,
        );
        sensor(
            &mut snapshot,
            device,
            second,
            "Send / write",
            (K::Rate, U::BytesPerSecond),
            0.,
            None,
        );
    }
    if sequence == 3 {
        let gap = snapshot
            .readings
            .iter_mut()
            .find(|reading| reading.sensor_id == "cpu:host/power")
            .unwrap();
        gap.value = None;
        gap.availability = Availability::Unavailable;
        gap.reason = Some("Fixture capture gap".into());
    }
    snapshot.processes = [(401, "compiler", 65.), (402, "idle-worker", 0.)]
        .into_iter()
        .map(|(pid, name, cpu)| ProcessRow {
            identity: ProcessIdentity {
                pid,
                start_time_ticks: pid as u64 * 100,
            },
            name: name.into(),
            user: Some("fixture-user".into()),
            user_reason: None,
            cpu_percent: reading("cpu", cpu),
            memory_bytes: reading("memory", 512. * 1024_f64.powi(2)),
            read_bytes_per_second: reading("read", 0.),
            write_bytes_per_second: reading("write", 1024.),
            threads: reading("threads", 8.),
        })
        .collect();
    snapshot
}
