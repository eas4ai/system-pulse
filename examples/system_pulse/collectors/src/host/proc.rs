use super::*;
impl HostCollector {
    pub(super) fn collect_cpu_memory(&mut self, s: &mut Snapshot) {
        monitor(s, "cpu:host", "CPU", MonitorKind::Cpu);
        let stat_started = self.now();
        let stat = self.read("/proc/stat");
        let stat_finished = self.now();
        match stat {
            Ok(text) => {
                for line in text.lines().filter(|l| l.starts_with("cpu")) {
                    let mut words = line.split_whitespace();
                    let name = words.next().unwrap_or("cpu");
                    if name != "cpu" && !name[3..].chars().all(|c| c.is_ascii_digit()) {
                        continue;
                    }
                    let suffix = if name == "cpu" {
                        "usage".into()
                    } else {
                        format!("core-{}-usage", &name[3..])
                    };
                    let id = format!("cpu:host/{suffix}");
                    let source = format!("/proc/stat:{name}");
                    let observation = (|| {
                        let values = words
                            .take(8)
                            .map(str::parse::<u64>)
                            .collect::<Result<Vec<_>, _>>()
                            .map_err(|e| format!("{source}: {e}"))?;
                        if values.len() < 4 {
                            return Err(format!("{source}: missing CPU counters"));
                        }
                        let mut o = raw_window(&source, stat_started, stat_finished, []);
                        for (i, k) in [
                            "user", "nice", "system", "idle", "iowait", "irq", "softirq", "steal",
                        ]
                        .iter()
                        .enumerate()
                        {
                            o.integers
                                .insert((*k).into(), values.get(i).copied().unwrap_or(0));
                        }
                        Ok(o)
                    })();
                    let r = self.counters.derive(&id, observation, |a, b, _| {
                        let deltas = [
                            "user", "nice", "system", "idle", "iowait", "irq", "softirq", "steal",
                        ]
                        .into_iter()
                        .map(|k| delta(a, b, k))
                        .collect::<Result<Vec<_>, _>>()?;
                        let total = deltas
                            .iter()
                            .try_fold(0u64, |n, v| n.checked_add(*v))
                            .ok_or("CPU counter sum overflow")?;
                        if total == 0 {
                            return Err("CPU total counter did not advance".into());
                        }
                        Ok(100.0 * (total - deltas[3] - deltas[4]) as f64 / total as f64)
                    });
                    sensor(
                        s,
                        "cpu:host",
                        &suffix,
                        if name == "cpu" {
                            "Overall utilization"
                        } else {
                            name
                        },
                        SensorKind::Percentage,
                        Unit::Percent,
                        &source,
                        "100 * delta(total - idle - iowait) / delta(total); guest excluded from total",
                        r,
                    );
                }
            }
            Err(e) => {
                let r = self
                    .counters
                    .derive("cpu:host/usage", Err(e.clone()), |_, _, _| Ok(0.0));
                sensor(
                    s,
                    "cpu:host",
                    "usage",
                    "Overall utilization",
                    SensorKind::Percentage,
                    Unit::Percent,
                    "/proc/stat",
                    "Host CPU",
                    r,
                );
                diagnostic(s, "linux-cpu", e);
            }
        }
        self.cpu_frequency(s);
        for (suffix, title, index) in [
            ("load-1", "Load average 1 minute", 0),
            ("load-5", "Load average 5 minutes", 1),
            ("load-15", "Load average 15 minutes", 2),
        ] {
            let id = format!("cpu:host/{suffix}");
            let result = self.read("/proc/loadavg").and_then(|t| {
                t.split_whitespace()
                    .nth(index)
                    .ok_or("missing load average".into())
                    .and_then(|v| v.parse::<f64>().map_err(|e| format!("/proc/loadavg: {e}")))
            });
            let r = self.decimal(&id, "/proc/loadavg", result);
            sensor(
                s,
                "cpu:host",
                suffix,
                title,
                SensorKind::Scalar,
                Unit::Load,
                "/proc/loadavg",
                "Host runnable/uninterruptible task average",
                r,
            );
        }
        let uptime = self.read("/proc/uptime").and_then(|t| {
            t.split_whitespace()
                .next()
                .ok_or("/proc/uptime empty".into())
                .and_then(|v| v.parse::<f64>().map_err(|e| format!("/proc/uptime: {e}")))
        });
        let r = self.decimal("cpu:host/uptime", "/proc/uptime", uptime);
        sensor(
            s,
            "cpu:host",
            "uptime",
            "Uptime",
            SensorKind::Duration,
            Unit::Seconds,
            "/proc/uptime",
            "Host uptime",
            r,
        );
        self.cpu_temperatures(s);
        monitor(s, "memory:host", "Memory", MonitorKind::Memory);
        let mem_started = self.now();
        let mem = self.read("/proc/meminfo").map(|t| fields(&t));
        let mem_finished = self.now();
        for (suffix, title, keys) in [
            ("used", "RAM used", vec!["MemTotal", "MemAvailable"]),
            ("total", "RAM total", vec!["MemTotal"]),
            ("available", "RAM available", vec!["MemAvailable"]),
            ("free", "RAM free", vec!["MemFree"]),
            (
                "cache",
                "Cache (Cached + SReclaimable - Shmem)",
                vec!["Cached", "SReclaimable", "Shmem"],
            ),
            ("buffers", "Buffers", vec!["Buffers"]),
            (
                "other",
                "Other (Total - Free - Cache - Buffers)",
                vec![
                    "MemTotal",
                    "MemFree",
                    "Cached",
                    "SReclaimable",
                    "Shmem",
                    "Buffers",
                ],
            ),
            ("swap", "Swap used", vec!["SwapTotal", "SwapFree"]),
            ("swap-total", "Swap total", vec!["SwapTotal"]),
        ] {
            let id = format!("memory:host/{suffix}");
            let result = mem.clone().and_then(|m| {
                let values = keys
                    .iter()
                    .map(|k| field(&m, k, "/proc/meminfo"))
                    .collect::<Result<Vec<_>, _>>()?;
                let value = match suffix {
                    "used" | "swap" => values[0].checked_sub(values[1]),
                    "cache" => values[0]
                        .checked_add(values[1])
                        .and_then(|v| v.checked_sub(values[2])),
                    "other" => values[2]
                        .checked_add(values[3])
                        .and_then(|v| v.checked_sub(values[4]))
                        .and_then(|cache| {
                            values[0]
                                .checked_sub(values[1])
                                .and_then(|v| v.checked_sub(cache))
                                .and_then(|v| v.checked_sub(values[5]))
                        }),
                    _ => Some(values[0]),
                }
                .ok_or("/proc/meminfo: inconsistent composition counters")?;
                let total = if suffix == "used" || suffix == "swap" {
                    Some(values[0] as f64 * 1024.0)
                } else {
                    None
                };
                let mut r = measured(&id, value as f64 * 1024.0, total);
                r.observations.push(RawObservation {
                    source: "/proc/meminfo (kB = 1024 bytes)".into(),
                    captured_ns: mem_finished,
                    read_started_ns: Some(mem_started),
                    integers: keys
                        .into_iter()
                        .zip(values)
                        .map(|(k, v)| (k.into(), v))
                        .collect(),
                    decimals: BTreeMap::new(),
                });
                Ok(r)
            });
            sensor(
                s,
                "memory:host",
                suffix,
                title,
                SensorKind::Capacity,
                Unit::Bytes,
                "/proc/meminfo",
                if suffix == "used" {
                    "MemTotal - MemAvailable"
                } else {
                    "Host memory; named composition is disjoint free/cache/buffers/other"
                },
                result.unwrap_or_else(|e| missing(&id, Availability::Failed, e)),
            );
        }
        let vmstat = self.read("/proc/vmstat").map(|t| fields(&t));
        for (suffix, key, title) in [
            ("page-faults", "pgfault", "Cumulative page faults"),
            (
                "major-page-faults",
                "pgmajfault",
                "Cumulative major page faults",
            ),
        ] {
            let id = format!("memory:host/{suffix}");
            let r = self.integer(
                &id,
                "/proc/vmstat",
                vmstat.clone().and_then(|m| field(&m, key, "/proc/vmstat")),
                1.0,
            );
            sensor(
                s,
                "memory:host",
                suffix,
                title,
                SensorKind::Counter,
                Unit::Count,
                "/proc/vmstat",
                "Host cumulative faults since boot",
                r,
            );
        }
    }
    pub(crate) fn integer(
        &self,
        id: &str,
        source: &str,
        value: Result<u64, String>,
        factor: f64,
    ) -> Reading {
        match value {
            Ok(v) => {
                let mut r = measured(id, v as f64 * factor, None);
                r.observations.push(raw(source, self.now(), [("value", v)]));
                r
            }
            Err(e) => missing(id, Availability::Failed, e),
        }
    }
    fn decimal(&self, id: &str, source: &str, value: Result<f64, String>) -> Reading {
        match value {
            Ok(v) if v.is_finite() => {
                let mut r = measured(id, v, None);
                let mut o = raw(source, self.now(), []);
                o.decimals.insert("value".into(), v);
                r.observations.push(o);
                r
            }
            Ok(_) => missing(
                id,
                Availability::Failed,
                format!("{source}: nonfinite number"),
            ),
            Err(e) => missing(id, Availability::Failed, e),
        }
    }
    fn cpu_frequency(&self, s: &mut Snapshot) {
        let cpuinfo = self.read("/proc/cpuinfo").map(|t| {
            t.split("\n\n")
                .filter_map(|block| {
                    let pairs = block
                        .lines()
                        .filter_map(|l| l.split_once(':'))
                        .map(|(k, v)| (k.trim(), v.trim()))
                        .collect::<BTreeMap<_, _>>();
                    Some((
                        pairs.get("processor")?.to_string(),
                        pairs.get("cpu MHz")?.parse::<f64>().ok()?,
                    ))
                })
                .collect::<BTreeMap<_, _>>()
        });
        let cores = s
            .sensors
            .iter()
            .filter_map(|d| {
                d.id.strip_prefix("cpu:host/core-")
                    .and_then(|v| v.strip_suffix("-usage"))
            })
            .map(str::to_string)
            .collect::<Vec<_>>();
        for core in cores {
            let suffix = format!("core-{core}-frequency");
            let id = format!("cpu:host/{suffix}");
            let path = format!("/sys/devices/system/cpu/cpu{core}/cpufreq/scaling_cur_freq");
            let (source, r) = if self.path(&path).exists() {
                (path.clone(), self.scalar(&id, &path, 1000.0))
            } else {
                let value = cpuinfo.clone().and_then(|m| {
                    m.get(&core)
                        .copied()
                        .ok_or_else(|| format!("/proc/cpuinfo: cpu {core} frequency unavailable"))
                });
                let mut r = self.decimal(&id, "/proc/cpuinfo:cpu MHz", value);
                r.value = r.value.map(|v| v * 1e6);
                ("/proc/cpuinfo:cpu MHz".into(), r)
            };
            sensor(
                s,
                "cpu:host",
                &suffix,
                &format!("CPU {core} frequency"),
                SensorKind::Frequency,
                Unit::Hertz,
                &source,
                "Current frequency of this logical CPU; scaling_cur_freq may reflect requested P-state",
                r,
            );
        }
    }
    fn cpu_temperatures(&self, s: &mut Snapshot) {
        let mut found = false;
        match self.entries("/sys/class/hwmon") {
            Ok(names) => {
                for name in names {
                    let base = format!("/sys/class/hwmon/{name}");
                    let driver = self.read(&format!("{base}/name")).unwrap_or_default();
                    if !matches!(
                        driver.trim(),
                        "coretemp" | "k10temp" | "zenpower" | "cpu_thermal" | "scpi_sensors"
                    ) {
                        continue;
                    }
                    let stable = std::fs::canonicalize(self.path(&format!("{base}/device")))
                        .ok()
                        .map(|p| p.to_string_lossy().into_owned())
                        .unwrap_or_else(|| driver.trim().into());
                    for file in self
                        .entries(&base)
                        .unwrap_or_default()
                        .into_iter()
                        .filter(|f| f.starts_with("temp") && f.ends_with("_input"))
                    {
                        let stem = file.trim_end_matches("_input");
                        let label = self
                            .read(&format!("{base}/{stem}_label"))
                            .unwrap_or_else(|_| stem.into())
                            .trim()
                            .to_string();
                        let suffix =
                            format!("temperature:{}:{label}", stable.trim_start_matches('/'));
                        let id = format!("cpu:host/{suffix}");
                        let path = format!("{base}/{file}");
                        let r = self.scalar(&id, &path, 0.001);
                        sensor(
                            s,
                            "cpu:host",
                            &suffix,
                            &format!("{} {label}", driver.trim()),
                            SensorKind::Temperature,
                            Unit::Celsius,
                            &path,
                            &format!("Physical CPU hwmon sensor: {label}"),
                            r,
                        );
                        found = true;
                    }
                }
            }
            Err(e) => diagnostic(s, "linux-cpu-temperature", e),
        }
        if !found {
            sensor(
                s,
                "cpu:host",
                "temperature",
                "CPU temperature",
                SensorKind::Temperature,
                Unit::Celsius,
                "/sys/class/hwmon",
                "CPU thermal providers",
                missing(
                    "cpu:host/temperature",
                    Availability::Unavailable,
                    "No CPU hwmon temperature provider exposed".into(),
                ),
            );
        }
    }
}
