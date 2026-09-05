use super::*;
use std::net::{IpAddr, Ipv4Addr, Ipv6Addr};
impl HostCollector {
    pub(super) fn collect_devices(&mut self, s: &mut Snapshot) {
        self.amd(s);
        self.network(s);
        self.volumes(s);
    }
    fn amd(&self, s: &mut Snapshot) {
        let cards = match self.entries("/sys/class/drm") {
            Ok(v) => v,
            Err(e) => {
                diagnostic(s, "linux-drm", e);
                return;
            }
        };
        let mut seen = std::collections::BTreeSet::new();
        for card in cards.into_iter().filter(|c| {
            c.strip_prefix("card")
                .is_some_and(|n| !n.is_empty() && n.chars().all(|c| c.is_ascii_digit()))
        }) {
            let base = format!("/sys/class/drm/{card}/device");
            let vendor = self.read(&format!("{base}/vendor"));
            if vendor.as_ref().is_ok_and(|v| v.trim() != "0x1002") {
                continue;
            }
            if let Err(e) = vendor {
                diagnostic(s, "linux-drm", e);
                continue;
            }
            let unique = self
                .read(&format!("{base}/unique_id"))
                .ok()
                .map(|v| v.trim().to_string())
                .filter(|v| !v.is_empty() && v != "0");
            let pci = std::fs::canonicalize(self.path(&base))
                .ok()
                .and_then(|p| p.file_name().map(|n| n.to_string_lossy().into_owned()))
                .filter(|n| n.contains(':'));
            let Some(identity) = unique.or(pci) else {
                diagnostic(
                    s,
                    "amdgpu",
                    format!("{base}: neither unique_id nor stable PCI identity accessible"),
                );
                continue;
            };
            let id = format!("amdgpu:{identity}");
            if !seen.insert(id.clone()) {
                continue;
            }
            let product = self
                .read(&format!("{base}/product_name"))
                .ok()
                .filter(|s| !s.trim().is_empty())
                .map(|s| s.trim().to_string())
                .unwrap_or_else(|| "AMD GPU".into());
            monitor(
                s,
                &id,
                &format!(
                    "{product} · {}",
                    &identity[identity.len().saturating_sub(8)..]
                ),
                MonitorKind::Gpu,
            );
            let path = format!("{base}/gpu_busy_percent");
            sensor(
                s,
                &id,
                "usage",
                "GPU utilization",
                SensorKind::Percentage,
                Unit::Percent,
                &path,
                "amdgpu device utilization",
                self.scalar(&format!("{id}/usage"), &path, 1.0),
            );
            let used_path = format!("{base}/mem_info_vram_used");
            let total_path = format!("{base}/mem_info_vram_total");
            let r = self.capacity(&format!("{id}/vram"), &used_path, &total_path);
            sensor(
                s,
                &id,
                "vram",
                "VRAM used",
                SensorKind::Capacity,
                Unit::Bytes,
                &format!("{used_path}; {total_path}"),
                "Device VRAM",
                r,
            );
            let hwmon = self
                .entries(&format!("{base}/hwmon"))
                .ok()
                .and_then(|v| v.into_iter().find(|n| n.starts_with("hwmon")));
            let hwbase = hwmon.map(|h| format!("{base}/hwmon/{h}"));
            for (suffix, file, label, kind, unit, factor, scope) in [
                (
                    "temp1",
                    "temp1_input",
                    "Edge temperature",
                    SensorKind::Temperature,
                    Unit::Celsius,
                    0.001,
                    "GPU edge temperature",
                ),
                (
                    "temp2",
                    "temp2_input",
                    "Junction temperature",
                    SensorKind::Temperature,
                    Unit::Celsius,
                    0.001,
                    "GPU junction temperature",
                ),
                (
                    "temp3",
                    "temp3_input",
                    "Memory temperature",
                    SensorKind::Temperature,
                    Unit::Celsius,
                    0.001,
                    "GPU memory temperature",
                ),
                (
                    "power-average",
                    "power1_average",
                    "Average SoC power",
                    SensorKind::Power,
                    Unit::Watts,
                    1e-6,
                    "Average SoC power; not instantaneous board power",
                ),
                (
                    "power-instant",
                    "power1_input",
                    "Instantaneous power",
                    SensorKind::Power,
                    Unit::Watts,
                    1e-6,
                    "Instantaneous power only if hardware exposes power1_input",
                ),
                (
                    "clock-graphics",
                    "freq1_input",
                    "Graphics clock (sclk)",
                    SensorKind::Frequency,
                    Unit::Hertz,
                    1.0,
                    "Graphics clock; zero is valid during sleep",
                ),
                (
                    "clock-memory",
                    "freq2_input",
                    "Memory clock (mclk)",
                    SensorKind::Frequency,
                    Unit::Hertz,
                    1.0,
                    "Memory clock",
                ),
                (
                    "fan-rpm",
                    "fan1_input",
                    "Fan speed",
                    SensorKind::Fan,
                    Unit::Rpm,
                    1.0,
                    "Measured fan revolutions per minute",
                ),
            ] {
                let path = hwbase
                    .as_ref()
                    .map(|h| format!("{h}/{file}"))
                    .unwrap_or_else(|| format!("{base}/hwmon/*/{file}"));
                let raw_label = hwbase.as_ref().and_then(|h| {
                    self.read(&format!(
                        "{h}/{}_label",
                        file.split('_').next().unwrap_or(file)
                    ))
                    .ok()
                });
                let title = raw_label
                    .filter(|l| !l.trim().is_empty())
                    .map(|l| format!("{label} ({})", l.trim()))
                    .unwrap_or_else(|| label.into());
                let r = self.scalar(&format!("{id}/{suffix}"), &path, factor);
                sensor(s, &id, suffix, &title, kind, unit, &path, scope, r);
            }
        }
    }
    fn capacity(&self, id: &str, used_path: &str, total_path: &str) -> Reading {
        match self
            .number(used_path)
            .and_then(|used| self.number(total_path).map(|total| (used, total)))
        {
            Ok((used, total)) if used <= total => {
                let mut r = measured(id, used as f64, Some(total as f64));
                r.observations.push(raw(
                    &format!("{used_path}; {total_path}"),
                    self.now(),
                    [("used", used), ("total", total)],
                ));
                r
            }
            Ok(_) => missing(
                id,
                Availability::Failed,
                "Used capacity exceeds total".into(),
            ),
            Err(e) => missing(id, Availability::Failed, e),
        }
    }
    fn network(&mut self, s: &mut Snapshot) {
        let names = match self.entries("/sys/class/net") {
            Ok(v) => v,
            Err(e) => {
                diagnostic(s, "linux-network", e);
                return;
            }
        };
        if self.root == Path::new("/") {
            self.networks.refresh(true);
        }
        let mut address_owners: BTreeMap<IpAddr, usize> = BTreeMap::new();
        for (_, n) in &self.networks {
            for ip in n.ip_networks() {
                *address_owners.entry(ip.addr).or_default() += 1;
            }
        }
        let connections = self
            .read("/proc/net/tcp")
            .and_then(|v4| self.read("/proc/net/tcp6").map(|v6| (v4, v6)))
            .and_then(|(a, b)| {
                let mut v = tcp_addresses(&a, false)?;
                v.extend(tcp_addresses(&b, true)?);
                Ok(v)
            });
        for name in names {
            let base = format!("/sys/class/net/{name}");
            let physical = std::fs::canonicalize(self.path(&format!("{base}/device")))
                .ok()
                .map(|p| p.to_string_lossy().into_owned());
            let mac = self
                .read(&format!("{base}/address"))
                .ok()
                .map(|v| v.trim().to_string())
                .filter(|v| !v.is_empty() && v != "00:00:00:00:00:00");
            let id = if let Some(p) = physical {
                format!(
                    "network:path:{p}:{}",
                    mac.unwrap_or_else(|| format!("name:{name}"))
                )
            } else if let Some(m) = mac {
                format!("network:mac:{m}")
            } else {
                format!("network:name:{name}")
            };
            monitor(s, &id, &name, MonitorKind::Network);
            for (suffix, file, title) in [
                ("rx", "rx_bytes", "Receive"),
                ("tx", "tx_bytes", "Transmit"),
            ] {
                let path = format!("{base}/statistics/{file}");
                let started = self.now();
                let value = self.number(&path);
                let ns = self.now();
                let observation = value
                    .clone()
                    .map(|v| raw_window(&path, started, ns, [("bytes", v)]));
                let sid = format!("{id}/{suffix}");
                let r = self.counters.derive(&sid, observation, |a, b, e| {
                    Ok(delta(a, b, "bytes")? as f64 / e)
                });
                sensor(
                    s,
                    &id,
                    suffix,
                    &format!("{title} rate"),
                    SensorKind::Rate,
                    Unit::BytesPerSecond,
                    &path,
                    "Interface byte counter delta over measured monotonic elapsed",
                    r,
                );
                let total_suffix = format!("{suffix}-total");
                let mut r = self.integer(&format!("{id}/{total_suffix}"), &path, value, 1.0);
                for o in &mut r.observations {
                    o.read_started_ns = Some(started);
                    o.captured_ns = ns;
                }
                sensor(
                    s,
                    &id,
                    &total_suffix,
                    &format!("{title} cumulative bytes"),
                    SensorKind::Counter,
                    Unit::Bytes,
                    &path,
                    "Interface cumulative byte counter",
                    r,
                );
            }
            let sid = format!("{id}/connections");
            let ips = self
                .networks
                .get(&name)
                .map(|n| {
                    n.ip_networks()
                        .iter()
                        .map(|ip| ip.addr)
                        .filter(|ip| address_owners.get(ip) == Some(&1))
                        .collect::<Vec<_>>()
                })
                .unwrap_or_default();
            let r = if ips.is_empty() {
                missing(&sid,Availability::Unavailable,"No uniquely attributable local interface address; wildcard sockets are excluded".into())
            } else {
                let result = connections
                    .clone()
                    .map(|addresses| addresses.iter().filter(|ip| ips.contains(ip)).count() as u64);
                self.integer(
                    &sid,
                    "/proc/net/tcp + /proc/net/tcp6; sysinfo interface addresses",
                    result,
                    1.0,
                )
            };
            sensor(
                s,
                &id,
                "connections",
                "Established TCP connections",
                SensorKind::Counter,
                Unit::Count,
                "/proc/net/tcp; /proc/net/tcp6; sysinfo::NetworkData::ip_networks",
                "Established TCP sockets with a uniquely owned non-wildcard local address; no system-wide attribution",
                r,
            );
        }
    }
    fn volumes(&mut self, s: &mut Snapshot) {
        let mounts = match self.read("/proc/self/mountinfo") {
            Ok(v) => v,
            Err(e) => {
                diagnostic(s, "linux-volumes", e);
                return;
            }
        };
        let mut seen = std::collections::BTreeSet::new();
        let uuids = self
            .entries("/dev/disk/by-uuid")
            .unwrap_or_default()
            .into_iter()
            .filter_map(|uuid| {
                std::fs::canonicalize(self.path(&format!("/dev/disk/by-uuid/{uuid}")))
                    .ok()
                    .map(|p| (p, uuid))
            })
            .collect::<BTreeMap<_, _>>();
        for line in mounts.lines() {
            let Some((left, right)) = line.split_once(" - ") else {
                diagnostic(
                    s,
                    "linux-volumes",
                    "/proc/self/mountinfo: malformed mount record".into(),
                );
                continue;
            };
            let a = left.split_whitespace().collect::<Vec<_>>();
            let b = right.split_whitespace().collect::<Vec<_>>();
            if a.len() < 6 || b.len() < 3 {
                diagnostic(
                    s,
                    "linux-volumes",
                    "/proc/self/mountinfo: incomplete mount record".into(),
                );
                continue;
            }
            if matches!(
                b[0],
                "proc"
                    | "sysfs"
                    | "devpts"
                    | "cgroup"
                    | "cgroup2"
                    | "securityfs"
                    | "debugfs"
                    | "tracefs"
                    | "configfs"
                    | "pstore"
                    | "bpf"
                    | "mqueue"
                    | "hugetlbfs"
                    | "fusectl"
                    | "autofs"
                    | "binfmt_misc"
                    | "rpc_pipefs"
                    | "nsfs"
                    | "efivarfs"
            ) {
                continue;
            }
            let mountpoint = unescape_mount(a[4]);
            let source = unescape_mount(b[1]);
            let fsroot = unescape_mount(a[3]);
            let block = if b[0] == "fuseblk" {
                use std::os::unix::fs::{FileTypeExt, MetadataExt};
                std::fs::metadata(self.path(&source))
                    .ok()
                    .filter(|m| m.file_type().is_block_device())
                    .map(|m| {
                        format!(
                            "{}:{}",
                            rustix::fs::major(m.rdev()),
                            rustix::fs::minor(m.rdev())
                        )
                    })
                    .unwrap_or_else(|| a[2].into())
            } else {
                a[2].into()
            };
            let uuid = std::fs::canonicalize(self.path(&source))
                .ok()
                .and_then(|p| uuids.get(&p));
            let loop_backing = self
                .read(&format!("/sys/dev/block/{block}/loop/backing_file"))
                .ok()
                .map(|v| v.trim().to_string())
                .filter(|v| !v.is_empty());
            let identity = uuid
                .map(|u| format!("uuid:{u}"))
                .or_else(|| loop_backing.map(|p| format!("loop-file:{p}")))
                .unwrap_or_else(|| format!("source:{source}"));
            let id = format!("volume:{identity}:{fsroot}:{mountpoint}");
            if !seen.insert(id.clone()) {
                continue;
            }
            monitor(
                s,
                &id,
                &format!("{mountpoint} ({})", b[0]),
                MonitorKind::Volume,
            );
            let capacity_id = format!("{id}/capacity");
            let capacity_started = self.now();
            let r = match rustix::fs::statvfs(self.path(&mountpoint)) {
                Ok(v) => {
                    let unit = v.f_frsize;
                    let total = v.f_blocks.checked_mul(unit);
                    let used = v
                        .f_blocks
                        .checked_sub(v.f_bfree)
                        .and_then(|v| v.checked_mul(unit));
                    match (used, total) {
                        (Some(used), Some(total)) => {
                            let mut r = measured(&capacity_id, used as f64, Some(total as f64));
                            r.observations.push(raw_window(
                                &format!("statvfs({mountpoint})"),
                                capacity_started,
                                self.now(),
                                [
                                    ("blocks", v.f_blocks),
                                    ("free_blocks", v.f_bfree),
                                    ("fragment_size", unit),
                                ],
                            ));
                            r
                        }
                        _ => missing(
                            &capacity_id,
                            Availability::Failed,
                            "statvfs capacity overflow".into(),
                        ),
                    }
                }
                Err(e) => missing(
                    &capacity_id,
                    Availability::Failed,
                    format!("statvfs({mountpoint}): {e}"),
                ),
            };
            sensor(
                s,
                &id,
                "capacity",
                "Filesystem used",
                SensorKind::Capacity,
                Unit::Bytes,
                &format!("statvfs({mountpoint})"),
                "(f_blocks - f_bfree) * f_frsize; includes reserved blocks as free",
                r,
            );
            let path = format!("/sys/dev/block/{block}/stat");
            let io_started = self.now();
            let values = self.read(&path).and_then(|t| {
                let v = t
                    .split_whitespace()
                    .map(str::parse::<u64>)
                    .collect::<Result<Vec<_>, _>>()
                    .map_err(|e| format!("{path}: {e}"))?;
                if v.len() < 8 {
                    return Err(format!("{path}: expected at least eight block counters"));
                }
                Ok(raw_window(
                    &path,
                    io_started,
                    self.now(),
                    [
                        ("read_ops", v[0]),
                        ("read_sectors", v[2]),
                        ("read_ms", v[3]),
                        ("write_ops", v[4]),
                        ("write_sectors", v[6]),
                        ("write_ms", v[7]),
                    ],
                ))
            });
            for (suffix, title, unit) in [
                ("read", "Backing device read", Unit::BytesPerSecond),
                ("write", "Backing device write", Unit::BytesPerSecond),
                ("iops", "Backing device IOPS", Unit::CountPerSecond),
                (
                    "latency",
                    "Backing device mean request latency",
                    Unit::Milliseconds,
                ),
            ] {
                let sid = format!("{id}/{suffix}");
                let r = if block.starts_with("0:") {
                    missing(
                        &sid,
                        Availability::Unavailable,
                        format!(
                            "{mountpoint}: filesystem has no directly attributable block device ({})",
                            a[2]
                        ),
                    )
                } else {
                    self.counters
                        .derive(&sid, values.clone(), |a, b, e| match suffix {
                            "read" => Ok(delta(a, b, "read_sectors")? as f64 * 512.0 / e),
                            "write" => Ok(delta(a, b, "write_sectors")? as f64 * 512.0 / e),
                            "iops" => Ok((delta(a, b, "read_ops")?
                                .checked_add(delta(a, b, "write_ops")?)
                                .ok_or("IOPS delta overflow")?)
                                as f64
                                / e),
                            _ => {
                                let ops = delta(a, b, "read_ops")?
                                    .checked_add(delta(a, b, "write_ops")?)
                                    .ok_or("I/O count overflow")?;
                                if ops == 0 {
                                    return Err(
                                        "No completed requests in the observation interval".into(),
                                    );
                                }
                                let ms = delta(a, b, "read_ms")?
                                    .checked_add(delta(a, b, "write_ms")?)
                                    .ok_or("I/O milliseconds overflow")?;
                                Ok(ms as f64 / ops as f64)
                            }
                        })
                };
                let mut r = r;
                if r.reason.as_deref() == Some("No completed requests in the observation interval")
                {
                    r.availability = Availability::Unavailable;
                }
                sensor(
                    s,
                    &id,
                    suffix,
                    title,
                    if suffix == "latency" {
                        SensorKind::Scalar
                    } else {
                        SensorKind::Rate
                    },
                    unit,
                    &path,
                    &format!(
                        "Shared backing device {block} ({source}); not per-volume I/O; sectors are 512 bytes"
                    ),
                    r,
                );
            }
        }
    }
}
fn unescape_mount(v: &str) -> String {
    v.replace("\\040", " ")
        .replace("\\011", "\t")
        .replace("\\012", "\n")
        .replace("\\134", "\\")
}
fn tcp_addresses(text: &str, ipv6: bool) -> Result<Vec<IpAddr>, String> {
    let mut result = Vec::new();
    for line in text.lines().skip(1) {
        let fields = line.split_whitespace().collect::<Vec<_>>();
        if fields.len() < 4 {
            return Err("/proc/net/tcp: malformed socket record".into());
        }
        if fields[3] != "01" {
            continue;
        }
        let hex = fields[1]
            .split(':')
            .next()
            .ok_or("TCP local address missing")?;
        let address = if ipv6 {
            if hex.len() != 32 {
                return Err("TCP6 address must contain 32 hex digits".into());
            }
            let mut bytes = [0u8; 16];
            for i in 0..4 {
                bytes[i * 4..i * 4 + 4].copy_from_slice(
                    &u32::from_str_radix(&hex[i * 8..i * 8 + 8], 16)
                        .map_err(|e| format!("TCP6 address: {e}"))?
                        .to_ne_bytes(),
                );
            }
            let address = Ipv6Addr::from(bytes);
            address
                .to_ipv4_mapped()
                .map(IpAddr::V4)
                .unwrap_or(IpAddr::V6(address))
        } else {
            IpAddr::V4(Ipv4Addr::from(
                u32::from_str_radix(hex, 16)
                    .map_err(|e| format!("TCP4 address: {e}"))?
                    .to_ne_bytes(),
            ))
        };
        if !address.is_unspecified() {
            result.push(address);
        }
    }
    Ok(result)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn established_connections_exclude_wildcards_and_normalize_ipv4_mapped_ipv6() {
        let v4 = "header\n0: 0100007F:1000 0100007F:2000 01\n1: 00000000:1000 00000000:0000 01\n2: 0100007F:1000 00000000:0000 0A\n";
        assert_eq!(
            tcp_addresses(v4, false).unwrap(),
            vec![IpAddr::V4(Ipv4Addr::LOCALHOST)]
        );
        let v6 = "header\n0: 0000000000000000FFFF00000100007F:1000 00000000000000000000000000000000:2000 01\n";
        assert_eq!(
            tcp_addresses(v6, true).unwrap(),
            vec![IpAddr::V4(Ipv4Addr::LOCALHOST)]
        );
    }
}
