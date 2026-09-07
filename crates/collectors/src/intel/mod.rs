//! Intel Linux physical devices. All collection runs in HostCollector's worker.
use crate::{
    MonitorKind, Snapshot,
    counters::Counters,
    host::{diagnostic, monitor},
};
mod drm;
mod native;
mod pmu;
mod rapl;
mod sysfs;
use std::{
    collections::BTreeMap,
    fs,
    path::{Path, PathBuf},
    time::Instant,
};

#[derive(Clone, Debug)]
struct Device {
    pci: String,
    driver: String,
    path: PathBuf,
    cards: Vec<PathBuf>,
}

fn discover(root: &Path) -> std::io::Result<(Vec<Device>, Vec<crate::BackendDiagnostic>)> {
    let mut issues = Vec::new();
    let mut devices = BTreeMap::<String, Device>::new();
    for entry in sysfs::entries(&root.join("sys/class/drm"))? {
        let name = entry.file_name().unwrap().to_string_lossy().into_owned();
        if !(numbered(&name, "card") || numbered(&name, "renderD")) {
            continue;
        }
        let path = match entry.join("device").canonicalize() {
            Ok(path) => path,
            Err(e) => {
                issues.push(crate::BackendDiagnostic {
                    backend: "intel discovery".into(),
                    availability: drm::error_availability(&e),
                    reason: format!(
                        "{}: {e}; unqualified PMU attribution disabled",
                        entry.display()
                    ),
                });
                continue;
            }
        };
        match sysfs::text(&path.join("vendor")) {
            Ok(value) if value == "0x8086" => {}
            Ok(_) => continue,
            Err(e) => {
                issues.push(crate::BackendDiagnostic {
                    backend: "intel discovery".into(),
                    availability: drm::error_availability(&e),
                    reason: format!(
                        "{}: {e}; unqualified PMU attribution disabled",
                        path.join("vendor").display()
                    ),
                });
                continue;
            }
        }
        let driver = match fs::read_link(path.join("driver")) {
            Ok(p) => p
                .file_name()
                .map(|v| v.to_string_lossy().into_owned())
                .unwrap_or_default(),
            Err(e) => {
                issues.push(crate::BackendDiagnostic {
                    backend: "intel discovery".into(),
                    availability: drm::error_availability(&e),
                    reason: format!(
                        "{}: {e}; unqualified PMU attribution disabled",
                        path.join("driver").display()
                    ),
                });
                continue;
            }
        };
        if !matches!(driver.as_str(), "i915" | "xe") {
            continue;
        }
        let Some(pci) = path
            .file_name()
            .and_then(|v| v.to_str())
            .filter(|v| valid_pci(v))
        else {
            continue;
        };
        let pci = pci.to_owned();
        let device = devices.entry(pci.clone()).or_insert_with(|| Device {
            pci,
            driver,
            path,
            cards: vec![],
        });
        device.cards.push(entry.clone());
    }
    Ok((devices.into_values().collect(), issues))
}
fn numbered(name: &str, prefix: &str) -> bool {
    name.strip_prefix(prefix)
        .is_some_and(|n| !n.is_empty() && n.bytes().all(|c| c.is_ascii_digit()))
}
fn valid_pci(pci: &str) -> bool {
    let b = pci.as_bytes();
    b.len() == 12
        && b[4] == b':'
        && b[7] == b':'
        && b[10] == b'.'
        && b.iter()
            .enumerate()
            .all(|(i, c)| matches!(i, 4 | 7 | 10) || c.is_ascii_hexdigit())
        && b[11] <= b'7'
}
pub(crate) struct IntelCollector {
    counters: Counters,
    pmu: pmu::Pmu,
    rapl: pmu::Pmu,
    fields: BTreeMap<String, BTreeMap<String, sysfs::Field>>,
    devices: BTreeMap<String, Device>,
}
struct Clock {
    origin: Instant,
    fixed: Option<u64>,
}
impl Clock {
    fn now(&self) -> u64 {
        self.fixed
            .unwrap_or_else(|| self.origin.elapsed().as_nanos().min(u64::MAX as u128) as u64)
    }
}
impl IntelCollector {
    pub(crate) fn new() -> Self {
        Self {
            counters: Counters::default(),
            pmu: pmu::Pmu::new(),
            rapl: pmu::Pmu::new(),
            fields: BTreeMap::new(),
            devices: BTreeMap::new(),
        }
    }
    pub(crate) fn collect(
        &mut self,
        snapshot: &mut Snapshot,
        root: &Path,
        origin: Instant,
        fixed_ns: Option<u64>,
    ) {
        let clock = Clock {
            origin,
            fixed: fixed_ns,
        };
        self.counters.begin();
        let mut inventory_complete = false;
        match discover(root) {
            Ok((devices, issues)) => {
                inventory_complete = issues.is_empty();
                snapshot.diagnostics.extend(issues);
                for device in devices {
                    if self
                        .devices
                        .get(&device.pci)
                        .is_some_and(|old| old.driver != device.driver)
                    {
                        self.fields.remove(&device.pci);
                    }
                    if self.devices.len() < 512 || self.devices.contains_key(&device.pci) {
                        self.devices.insert(device.pci.clone(), device);
                    } else {
                        diagnostic(
                            snapshot,
                            "intel discovery",
                            "512-device limit exceeded".into(),
                        );
                    }
                }
            }
            Err(e) if e.kind() == std::io::ErrorKind::NotFound && self.devices.is_empty() => {}
            Err(e) => diagnostic(snapshot, "intel discovery", e.to_string()),
        }
        // An unreadable inventory does not prove removal. The canonical physical PCI path does.
        self.devices.retain(|_, device| {
            !fs::metadata(&device.path).is_err_and(|e| e.kind() == std::io::ErrorKind::NotFound)
                && !sysfs::text(&device.path.join("vendor")).is_ok_and(|v| v != "0x8086")
        });
        for device in self.devices.values_mut() {
            device.cards.retain(|card| {
                card.join("device")
                    .canonicalize()
                    .is_ok_and(|p| p == device.path)
            });
        }
        let devices: Vec<_> = self.devices.values().cloned().collect();
        self.fields
            .retain(|pci, _| devices.iter().any(|d| &d.pci == pci));
        let plain_candidates: Vec<_> = devices
            .iter()
            .filter(|d| {
                d.driver == "i915"
                    && !root
                        .join("sys/bus/event_source/devices")
                        .join(format!("i915_{}", d.pci.replace(':', "_")))
                        .exists()
            })
            .map(|d| d.pci.clone())
            .collect();
        self.pmu.retain(
            &devices
                .iter()
                .map(|d| format!("intel-pci:{}", d.pci))
                .collect::<Vec<_>>(),
        );
        self.rapl.retain(
            &devices
                .iter()
                .filter(|d| {
                    inventory_complete
                        && plain_candidates.len() == 1
                        && plain_candidates[0] == d.pci
                        && root.join("sys/bus/event_source/devices/i915").is_dir()
                })
                .map(|d| format!("intel-pci:{}", d.pci))
                .collect::<Vec<_>>(),
        );
        for device in devices {
            let id = format!("intel-pci:{}", device.pci);
            monitor(
                snapshot,
                &id,
                &format!("Intel GPU · {} ({})", device.pci, device.driver),
                MonitorKind::Gpu,
            );
            let integrated = inventory_complete
                && plain_candidates.len() == 1
                && plain_candidates[0] == device.pci
                && root.join("sys/bus/event_source/devices/i915").is_dir();
            if integrated {
                snapshot.diagnostics.push(crate::BackendDiagnostic {backend:format!("intel identity {}",device.pci),availability:crate::Availability::Available,reason:"Integrated: kernel unqualified i915 PMU is uniquely attributable; discrete i915 PMUs include PCI identity".into()});
            }
            let fields = self.fields.entry(device.pci.clone()).or_default();
            fields.retain(|key, _| !key.starts_with("rapl-"));
            if integrated {
                match rapl::powercap(root, integrated) {
                    Ok((key, field)) => {
                        fields.insert(key, field);
                    }
                    Err(e) => snapshot.diagnostics.push(crate::BackendDiagnostic {
                        backend: format!("intel RAPL powercap {}", device.pci),
                        availability: drm::error_availability(&e),
                        reason: e.to_string(),
                    }),
                }
            }
            sysfs::collect(snapshot, &device, &id, &clock, fields, &mut self.counters);
            let engines = drm::collect(snapshot, &device, root, &id, &clock);
            if integrated {
                self.rapl.sample_power(
                    snapshot,
                    &id,
                    &clock,
                    rapl::specification(root, &device, integrated),
                );
            }
            self.pmu.collect(
                snapshot,
                &device,
                root,
                &clock,
                engines,
                inventory_complete
                    && plain_candidates.len() == 1
                    && plain_candidates[0] == device.pci,
            );
        }
        self.counters.finish();
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn physical_device_churn_prunes_inventory_fields_and_baselines() {
        let root = std::env::temp_dir().join(format!("pulse-intel-churn-{}", std::process::id()));
        let driver = root.join("sys/bus/pci/drivers/i915");
        fs::create_dir_all(&driver).unwrap();
        let card = root.join("sys/class/drm/card7");
        let mut collector = IntelCollector::new();
        for index in 0..32 {
            let physical = root.join(format!("sys/devices/pci0000:00/0000:00:{index:02x}.0"));
            fs::create_dir_all(&physical).unwrap();
            fs::write(physical.join("vendor"), "0x8086").unwrap();
            std::os::unix::fs::symlink(&driver, physical.join("driver")).unwrap();
            fs::create_dir_all(&card).unwrap();
            std::os::unix::fs::symlink(&physical, card.join("device")).unwrap();
            collector.collect(&mut Snapshot::default(), &root, Instant::now(), Some(1));
            assert_eq!(collector.devices.len(), 1);
            assert_eq!(collector.fields.len(), 1);
            fs::remove_dir_all(physical).unwrap();
            fs::remove_dir_all(&card).unwrap();
            collector.collect(&mut Snapshot::default(), &root, Instant::now(), Some(2));
            assert!(collector.devices.is_empty());
            assert!(collector.fields.is_empty());
            assert!(collector.counters.is_empty());
        }
        fs::remove_dir_all(root).unwrap();
    }
}
