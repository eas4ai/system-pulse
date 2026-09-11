use super::*;
use std::collections::VecDeque;

struct Fake {
    inventories: VecDeque<Result<Vec<Adapter>>>,
    metrics: VecDeque<Metrics>,
}
impl Backend for Fake {
    fn inventory(&mut self) -> Result<Vec<Adapter>> {
        self.inventories.pop_front().unwrap()
    }
    fn sample(&mut self, _: &Adapter, _: Instant) -> Metrics {
        self.metrics.pop_front().unwrap()
    }
}
fn adapter(vendor: u32, instance: &str, bus: u32) -> Adapter {
    Adapter {
        instance_id: format!(r"PCI\VEN_{vendor:04X}&DEV_1234\{instance}"),
        name: format!("GPU {instance}"),
        vendor,
        pci: Some((0, bus, 0, 0)),
        luid: Some(u64::from(bus) + 1),
    }
}
fn metrics(ns: u64, ticks: u64) -> Metrics {
    Metrics {
        nodes: Ok(vec![
            Node {
                id: 0,
                running_ticks: ticks,
                started_ns: ns - 1,
                ended_ns: ns,
            },
            Node {
                id: 1,
                running_ticks: ticks / 2,
                started_ns: ns - 1,
                ended_ns: ns,
            },
        ]),
        memory: Ok(Memory {
            dedicated: 128,
            shared: 1024,
            dedicated_limit: 512,
            shared_limit: 8192,
            started_ns: ns - 1,
            ended_ns: ns,
        }),
    }
}
fn collector(inventories: Vec<Result<Vec<Adapter>>>, metrics: Vec<Metrics>) -> WindowsGpuCollector {
    WindowsGpuCollector {
        backend: Box::new(Fake {
            inventories: inventories.into(),
            metrics: metrics.into(),
        }),
        inventory: Vec::new(),
        inventory_current: false,
        counters: Counters::default(),
    }
}
fn collect(collector: &mut WindowsGpuCollector) -> Snapshot {
    let mut snapshot = Snapshot::default();
    collector.collect(&mut snapshot, Instant::now());
    snapshot
}
fn reading<'a>(snapshot: &'a Snapshot, suffix: &str) -> &'a Reading {
    snapshot
        .readings
        .iter()
        .find(|r| r.sensor_id.ends_with(suffix))
        .unwrap()
}

#[test]
fn all_vendors_and_same_model_adapters_survive_missing_telemetry() {
    let adapters = vec![
        adapter(0x8086, "integrated", 0),
        adapter(0x8086, "discrete", 1),
        adapter(0x1002, "amd", 2),
        adapter(0x10de, "nvidia", 3),
    ];
    let mut c = collector(
        vec![Ok(adapters.clone())],
        (0..4)
            .map(|_| Metrics::failed(Failure::unavailable("driver API unavailable")))
            .collect(),
    );
    let s = collect(&mut c);
    assert_eq!(s.monitors.len(), 4);
    assert_eq!(
        s.monitors
            .iter()
            .map(|m| &m.id)
            .collect::<std::collections::BTreeSet<_>>()
            .len(),
        4
    );
    assert!(
        s.readings
            .iter()
            .all(|r| r.value.is_none() && r.availability == Availability::Unavailable)
    );
    assert!(
        s.readings
            .iter()
            .all(|r| r.reason.as_ref().is_some_and(|r| !r.is_empty()))
    );
    assert_eq!(
        c.nvidia_identities().values().cloned().collect::<Vec<_>>(),
        vec![adapters[3].id()]
    );
}

#[test]
fn reorder_removal_and_reappearance_do_not_change_identity_or_reuse_baselines() {
    let a = adapter(0x8086, "a", 0);
    let b = adapter(0x1002, "b", 1);
    let mut c = collector(
        vec![
            Ok(vec![a.clone(), b.clone()]),
            Ok(vec![b.clone(), a.clone()]),
            Ok(vec![b.clone()]),
            Ok(vec![a.clone(), b]),
        ],
        vec![
            metrics(1_000_000_000, 0),
            metrics(1_000_000_000, 0),
            metrics(2_000_000_000, 5_000_000),
            metrics(2_000_000_000, 5_000_000),
            metrics(3_000_000_000, 10_000_000),
            metrics(4_000_000_000, 15_000_000),
            metrics(4_000_000_000, 15_000_000),
        ],
    );
    let first = collect(&mut c);
    let second = collect(&mut c);
    assert_eq!(
        first.monitors.iter().map(|m| &m.id).collect::<Vec<_>>(),
        second.monitors.iter().map(|m| &m.id).collect::<Vec<_>>()
    );
    assert!((reading(&second, "/usage").value.unwrap() - 50.0).abs() < 1e-9);
    let removed = collect(&mut c);
    assert_eq!(removed.monitors.len(), 1);
    let returned = collect(&mut c);
    assert_eq!(
        returned
            .readings
            .iter()
            .find(|r| r.sensor_id == format!("{}/usage", a.id()))
            .unwrap()
            .availability,
        Availability::WarmingUp
    );
}

#[test]
fn failed_inventory_keeps_known_devices_failed_and_recovery_starts_fresh() {
    let a = adapter(0x10de, "nvidia", 0);
    let mut c = collector(
        vec![
            Ok(vec![a.clone()]),
            Err(Failure::failed("SetupAPI interrupted")),
            Ok(vec![a]),
            Ok(vec![]),
        ],
        vec![
            metrics(1_000_000_000, 0),
            metrics(3_000_000_000, 10_000_000),
        ],
    );
    collect(&mut c);
    let failed = collect(&mut c);
    assert_eq!(failed.monitors.len(), 1);
    assert_eq!(
        reading(&failed, "/usage").availability,
        Availability::Failed
    );
    assert!(c.nvidia_identities().is_empty());
    assert!(c.counters.is_empty());
    assert_eq!(
        reading(&collect(&mut c), "/usage").availability,
        Availability::WarmingUp
    );
    assert!(collect(&mut c).monitors.is_empty());
    assert!(c.inventory.is_empty());
    assert!(c.counters.is_empty());
}

#[test]
fn initial_discovery_failure_creates_no_synthetic_adapter() {
    let mut c = collector(vec![Err(Failure::failed("enumeration failed"))], vec![]);
    let s = collect(&mut c);
    assert!(s.monitors.is_empty());
    assert_eq!(s.diagnostics[0].availability, Availability::Failed);
}

#[test]
fn runtime_luid_change_invalidates_only_the_affected_rate() {
    let a = adapter(0x8086, "a", 0);
    let mut rebooted = a.clone();
    rebooted.luid = Some(999);
    let mut c = collector(
        vec![Ok(vec![a]), Ok(vec![rebooted])],
        vec![metrics(1_000_000_000, 0), metrics(2_000_000_000, 5_000_000)],
    );
    let first = collect(&mut c);
    let second = collect(&mut c);
    assert_eq!(first.monitors[0].id, second.monitors[0].id);
    assert_eq!(
        reading(&second, "/usage").availability,
        Availability::WarmingUp
    );
    assert_eq!(reading(&second, "/shared-used").value, Some(1024.0));
    assert_eq!(c.counters.len(), 2);
}

#[test]
fn shared_memory_never_becomes_discrete_vram_capacity() {
    let mut c = collector(
        vec![Ok(vec![adapter(0x8086, "a", 0)])],
        vec![metrics(1_000_000_000, 0)],
    );
    let s = collect(&mut c);
    assert_eq!(reading(&s, "/shared-used").total, None);
    assert_eq!(reading(&s, "/shared-used").value, Some(1024.0));
    assert_eq!(reading(&s, "/vram").total, Some(512.0));
    assert_eq!(reading(&s, "/vram").value, Some(128.0));
    assert!(
        s.sensors
            .iter()
            .find(|s| s.id.ends_with("/shared-used"))
            .unwrap()
            .scope
            .contains("not dedicated VRAM")
    );
}

#[test]
fn duplicate_inventory_is_deduplicated_and_ambiguous_pci_is_not_used() {
    let a = adapter(0x10de, "a", 0);
    assert_eq!(
        validate_inventory(vec![a.clone(), a.clone()])
            .unwrap()
            .len(),
        1
    );
    let mut conflict = a.clone();
    conflict.luid = Some(999);
    assert!(validate_inventory(vec![a.clone(), conflict]).is_err());
    let b = adapter(0x10de, "b", 0);
    let mut c = collector(vec![Ok(vec![a, b])], vec![metrics(1, 0), metrics(1, 0)]);
    assert_eq!(collect(&mut c).monitors.len(), 2);
    assert!(c.nvidia_identities().is_empty());
}

#[test]
fn node_counter_failure_reset_and_impossible_delta_never_publish_zero() {
    let a = adapter(0x8086, "a", 0);
    let frames = vec![
        metrics(1_000_000_000, 100),
        metrics(2_000_000_000, 50),
        Metrics::failed(Failure::failed("driver reset")),
        metrics(4_000_000_000, 100),
        metrics(5_000_000_000, 50_000_000),
    ];
    let mut c = collector(vec![Ok(vec![a]); 5], frames);
    for index in 0..5 {
        let s = collect(&mut c);
        let usage = reading(&s, "/usage");
        assert!(usage.value.is_none());
        assert_eq!(
            usage.availability,
            if index == 2 {
                Availability::Failed
            } else {
                Availability::WarmingUp
            }
        );
    }
}

#[test]
fn vendor_merge_uses_sensor_identity_and_does_not_replace_real_data_with_failure() {
    let a = adapter(0x10de, "a", 0);
    let mut c = collector(vec![Ok(vec![a.clone()])], vec![metrics(1_000_000_000, 0)]);
    let mut s = collect(&mut c);
    s.readings.reverse();
    let usage = s
        .sensors
        .iter()
        .find(|d| d.id.ends_with("/usage"))
        .unwrap()
        .clone();
    let shared = s
        .sensors
        .iter()
        .find(|d| d.id.ends_with("/shared-used"))
        .unwrap()
        .clone();
    let vendor = Snapshot {
        sensors: vec![usage.clone(), shared.clone()],
        readings: vec![
            measured(&usage.id, 75., None),
            Failure::failed("NVML unavailable").reading(&shared.id),
        ],
        ..Default::default()
    };
    merge_vendor(&mut s, vendor);
    assert_eq!(s.monitors.len(), 1);
    assert_eq!(reading(&s, "/usage").value, Some(75.));
    assert_eq!(reading(&s, "/shared-used").value, Some(1024.));
    assert_eq!(
        s.readings
            .iter()
            .map(|r| &r.sensor_id)
            .collect::<std::collections::BTreeSet<_>>()
            .len(),
        s.readings.len()
    );
}
