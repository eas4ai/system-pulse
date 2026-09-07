use super::*;
use crate::*;
use std::{
    fs,
    path::PathBuf,
    sync::atomic::{AtomicU64, Ordering},
};
static SERIAL: AtomicU64 = AtomicU64::new(0);
struct Fixture(PathBuf);
impl Fixture {
    fn new() -> Self {
        let p = std::env::temp_dir().join(format!(
            "pulse-test-{}-{}",
            std::process::id(),
            SERIAL.fetch_add(1, Ordering::SeqCst)
        ));
        fs::create_dir_all(&p).unwrap();
        Self(p)
    }
    fn put(&self, path: &str, value: &str) {
        let p = self.0.join(path);
        fs::create_dir_all(p.parent().unwrap()).unwrap();
        fs::write(p, value).unwrap();
    }
    fn base(&self) {
        self.put("proc/stat","cpu 100 0 50 800 50 0 0 0 20 0\ncpu0 50 0 25 400 25 0 0 0 10 0\ncpu1 50 0 25 400 25 0 0 0 10 0\n");
        self.put("proc/meminfo","MemTotal: 1000 kB\nMemAvailable: 400 kB\nMemFree: 100 kB\nCached: 200 kB\nBuffers: 50 kB\nSReclaimable: 20 kB\nShmem: 10 kB\nSwapTotal: 500 kB\nSwapFree: 200 kB\n");
        self.put("proc/uptime", "123.5 100\n");
        self.put("proc/loadavg", "1.0 2.0 3.0 1/20 500\n");
        self.put("proc/vmstat", "pgfault 900\npgmajfault 20\n");
        self.put(
            "proc/cpuinfo",
            "processor : 0\ncpu MHz : 3000.0\n\nprocessor : 1\ncpu MHz : 2900.0\n",
        );
        self.put("proc/self/mountinfo", "");
        self.put("etc/passwd", "test:x:1000:1000::/home/test:/bin/sh\n");
    }
    fn process(&self, pid: u32, start: u64, ticks: u64) {
        let mut fields = vec!["0".to_string(); 22];
        fields[0] = "S".into();
        fields[11] = ticks.to_string();
        fields[12] = "0".into();
        fields[17] = "3".into();
        fields[19] = start.to_string();
        fields[21] = "10".into();
        self.put(
            &format!("proc/{pid}/stat"),
            &format!("{pid} (name with ) brackets) {}", fields.join(" ")),
        );
        self.put(
            &format!("proc/{pid}/status"),
            "Name:\tname\nUid:\t1000 1000 1000 1000\nThreads:\t3\nVmRSS:\t40 kB\n",
        );
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}
fn reading<'a>(s: &'a Snapshot, id: &str) -> &'a Reading {
    s.readings
        .iter()
        .find(|r| r.sensor_id == id)
        .unwrap_or_else(|| panic!("missing {id}"))
}
#[test]
fn network_preference_tracks_route_and_falls_back_to_physical_interface() {
    use std::os::unix::fs::symlink;
    let f = Fixture::new();
    f.base();
    for name in ["docker0", "enp10s0", "wlan0"] {
        f.put(&format!("sys/class/net/{name}/statistics/rx_bytes"), "10");
        f.put(&format!("sys/class/net/{name}/statistics/tx_bytes"), "20");
    }
    f.put("sys/devices/ethernet/marker", "");
    symlink(
        f.0.join("sys/devices/ethernet"),
        f.0.join("sys/class/net/enp10s0/device"),
    )
    .unwrap();
    f.put("sys/class/net/enp10s0/operstate", "up");
    f.put(
        "proc/net/route",
        "enp10s0 00000000 0101A8C0 0003 0 0 100 00000000\n",
    );
    let mut c = HostCollector::rooted(f.0.clone());
    let first = c.collect_at(1);
    let ethernet = first
        .monitors
        .iter()
        .find(|m| m.id.contains("enp10s0"))
        .unwrap()
        .id
        .clone();
    assert_eq!(
        first.preferred_network_monitor_id.as_deref(),
        Some(ethernet.as_str())
    );
    f.put(
        "proc/net/route",
        "wlan0 00000000 0101A8C0 0003 0 0 100 00000000\n",
    );
    assert_eq!(
        c.collect_at(2).preferred_network_monitor_id.as_deref(),
        Some("network:name:wlan0")
    );
    f.put("proc/net/route", "");
    assert_eq!(
        c.collect_at(3).preferred_network_monitor_id.as_deref(),
        Some(ethernet.as_str())
    );
}

#[test]
fn monitor_names_use_host_descriptions_without_changing_identity() {
    use std::os::unix::fs::symlink;
    let f = Fixture::new();
    f.base();
    let physical = "sys/devices/pci0000:00/0000:03:00.0";
    f.put(&format!("{physical}/vendor"), "0x1002");
    f.put(&format!("{physical}/unique_id"), "physical-uuid");
    fs::create_dir_all(f.0.join("sys/class/drm/card7")).unwrap();
    symlink(f.0.join(physical), f.0.join("sys/class/drm/card7/device")).unwrap();
    f.put(
        "run/udev/data/+pci:0000:03:00.0",
        "E:ID_MODEL_FROM_DATABASE=Navi 48 [Radeon AI PRO R9700]\n",
    );
    for (name, alias) in [
        ("veth2986d25", ""),
        ("tap-123abc", ""),
        ("docker0", ""),
        ("eth0", "Office LAN"),
    ] {
        f.put(&format!("sys/class/net/{name}/ifalias"), alias);
        f.put(&format!("sys/class/net/{name}/type"), "1");
    }
    f.put("sys/class/net/tap-123abc/tun_flags", "0x1002");
    fs::create_dir_all(f.0.join("sys/class/net/docker0/bridge")).unwrap();
    let mut c = HostCollector::rooted(f.0.clone());
    let first = c.collect_at(1);
    for (id, expected) in [
        ("amdgpu:physical-uuid", "Radeon AI PRO R9700 (0000:03:00.0)"),
        ("network:name:veth2986d25", "Virtual Ethernet (veth2986d25)"),
        ("network:name:tap-123abc", "Virtual TAP (tap-123abc)"),
        ("network:name:docker0", "Docker bridge (docker0)"),
        ("network:name:eth0", "Office LAN (eth0)"),
    ] {
        assert_eq!(
            first.monitors.iter().find(|m| m.id == id).unwrap().title,
            expected
        );
    }
    f.put("sys/class/net/eth0/ifalias", "Renamed LAN");
    let second = c.collect_at(2);
    let ethernet = second
        .monitors
        .iter()
        .find(|m| m.id == "network:name:eth0")
        .unwrap();
    assert_eq!(ethernet.title, "Renamed LAN (eth0)");
    fs::remove_file(f.0.join("run/udev/data/+pci:0000:03:00.0")).unwrap();
    let third = c.collect_at(3);
    assert_eq!(
        third
            .monitors
            .iter()
            .find(|m| m.id == "amdgpu:physical-uuid")
            .unwrap()
            .title,
        "AMD GPU (0000:03:00.0)"
    );
}

#[test]
fn intel_pci_device_is_discovered_without_card_index_identity() {
    use std::os::unix::fs::symlink;
    let f = Fixture::new();
    f.base();
    let physical = "sys/devices/pci0000:00/0000:00:02.0";
    f.put(&format!("{physical}/vendor"), "0x8086");
    f.put(&format!("{physical}/device"), "0x46a6");
    f.put(
        &format!("{physical}/uevent"),
        "DRIVER=i915\nPCI_SLOT_NAME=0000:00:02.0\n",
    );
    fs::create_dir_all(f.0.join("sys/bus/pci/drivers/i915")).unwrap();
    symlink(
        f.0.join("sys/bus/pci/drivers/i915"),
        f.0.join(format!("{physical}/driver")),
    )
    .unwrap();
    fs::create_dir_all(f.0.join("sys/class/drm/card7")).unwrap();
    symlink(f.0.join(physical), f.0.join("sys/class/drm/card7/device")).unwrap();
    let snapshot = HostCollector::rooted(f.0.clone()).collect_at(1);
    let gpus: Vec<_> = snapshot
        .monitors
        .iter()
        .filter(|m| m.kind == MonitorKind::Gpu)
        .collect();
    assert_eq!(
        gpus.len(),
        1,
        "Intel physical device must produce a monitor"
    );
    assert_eq!(gpus[0].id, "intel-pci:0000:00:02.0");
}

impl Fixture {
    fn intel(&self, pci: &str, driver: &str, nodes: &[&str]) -> String {
        let physical = format!("sys/devices/pci0000:00/{pci}");
        self.put(&format!("{physical}/vendor"), "0x8086");
        self.put(&format!("{physical}/device"), "0x46a6");
        self.put(
            &format!("{physical}/uevent"),
            &format!("DRIVER={driver}\nPCI_SLOT_NAME={pci}\n"),
        );
        fs::create_dir_all(self.0.join(format!("sys/bus/pci/drivers/{driver}"))).unwrap();
        std::os::unix::fs::symlink(
            self.0.join(format!("sys/bus/pci/drivers/{driver}")),
            self.0.join(format!("{physical}/driver")),
        )
        .unwrap();
        for node in nodes {
            fs::create_dir_all(self.0.join(format!("sys/class/drm/{node}"))).unwrap();
            std::os::unix::fs::symlink(
                self.0.join(&physical),
                self.0.join(format!("sys/class/drm/{node}/device")),
            )
            .unwrap();
        }
        physical
    }
}

#[test]
fn intel_sparse_gt_clocks_aliases_same_names_and_mixed_amd() {
    let f = Fixture::new();
    f.base();
    let i915 = f.intel("0000:00:02.0", "i915", &["card7", "renderD128"]);
    let xe = f.intel("0000:03:00.0", "xe", &["card2", "renderD129"]);
    f.put("sys/class/drm/card7/gt/gt3/rps_act_freq_mhz", "500");
    f.put("sys/class/drm/card7/gt/gt3/rps_cur_freq_mhz", "700");
    f.put("sys/class/drm/card7/gt/gt8/rps_act_freq_mhz", "900");
    f.put(&format!("{xe}/tile2/gt5/freq0/act_freq"), "1000");
    f.put(&format!("{xe}/tile2/gt5/freq0/cur_freq"), "1200");
    f.put(&format!("{i915}/product_name"), "same name");
    f.put(&format!("{xe}/product_name"), "same name");
    f.put("sys/class/drm/card0/device/vendor", "0x1002");
    f.put("sys/class/drm/card0/device/unique_id", "amd-preserved");
    f.put("sys/class/drm/card0/device/gpu_busy_percent", "31");
    let mut c = HostCollector::rooted(f.0.clone());
    let s = c.collect_at(10);
    assert_eq!(
        s.monitors
            .iter()
            .filter(|m| m.kind == MonitorKind::Gpu)
            .count(),
        3
    );
    assert_eq!(reading(&s, "amdgpu:amd-preserved/usage").value, Some(31.0));
    for (id, value) in [
        ("intel-pci:0000:00:02.0/gt3-frequency-actual", 500e6),
        ("intel-pci:0000:00:02.0/gt3-frequency-requested", 700e6),
        ("intel-pci:0000:00:02.0/gt8-frequency-actual", 900e6),
        ("intel-pci:0000:03:00.0/tile2-gt5-frequency-actual", 1000e6),
        (
            "intel-pci:0000:03:00.0/tile2-gt5-frequency-requested",
            1200e6,
        ),
    ] {
        let r = reading(&s, id);
        assert_eq!(r.value, Some(value));
        assert_eq!(r.observations[0].integers["value"], (value / 1e6) as u64);
        assert_eq!(r.observations[0].read_started_ns, Some(10));
    }
    assert_eq!(
        reading(&s, "intel-pci:0000:00:02.0/gt8-frequency-requested").availability,
        Availability::Unavailable
    );
    fs::rename(
        f.0.join("sys/class/drm/card7"),
        f.0.join("sys/class/drm/card9"),
    )
    .unwrap();
    assert_eq!(
        reading(
            &c.collect_at(20),
            "intel-pci:0000:00:02.0/gt3-frequency-actual"
        )
        .value,
        Some(500e6)
    );
}

#[test]
fn intel_hwmon_scope_units_failure_independence_and_energy_recovery() {
    let f = Fixture::new();
    f.base();
    let physical = f.intel("0000:00:02.0", "xe", &["card7"]);
    let hw = format!("{physical}/hwmon/hwmon91");
    for (name, value) in [
        ("name", "xe"),
        ("temp2_input", "51000"),
        ("temp3_input", "-1000"),
        ("temp3_label", "VRAM"),
        ("fan2_input", "1200"),
        ("energy1_input", "1000000"),
        ("energy2_input", "2000000"),
        ("power1_average", "2500000"),
    ] {
        f.put(&format!("{hw}/{name}"), value);
    }
    let mut c = HostCollector::rooted(f.0.clone());
    let s = c.collect_at(1_000_000_000);
    let prefix = "intel-pci:0000:00:02.0/hwmon-xe";
    assert_eq!(
        reading(&s, &format!("{prefix}-temp2_input")).value,
        Some(51.0)
    );
    assert!(
        s.sensors
            .iter()
            .find(|d| d.id == format!("{prefix}-temp2_input"))
            .unwrap()
            .scope
            .contains("Package")
    );
    assert_eq!(
        reading(&s, &format!("{prefix}-temp3_input")).value,
        Some(-1.0)
    );
    assert_eq!(
        reading(&s, &format!("{prefix}-fan2_input")).value,
        Some(1200.0)
    );
    assert_eq!(
        reading(&s, &format!("{prefix}-power1_average")).value,
        Some(2.5)
    );
    assert_eq!(
        reading(&s, &format!("{prefix}-energy1_input-power")).availability,
        Availability::WarmingUp
    );
    f.put(&format!("{hw}/energy1_input"), "4000000");
    f.put(&format!("{hw}/temp2_input"), "denied");
    let s = c.collect_at(2_500_000_000);
    assert_eq!(
        reading(&s, &format!("{prefix}-energy1_input-power")).value,
        Some(2.0)
    );
    assert_eq!(
        reading(&s, &format!("{prefix}-temp2_input")).availability,
        Availability::Failed
    );
    assert_eq!(
        reading(&s, &format!("{prefix}-fan2_input")).value,
        Some(1200.0)
    );
    f.put(&format!("{hw}/energy1_input"), "bad");
    c.collect_at(3_000_000_000);
    f.put(&format!("{hw}/energy1_input"), "9000000");
    assert_eq!(
        reading(
            &c.collect_at(4_000_000_000),
            &format!("{prefix}-energy1_input-power")
        )
        .availability,
        Availability::WarmingUp
    );
    f.put(&format!("{hw}/temp2_input"), "52000");
    fs::rename(f.0.join(&hw), f.0.join(format!("{physical}/hwmon/hwmon4"))).unwrap();
    assert_eq!(
        reading(
            &c.collect_at(5_000_000_000),
            &format!("{prefix}-temp2_input")
        )
        .value,
        Some(52.0)
    );
}

#[test]
fn intel_hwmon_invalid_identity_never_reuses_old_scope_or_baseline() {
    for invalidation in [
        "replacement",
        "missing",
        "malformed",
        "duplicate",
        "unknown-peer",
    ] {
        let f = Fixture::new();
        f.base();
        let physical = f.intel("0000:00:02.0", "i915", &["card7"]);
        let hw = format!("{physical}/hwmon/hwmon91");
        f.put(&format!("{hw}/name"), "i915");
        f.put(&format!("{hw}/energy1_input"), "1000000");
        f.put(&format!("{hw}/temp1_input"), "50000");
        let sid = "intel-pci:0000:00:02.0/hwmon-i915-energy1_input-power";
        let mut c = HostCollector::rooted(f.0.clone());
        c.collect_at(1_000_000_000);
        match invalidation {
            "replacement" => f.put(&format!("{hw}/name"), "i915_gt0"),
            "missing" => fs::remove_file(f.0.join(format!("{hw}/name"))).unwrap(),
            "malformed" => fs::write(f.0.join(format!("{hw}/name")), [0xff]).unwrap(),
            "duplicate" => f.put(&format!("{physical}/hwmon/hwmon92/name"), "i915"),
            "unknown-peer" => {
                f.put(&format!("{physical}/hwmon/hwmon92/name"), "i915");
                fs::write(f.0.join(format!("{physical}/hwmon/hwmon92/name")), [0xff]).unwrap();
            }
            _ => unreachable!(),
        }
        f.put(&format!("{hw}/energy1_input"), "4000000");
        let s = c.collect_at(2_500_000_000);
        let r = reading(&s, sid);
        assert_eq!(r.value, None, "{invalidation}: old scope must not publish");
        assert_eq!(
            r.availability,
            if matches!(invalidation, "malformed" | "unknown-peer") {
                Availability::Failed
            } else {
                Availability::Unavailable
            },
            "{invalidation}"
        );
        assert_eq!(
            reading(&s, "intel-pci:0000:00:02.0/hwmon-i915-temp1_input").value,
            None
        );
        if invalidation == "replacement" {
            assert_eq!(
                reading(
                    &s,
                    "intel-pci:0000:00:02.0/hwmon-i915_gt0-energy1_input-power"
                )
                .availability,
                Availability::WarmingUp
            );
        }
        f.put(&format!("{hw}/name"), "i915");
        if matches!(invalidation, "duplicate" | "unknown-peer") {
            fs::remove_dir_all(f.0.join(format!("{physical}/hwmon/hwmon92"))).unwrap();
        }
        f.put(&format!("{hw}/energy1_input"), "9000000");
        assert_eq!(
            reading(&c.collect_at(4_000_000_000), sid).availability,
            Availability::WarmingUp,
            "{invalidation}: recovery must reset baseline"
        );
    }
}

#[test]
fn intel_legacy_clocks_reject_overflow_and_keep_requested_semantics() {
    let f = Fixture::new();
    f.base();
    f.intel("0000:00:02.0", "i915", &["card7"]);
    f.put(
        "sys/class/drm/card7/gt_act_freq_mhz",
        "18446744073709551615",
    );
    f.put("sys/class/drm/card7/gt_cur_freq_mhz", "1100");
    let s = HostCollector::rooted(f.0.clone()).collect_at(1);
    assert_eq!(
        reading(&s, "intel-pci:0000:00:02.0/gt0-frequency-actual").availability,
        Availability::Failed
    );
    assert_eq!(
        reading(&s, "intel-pci:0000:00:02.0/gt0-frequency-requested").value,
        Some(1100e6)
    );
    assert!(
        s.sensors
            .iter()
            .find(|d| d.id.ends_with("gt0-frequency-requested"))
            .unwrap()
            .title
            .contains("requested")
    );
}

#[test]
fn intel_temporary_discovery_failure_does_not_reassign_alias_or_drop_physical_identity() {
    let f = Fixture::new();
    f.base();
    let physical = f.intel("0000:00:02.0", "i915", &["card7"]);
    f.put("sys/class/drm/card7/gt_act_freq_mhz", "500");
    let mut c = HostCollector::rooted(f.0.clone());
    c.collect_at(1);
    fs::remove_file(f.0.join(format!("{physical}/vendor"))).unwrap();
    let s = c.collect_at(2);
    assert!(s.monitors.iter().any(|m| m.id == "intel-pci:0000:00:02.0"));
    // The old card ordinal can now name a different device. Never read its clocks into the saved Intel identity.
    fs::remove_file(f.0.join("sys/class/drm/card7/device")).unwrap();
    f.put("sys/devices/pci0000:00/0000:09:00.0/vendor", "0x1002");
    std::os::unix::fs::symlink(
        f.0.join("sys/devices/pci0000:00/0000:09:00.0"),
        f.0.join("sys/class/drm/card7/device"),
    )
    .unwrap();
    f.put("sys/class/drm/card7/gt_act_freq_mhz", "1500");
    let s = c.collect_at(3);
    assert_eq!(
        reading(&s, "intel-pci:0000:00:02.0/gt0-frequency-actual").value,
        None
    );
    fs::remove_dir_all(f.0.join(physical)).unwrap();
    assert!(
        !c.collect_at(4)
            .monitors
            .iter()
            .any(|m| m.id == "intel-pci:0000:00:02.0")
    );
}
#[test]
fn intel_integrated_powercap_pp1_is_separate_and_rejects_package_substitution() {
    let f = Fixture::new();
    f.base();
    f.intel("0000:00:02.0", "i915", &["card7"]);
    f.put("sys/bus/event_source/devices/i915/type", "17");
    f.put("sys/class/powercap/intel-rapl:0/name", "package-0");
    f.put("sys/class/powercap/intel-rapl:0/energy_uj", "999999999");
    f.put(
        "sys/class/powercap/intel-rapl:0/intel-rapl:0:3/name",
        "uncore",
    );
    f.put(
        "sys/class/powercap/intel-rapl:0/intel-rapl:0:3/energy_uj",
        "1000000",
    );
    let mut c = HostCollector::rooted(f.0.clone());
    c.collect_at(1_000_000_000);
    f.put(
        "sys/class/powercap/intel-rapl:0/intel-rapl:0:3/energy_uj",
        "4000000",
    );
    let s = c.collect_at(2_500_000_000);
    assert_eq!(
        reading(&s, "intel-pci:0000:00:02.0/rapl-package-0-uncore-power").value,
        Some(2.0)
    );
    assert!(
        s.sensors
            .iter()
            .find(|d| d.id.ends_with("rapl-package-0-uncore-power"))
            .unwrap()
            .scope
            .contains("PP1")
    );
    f.put("sys/class/powercap/intel-rapl:1/name", "package-1");
    let s = c.collect_at(3_000_000_000);
    assert!(
        !s.readings
            .iter()
            .any(|r| r.sensor_id.ends_with("rapl-package-0-uncore-power") && r.value.is_some())
    );
}
#[test]
fn intel_incomplete_powercap_identity_cannot_create_unique_attribution() {
    for level in ["package", "domain"] {
        let f = Fixture::new();
        f.base();
        f.intel("0000:00:02.0", "i915", &["card7"]);
        f.put("sys/bus/event_source/devices/i915/type", "17");
        let package = "sys/class/powercap/intel-rapl:0";
        let domain = format!("{package}/intel-rapl:0:3");
        f.put(&format!("{package}/name"), "package-0");
        f.put(&format!("{package}/energy_uj"), "99999999");
        f.put(&format!("{domain}/name"), "uncore");
        f.put(&format!("{domain}/energy_uj"), "1000000");
        let sid = "intel-pci:0000:00:02.0/rapl-package-0-uncore-power";
        let mut c = HostCollector::rooted(f.0.clone());
        assert_eq!(
            reading(&c.collect_at(1_000_000_000), sid).availability,
            Availability::WarmingUp
        );
        let unknown = if level == "package" {
            "sys/class/powercap/intel-rapl:1".to_string()
        } else {
            format!("{package}/intel-rapl:0:4")
        };
        f.put(&format!("{unknown}/name"), "unknown");
        fs::write(f.0.join(format!("{unknown}/name")), [0xff]).unwrap();
        f.put(&format!("{domain}/energy_uj"), "4000000");
        let s = c.collect_at(2_500_000_000);
        assert!(
            !s.readings
                .iter()
                .any(|r| r.sensor_id == sid && r.value.is_some()),
            "{level}: unreadable zone must invalidate uniqueness"
        );
        assert!(
            s.diagnostics
                .iter()
                .any(|d| d.availability == Availability::Failed
                    && d.reason.contains(&format!("{unknown}/name")))
        );
        fs::remove_dir_all(f.0.join(unknown)).unwrap();
        f.put(&format!("{domain}/energy_uj"), "9000000");
        assert_eq!(
            reading(&c.collect_at(4_000_000_000), sid).availability,
            Availability::WarmingUp
        );
    }
}
#[test]
fn intel_optional_sources_report_absence_and_malformed_discovery_explicitly() {
    let f = Fixture::new();
    f.base();
    let physical = f.intel("0000:00:02.0", "xe", &["card7"]);
    let mut c = HostCollector::rooted(f.0.clone());
    let s = c.collect_at(1);
    for suffix in ["temperature", "power", "fan", "frequency-actual"] {
        assert_eq!(
            reading(&s, &format!("intel-pci:0000:00:02.0/{suffix}")).availability,
            Availability::Unavailable
        );
    }
    f.put(&format!("{physical}/hwmon"), "not a directory");
    let s = c.collect_at(2);
    assert!(s.diagnostics.iter().any(|d| d.backend == "intel sysfs"
        && d.availability == Availability::Failed
        && d.reason.contains("hwmon")));
    assert!(s.monitors.iter().any(|m| m.id == "intel-pci:0000:00:02.0"));
}
#[test]
fn intel_collection_preserves_existing_nvidia_and_amd_snapshot_fields() {
    let f = Fixture::new();
    f.base();
    f.intel("0000:00:02.0", "i915", &["card7", "renderD137"]);
    let mut s = Snapshot::default();
    for id in ["nvidia:GPU-physical", "amdgpu:physical"] {
        monitor(&mut s, id, "Existing GPU", MonitorKind::Gpu);
        sensor(
            &mut s,
            id,
            "usage",
            "Existing usage",
            SensorKind::Percentage,
            Unit::Percent,
            "existing vendor",
            "physical device",
            measured(&format!("{id}/usage"), 42.0, None),
        );
    }
    let mut c = HostCollector::rooted(f.0.clone());
    c.intel.collect(&mut s, &f.0, c.origin, Some(10));
    assert_eq!(s.monitors.len(), 3);
    assert_eq!(reading(&s, "nvidia:GPU-physical/usage").value, Some(42.0));
    assert_eq!(reading(&s, "amdgpu:physical/usage").value, Some(42.0));
    assert_eq!(
        s.sensors
            .iter()
            .find(|d| d.id == "nvidia:GPU-physical/usage")
            .unwrap()
            .source,
        "existing vendor"
    );
}
#[test]
fn intel_proven_vendor_replacement_is_not_retained_as_old_gpu() {
    let f = Fixture::new();
    f.base();
    let physical = f.intel("0000:00:02.0", "i915", &["card7"]);
    let mut c = HostCollector::rooted(f.0.clone());
    assert!(
        c.collect_at(1)
            .monitors
            .iter()
            .any(|m| m.id == "intel-pci:0000:00:02.0")
    );
    f.put(&format!("{physical}/vendor"), "0x1002");
    assert!(
        !c.collect_at(2)
            .monitors
            .iter()
            .any(|m| m.id == "intel-pci:0000:00:02.0")
    );
}
#[test]
fn intel_incomplete_inventory_cannot_assign_unqualified_pmu_to_another_gpu() {
    let f = Fixture::new();
    f.base();
    f.intel("0000:03:00.0", "i915", &["card7"]);
    let hidden = f.intel("0000:00:02.0", "i915", &["card8"]);
    fs::remove_file(f.0.join(format!("{hidden}/vendor"))).unwrap();
    f.put("sys/bus/event_source/devices/i915/type", "17");
    let s = HostCollector::rooted(f.0.clone()).collect_at(1);
    assert!(
        !s.readings
            .iter()
            .any(|r| r.sensor_id.starts_with("intel-pci:0000:03:00.0/rapl-"))
    );
    assert!(
        !s.diagnostics
            .iter()
            .any(|d| d.reason.starts_with("Integrated:"))
    );
}
#[test]
fn cpu_all_cores_exclude_guest_and_iowait() {
    let f = Fixture::new();
    f.base();
    let mut c = HostCollector::rooted(f.0.clone());
    let first = c.collect_at(1_000_000_000);
    assert_eq!(
        reading(&first, "cpu:host/usage").availability,
        Availability::WarmingUp
    );
    f.put("proc/stat","cpu 140 0 70 830 60 0 0 0 40 0\ncpu0 70 0 35 415 30 0 0 0 20 0\ncpu1 70 0 35 415 30 0 0 0 20 0\n");
    let s = c.collect_at(2_500_000_000);
    assert_eq!(reading(&s, "cpu:host/usage").value, Some(60.0));
    assert_eq!(reading(&s, "cpu:host/core-1-usage").value, Some(60.0));
    assert_eq!(reading(&s, "cpu:host/core-0-frequency").value, Some(3e9));
    assert_eq!(reading(&s, "cpu:host/load-15").value, Some(3.0));
    assert_eq!(reading(&s, "cpu:host/uptime").value, Some(123.5));
    assert_eq!(reading(&s, "cpu:host/usage").observations.len(), 2);
}
#[test]
fn memory_definition_and_raw_conversion() {
    let f = Fixture::new();
    f.base();
    let s = HostCollector::rooted(f.0.clone()).collect_at(1);
    let used = reading(&s, "memory:host/used");
    assert_eq!(used.value, Some(600.0 * 1024.0));
    assert_eq!(used.total, Some(1000.0 * 1024.0));
    assert!(!used.observations.is_empty());
    assert_eq!(reading(&s, "memory:host/cache").value, Some(210.0 * 1024.0));
    assert_eq!(reading(&s, "memory:host/other").value, Some(640.0 * 1024.0));
    assert_eq!(reading(&s, "memory:host/swap").value, Some(300.0 * 1024.0));
    assert_eq!(reading(&s, "memory:host/page-faults").value, Some(900.0));
}
#[test]
fn over_500_processes_denial_and_pid_reuse() {
    let f = Fixture::new();
    f.base();
    for pid in 1000..1601 {
        f.process(pid, 50, 100);
    }
    let mut c = HostCollector::rooted(f.0.clone());
    assert_eq!(c.collect_at(1_000_000_000).processes.len(), 601);
    f.process(1000, 50, 400);
    f.process(1001, 90, 10000);
    let s = c.collect_at(2_500_000_000);
    let row = s.processes.iter().find(|r| r.identity.pid == 1000).unwrap();
    assert_eq!(row.cpu_percent.value, Some(200.0));
    assert_eq!(row.memory_bytes.value, Some(40960.0));
    assert_eq!(row.user.as_deref(), Some("test"));
    assert_eq!(row.read_bytes_per_second.value, None);
    assert!(
        row.read_bytes_per_second
            .reason
            .as_ref()
            .unwrap()
            .contains("io")
    );
    assert_eq!(
        s.processes
            .iter()
            .find(|r| r.identity.pid == 1001)
            .unwrap()
            .cpu_percent
            .availability,
        Availability::WarmingUp
    );
}
#[test]
fn amd_identity_capabilities_conversions_and_reappearance() {
    let f = Fixture::new();
    f.base();
    let path = "sys/class/drm/card7/device";
    f.put(&format!("{path}/vendor"), "0x1002");
    f.put(&format!("{path}/unique_id"), "physical-uuid");
    f.put(&format!("{path}/gpu_busy_percent"), "37");
    f.put(&format!("{path}/mem_info_vram_used"), "1000");
    f.put(&format!("{path}/mem_info_vram_total"), "4000");
    for (name, value) in [
        ("temp1_input", "-1000"),
        ("temp1_label", "edge"),
        ("temp2_input", "52000"),
        ("temp2_label", "junction"),
        ("temp3_input", "43000"),
        ("temp3_label", "memory"),
        ("power1_average", "25000000"),
        ("freq1_input", "0"),
        ("freq2_input", "1500000000"),
        ("fan1_input", "1200"),
    ] {
        f.put(&format!("{path}/hwmon/hwmon99/{name}"), value);
    }
    let mut c = HostCollector::rooted(f.0.clone());
    let s = c.collect_at(1);
    assert!(s.monitors.iter().any(|m| m.id == "amdgpu:physical-uuid"));
    for (suffix, v) in [
        ("usage", 37.0),
        ("vram", 1000.0),
        ("temp1", -1.0),
        ("temp2", 52.0),
        ("temp3", 43.0),
        ("power-average", 25.0),
        ("clock-graphics", 0.0),
        ("clock-memory", 1.5e9),
        ("fan-rpm", 1200.0),
    ] {
        assert_eq!(
            reading(&s, &format!("amdgpu:physical-uuid/{suffix}")).value,
            Some(v)
        );
    }
    assert_eq!(
        reading(&s, "amdgpu:physical-uuid/power-instant").availability,
        Availability::Unavailable
    );
    fs::rename(
        f.0.join("sys/class/drm/card7"),
        f.0.join("sys/class/drm/card2"),
    )
    .unwrap();
    assert!(
        c.collect_at(2)
            .monitors
            .iter()
            .any(|m| m.id == "amdgpu:physical-uuid")
    );
    fs::remove_dir_all(f.0.join("sys/class/drm/card2")).unwrap();
    assert!(
        !c.collect_at(3)
            .monitors
            .iter()
            .any(|m| m.id == "amdgpu:physical-uuid")
    );
}
#[test]
fn network_rates_totals_and_no_invented_connection_counts() {
    let f = Fixture::new();
    f.base();
    for (name, v) in [
        ("address", "aa:bb:cc:dd:ee:ff"),
        ("statistics/rx_bytes", "1000"),
        ("statistics/tx_bytes", "700"),
    ] {
        f.put(&format!("sys/class/net/eth9/{name}"), v);
    }
    let mut c = HostCollector::rooted(f.0.clone());
    c.collect_at(1_000_000_000);
    f.put("sys/class/net/eth9/statistics/rx_bytes", "4000");
    let s = c.collect_at(2_500_000_000);
    assert_eq!(
        reading(&s, "network:mac:aa:bb:cc:dd:ee:ff:name:eth9/rx").value,
        Some(2000.0)
    );
    assert_eq!(
        reading(&s, "network:mac:aa:bb:cc:dd:ee:ff:name:eth9/rx-total").value,
        Some(4000.0)
    );
    assert_eq!(
        reading(&s, "network:mac:aa:bb:cc:dd:ee:ff:name:eth9/connections").value,
        None
    );
}
#[test]
fn volume_device_rates_sectors_iops_and_latency() {
    let f = Fixture::new();
    f.base();
    f.put(
        "proc/self/mountinfo",
        "24 1 8:1 / /mnt/test rw - ext4 /dev/sda1 rw\n",
    );
    f.put("sys/dev/block/8:1/stat", "10 0 100 40 20 0 200 60 0 0 0\n");
    let mut c = HostCollector::rooted(f.0.clone());
    c.collect_at(1_000_000_000);
    f.put("sys/dev/block/8:1/stat", "13 0 106 46 22 0 208 70 0 0 0\n");
    let s = c.collect_at(2_500_000_000);
    let m = s
        .monitors
        .iter()
        .find(|m| m.kind == MonitorKind::Volume)
        .unwrap();
    assert_eq!(reading(&s, &format!("{}/read", m.id)).value, Some(2048.0));
    assert_eq!(
        reading(&s, &format!("{}/write", m.id)).value,
        Some(4096.0 / 1.5)
    );
    assert_eq!(
        reading(&s, &format!("{}/iops", m.id)).value,
        Some(5.0 / 1.5)
    );
    assert_eq!(
        reading(&s, &format!("{}/latency", m.id)).value,
        Some(16.0 / 5.0)
    );
    assert!(
        s.sensors
            .iter()
            .find(|d| d.id == format!("{}/read", m.id))
            .unwrap()
            .scope
            .contains("Shared backing device")
    );
}

#[test]
fn network_duplicate_hardware_parent_keeps_identity_after_port_removal() {
    use std::os::unix::fs::symlink;
    let f = Fixture::new();
    f.base();
    f.put("sys/devices/pci/test/device", "x");
    for (name, mac) in [("eth0", "00:11:22:33:44:55"), ("eth1", "00:11:22:33:44:66")] {
        f.put(&format!("sys/class/net/{name}/address"), mac);
        f.put(&format!("sys/class/net/{name}/statistics/rx_bytes"), "100");
        f.put(&format!("sys/class/net/{name}/statistics/tx_bytes"), "100");
        symlink(
            f.0.join("sys/devices/pci/test"),
            f.0.join(format!("sys/class/net/{name}/device")),
        )
        .unwrap();
    }
    let mut c = HostCollector::rooted(f.0.clone());
    let s = c.collect_at(1);
    let before = s
        .monitors
        .iter()
        .find(|m| m.title == "Network interface (eth1)")
        .unwrap()
        .id
        .clone();
    fs::remove_dir_all(f.0.join("sys/class/net/eth0")).unwrap();
    let s = c.collect_at(2);
    assert_eq!(
        s.monitors
            .iter()
            .find(|m| m.title == "Network interface (eth1)")
            .unwrap()
            .id,
        before
    );
}
#[test]
fn whole_cpu_failure_and_device_churn_reset_and_prune_baselines() {
    let f = Fixture::new();
    f.base();
    let mut c = HostCollector::rooted(f.0.clone());
    c.collect_at(1);
    let initial = c.counters.len();
    assert!(initial >= 3);
    fs::remove_file(f.0.join("proc/stat")).unwrap();
    let s = c.collect_at(2);
    assert_eq!(
        reading(&s, "cpu:host/usage").availability,
        Availability::Failed
    );
    assert_eq!(c.counters.len(), 0);
    f.base();
    let s = c.collect_at(3);
    assert_eq!(
        reading(&s, "cpu:host/usage").availability,
        Availability::WarmingUp
    );
    assert_eq!(c.counters.len(), initial);
}
#[test]
fn cpu_temperature_retains_sparse_physical_labels() {
    let f = Fixture::new();
    f.base();
    f.put("sys/class/hwmon/hwmon9/name", "coretemp");
    f.put("sys/class/hwmon/hwmon9/temp1_label", "Package id 0");
    f.put("sys/class/hwmon/hwmon9/temp1_input", "51000");
    f.put("sys/class/hwmon/hwmon9/temp6_label", "Core 4");
    f.put("sys/class/hwmon/hwmon9/temp6_input", "49000");
    let s = HostCollector::rooted(f.0.clone()).collect_at(1);
    let sensor = s
        .sensors
        .iter()
        .find(|d| d.title.contains("Core 4"))
        .unwrap();
    assert_eq!(reading(&s, &sensor.id).value, Some(49.0));
    assert!(!sensor.id.contains("hwmon9"));
}

#[test]
fn derived_source_observations_have_read_windows() {
    let f = Fixture::new();
    f.base();
    f.process(1000, 50, 100);
    f.put("proc/1000/io", "read_bytes: 100\nwrite_bytes: 200\n");
    f.put("sys/class/net/eth0/address", "aa:bb:cc:dd:ee:ff");
    f.put("sys/class/net/eth0/statistics/rx_bytes", "100");
    f.put("sys/class/net/eth0/statistics/tx_bytes", "100");
    f.put(
        "proc/self/mountinfo",
        "24 1 8:1 / /mnt/test rw - ext4 /dev/sda1 rw\n",
    );
    f.put("sys/dev/block/8:1/stat", "10 0 100 40 20 0 200 60 0 0 0\n");
    let mut c = HostCollector::rooted(f.0.clone());
    let s = c.collect_at(500);
    for id in [
        "cpu:host/usage",
        "network:mac:aa:bb:cc:dd:ee:ff:name:eth0/rx",
        "volume:source:/dev/sda1:/:/mnt/test/read",
    ] {
        let o = &reading(&s, id).observations[0];
        assert_eq!(o.read_started_ns, Some(500), "{id}");
        assert_eq!(o.captured_ns, 500);
    }
    for r in [
        &s.processes[0].cpu_percent,
        &s.processes[0].read_bytes_per_second,
    ] {
        assert_eq!(r.observations[0].read_started_ns, Some(500));
    }
}

#[test]
fn kernel_thread_count_survives_process_census_races() {
    let f = Fixture::new();
    f.base();
    f.put("proc/999/stat", "process exited");
    let s = HostCollector::rooted(f.0.clone()).collect_at(1);
    let r = reading(&s, "cpu:host/threads");
    assert_eq!(r.value, Some(20.0));
    assert!(r.observations[0].source.contains("loadavg"));
}

#[test]
fn shared_mac_interfaces_keep_independent_rates_through_discovery_churn() {
    for hardware_parent in [false, true] {
        let f = Fixture::new();
        f.base();
        if hardware_parent {
            f.put(
                "sys/devices/pci/shared/uevent",
                "PCI_SLOT_NAME=0000:01:00.0",
            );
        }
        let put_interface = |name: &str, rx: u64| {
            f.put(
                &format!("sys/class/net/{name}/address"),
                "aa:bb:cc:dd:ee:ff",
            );
            f.put(
                &format!("sys/class/net/{name}/statistics/rx_bytes"),
                &rx.to_string(),
            );
            f.put(&format!("sys/class/net/{name}/statistics/tx_bytes"), "0");
            if hardware_parent {
                let link = f.0.join(format!("sys/class/net/{name}/device"));
                if !link.exists() {
                    std::os::unix::fs::symlink(f.0.join("sys/devices/pci/shared"), link).unwrap();
                }
            }
        };
        // First creation order; both VLAN interfaces belong to the same hardware MAC.
        put_interface("eth0.10", 1000);
        put_interface("eth0.20", 9000);
        let mut c = HostCollector::rooted(f.0.clone());
        let first = c.collect_at(1_000_000_000);
        let id10 = first
            .monitors
            .iter()
            .find(|m| m.title == "Network interface (eth0.10)")
            .unwrap()
            .id
            .clone();
        let id20 = first
            .monitors
            .iter()
            .find(|m| m.title == "Network interface (eth0.20)")
            .unwrap()
            .id
            .clone();
        assert_ne!(
            id10, id20,
            "two VLAN interfaces sharing one MAC must remain distinct"
        );
        assert_eq!(
            reading(&first, &format!("{id10}/rx")).availability,
            Availability::WarmingUp
        );
        assert_eq!(
            reading(&first, &format!("{id20}/rx")).availability,
            Availability::WarmingUp
        );
        // Recreate in reverse directory enumeration order without an intervening sample.
        fs::remove_dir_all(f.0.join("sys/class/net/eth0.10")).unwrap();
        fs::remove_dir_all(f.0.join("sys/class/net/eth0.20")).unwrap();
        put_interface("eth0.20", 15000);
        put_interface("eth0.10", 4000);
        let reordered = c.collect_at(2_500_000_000);
        assert_eq!(
            reordered
                .monitors
                .iter()
                .find(|m| m.title == "Network interface (eth0.10)")
                .unwrap()
                .id,
            id10
        );
        assert_eq!(
            reordered
                .monitors
                .iter()
                .find(|m| m.title == "Network interface (eth0.20)")
                .unwrap()
                .id,
            id20
        );
        assert_eq!(
            reading(&reordered, &format!("{id10}/rx")).value,
            Some(2000.0)
        );
        assert_eq!(
            reading(&reordered, &format!("{id20}/rx")).value,
            Some(4000.0)
        );
        fs::remove_dir_all(f.0.join("sys/class/net/eth0.10")).unwrap();
        put_interface("eth0.20", 17000);
        let removed = c.collect_at(3_500_000_000);
        assert!(!removed.monitors.iter().any(|m| m.id == id10));
        assert_eq!(reading(&removed, &format!("{id20}/rx")).value, Some(2000.0));
        put_interface("eth0.10", 30000);
        put_interface("eth0.20", 19000);
        let restored = c.collect_at(4_500_000_000);
        assert_eq!(
            restored
                .monitors
                .iter()
                .find(|m| m.title == "Network interface (eth0.10)")
                .unwrap()
                .id,
            id10
        );
        assert_eq!(
            reading(&restored, &format!("{id10}/rx")).availability,
            Availability::WarmingUp
        );
        assert_eq!(
            reading(&restored, &format!("{id20}/rx")).value,
            Some(2000.0)
        );
    }
}

#[test]
fn linux_snapshot_contains_shared_network_query_evidence() {
    let f = Fixture::new();
    f.base();
    f.put("sys/class/net/lo/address", "00:00:00:00:00:00");
    f.put(
        "proc/net/tcp",
        "sl local_address rem_address st\n0: 0100007F:1234 00000000:0000 0A\n",
    );
    f.put("proc/net/tcp6", "sl local_address rem_address st\n");
    let mut collector = HostCollector::rooted(f.0.clone());
    let snapshot = collector.collect_at(10);
    let evidence = snapshot.network_attribution.unwrap();
    assert_eq!(evidence.tcp_v4.rows.len(), 1);
    assert_eq!(evidence.tcp_v4.rows[0].state_hex.as_deref(), Some("0A"));
    assert_eq!(evidence.tcp_v6.query.source, "/proc/net/tcp6");
    fs::remove_file(f.0.join("proc/net/tcp")).unwrap();
    let failed = collector.collect_at(20).network_attribution.unwrap();
    assert_eq!(failed.tcp_v4.query.availability, Availability::Failed);
    assert_eq!(failed.tcp_v6.query.availability, Availability::Available);
    assert_eq!(failed.tcp_v6.query.captured_ns, 20);
}
