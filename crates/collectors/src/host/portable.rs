//! Common sysinfo path. Linux uses direct sources to retain permission and counter detail.
use super::*;
use sysinfo::{
    CpuRefreshKind, MemoryRefreshKind, ProcessRefreshKind, ProcessesToUpdate, UpdateKind,
};

#[derive(Clone, Copy, Debug)]
struct QueryWindow {
    started_ns: u64,
    captured_ns: u64,
}
fn query<T>(clock: impl Fn() -> u64, operation: impl FnOnce() -> T) -> (T, QueryWindow) {
    let started_ns = clock();
    let value = operation();
    (
        value,
        QueryWindow {
            started_ns,
            captured_ns: clock(),
        },
    )
}
fn api_raw<const N: usize>(
    source: &str,
    window: QueryWindow,
    values: [(&str, u64); N],
) -> RawObservation {
    raw_window(source, window.started_ns, window.captured_ns, values)
}
#[cfg_attr(target_os = "linux", allow(dead_code))]
impl HostCollector {
    pub(super) fn collect_portable(&mut self, s: &mut Snapshot) {
        let origin = self.origin;
        let fixed_ns = self.fixed_ns;
        let clock =
            || fixed_ns.unwrap_or_else(|| origin.elapsed().as_nanos().min(u64::MAX as u128) as u64);
        let (_, cpu_window) = query(clock, || {
            self.system
                .refresh_cpu_specifics(CpuRefreshKind::everything())
        });
        let (_, memory_window) = query(clock, || {
            self.system
                .refresh_memory_specifics(MemoryRefreshKind::everything())
        });
        // Deliberately exclude command lines, environments, working directories, and executable paths.
        let (_, process_window) = query(clock, || {
            self.system.refresh_processes_specifics(
                ProcessesToUpdate::All,
                true,
                ProcessRefreshKind::nothing()
                    .with_cpu()
                    .with_memory()
                    .with_disk_usage()
                    .with_user(UpdateKind::Always)
                    .with_tasks(),
            )
        });
        // sysinfo's process refresh may also refresh the global CPU cache. Bound both
        // calls before reading that shared cache, including a slow process refresh.
        let cpu_window = QueryWindow {
            started_ns: cpu_window.started_ns,
            captured_ns: process_window.captured_ns,
        };
        let (_, network_window) = query(clock, || self.networks.refresh(true));
        monitor(s, "cpu:host", "CPU", MonitorKind::Cpu);
        monitor(s, "memory:host", "Memory", MonitorKind::Memory);
        let mut usage = api_scalar(
            "cpu:host/usage",
            "sysinfo::System::global_cpu_usage",
            self.system.global_cpu_usage() as f64,
            cpu_window,
        );
        if self.sequence <= 1 {
            usage.value = None;
            usage.availability = Availability::WarmingUp;
            usage.reason = Some("sysinfo CPU counters need a second refresh".into());
        }
        sensor(
            s,
            "cpu:host",
            "usage",
            "Overall utilization",
            SensorKind::Percentage,
            Unit::Percent,
            "sysinfo::System::global_cpu_usage",
            "Host CPU usage normalized to all CPUs",
            usage,
        );
        for (index, cpu) in self.system.cpus().iter().enumerate() {
            for (suffix, title, kind, unit, v, source) in [
                (
                    format!("core-{index}-usage"),
                    format!("CPU {index} utilization"),
                    SensorKind::Percentage,
                    Unit::Percent,
                    cpu.cpu_usage() as f64,
                    "sysinfo::Cpu::cpu_usage",
                ),
                (
                    format!("core-{index}-frequency"),
                    format!("CPU {index} frequency"),
                    SensorKind::Frequency,
                    Unit::Hertz,
                    cpu.frequency() as f64 * 1e6,
                    "sysinfo::Cpu::frequency (MHz)",
                ),
            ] {
                let id = format!("cpu:host/{suffix}");
                let mut r = api_scalar(&id, source, v, cpu_window);
                if suffix.ends_with("frequency") {
                    r.observations[0]
                        .integers
                        .insert("MHz".into(), cpu.frequency());
                } else if self.sequence <= 1 {
                    r.value = None;
                    r.availability = Availability::WarmingUp;
                    r.reason = Some("sysinfo CPU counters need a second refresh".into());
                }
                sensor(
                    s,
                    "cpu:host",
                    &suffix,
                    &title,
                    kind,
                    unit,
                    source,
                    "Logical CPU reported by sysinfo",
                    r,
                );
            }
        }
        #[cfg(not(all(target_os = "macos", target_arch = "aarch64")))]
        let (components, component_window) =
            query(clock, sysinfo::Components::new_with_refreshed_list);
        #[cfg(all(target_os = "macos", target_arch = "aarch64"))]
        let (components, component_window) = query(clock, || self.temperatures.refresh());
        for component in components.iter() {
            let suffix = format!("temperature:{}", component.label());
            let id = format!("cpu:host/{suffix}");
            let source = "sysinfo::Component::temperature";
            let r = component
                .temperature()
                .map(|v| api_scalar(&id, source, v as f64, component_window))
                .unwrap_or_else(|| {
                    missing(
                        &id,
                        Availability::Unavailable,
                        format!("{source}: no reading"),
                    )
                });
            sensor(
                s,
                "cpu:host",
                &suffix,
                component.label(),
                SensorKind::Temperature,
                Unit::Celsius,
                source,
                "Named hardware component; backend label retained",
                r,
            );
        }
        if components.is_empty() {
            unsupported(
                s,
                "cpu:host",
                "temperature",
                "CPU temperature",
                SensorKind::Temperature,
                Unit::Celsius,
                "sysinfo::Components",
                "No hardware component temperature exposed",
            );
        }
        let (load, load_window) = query(clock, sysinfo::System::load_average);
        for (suffix, v) in [
            ("load-1", load.one),
            ("load-5", load.five),
            ("load-15", load.fifteen),
        ] {
            if cfg!(target_os = "windows") {
                unsupported(
                    s,
                    "cpu:host",
                    suffix,
                    "Load average",
                    SensorKind::Scalar,
                    Unit::Load,
                    "sysinfo::System::load_average",
                    "Load average is not supported by the Windows sysinfo backend",
                );
            } else {
                let r = api_scalar(
                    &format!("cpu:host/{suffix}"),
                    "sysinfo::System::load_average",
                    v,
                    load_window,
                );
                sensor(
                    s,
                    "cpu:host",
                    suffix,
                    "Load average",
                    SensorKind::Scalar,
                    Unit::Load,
                    "sysinfo::System::load_average",
                    "Host scheduler load average",
                    r,
                );
            }
        }
        let (uptime, uptime_window) = query(clock, sysinfo::System::uptime);
        let r = api_integer(
            "cpu:host/uptime",
            "sysinfo::System::uptime",
            uptime,
            uptime_window,
        );
        sensor(
            s,
            "cpu:host",
            "uptime",
            "Uptime",
            SensorKind::Duration,
            Unit::Seconds,
            "sysinfo::System::uptime",
            "Host uptime",
            r,
        );
        for (suffix, title, value, total) in [
            (
                "used",
                "RAM used",
                self.system
                    .total_memory()
                    .checked_sub(self.system.available_memory()),
                Some(self.system.total_memory()),
            ),
            ("total", "RAM total", Some(self.system.total_memory()), None),
            (
                "available",
                "RAM available",
                Some(self.system.available_memory()),
                None,
            ),
            ("free", "RAM free", Some(self.system.free_memory()), None),
            (
                "swap",
                "Swap used",
                Some(self.system.used_swap()),
                Some(self.system.total_swap()),
            ),
            (
                "swap-total",
                "Swap total",
                Some(self.system.total_swap()),
                None,
            ),
        ] {
            let id = format!("memory:host/{suffix}");
            let source = "sysinfo::System memory bytes";
            let mut r = value
                .map(|v| api_integer(&id, source, v, memory_window))
                .unwrap_or_else(|| {
                    missing(
                        &id,
                        Availability::Failed,
                        "Available memory exceeds total".into(),
                    )
                });
            r.total = total.map(|v| v as f64);
            if suffix == "used" {
                r.observations = vec![api_raw(
                    source,
                    memory_window,
                    [
                        ("total", self.system.total_memory()),
                        ("available", self.system.available_memory()),
                    ],
                )];
            }
            sensor(
                s,
                "memory:host",
                suffix,
                title,
                SensorKind::Capacity,
                Unit::Bytes,
                source,
                "RAM used = total - available; backend memory definitions",
                r,
            );
        }
        for suffix in [
            "cache",
            "buffers",
            "other",
            "page-faults",
            "major-page-faults",
        ] {
            unsupported(
                s,
                "memory:host",
                suffix,
                suffix,
                if suffix.contains("faults") {
                    SensorKind::Counter
                } else {
                    SensorKind::Capacity
                },
                if suffix.contains("faults") {
                    Unit::Count
                } else {
                    Unit::Bytes
                },
                "sysinfo::System",
                "sysinfo does not expose this host memory field on this platform",
            );
        }
        let users = sysinfo::Users::new_with_refreshed_list();
        let mut thread_total = Some(0u64);
        for (pid, process) in self.system.processes() {
            let identity = ProcessIdentity {
                pid: pid.as_u32(),
                start_time_ticks: process.start_time(),
            };
            let key = format!("process:{}:{}", identity.pid, identity.start_time_ticks);
            let source = "sysinfo::Process::accumulated_cpu_time (milliseconds)";
            let cpu_percent = self.counters.derive(
                &format!("{key}/cpu"),
                Ok(api_raw(
                    source,
                    process_window,
                    [("cpu_ms", process.accumulated_cpu_time())],
                )),
                |a, b, e| Ok(delta(a, b, "cpu_ms")? as f64 / 10.0 / e),
            );
            let disk = process.disk_usage();
            let mut rate = |suffix: &str, bytes: u64| {
                self.counters.derive(
                    &format!("{key}/{suffix}"),
                    Ok(api_raw(
                        "sysinfo::Process::disk_usage",
                        process_window,
                        [("bytes", bytes)],
                    )),
                    |a, b, e| Ok(delta(a, b, "bytes")? as f64 / e),
                )
            };
            let read_bytes_per_second = rate("read", disk.total_read_bytes);
            let write_bytes_per_second = rate("write", disk.total_written_bytes);
            let user = process
                .user_id()
                .and_then(|id| users.get_user_by_id(id))
                .map(|u| u.name().to_string());
            let count = process.tasks().map(|t| t.len() as u64);
            thread_total = thread_total.zip(count).and_then(|(a, b)| a.checked_add(b));
            let threads = count
                .map(|v| {
                    api_integer(
                        &format!("{key}/threads"),
                        "sysinfo::Process::tasks",
                        v,
                        process_window,
                    )
                })
                .unwrap_or_else(|| {
                    missing(
                        &format!("{key}/threads"),
                        Availability::Unavailable,
                        "sysinfo does not expose this process's thread set".into(),
                    )
                });
            s.processes.push(ProcessRow {
                identity,
                name: process.name().to_string_lossy().into_owned(),
                user_reason: if user.is_none() {
                    Some("sysinfo process user unavailable".into())
                } else {
                    None
                },
                user,
                cpu_percent,
                memory_bytes: api_integer(
                    &format!("{key}/memory"),
                    "sysinfo::Process::memory",
                    process.memory(),
                    process_window,
                ),
                read_bytes_per_second,
                write_bytes_per_second,
                threads,
            });
        }
        let r = api_integer(
            "cpu:host/processes",
            "sysinfo::System::processes",
            s.processes.len() as u64,
            process_window,
        );
        sensor(
            s,
            "cpu:host",
            "processes",
            "Processes",
            SensorKind::Counter,
            Unit::Count,
            "sysinfo::System::processes",
            "Enumerated processes",
            r,
        );
        let r = thread_total
            .map(|n| {
                api_integer(
                    "cpu:host/threads",
                    "sysinfo::Process::tasks",
                    n,
                    process_window,
                )
            })
            .unwrap_or_else(|| {
                missing(
                    "cpu:host/threads",
                    Availability::Unavailable,
                    "Thread counts are not exposed for all processes by sysinfo".into(),
                )
            });
        sensor(
            s,
            "cpu:host",
            "threads",
            "Threads",
            SensorKind::Counter,
            Unit::Count,
            "sysinfo::Process::tasks",
            "Sum of enumerated process threads",
            r,
        );
        for (name, data) in &self.networks {
            let mac = data.mac_address().to_string();
            let id = network_identity(name, Some(&mac), None);
            monitor(s, &id, name, MonitorKind::Network);
            for (suffix, total) in [
                ("rx", data.total_received()),
                ("tx", data.total_transmitted()),
            ] {
                let source = "sysinfo::NetworkData cumulative bytes";
                let sid = format!("{id}/{suffix}");
                let r = self.counters.derive(
                    &sid,
                    Ok(api_raw(source, network_window, [("bytes", total)])),
                    |a, b, e| Ok(delta(a, b, "bytes")? as f64 / e),
                );
                sensor(
                    s,
                    &id,
                    suffix,
                    suffix,
                    SensorKind::Rate,
                    Unit::BytesPerSecond,
                    source,
                    "Interface bytes per measured second",
                    r,
                );
                let suffix = format!("{suffix}-total");
                let r = api_integer(&format!("{id}/{suffix}"), source, total, network_window);
                sensor(
                    s,
                    &id,
                    &suffix,
                    &suffix,
                    SensorKind::Counter,
                    Unit::Bytes,
                    source,
                    "Interface cumulative bytes",
                    r,
                );
            }
            unsupported(
                s,
                &id,
                "connections",
                "Established TCP connections",
                SensorKind::Counter,
                Unit::Count,
                "sysinfo::Networks",
                "sysinfo exposes no address-attributed connection counts",
            );
        }
        let (disks, disk_window) = query(clock, sysinfo::Disks::new_with_refreshed_list);
        for disk in &disks {
            let id = format!(
                "volume:source:{}:{}",
                disk.name().to_string_lossy(),
                disk.mount_point().display()
            );
            monitor(
                s,
                &id,
                &disk.mount_point().display().to_string(),
                MonitorKind::Volume,
            );
            let source = "sysinfo::Disk capacity bytes";
            let mut r = api_integer(
                &format!("{id}/capacity"),
                source,
                disk.total_space().saturating_sub(disk.available_space()),
                disk_window,
            );
            r.total = Some(disk.total_space() as f64);
            r.observations = vec![api_raw(
                source,
                disk_window,
                [
                    ("total", disk.total_space()),
                    ("available", disk.available_space()),
                ],
            )];
            sensor(
                s,
                &id,
                "capacity",
                "Filesystem used",
                SensorKind::Capacity,
                Unit::Bytes,
                source,
                "Filesystem total - available bytes",
                r,
            );
            for (suffix, total) in [
                ("read", disk.usage().total_read_bytes),
                ("write", disk.usage().total_written_bytes),
            ] {
                let source = "sysinfo::Disk::usage cumulative bytes";
                let sid = format!("{id}/{suffix}");
                let r = self.counters.derive(
                    &sid,
                    Ok(api_raw(source, disk_window, [("bytes", total)])),
                    |a, b, e| Ok(delta(a, b, "bytes")? as f64 / e),
                );
                sensor(
                    s,
                    &id,
                    suffix,
                    suffix,
                    SensorKind::Rate,
                    Unit::BytesPerSecond,
                    source,
                    "Shared backing device I/O; not per-volume attribution",
                    r,
                );
            }
            for suffix in ["iops", "latency"] {
                unsupported(
                    s,
                    &id,
                    suffix,
                    suffix,
                    SensorKind::Scalar,
                    if suffix == "iops" {
                        Unit::CountPerSecond
                    } else {
                        Unit::Milliseconds
                    },
                    "sysinfo::Disk::usage",
                    "sysinfo does not expose request counts or request latency",
                );
            }
        }
        s.diagnostics.push(BackendDiagnostic{backend:"sysinfo".into(),availability:Availability::Available,reason:"sysinfo 0.37.2 common backend; some APIs expose no per-field error channel. Native macOS/Windows accuracy is not validated on Linux. Process identity start value is Unix seconds on this backend.".into()});
    }
}
fn api_scalar(id: &str, source: &str, value: f64, window: QueryWindow) -> Reading {
    if !value.is_finite() {
        return missing(
            id,
            Availability::Failed,
            format!("{source}: nonfinite API result"),
        );
    }
    let mut r = measured(id, value, None);
    let mut o = api_raw(source, window, []);
    o.decimals.insert("value".into(), value);
    r.observations.push(o);
    r
}
fn api_integer(id: &str, source: &str, value: u64, window: QueryWindow) -> Reading {
    let mut r = measured(id, value as f64, None);
    r.observations
        .push(api_raw(source, window, [("value", value)]));
    r
}
#[allow(clippy::too_many_arguments)]
fn unsupported(
    s: &mut Snapshot,
    id: &str,
    suffix: &str,
    title: &str,
    kind: SensorKind,
    unit: Unit,
    source: &str,
    reason: &str,
) {
    sensor(
        s,
        id,
        suffix,
        title,
        kind,
        unit,
        source,
        reason,
        missing(
            &format!("{id}/{suffix}"),
            Availability::Unavailable,
            reason.into(),
        ),
    );
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn common_backend_exposes_host_memory_and_real_process_identity() {
        if !sysinfo::IS_SUPPORTED_SYSTEM {
            return;
        }
        let mut c = HostCollector::new();
        let mut s = Snapshot::default();
        c.collect_portable(&mut s);
        assert!(
            s.network_attribution.is_none(),
            "the common backend has no Linux TCP table evidence"
        );
        assert!(
            s.readings
                .iter()
                .any(|r| r.sensor_id == "memory:host/used" && r.total.is_some_and(|v| v > 0.0))
        );
        assert!(
            s.processes
                .iter()
                .any(|p| p.identity.pid == std::process::id())
        );
        let finished_ns = c.now();
        for observation in s
            .readings
            .iter()
            .chain(s.processes.iter().flat_map(|p| {
                [
                    &p.cpu_percent,
                    &p.memory_bytes,
                    &p.read_bytes_per_second,
                    &p.write_bytes_per_second,
                    &p.threads,
                ]
            }))
            .flat_map(|reading| &reading.observations)
        {
            assert!(
                observation
                    .read_started_ns
                    .is_some_and(|start| start <= observation.captured_ns)
            );
            assert!(observation.captured_ns <= finished_ns);
        }
        let uptime_end = s
            .readings
            .iter()
            .find(|r| r.sensor_id == "cpu:host/uptime")
            .unwrap()
            .observations[0]
            .captured_ns;
        for disk_observation in s
            .readings
            .iter()
            .flat_map(|r| &r.observations)
            .filter(|o| o.source.starts_with("sysinfo::Disk"))
        {
            assert!(
                disk_observation.read_started_ns.unwrap() >= uptime_end,
                "disk observations must use the later disk refresh window, not the earlier system timestamp"
            );
        }
    }

    #[test]
    fn delayed_queries_stamp_completion_and_use_measured_disk_rate() {
        use std::cell::Cell;
        let clock = Cell::new(800_000_000u64);
        let now = || clock.get();
        let (first, first_window) = query(now, || {
            clock.set(clock.get() + 200_000_000);
            1000
        });
        assert_eq!(first_window.captured_ns, 1_000_000_000);
        let mut counters = Counters::default();
        let first_reading = counters.derive(
            "disk/read",
            Ok(api_raw(
                "sysinfo::Disk::usage",
                first_window,
                [("bytes", first)],
            )),
            |a, b, e| Ok(delta(a, b, "bytes")? as f64 / e),
        );
        assert_eq!(first_reading.availability, Availability::WarmingUp);
        clock.set(1_500_000_000);
        let (second, second_window) = query(now, || {
            clock.set(clock.get() + 1_000_000_000);
            4000
        });
        let reading = counters.derive(
            "disk/read",
            Ok(api_raw(
                "sysinfo::Disk::usage",
                second_window,
                [("bytes", second)],
            )),
            |a, b, e| Ok(delta(a, b, "bytes")? as f64 / e),
        );
        assert_eq!(reading.value, Some(2000.0));
        assert_eq!(reading.observations[0].read_started_ns, Some(800_000_000));
        assert_eq!(reading.observations[1].read_started_ns, Some(1_500_000_000));
        assert_eq!(reading.observations[1].captured_ns, 2_500_000_000);
    }
}
