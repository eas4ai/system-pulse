//! Direct Linux performance counters. Percentages retain their engine scope.
use super::{
    Clock,
    native::{Counter, PerfCounter},
};
use super::{Device, drm::Engine, sysfs};
use crate::{counters::*, types::*};
use std::collections::BTreeMap;
use std::{
    io,
    path::{Path, PathBuf},
};
type Factory = Box<dyn FnMut(&Spec) -> io::Result<Box<dyn Counter>> + Send>;
struct Slot {
    spec: Spec,
    handle: Option<Box<dyn Counter>>,
}
pub(super) struct Pmu {
    slots: BTreeMap<String, Slot>,
    counters: Counters,
    factory: Factory,
}
impl Pmu {
    pub(super) fn new() -> Self {
        Self {
            slots: BTreeMap::new(),
            counters: Counters::default(),
            factory: Box::new(PerfCounter::open),
        }
    }
    fn sample_specs(
        &mut self,
        s: &mut Snapshot,
        id: &str,
        clock: &Clock,
        specs: io::Result<Vec<Spec>>,
    ) {
        let prefix = format!("{id}/");
        let error = match specs {
            Ok(mut specs) => {
                // A failed event config cannot establish an engine class. Preserve
                // the previous attributable identity when this event was known.
                for spec in &mut specs {
                    if spec.metadata_error.is_some()
                        && let Some(slot) = self.slots.iter().find_map(|(key, slot)| {
                            (key.starts_with(&prefix)
                                && slot.spec.event_path == spec.event_path
                                && spec.event_path.is_some())
                            .then_some(slot)
                        })
                    {
                        let error = spec.metadata_error.take();
                        *spec = slot.spec.clone();
                        spec.metadata_error = error;
                    }
                }
                self.slots.retain(|key, _| {
                    !key.starts_with(&prefix)
                        || specs.iter().any(|v| key == &format!("{prefix}{}", v.id))
                });
                for spec in specs {
                    let key = format!("{prefix}{}", spec.id);
                    if self.slots.get(&key).is_some_and(|slot| slot.spec != spec) {
                        self.slots.remove(&key);
                        self.counters.derive(
                            &key,
                            Err("PMU configuration changed".into()),
                            utilization,
                        );
                    }
                    self.slots.entry(key).or_insert(Slot { spec, handle: None });
                }
                None
            }
            Err(e) => Some(e),
        };
        let mut first = None;
        let mut count = 0;
        for (key, slot) in self
            .slots
            .iter_mut()
            .filter(|(key, _)| key.starts_with(&prefix))
        {
            count += 1;
            if slot.spec.energy_denominator == 0 {
                first.get_or_insert_with(|| key.clone());
            }
            let spec = &slot.spec;
            let source = format!(
                "{} perf_event_open config={:#x}{} ({})",
                spec.pmu.display(),
                spec.active,
                spec.total.map_or(String::new(), |v| format!(",{v:#x}")),
                if spec.energy_denominator > 0 {
                    "2^-32 Joules"
                } else if spec.total.is_some() {
                    "GuC ticks"
                } else {
                    "busy ns"
                }
            );
            let start = clock.now();
            let result = (|| {
                if let Some(e) = &error {
                    return Err(io::Error::new(e.kind(), e.to_string()));
                }
                if let Some((kind, reason)) = &spec.metadata_error {
                    return Err(io::Error::new(*kind, reason.clone()));
                }
                if slot.handle.is_none() {
                    slot.handle = Some((self.factory)(spec)?);
                }
                slot.handle
                    .as_mut()
                    .ok_or_else(|| io::Error::other("No perf handle"))?
                    .read()
            })();
            let end = clock.now();
            let failure = result
                .as_ref()
                .err()
                .map(|e| (super::drm::error_availability(e), format!("{source}: {e}")));
            let observation = result.map(|v| {
                raw_window(
                    &source,
                    start,
                    end,
                    [
                        ("active", v.active),
                        ("total", v.total),
                        ("ticks", u64::from(spec.total.is_some())),
                        ("enabled_ns", v.enabled),
                        ("running_ns", v.running),
                        ("capacity", 1),
                        ("energy_denominator", spec.energy_denominator),
                        ("config_active", spec.active),
                        ("config_total", spec.total.unwrap_or(0)),
                        ("pmu_type", u64::from(spec.kind)),
                        ("cpu", spec.cpu as u64),
                    ],
                )
            });
            let mut r = self.counters.derive(
                key,
                observation.map_err(|e| format!("{source}: {e}")),
                utilization,
            );
            if let Some((availability, reason)) = failure {
                slot.handle = None;
                r.availability = availability;
                r.reason = Some(reason);
                r.observations.push(raw_window(&source, start, end, []));
            }
            crate::host::sensor(
                s,
                id,
                &spec.id,
                &format!(
                    "{} {}",
                    spec.id,
                    if spec.energy_denominator > 0 {
                        "power"
                    } else {
                        "activity"
                    }
                ),
                if spec.energy_denominator > 0 {
                    SensorKind::Power
                } else {
                    SensorKind::Percentage
                },
                if spec.energy_denominator > 0 {
                    Unit::Watts
                } else {
                    Unit::Percent
                },
                &source,
                &spec.scope,
                r,
            );
        }
        if let Some(key) = first {
            if let Some(m) = s.monitors.iter_mut().find(|m| m.id == id) {
                m.summary_sensor_id = key;
            }
        } else if count == 0 {
            let availability = error
                .as_ref()
                .map_or(Availability::Unavailable, super::drm::error_availability);
            let reason =
                error.map_or_else(|| "No engine counters exposed".into(), |e| e.to_string());
            let r = missing(&format!("{id}/usage"), availability, reason);
            crate::host::sensor(
                s,
                id,
                "usage",
                "GPU engine activity",
                SensorKind::Percentage,
                Unit::Percent,
                "Linux Intel device PMU",
                "No whole-device activity inferred from clients or clocks",
                r,
            );
        }
        let keys: Vec<_> = self.slots.keys().map(String::as_str).collect();
        self.counters.retain(&keys);
    }
    pub(super) fn sample_power(
        &mut self,
        s: &mut Snapshot,
        id: &str,
        clock: &Clock,
        spec: io::Result<Spec>,
    ) {
        match spec {
            Ok(spec) => self.sample_specs(s, id, clock, Ok(vec![spec])),
            Err(e)
                if self
                    .slots
                    .keys()
                    .any(|key| key.starts_with(&format!("{id}/"))) =>
            {
                self.sample_specs(s, id, clock, Err(e))
            }
            Err(e) => {
                let r = missing(
                    &format!("{id}/rapl-graphics-power"),
                    super::drm::error_availability(&e),
                    e.to_string(),
                );
                crate::host::sensor(
                    s,
                    id,
                    "rapl-graphics-power",
                    "RAPL graphics-domain power",
                    SensorKind::Power,
                    Unit::Watts,
                    "Intel RAPL energy-gpu",
                    "Attribution requires one evidenced integrated GPU and one RAPL die",
                    r,
                );
            }
        }
    }
    pub(super) fn retain(&mut self, ids: &[String]) {
        self.slots
            .retain(|key, _| ids.iter().any(|id| key.starts_with(&format!("{id}/"))));
        let keys: Vec<_> = self.slots.keys().map(String::as_str).collect();
        self.counters.retain(&keys);
    }
    pub(super) fn collect(
        &mut self,
        s: &mut Snapshot,
        device: &Device,
        root: &Path,
        clock: &Clock,
        engines: io::Result<Vec<Engine>>,
        unqualified_i915: bool,
    ) {
        let specs = (|| {
            let directory = root.join("sys/bus/event_source/devices");
            let mut pmu = directory.join(format!(
                "{}_{}",
                device.driver,
                device.pci.replace(':', "_")
            ));
            if device.driver == "i915" && !pmu.exists() && unqualified_i915 {
                pmu = directory.join("i915");
            }
            let cpus = match sysfs::text(&pmu.join("cpumask")) {
                Ok(v) => v,
                Err(e) if e.kind() == io::ErrorKind::NotFound => {
                    sysfs::text(&root.join("sys/devices/system/cpu/online"))?
                }
                Err(e) => return Err(e),
            };
            let cpu = first_cpu(&cpus)?;
            let engines = if device.driver == "xe" {
                engines?
            } else {
                engines.unwrap_or_default()
            };
            specifications(device, &pmu, &engines, cpu)
        })();
        self.sample_specs(s, &format!("intel-pci:{}", device.pci), clock, specs);
    }
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub(super) struct Spec {
    pub id: String,
    pub pmu: PathBuf,
    pub kind: u32,
    pub cpu: i32,
    pub active: u64,
    pub total: Option<u64>,
    pub energy_denominator: u64,
    pub scope: String,
    pub event_path: Option<PathBuf>,
    pub metadata_error: Option<(io::ErrorKind, String)>,
}
fn first_cpu(list: &str) -> io::Result<i32> {
    let mut first = None;
    for range in list.trim().split(',') {
        let mut parts = range.split('-');
        let start = parts
            .next()
            .unwrap_or("")
            .parse::<i32>()
            .map_err(|_| invalid("Invalid PMU CPU list"))?;
        let end = parts
            .next()
            .map(str::parse::<i32>)
            .transpose()
            .map_err(|_| invalid("Invalid PMU CPU range"))?
            .unwrap_or(start);
        if start < 0 || end < start || parts.next().is_some() {
            return Err(invalid("Invalid PMU CPU range"));
        }
        first = Some(first.map_or(start, |old: i32| old.min(start)));
    }
    first.ok_or_else(|| invalid("Empty PMU CPU list"))
}
fn invalid(message: &str) -> io::Error {
    io::Error::new(io::ErrorKind::InvalidData, message)
}
fn event(path: &Path, key: &str) -> io::Result<u64> {
    let text = sysfs::text(path)?;
    let value = text
        .strip_prefix(key)
        .ok_or_else(|| invalid("Unexpected PMU config format"))?;
    let value = value
        .strip_prefix("0x")
        .ok_or_else(|| invalid("PMU config must be hexadecimal"))?;
    u64::from_str_radix(value, 16).map_err(|_| invalid("Invalid PMU config value"))
}
fn specifications(
    device: &Device,
    pmu: &Path,
    engines: &[Engine],
    cpu: i32,
) -> io::Result<Vec<Spec>> {
    let kind = sysfs::text(&pmu.join("type"))?
        .parse()
        .map_err(|_| invalid("Invalid PMU type"))?;
    let mut specs = Vec::new();
    if device.driver == "i915" {
        for path in sysfs::entries(&pmu.join("events"))? {
            let name = path.file_name().unwrap().to_string_lossy().into_owned();
            if !name.ends_with("-busy") {
                continue;
            }
            specs.push(i915_spec(pmu, &path, &name, kind, cpu, &sysfs::text));
        }
    } else {
        for (key, expected) in [
            ("event", "config:0-11"),
            ("engine_class", "config:20-27"),
            ("engine_instance", "config:12-19"),
            ("gt", "config:60-63"),
        ] {
            if sysfs::text(&pmu.join(format!("format/{key}")))? != expected {
                return Err(invalid(
                    "xe PMU layout differs from supported documented format",
                ));
            }
        }
        let active = event(&pmu.join("events/engine-active-ticks"), "event=")?;
        let total = event(&pmu.join("events/engine-total-ticks"), "event=")?;
        if active != 2 || total != 3 {
            return Err(invalid("Unexpected xe active/total event IDs"));
        }
        for name in ["engine-active-ticks", "engine-total-ticks"] {
            match sysfs::text(&pmu.join(format!("events/{name}.unit"))) {
                Ok(unit) if unit != "ticks" => return Err(invalid("Unexpected xe tick unit")),
                Err(e) if e.kind() != io::ErrorKind::NotFound => return Err(e),
                _ => {}
            }
        }
        let sriov = sysfs::text(&device.path.join("sriov_numvfs"))
            .ok()
            .and_then(|v| v.parse::<u64>().ok())
            .is_some_and(|v| v > 0);
        for engine in engines {
            if engine.gt > 15 || engine.instance > 255 || engine.class > 4 {
                return Err(invalid("Engine does not fit xe PMU selectors"));
            }
            let selectors = (u64::from(engine.gt) << 60)
                | (u64::from(engine.class) << 20)
                | (u64::from(engine.instance) << 12);
            specs.push(Spec {
                id: format!(
                    "gt{}-engine-class{}-instance{}",
                    engine.gt, engine.class, engine.instance
                ),
                event_path: None,
                metadata_error: None,
                pmu: pmu.into(),
                kind,
                cpu,
                active: selectors | active,
                total: Some(selectors | total),
                energy_denominator: 0,
                scope: format!(
                    "{}; GT {}, engine class {}, instance {}; active/total GuC ticks, capacity 1",
                    if sriov {
                        "PCI physical function 0 only; excludes VF activity"
                    } else {
                        "Physical GPU engine"
                    },
                    engine.gt,
                    engine.class,
                    engine.instance
                ),
            });
        }
    }
    specs.sort_by(|a, b| a.id.cmp(&b.id));
    if specs.is_empty() {
        return Err(io::Error::new(
            io::ErrorKind::Unsupported,
            "No documented engine counters exposed",
        ));
    }
    if specs.windows(2).any(|s| s[0].id == s[1].id) {
        return Err(invalid("Duplicate engine PMU configuration"));
    }
    Ok(specs)
}
fn i915_spec(
    pmu: &Path,
    path: &Path,
    name: &str,
    kind: u32,
    cpu: i32,
    read: &impl Fn(&Path) -> io::Result<String>,
) -> Spec {
    let config = (|| {
        let unit_path = pmu.join(format!("events/{name}.unit"));
        let unit = read(&unit_path)
            .map_err(|e| io::Error::new(e.kind(), format!("{}: {e}", unit_path.display())))?;
        if unit != "ns" {
            return Err(invalid(&format!(
                "{}: i915 busy counter unit is not ns",
                unit_path.display()
            )));
        }
        let text = read(path)?;
        let value = text
            .strip_prefix("config=0x")
            .ok_or_else(|| invalid("Unexpected PMU config format"))?;
        let config =
            u64::from_str_radix(value, 16).map_err(|_| invalid("Invalid PMU config value"))?;
        if config & 0xf != 0 || config >> 12 > 4 {
            return Err(invalid("Unknown i915 engine busy configuration"));
        }
        Ok(config)
    })();
    let (id, active, scope, metadata_error) = match config {
        Ok(config) => {
            let class = config >> 12;
            let instance = (config >> 4) & 0xff;
            (
                format!("engine-class{class}-instance{instance}"),
                config,
                format!(
                    "Physical GPU engine class {class}, instance {instance}; busy nanoseconds / measured elapsed nanoseconds; capacity 1"
                ),
                None,
            )
        }
        Err(e) => (
            format!("event-{name}"),
            0,
            "PMU event metadata unavailable; no engine identity inferred".into(),
            Some((e.kind(), format!("{}: {e}", path.display()))),
        ),
    };
    Spec {
        id,
        pmu: pmu.into(),
        kind,
        cpu,
        active,
        total: None,
        energy_denominator: 0,
        scope,
        event_path: Some(path.into()),
        metadata_error,
    }
}
fn utilization(a: &RawObservation, b: &RawObservation, elapsed: f64) -> Result<f64, String> {
    if !elapsed.is_finite() || elapsed <= 0.0 {
        return Err("Invalid measured elapsed time".into());
    }
    for key in [
        "ticks",
        "capacity",
        "config_active",
        "config_total",
        "energy_denominator",
    ] {
        if a.integers.get(key) != b.integers.get(key) {
            return Err(format!("Counter metadata changed: {key}"));
        }
    }
    let enabled = delta(a, b, "enabled_ns")?;
    let running = delta(a, b, "running_ns")?;
    if enabled == 0 || running != enabled {
        return Err("PMU was not continuously scheduled; no scaled estimate".into());
    }
    let active = delta(a, b, "active")?;
    if let Some(denominator) = b.integers.get("energy_denominator").filter(|v| **v > 0) {
        if *denominator != 1u64 << 32 {
            return Err("Unknown energy unit".into());
        }
        return Ok(active as f64 / *denominator as f64 / elapsed);
    }
    let total = if b.integers.get("ticks") == Some(&1) {
        delta(a, b, "total")? as f64
    } else {
        elapsed * 1e9
    };
    if total <= 0.0 || active as f64 > total || b.integers.get("capacity") != Some(&1) {
        return Err("Invalid engine activity/capacity; no clamp".into());
    }
    Ok(active as f64 / total * 100.0)
}
#[cfg(test)]
mod tests {
    use super::*;
    fn sample(ns: u64, busy: u64, total: u64, ticks: bool) -> RawObservation {
        raw_window(
            "test perf engine",
            ns.saturating_sub(10),
            ns,
            [
                ("active", busy),
                ("total", total),
                ("ticks", u64::from(ticks)),
                ("enabled_ns", ns),
                ("running_ns", ns),
                ("capacity", 1),
                ("config_active", 1),
                ("config_total", 2),
            ],
        )
    }
    #[test]
    fn engine_activity_normalizes_busy_ns_or_active_over_total_ticks() {
        assert_eq!(
            utilization(
                &sample(1_000_000_000, 100, 0, false),
                &sample(2_500_000_000, 750_000_100, 0, false),
                1.5
            )
            .unwrap(),
            50.0
        );
        assert_eq!(
            utilization(
                &sample(1_000_000_000, 250, 1000, true),
                &sample(2_500_000_000, 1000, 2000, true),
                1.5
            )
            .unwrap(),
            75.0
        );
    }
    #[test]
    fn rapl_fixed_point_joules_use_measured_elapsed_not_percent() {
        let mut a = sample(1_000_000_000, 1u64 << 32, 0, false);
        let mut b = sample(2_500_000_000, 4u64 << 32, 0, false);
        a.integers.insert("energy_denominator".into(), 1u64 << 32);
        b.integers.insert("energy_denominator".into(), 1u64 << 32);
        assert_eq!(utilization(&a, &b, 1.5).unwrap(), 2.0);
    }
    #[test]
    fn first_reset_failed_baseline_irregular_time_and_impossible_activity() {
        let mut c = Counters::default();
        let key = "engine";
        assert_eq!(
            c.derive(key, Ok(sample(1_000_000_000, 100, 1000, true)), utilization)
                .availability,
            Availability::WarmingUp
        );
        let r = c.derive(key, Ok(sample(2_500_000_000, 850, 2000, true)), utilization);
        assert_eq!(r.value, Some(75.0));
        assert_eq!(r.observations.len(), 2);
        assert_eq!(
            c.derive(key, Ok(sample(3_000_000_000, 0, 0, true)), utilization)
                .value,
            None
        );
        assert_eq!(
            c.derive(key, Err("Permission denied".into()), utilization)
                .availability,
            Availability::Failed
        );
        assert_eq!(
            c.derive(key, Ok(sample(4_000_000_000, 100, 200, true)), utilization)
                .availability,
            Availability::WarmingUp
        );
        assert_eq!(
            c.derive(key, Ok(sample(4_000_000_000, 200, 400, true)), utilization)
                .value,
            None
        );
        assert!(utilization(&sample(1, 0, 0, true), &sample(2, 1000, 100, true), 1.0).is_err());
        assert!(
            utilization(
                &sample(1, 0, 0, false),
                &sample(2, 2_000_000_000, 0, false),
                1.0
            )
            .is_err()
        );
        let mut multiplexed = sample(2_000_000_000, 1000, 2000, true);
        multiplexed
            .integers
            .insert("running_ns".into(), 1_500_000_000);
        assert!(utilization(&sample(1_000_000_000, 100, 1000, true), &multiplexed, 1.0).is_err());
    }
    #[test]
    fn pmu_specs_validate_units_formats_and_sparse_xe_engine_selectors() {
        let path = std::env::temp_dir().join(format!("pulse-pmu-specs-{}", std::process::id()));
        std::fs::create_dir_all(path.join("events")).unwrap();
        std::fs::create_dir_all(path.join("format")).unwrap();
        let put = |p: &str, v: &str| std::fs::write(path.join(p), v).unwrap();
        put("type", "17");
        put("events/rcs0-busy", "config=0x0");
        put("events/rcs0-busy.unit", "ns");
        let mut d = Device {
            pci: "0000:00:02.0".into(),
            driver: "i915".into(),
            path: path.clone(),
            cards: vec![],
        };
        let specs = specifications(&d, &path, &[], 0).unwrap();
        assert_eq!(specs.len(), 1);
        assert_eq!(specs[0].active, 0);
        assert_eq!(specs[0].total, None);
        put("events/rcs0-busy.unit", "MHz");
        assert!(
            specifications(&d, &path, &[], 0).unwrap()[0]
                .metadata_error
                .is_some()
        );
        d.driver = "xe".into();
        put("events/engine-active-ticks", "event=0x2");
        put("events/engine-total-ticks", "event=0x3");
        for (key, value) in [
            ("event", "config:0-11"),
            ("engine_class", "config:20-27"),
            ("engine_instance", "config:12-19"),
            ("gt", "config:60-63"),
        ] {
            put(&format!("format/{key}"), value);
        }
        let e = Engine {
            gt: 9,
            class: 4,
            instance: 7,
        };
        let specs = specifications(&d, &path, std::slice::from_ref(&e), 3).unwrap();
        assert_eq!(specs.len(), 1);
        assert_eq!(specs[0].active, (9u64 << 60) | (4 << 20) | (7 << 12) | 2);
        assert_eq!(specs[0].cpu, 3);
        put("format/gt", "config:59-63");
        assert!(specifications(&d, &path, std::slice::from_ref(&e), 0).is_err());
        std::fs::remove_dir_all(path).unwrap();
    }
    #[test]
    fn i915_bad_event_metadata_preserves_peer_sampling_and_recovery() {
        struct Fake(u64);
        impl Counter for Fake {
            fn read(&mut self) -> io::Result<super::super::native::PerfRead> {
                self.0 += 1;
                Ok(super::super::native::PerfRead {
                    active: self.0 * 500_000_000,
                    total: 0,
                    enabled: self.0 * 1_000_000_000,
                    running: self.0 * 1_000_000_000,
                })
            }
        }
        let path = std::env::temp_dir().join(format!("pulse-pmu-peer-{}", std::process::id()));
        std::fs::create_dir_all(path.join("events")).unwrap();
        let put = |p: &str, v: &str| std::fs::write(path.join(p), v).unwrap();
        put("type", "17");
        put("events/rcs0-busy", "config=0x0");
        put("events/rcs0-busy.unit", "ns");
        put("events/bcs0-busy", "config=0x1000");
        put("events/bcs0-busy.unit", "MHz");
        let d = Device {
            pci: "0000:00:02.0".into(),
            driver: "i915".into(),
            path: path.clone(),
            cards: vec![],
        };
        let mut p = Pmu::new();
        p.factory = Box::new(|_| Ok(Box::new(Fake(0))));
        let run = |p: &mut Pmu, ns| {
            let mut s = Snapshot::default();
            p.sample_specs(
                &mut s,
                "intel-pci:test",
                &Clock {
                    origin: std::time::Instant::now(),
                    fixed: Some(ns),
                },
                specifications(&d, &path, &[], 0),
            );
            s
        };
        let first = run(&mut p, 1_000_000_000);
        assert!(
            first
                .readings
                .iter()
                .any(|r| r.sensor_id.ends_with("engine-class0-instance0")
                    && r.availability == Availability::WarmingUp),
            "valid peer suppressed: {:?}",
            first.readings
        );
        assert!(
            first
                .readings
                .iter()
                .any(|r| r.availability == Availability::Failed)
        );
        let s = run(&mut p, 2_000_000_000);
        assert!(s.readings.iter().any(|r| r.value == Some(50.0)));
        put("events/bcs0-busy.unit", "ns");
        let s = run(&mut p, 3_000_000_000);
        assert!(
            s.readings
                .iter()
                .any(|r| r.sensor_id.ends_with("engine-class1-instance0")
                    && r.availability == Availability::WarmingUp)
        );
        put("events/bcs0-busy", "malformed");
        let s = run(&mut p, 4_000_000_000);
        assert!(
            s.readings
                .iter()
                .any(|r| r.sensor_id.ends_with("engine-class0-instance0") && r.value == Some(50.0))
        );
        assert!(
            s.readings
                .iter()
                .any(|r| r.sensor_id.ends_with("engine-class1-instance0")
                    && r.availability == Availability::Failed)
        );
        put("events/bcs0-busy", "config=0x1000");
        let s = run(&mut p, 5_000_000_000);
        assert!(
            s.readings
                .iter()
                .any(|r| r.sensor_id.ends_with("engine-class1-instance0")
                    && r.availability == Availability::WarmingUp)
        );
        for (i, denied) in ["bcs0-busy", "bcs0-busy.unit"].iter().enumerate() {
            let read = |path: &Path| {
                if path.file_name().unwrap() == *denied {
                    Err(io::Error::from(io::ErrorKind::PermissionDenied))
                } else {
                    sysfs::text(path)
                }
            };
            let specs = ["rcs0-busy", "bcs0-busy"]
                .iter()
                .map(|name| {
                    i915_spec(
                        &path,
                        &path.join(format!("events/{name}")),
                        name,
                        17,
                        0,
                        &read,
                    )
                })
                .collect();
            let mut s = Snapshot::default();
            p.sample_specs(
                &mut s,
                "intel-pci:test",
                &Clock {
                    origin: std::time::Instant::now(),
                    fixed: Some((6 + i as u64 * 2) * 1_000_000_000),
                },
                Ok(specs),
            );
            assert!(
                s.readings
                    .iter()
                    .any(|r| r.sensor_id.ends_with("engine-class0-instance0")
                        && r.value == Some(50.0))
            );
            assert!(
                s.readings
                    .iter()
                    .any(|r| r.sensor_id.ends_with("engine-class1-instance0")
                        && r.availability == Availability::Unavailable
                        && r.value.is_none())
            );
            let recovered = run(&mut p, (7 + i as u64 * 2) * 1_000_000_000);
            assert!(
                recovered
                    .readings
                    .iter()
                    .any(|r| r.sensor_id.ends_with("engine-class1-instance0")
                        && r.availability == Availability::WarmingUp)
            );
        }
        std::fs::remove_dir_all(path).unwrap();
    }
    #[test]
    fn initial_malformed_pmu_discovery_is_failed() {
        let mut p = Pmu::new();
        let mut s = Snapshot::default();
        p.sample_specs(
            &mut s,
            "intel-pci:test",
            &Clock {
                origin: std::time::Instant::now(),
                fixed: Some(1),
            },
            Err(invalid("Malformed PMU type")),
        );
        assert_eq!(s.readings[0].availability, Availability::Failed);
    }
    fn spec(id: &str) -> Spec {
        Spec {
            id: id.into(),
            event_path: None,
            metadata_error: None,
            pmu: "/sys/test".into(),
            kind: 17,
            cpu: 0,
            active: 2,
            total: Some(3),
            energy_denominator: 0,
            scope: "GT5 engine capacity 1".into(),
        }
    }
    #[test]
    fn pmu_retry_failed_read_independence_and_disappearance_release_state() {
        use std::sync::{Arc, Mutex};
        struct Fake(
            Arc<
                Mutex<
                    std::collections::VecDeque<
                        Result<super::super::native::PerfRead, io::ErrorKind>,
                    >,
                >,
            >,
        );
        impl Counter for Fake {
            fn read(&mut self) -> io::Result<super::super::native::PerfRead> {
                self.0
                    .lock()
                    .unwrap()
                    .pop_front()
                    .unwrap()
                    .map_err(io::Error::from)
            }
        }
        let queue = Arc::new(Mutex::new(std::collections::VecDeque::from([
            Ok(super::super::native::PerfRead {
                active: 100,
                total: 1000,
                enabled: 100,
                running: 100,
            }),
            Ok(super::super::native::PerfRead {
                active: 850,
                total: 2000,
                enabled: 200,
                running: 200,
            }),
            Err(io::ErrorKind::PermissionDenied),
            Ok(super::super::native::PerfRead {
                active: 10000,
                total: 20000,
                enabled: 1000,
                running: 1000,
            }),
        ])));
        let mut p = Pmu::new();
        let q = queue.clone();
        let mut opens = 0;
        p.factory = Box::new(move |s| {
            if s.id == "bad" {
                return Err(io::Error::from(io::ErrorKind::PermissionDenied));
            }
            opens += 1;
            if opens == 1 {
                Err(io::Error::from(io::ErrorKind::PermissionDenied))
            } else {
                Ok(Box::new(Fake(q.clone())))
            }
        });
        let run = |p: &mut Pmu, ns| {
            let mut s = Snapshot::default();
            p.sample_specs(
                &mut s,
                "intel-pci:test",
                &Clock {
                    origin: std::time::Instant::now(),
                    fixed: Some(ns),
                },
                Ok(vec![spec("good"), spec("bad")]),
            );
            s
        };
        let s = run(&mut p, 1_000_000_000);
        assert_eq!(s.readings.len(), 2);
        assert!(s.readings.iter().all(|r| r.value.is_none()));
        let s = run(&mut p, 2_000_000_000);
        assert_eq!(
            s.readings
                .iter()
                .find(|r| r.sensor_id.ends_with("/good"))
                .unwrap()
                .availability,
            Availability::WarmingUp
        );
        let s = run(&mut p, 3_500_000_000);
        assert_eq!(
            s.readings
                .iter()
                .find(|r| r.sensor_id.ends_with("/good"))
                .unwrap()
                .value,
            Some(75.0)
        );
        let s = run(&mut p, 4_000_000_000);
        assert_eq!(
            s.readings
                .iter()
                .find(|r| r.sensor_id.ends_with("/good"))
                .unwrap()
                .availability,
            Availability::Unavailable
        );
        let s = run(&mut p, 5_000_000_000);
        assert_eq!(
            s.readings
                .iter()
                .find(|r| r.sensor_id.ends_with("/good"))
                .unwrap()
                .availability,
            Availability::WarmingUp
        );
        p.retain(&[]);
        assert!(p.slots.is_empty());
        assert!(p.counters.is_empty());
    }
}
