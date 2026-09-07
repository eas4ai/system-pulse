//! Blocking host collection; no UI dependency and no synthetic runtime values.
use crate::{counters::*, types::*};
#[cfg(target_os = "linux")]
use std::collections::BTreeMap;
use std::{
    path::{Path, PathBuf},
    time::Instant,
};
#[cfg(target_os = "linux")]
mod devices;
#[cfg(target_os = "linux")]
mod names;
#[cfg(target_os = "linux")]
mod network_attribution;
#[cfg(target_os = "linux")]
mod network_route;
mod portable;
#[cfg(target_os = "linux")]
mod proc;
#[cfg(target_os = "linux")]
mod process;
#[cfg(any(test, all(target_os = "macos", target_arch = "aarch64")))]
mod temperature;

pub struct HostCollector {
    origin: Instant,
    sequence: u64,
    pub(crate) counters: Counters,
    pub(crate) root: PathBuf,
    fixed_ns: Option<u64>,
    #[cfg(target_os = "linux")]
    pub(crate) ticks_per_second: u64,
    #[cfg(target_os = "linux")]
    pub(crate) page_size: u64,
    pub(crate) system: sysinfo::System,
    pub(crate) networks: sysinfo::Networks,
    #[cfg(all(target_os = "macos", target_arch = "aarch64"))]
    temperatures: temperature::TemperatureInventory,
    nvidia: crate::nvidia::NvidiaCollector,
    #[cfg(all(target_os = "macos", target_arch = "aarch64"))]
    apple: crate::apple::AppleCollector,
    #[cfg(target_os = "linux")]
    intel: crate::intel::IntelCollector,
}
impl Default for HostCollector {
    fn default() -> Self {
        Self::new()
    }
}
impl HostCollector {
    pub fn new() -> Self {
        Self {
            origin: Instant::now(),
            sequence: 0,
            counters: Counters::default(),
            root: PathBuf::from("/"),
            fixed_ns: None,
            #[cfg(target_os = "linux")]
            ticks_per_second: rustix::param::clock_ticks_per_second(),
            #[cfg(target_os = "linux")]
            page_size: rustix::param::page_size() as u64,
            system: sysinfo::System::new(),
            networks: sysinfo::Networks::new(),
            #[cfg(all(target_os = "macos", target_arch = "aarch64"))]
            temperatures: temperature::TemperatureInventory::default(),
            nvidia: crate::nvidia::NvidiaCollector::new(),
            #[cfg(all(target_os = "macos", target_arch = "aarch64"))]
            apple: crate::apple::AppleCollector::default(),
            #[cfg(target_os = "linux")]
            intel: crate::intel::IntelCollector::new(),
        }
    }
    /// Captures a complete owned snapshot. Nanoseconds are relative to this collector's creation.
    pub fn collect(&mut self) -> Snapshot {
        self.sequence = self.sequence.saturating_add(1);
        let mut s = Snapshot {
            sequence: self.sequence,
            capture_started_ns: self.now(),
            ..Snapshot::default()
        };
        let before = self.now();
        if let Ok(unix) = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH) {
            let after = self.now();
            if let Ok(unix_ns) = u64::try_from(unix.as_nanos()) {
                s.clock_anchor = Some(ClockAnchor {
                    unix_ns,
                    monotonic_before_ns: before,
                    monotonic_after_ns: after,
                });
            }
        }
        self.counters.begin();
        #[cfg(target_os = "linux")]
        {
            self.collect_cpu_memory(&mut s);
            self.collect_processes(&mut s);
            self.collect_devices(&mut s);
            self.intel
                .collect(&mut s, &self.root, self.origin, self.fixed_ns);
        }
        #[cfg(not(target_os = "linux"))]
        self.collect_portable(&mut s);
        if self.root == Path::new("/") {
            self.nvidia.collect_at_origin(&mut s, self.origin);
        }
        #[cfg(all(target_os = "macos", target_arch = "aarch64"))]
        self.apple.collect(&mut s, self.origin);
        self.counters.finish();
        s.capture_finished_ns = self.now();
        s
    }
    pub(crate) fn now(&self) -> u64 {
        self.fixed_ns
            .unwrap_or_else(|| self.origin.elapsed().as_nanos().min(u64::MAX as u128) as u64)
    }
    #[cfg(target_os = "linux")]
    pub(crate) fn path(&self, path: &str) -> PathBuf {
        self.root.join(path.trim_start_matches('/'))
    }
    #[cfg(target_os = "linux")]
    pub(crate) fn read(&self, path: &str) -> Result<String, String> {
        std::fs::read_to_string(self.path(path)).map_err(|e| format!("{path}: {e}"))
    }
    #[cfg(target_os = "linux")]
    pub(crate) fn entries(&self, path: &str) -> Result<Vec<String>, String> {
        let mut names = std::fs::read_dir(self.path(path))
            .map_err(|e| format!("{path}: {e}"))?
            .map(|e| {
                e.map(|e| e.file_name().to_string_lossy().into_owned())
                    .map_err(|e| format!("{path}: {e}"))
            })
            .collect::<Result<Vec<_>, _>>()?;
        names.sort();
        Ok(names)
    }
    #[cfg(target_os = "linux")]
    pub(crate) fn number(&self, path: &str) -> Result<u64, String> {
        self.read(path)?
            .trim()
            .parse()
            .map_err(|e| format!("{path}: invalid unsigned integer: {e}"))
    }
    #[cfg(target_os = "linux")]
    pub(crate) fn scalar(&self, id: &str, path: &str, factor: f64) -> Reading {
        let started = self.now();
        let result = self.read(path).and_then(|s| {
            s.trim()
                .parse::<f64>()
                .map_err(|e| format!("{path}: invalid number: {e}"))
        });
        match result {
            Ok(v) if v.is_finite() && (v * factor).is_finite() => {
                let mut r = measured(id, v * factor, None);
                let mut o = raw_window(path, started, self.now(), []);
                o.decimals.insert("value".into(), v);
                r.observations.push(o);
                r
            }
            Ok(_) => missing(
                id,
                Availability::Failed,
                format!("{path}: non-finite value"),
            ),
            Err(e) => missing(
                id,
                if self.path(path).exists() {
                    Availability::Failed
                } else {
                    Availability::Unavailable
                },
                e,
            ),
        }
    }
    #[cfg(all(test, target_os = "linux"))]
    fn rooted(root: PathBuf) -> Self {
        let mut s = Self::new();
        s.root = root;
        s.ticks_per_second = 100;
        s.page_size = 4096;
        s
    }
    #[cfg(all(test, target_os = "linux"))]
    fn collect_at(&mut self, ns: u64) -> Snapshot {
        self.fixed_ns = Some(ns);
        self.collect()
    }
}
/// Interface names distinguish VLANs and ports even when MACs and hardware parents match.
/// Names are always present in the key; sibling arrival/removal never changes an existing key.
fn network_identity(name: &str, mac: Option<&str>, hardware_path: Option<&str>) -> String {
    if let Some(path) = hardware_path {
        format!("network:path:{path}:name:{name}")
    } else if let Some(mac) = mac.filter(|m| !m.is_empty() && *m != "00:00:00:00:00:00") {
        format!("network:mac:{mac}:name:{name}")
    } else {
        format!("network:name:{name}")
    }
}
pub(crate) fn monitor(s: &mut Snapshot, id: &str, title: &str, kind: MonitorKind) {
    let suffix = match kind {
        MonitorKind::Cpu | MonitorKind::Gpu => "usage",
        MonitorKind::Memory => "used",
        MonitorKind::Volume => "capacity",
        MonitorKind::Network => "rx",
    };
    s.monitors.push(MonitorDescriptor {
        id: id.into(),
        title: title.into(),
        kind,
        summary_sensor_id: format!("{id}/{suffix}"),
    });
}
#[allow(clippy::too_many_arguments)]
pub(crate) fn sensor(
    s: &mut Snapshot,
    monitor_id: &str,
    suffix: &str,
    title: &str,
    kind: SensorKind,
    unit: Unit,
    source: &str,
    scope: &str,
    reading: Reading,
) {
    s.sensors.push(SensorDescriptor {
        id: format!("{monitor_id}/{suffix}"),
        monitor_id: monitor_id.into(),
        title: title.into(),
        kind,
        unit,
        source: source.into(),
        scope: scope.into(),
        scale: reading.total,
    });
    s.readings.push(reading);
}
pub(crate) fn diagnostic(s: &mut Snapshot, backend: &str, e: String) {
    s.diagnostics.push(BackendDiagnostic {
        backend: backend.into(),
        availability: Availability::Failed,
        reason: e,
    });
}
#[cfg(target_os = "linux")]
pub(crate) fn fields(text: &str) -> BTreeMap<String, u64> {
    text.lines()
        .filter_map(|line| {
            let mut words = line.split_whitespace();
            Some((
                words.next()?.trim_end_matches(':').into(),
                words.next()?.parse().ok()?,
            ))
        })
        .collect()
}
#[cfg(target_os = "linux")]
pub(crate) fn field(m: &BTreeMap<String, u64>, key: &str, source: &str) -> Result<u64, String> {
    m.get(key)
        .copied()
        .ok_or_else(|| format!("{source}: missing {key}"))
}
#[cfg(all(test, target_os = "linux"))]
mod tests;
