//! Runtime-loaded NVML. No linked NVIDIA library and no assumed GPU enumeration index identity.
use crate::{
    counters::*,
    host::{diagnostic, monitor, sensor},
    types::*,
};
use nvml_wrapper::{
    Nvml,
    enum_wrappers::device::{Clock, TemperatureSensor},
};
use std::collections::BTreeMap;
type Value = Result<u64, String>;
type Windows = BTreeMap<String, (u64, u64)>;
struct DeviceSample {
    uuid: Result<String, String>,
    name: Result<String, String>,
    values: BTreeMap<String, Value>,
    memory: Result<(u64, u64), String>,
    fans: Vec<(Value, Value)>,
    windows: Windows,
}
trait NvmlBackend: Send {
    fn devices(&mut self, clock: &CaptureClock) -> Result<Vec<DeviceSample>, String>;
}
trait NvmlSession: Send {
    fn count(&mut self) -> Result<u32, String>;
    fn sample(&mut self, index: u32, clock: &CaptureClock) -> Result<DeviceSample, String>;
}
struct CaptureClock {
    base: u64,
    origin: std::time::Instant,
}
impl CaptureClock {
    #[cfg(test)]
    fn new(base: u64) -> Self {
        Self {
            base,
            origin: std::time::Instant::now(),
        }
    }
    fn now(&self) -> u64 {
        self.base
            .saturating_add(self.origin.elapsed().as_nanos().min(u64::MAX as u128) as u64)
    }
}
type Factory = Box<dyn FnMut() -> Result<Box<dyn NvmlSession>, String> + Send>;
struct RuntimeNvml {
    session: Option<Box<dyn NvmlSession>>,
    factory: Factory,
}
pub(crate) struct NvidiaCollector {
    backend: Box<dyn NvmlBackend>,
}
impl RuntimeNvml {
    fn new() -> Self {
        Self {
            session: None,
            factory: Box::new(|| {
                Nvml::init()
                    .map(|nvml| Box::new(nvml) as Box<dyn NvmlSession>)
                    .map_err(|e| format!("NVML init: {e:?}"))
            }),
        }
    }
    #[cfg(test)]
    fn injected(
        factory: impl FnMut() -> Result<Box<dyn NvmlSession>, String> + Send + 'static,
    ) -> Self {
        Self {
            session: None,
            factory: Box::new(factory),
        }
    }
}
impl NvmlBackend for RuntimeNvml {
    fn devices(&mut self, clock: &CaptureClock) -> Result<Vec<DeviceSample>, String> {
        if self.session.is_none() {
            self.session = Some((self.factory)()?);
        }
        let session = self
            .session
            .as_mut()
            .ok_or("NVML initialization yielded no session")?;
        let count = match session.count() {
            Ok(v) => v,
            Err(e) => {
                self.session = None;
                return Err(e);
            }
        };
        let mut lost = false;
        let mut result = Vec::new();
        for index in 0..count {
            match session.sample(index, clock) {
                Ok(sample) => {
                    let lost_error =
                        |e: &String| e.contains("GpuLost") || e.contains("DriverNotLoaded");
                    if sample
                        .values
                        .values()
                        .any(|v| v.as_ref().is_err_and(lost_error))
                        || sample.memory.as_ref().is_err_and(lost_error)
                        || sample.uuid.as_ref().is_err_and(lost_error)
                        || sample.name.as_ref().is_err_and(lost_error)
                        || sample.fans.iter().any(|(p, r)| {
                            p.as_ref().is_err_and(lost_error) || r.as_ref().is_err_and(lost_error)
                        })
                    {
                        lost = true;
                    }
                    result.push(sample);
                }
                Err(e) => {
                    lost |= e.contains("GpuLost") || e.contains("DriverNotLoaded");
                    result.push(DeviceSample {
                        uuid: Err(e.clone()),
                        name: Err(e.clone()),
                        values: BTreeMap::new(),
                        memory: Err(e),
                        fans: Vec::new(),
                        windows: BTreeMap::new(),
                    });
                }
            }
        }
        if lost {
            self.session = None;
        }
        Ok(result)
    }
}
fn query<T>(
    clock: &CaptureClock,
    windows: &mut Windows,
    key: &str,
    source: &str,
    operation: impl FnOnce() -> Result<T, nvml_wrapper::error::NvmlError>,
) -> Result<T, String> {
    let start = clock.now();
    let value = operation().map_err(|e| format!("{source}: {e:?}"));
    windows.insert(key.into(), (start, clock.now()));
    value
}
impl NvmlSession for Nvml {
    fn count(&mut self) -> Result<u32, String> {
        self.device_count()
            .map_err(|e| format!("NVML device_count: {e:?}"))
    }
    fn sample(&mut self, index: u32, clock: &CaptureClock) -> Result<DeviceSample, String> {
        let device = self
            .device_by_index(index)
            .map_err(|e| format!("NVML device_by_index({index}): {e:?}"))?;
        let mut windows = Windows::new();
        let mut values = BTreeMap::new();
        let uuid = device.uuid().map_err(|e| format!("NVML uuid: {e:?}"));
        let name = device.name().map_err(|e| format!("NVML name: {e:?}"));
        values.insert(
            "usage".into(),
            query(
                clock,
                &mut windows,
                "usage",
                "NVML utilization_rates",
                || device.utilization_rates(),
            )
            .map(|v| v.gpu as u64),
        );
        values.insert(
            "temperature".into(),
            query(
                clock,
                &mut windows,
                "temperature",
                "NVML temperature(Gpu)",
                || device.temperature(TemperatureSensor::Gpu),
            )
            .map(u64::from),
        );
        values.insert(
            "power".into(),
            query(clock, &mut windows, "power", "NVML power_usage", || {
                device.power_usage()
            })
            .map(u64::from),
        );
        values.insert(
            "clock-graphics".into(),
            query(
                clock,
                &mut windows,
                "clock-graphics",
                "NVML clock_info(Graphics)",
                || device.clock_info(Clock::Graphics),
            )
            .map(u64::from),
        );
        values.insert(
            "clock-memory".into(),
            query(
                clock,
                &mut windows,
                "clock-memory",
                "NVML clock_info(Memory)",
                || device.clock_info(Clock::Memory),
            )
            .map(u64::from),
        );
        let memory = query(clock, &mut windows, "vram", "NVML memory_info v2", || {
            device.memory_info()
        })
        .map(|v| (v.used, v.total));
        let fan_count = device.num_fans();
        let count = match fan_count {
            Ok(n) => n,
            Err(e) => {
                values.insert("fan-count".into(), Err(format!("NVML num_fans: {e:?}")));
                1
            }
        };
        let mut fans = Vec::new();
        for fan in 0..count {
            let percent = query(
                clock,
                &mut windows,
                &format!("fan-{fan}-percent"),
                &format!("NVML fan_speed({fan})"),
                || device.fan_speed(fan),
            )
            .map(u64::from);
            let rpm = query(
                clock,
                &mut windows,
                &format!("fan-{fan}-rpm"),
                &format!("NVML fan_speed_rpm({fan})"),
                || device.fan_speed_rpm(fan),
            )
            .map(u64::from);
            fans.push((percent, rpm));
        }
        if count == 0 {
            fans.push((
                Err("NVML num_fans: device exposes no fans".into()),
                Err("NVML num_fans: device exposes no fans".into()),
            ));
        }
        Ok(DeviceSample {
            uuid,
            name,
            values,
            memory,
            fans,
            windows,
        })
    }
}
fn timed(mut reading: Reading, windows: &Windows, key: &str) -> Reading {
    if let Some((start, end)) = windows.get(key) {
        for o in &mut reading.observations {
            o.read_started_ns = Some(*start);
            o.captured_ns = *end;
        }
    }
    reading
}
fn error_status(e: &str) -> Availability {
    if e.contains("NotSupported") || e.contains("FailedToLoadSymbol") || e.contains("no fans") {
        Availability::Unavailable
    } else {
        Availability::Failed
    }
}
impl NvidiaCollector {
    pub(crate) fn new() -> Self {
        Self {
            backend: Box::new(RuntimeNvml::new()),
        }
    }
    pub(crate) fn collect_at_origin(&mut self, s: &mut Snapshot, origin: std::time::Instant) {
        let clock = CaptureClock { base: 0, origin };
        let ns = clock.now();
        self.collect_clock(s, ns, &clock);
    }
    #[cfg(test)]
    fn collect(&mut self, s: &mut Snapshot, ns: u64) {
        self.collect_clock(s, ns, &CaptureClock::new(ns));
    }
    fn collect_clock(&mut self, s: &mut Snapshot, ns: u64, clock: &CaptureClock) {
        let devices = match self.backend.devices(clock) {
            Ok(v) => v,
            Err(e) => {
                diagnostic(s, "nvml", e);
                return;
            }
        };
        s.diagnostics.push(BackendDiagnostic {
            backend: "nvml".into(),
            availability: Availability::Available,
            reason: format!("NVML discovered {} devices", devices.len()),
        });
        for device in devices {
            let uuid = match device.uuid {
                Ok(v) if !v.is_empty() => v,
                Ok(_) => {
                    diagnostic(s, "nvml", "NVML uuid returned an empty identifier".into());
                    continue;
                }
                Err(e) => {
                    diagnostic(s, "nvml", e);
                    continue;
                }
            };
            let id = format!("nvidia:{uuid}");
            let name = match device.name {
                Ok(v) => v,
                Err(e) => {
                    diagnostic(s, "nvml", e);
                    "NVIDIA GPU".into()
                }
            };
            monitor(
                s,
                &id,
                &format!("{name} · {}", &uuid[uuid.len().saturating_sub(8)..]),
                MonitorKind::Gpu,
            );
            for (suffix, title, kind, unit, source, factor) in [
                (
                    "usage",
                    "GPU utilization",
                    SensorKind::Percentage,
                    Unit::Percent,
                    "NVML utilization_rates().gpu (%)",
                    1.0,
                ),
                (
                    "temperature",
                    "GPU temperature",
                    SensorKind::Temperature,
                    Unit::Celsius,
                    "NVML temperature(Gpu) (C)",
                    1.0,
                ),
                (
                    "power",
                    "GPU power",
                    SensorKind::Power,
                    Unit::Watts,
                    "NVML power_usage() (mW)",
                    0.001,
                ),
                (
                    "clock-graphics",
                    "Graphics clock",
                    SensorKind::Frequency,
                    Unit::Hertz,
                    "NVML clock_info(Graphics) (MHz)",
                    1e6,
                ),
                (
                    "clock-memory",
                    "Memory clock",
                    SensorKind::Frequency,
                    Unit::Hertz,
                    "NVML clock_info(Memory) (MHz)",
                    1e6,
                ),
            ] {
                let value = device
                    .values
                    .get(suffix)
                    .cloned()
                    .unwrap_or_else(|| Err(format!("{source}: no result")));
                let r = timed(
                    nvml_reading(&format!("{id}/{suffix}"), source, value, factor, ns),
                    &device.windows,
                    suffix,
                );
                sensor(
                    s,
                    &id,
                    suffix,
                    title,
                    kind,
                    unit,
                    source,
                    "Physical NVIDIA device identified by GPU UUID",
                    r,
                );
            }
            let sid = format!("{id}/vram");
            let source = "NVML memory_info v2 (bytes)";
            let r = match device.memory {
                Ok((used, total)) if used <= total => {
                    let mut r = measured(&sid, used as f64, Some(total as f64));
                    r.observations
                        .push(raw(source, ns, [("used", used), ("total", total)]));
                    r
                }
                Ok(_) => missing(
                    &sid,
                    Availability::Failed,
                    format!("{source}: used exceeds total"),
                ),
                Err(e) => missing(&sid, error_status(&e), e),
            };
            let r = timed(r, &device.windows, "vram");
            sensor(
                s,
                &id,
                "vram",
                "VRAM used",
                SensorKind::Capacity,
                Unit::Bytes,
                source,
                "Physical device VRAM",
                r,
            );
            if let Some(Err(e)) = device.values.get("fan-count") {
                diagnostic(s, "nvml", e.clone());
            }
            for (index, (percent, rpm)) in device.fans.into_iter().enumerate() {
                for (suffix, title, unit, value, source) in [
                    (
                        format!("fan-{index}-percent"),
                        format!("Fan {index} intended speed"),
                        Unit::Percent,
                        percent,
                        format!("NVML fan_speed({index}) (%)"),
                    ),
                    (
                        format!("fan-{index}-rpm"),
                        format!("Fan {index} intended RPM"),
                        Unit::Rpm,
                        rpm,
                        format!("NVML fan_speed_rpm({index}) (RPM)"),
                    ),
                ] {
                    let r = timed(
                        nvml_reading(&format!("{id}/{suffix}"), &source, value, 1.0, ns),
                        &device.windows,
                        &suffix,
                    );
                    sensor(
                        s,
                        &id,
                        &suffix,
                        &title,
                        SensorKind::Fan,
                        unit,
                        &source,
                        "Intended device fan speed; NVML does not prove actual rotation; percent may exceed 100 and is never converted to RPM",
                        r,
                    );
                }
            }
        }
    }
}
fn nvml_reading(id: &str, source: &str, value: Value, factor: f64, ns: u64) -> Reading {
    match value {
        Ok(v) => {
            let mut r = measured(id, v as f64 * factor, None);
            r.observations.push(raw(source, ns, [("value", v)]));
            r
        }
        Err(e) => {
            let status = error_status(&e);
            missing(id, status, e)
        }
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    struct Fake {
        frames: std::collections::VecDeque<Result<Vec<DeviceSample>, String>>,
    }
    impl NvmlBackend for Fake {
        fn devices(&mut self, _clock: &CaptureClock) -> Result<Vec<DeviceSample>, String> {
            self.frames.pop_front().unwrap()
        }
    }
    fn device(uuid: &str) -> DeviceSample {
        DeviceSample {
            uuid: Ok(uuid.into()),
            name: Ok("GPU".into()),
            values: [
                ("usage", Ok(0)),
                ("temperature", Ok(40)),
                ("power", Ok(123456)),
                ("clock-graphics", Ok(1234)),
                ("clock-memory", Ok(5678)),
            ]
            .into_iter()
            .map(|(k, v)| (k.into(), v))
            .collect(),
            memory: Ok((1000, 4000)),
            fans: vec![(Ok(110), Ok(1500))],
            windows: Windows::new(),
        }
    }
    fn collector(frames: Vec<Result<Vec<DeviceSample>, String>>) -> NvidiaCollector {
        NvidiaCollector {
            backend: Box::new(Fake {
                frames: frames.into(),
            }),
        }
    }
    fn r<'a>(s: &'a Snapshot, id: &str) -> &'a Reading {
        s.readings.iter().find(|r| r.sensor_id == id).unwrap()
    }
    #[test]
    fn conversions_preserve_units_and_valid_zero() {
        let mut c = collector(vec![Ok(vec![device("GPU-one"), device("GPU-two")])]);
        let mut s = Snapshot::default();
        c.collect(&mut s, 5);
        assert_eq!(s.monitors.len(), 2);
        for (suffix, value) in [
            ("usage", 0.0),
            ("vram", 1000.0),
            ("temperature", 40.0),
            ("power", 123.456),
            ("clock-graphics", 1_234_000_000.0),
            ("clock-memory", 5_678_000_000.0),
            ("fan-0-percent", 110.0),
            ("fan-0-rpm", 1500.0),
        ] {
            let r = r(&s, &format!("nvidia:GPU-one/{suffix}"));
            assert_eq!(r.value, Some(value));
            assert_eq!(r.observations[0].captured_ns, 5);
        }
        assert_eq!(
            s.sensors
                .iter()
                .find(|s| s.id == "nvidia:GPU-one/fan-0-rpm")
                .unwrap()
                .unit,
            Unit::Rpm
        );
        assert_eq!(
            s.sensors
                .iter()
                .find(|s| s.id == "nvidia:GPU-one/fan-0-percent")
                .unwrap()
                .unit,
            Unit::Percent
        );
    }
    #[test]
    fn reorder_removal_zero_devices_and_recovery() {
        let mut c = collector(vec![
            Ok(vec![device("GPU-a"), device("GPU-b")]),
            Ok(vec![device("GPU-b"), device("GPU-a")]),
            Ok(vec![]),
            Err("NVML: DriverNotLoaded".into()),
            Ok(vec![device("GPU-a")]),
        ]);
        for ids in [
            vec!["nvidia:GPU-a", "nvidia:GPU-b"],
            vec!["nvidia:GPU-b", "nvidia:GPU-a"],
            vec![],
            vec![],
            vec!["nvidia:GPU-a"],
        ] {
            let mut s = Snapshot::default();
            c.collect(&mut s, 0);
            assert_eq!(
                s.monitors.iter().map(|m| m.id.as_str()).collect::<Vec<_>>(),
                ids
            );
            assert!(!s.diagnostics.is_empty());
        }
    }
    #[test]
    fn uuid_failure_has_no_fabricated_index_identity() {
        let mut bad = device("ignored");
        bad.uuid = Err("NVML uuid: NoPermission".into());
        let mut c = collector(vec![Ok(vec![bad, device("GPU-real")])]);
        let mut s = Snapshot::default();
        c.collect(&mut s, 0);
        assert_eq!(s.monitors.len(), 1);
        assert_eq!(s.monitors[0].id, "nvidia:GPU-real");
        assert!(
            s.diagnostics
                .iter()
                .any(|d| d.reason.contains("NoPermission"))
        );
    }
    #[test]
    fn per_field_loss_and_recovery_leave_other_fields_real() {
        let mut bad = device("GPU-a");
        bad.values
            .insert("power".into(), Err("NVML power: GpuLost".into()));
        bad.memory = Err("NVML memory_info v2: FailedToLoadSymbol".into());
        bad.fans[0].1 = Err("NVML RPM: NotSupported".into());
        let mut c = collector(vec![Ok(vec![bad]), Ok(vec![device("GPU-a")])]);
        let mut s = Snapshot::default();
        c.collect(&mut s, 1);
        assert_eq!(r(&s, "nvidia:GPU-a/power").value, None);
        assert!(
            r(&s, "nvidia:GPU-a/power")
                .reason
                .as_ref()
                .unwrap()
                .contains("GpuLost")
        );
        assert_eq!(r(&s, "nvidia:GPU-a/temperature").value, Some(40.0));
        assert_eq!(r(&s, "nvidia:GPU-a/vram").value, None);
        let mut s = Snapshot::default();
        c.collect(&mut s, 2);
        assert_eq!(r(&s, "nvidia:GPU-a/power").value, Some(123.456));
    }
    #[test]
    fn initialization_failure_is_diagnostic_not_fake_gpu() {
        let mut c = collector(vec![Err("NVML init: LibraryNotFound".into())]);
        let mut s = Snapshot::default();
        c.collect(&mut s, 0);
        assert!(s.monitors.is_empty());
        assert!(
            s.diagnostics
                .iter()
                .any(|d| d.reason.contains("LibraryNotFound"))
        );
    }

    #[test]
    fn memory_permission_failure_is_failed() {
        let mut d = device("GPU-a");
        d.memory = Err("NVML memory: NoPermission".into());
        let mut c = collector(vec![Ok(vec![d])]);
        let mut s = Snapshot::default();
        c.collect(&mut s, 0);
        assert_eq!(
            r(&s, "nvidia:GPU-a/vram").availability,
            Availability::Failed
        );
    }
    struct Session {
        count: Result<u32, String>,
        bad_index: Option<u32>,
    }
    impl NvmlSession for Session {
        fn count(&mut self) -> Result<u32, String> {
            self.count.clone()
        }
        fn sample(&mut self, index: u32, _clock: &CaptureClock) -> Result<DeviceSample, String> {
            if self.bad_index == Some(index) {
                Err("device_by_index: GpuLost".into())
            } else {
                Ok(device(&format!("GPU-{index}")))
            }
        }
    }
    #[test]
    fn runtime_reuses_session_and_reinitializes_after_count_failure() {
        use std::sync::{
            Arc,
            atomic::{AtomicUsize, Ordering},
        };
        let calls = Arc::new(AtomicUsize::new(0));
        let counter = calls.clone();
        let mut runtime = RuntimeNvml::injected(move || {
            let n = counter.fetch_add(1, Ordering::SeqCst);
            if n == 0 {
                Err("init: DriverNotLoaded".into())
            } else {
                Ok(Box::new(Session {
                    count: if n == 1 {
                        Err("count: GpuLost".into())
                    } else {
                        Ok(2)
                    },
                    bad_index: Some(0),
                }))
            }
        });
        assert!(runtime.devices(&CaptureClock::new(0)).is_err());
        assert!(runtime.devices(&CaptureClock::new(0)).is_err());
        let devices = runtime.devices(&CaptureClock::new(0)).unwrap();
        assert_eq!(devices.len(), 2);
        assert!(devices[0].uuid.is_err());
        assert_eq!(devices[1].uuid.as_deref(), Ok("GPU-1"));
        runtime.devices(&CaptureClock::new(0)).unwrap();
        assert_eq!(calls.load(Ordering::SeqCst), 4);
    }

    #[test]
    fn runtime_reinitializes_after_memory_gpu_loss() {
        use std::sync::{
            Arc,
            atomic::{AtomicUsize, Ordering},
        };
        struct MemoryLost;
        impl NvmlSession for MemoryLost {
            fn count(&mut self) -> Result<u32, String> {
                Ok(1)
            }
            fn sample(
                &mut self,
                _index: u32,
                _clock: &CaptureClock,
            ) -> Result<DeviceSample, String> {
                let mut d = device("GPU-one");
                d.memory = Err("memory: GpuLost".into());
                Ok(d)
            }
        }
        let calls = Arc::new(AtomicUsize::new(0));
        let c = calls.clone();
        let mut runtime = RuntimeNvml::injected(move || {
            c.fetch_add(1, Ordering::SeqCst);
            Ok(Box::new(MemoryLost))
        });
        runtime.devices(&CaptureClock::new(0)).unwrap();
        runtime.devices(&CaptureClock::new(0)).unwrap();
        assert_eq!(calls.load(Ordering::SeqCst), 2);
    }
    #[test]
    fn successful_runtime_session_is_reused() {
        use std::sync::{
            Arc,
            atomic::{AtomicUsize, Ordering},
        };
        let calls = Arc::new(AtomicUsize::new(0));
        let c = calls.clone();
        let mut runtime = RuntimeNvml::injected(move || {
            c.fetch_add(1, Ordering::SeqCst);
            Ok(Box::new(Session {
                count: Ok(2),
                bad_index: None,
            }))
        });
        runtime.devices(&CaptureClock::new(0)).unwrap();
        runtime.devices(&CaptureClock::new(0)).unwrap();
        assert_eq!(calls.load(Ordering::SeqCst), 1);
    }
    #[test]
    fn query_window_is_after_initialization_delay_and_bounds_query() {
        let clock = CaptureClock::new(42);
        std::thread::sleep(std::time::Duration::from_millis(2));
        let mut windows = Windows::new();
        let value = query(&clock, &mut windows, "power", "NVML power", || {
            std::thread::sleep(std::time::Duration::from_millis(2));
            Ok(123u64)
        })
        .unwrap();
        let r = timed(
            nvml_reading("id", "NVML power", Ok(value), 0.001, 42),
            &windows,
            "power",
        );
        let o = &r.observations[0];
        assert!(o.read_started_ns.unwrap() >= 2_000_042);
        assert!(o.captured_ns >= o.read_started_ns.unwrap() + 2_000_000);
    }
}
