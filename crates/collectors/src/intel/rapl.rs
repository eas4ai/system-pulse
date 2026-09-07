//! Optional Intel CPU graphics-domain energy, only with unambiguous physical attribution.
use super::{Device, pmu::Spec};
use std::{io, path::Path};
pub(super) fn powercap(root: &Path, integrated: bool) -> io::Result<(String, super::sysfs::Field)> {
    powercap_with_reader(root, integrated, &super::sysfs::text)
}
fn powercap_with_reader(
    root: &Path,
    integrated: bool,
    read: &impl Fn(&Path) -> io::Result<String>,
) -> io::Result<(String, super::sysfs::Field)> {
    use super::sysfs::{Field, entries};
    let name = |path: &Path| {
        let path = path.join("name");
        read(&path).map_err(|e| io::Error::new(e.kind(), format!("{}: {e}", path.display())))
    };
    let unavailable = |message: &str| io::Error::new(io::ErrorKind::Unsupported, message);
    if !integrated {
        return Err(unavailable("No integrated GPU association for RAPL"));
    }
    let mut packages = std::collections::BTreeMap::new();
    for path in entries(&root.join("sys/class/powercap"))? {
        if !zone_path(&path) {
            continue;
        }
        let name = name(&path)?;
        if let Some(package) = name.strip_prefix("package-") {
            package.parse::<u32>().map_err(|_| {
                io::Error::new(
                    io::ErrorKind::InvalidData,
                    format!(
                        "{}: invalid package identity {name}",
                        path.join("name").display()
                    ),
                )
            })?;
            packages.insert(path.canonicalize()?, name);
        }
    }
    if packages.len() != 1 {
        return Err(unavailable(
            "Powercap GPU attribution requires one package; multi-die/unknown zones are ambiguous",
        ));
    }
    let (package, package_name) = packages.into_iter().next().unwrap();
    let mut domains = std::collections::BTreeSet::new();
    for path in entries(&package)? {
        // Zone directories have a control type plus numeric colon selectors.
        // Ordinary attributes (energy_uj/name/etc.) are not zone candidates.
        if zone_path(&path) && name(&path)? == "uncore" {
            domains.insert(path.canonicalize()?);
        }
    }
    if domains.len() != 1 {
        return Err(unavailable("No unique Intel RAPL PP1 uncore domain"));
    }
    Ok((
        format!("rapl-{package_name}-uncore-power"),
        Field::energy(
            domains.into_iter().next().unwrap().join("energy_uj"),
            format!("RAPL {package_name} graphics-domain power"),
            format!(
                "CPU {package_name} PP1 graphics domain associated with the unique integrated i915 GPU; not CPU package energy or whole graphics-card power"
            ),
        ),
    ))
}
fn zone_path(path: &Path) -> bool {
    let Some(name) = path.file_name().and_then(|v| v.to_str()) else {
        return false;
    };
    let Some(selectors) = name
        .strip_prefix("intel-rapl:")
        .or_else(|| name.strip_prefix("intel-rapl-mmio:"))
    else {
        return false;
    };
    selectors
        .split(':')
        .all(|part| !part.is_empty() && part.bytes().all(|v| v.is_ascii_digit()))
}
pub(super) fn specification(root: &Path, device: &Device, integrated: bool) -> io::Result<Spec> {
    use super::sysfs::text;
    let unavailable = |s: &str| io::Error::new(io::ErrorKind::Unsupported, s);
    if !integrated {
        return Err(unavailable(
            "RAPL PP1 is a CPU graphics domain; physical integrated-GPU association is not evidenced",
        ));
    }
    let pmu = root.join("sys/bus/event_source/devices/power");
    let mask = text(&pmu.join("cpumask"))?;
    let cpu = mask
        .parse::<i32>()
        .ok()
        .filter(|v| *v >= 0)
        .ok_or_else(|| {
            unavailable("RAPL exposes multiple or ambiguous dies; no arbitrary package selection")
        })?;
    let topology = root.join(format!("sys/devices/system/cpu/cpu{cpu}/topology"));
    let package = text(&topology.join("physical_package_id"))?
        .parse::<u32>()
        .map_err(|_| unavailable("Invalid RAPL package identity"))?;
    let die = text(&topology.join("die_id"))?
        .parse::<u32>()
        .map_err(|_| unavailable("Invalid RAPL die identity"))?;
    if text(&pmu.join("format/event"))? != "config:0-7"
        || text(&pmu.join("events/energy-gpu"))? != "event=0x04"
        || text(&pmu.join("events/energy-gpu.unit"))? != "Joules"
        || text(&pmu.join("events/energy-gpu.scale"))?
            .parse::<f64>()
            .ok()
            != Some(1.0 / (1u64 << 32) as f64)
    {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "RAPL GPU event layout/unit differs from documented 2^-32 Joules",
        ));
    }
    let kind = text(&pmu.join("type"))?
        .parse()
        .map_err(|_| io::Error::new(io::ErrorKind::InvalidData, "Invalid RAPL PMU type"))?;
    Ok(Spec {
        event_path: None,
        metadata_error: None,
        id: format!("rapl-package{package}-die{die}-graphics"),
        pmu,
        kind,
        cpu,
        active: 4,
        total: None,
        energy_denominator: 1u64 << 32,
        scope: format!(
            "Intel CPU package {package}, die {die}, PP1 graphics domain associated with integrated PCI {}; excludes CPU cores/package energy; not whole graphics-card power",
            device.pci
        ),
    })
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn powercap_denied_zone_identity_invalidates_uniqueness_but_attributes_are_skipped() {
        let root =
            std::env::temp_dir().join(format!("pulse-powercap-denied-{}", std::process::id()));
        let package = root.join("sys/class/powercap/intel-rapl:0");
        let domain = package.join("intel-rapl:0:3");
        std::fs::create_dir_all(&domain).unwrap();
        std::fs::write(package.join("name"), "package-0").unwrap();
        std::fs::write(package.join("energy_uj"), "99999999").unwrap();
        std::fs::write(domain.join("name"), "uncore").unwrap();
        assert!(powercap(&root, true).is_ok());
        for unknown in [
            root.join("sys/class/powercap/intel-rapl:1"),
            package.join("intel-rapl:0:4"),
        ] {
            std::fs::create_dir_all(&unknown).unwrap();
            let denied_path = unknown.join("name");
            let read = |path: &Path| {
                if path == denied_path {
                    Err(io::Error::from(io::ErrorKind::PermissionDenied))
                } else {
                    super::super::sysfs::text(path)
                }
            };
            let error = powercap_with_reader(&root, true, &read).err().unwrap();
            assert_eq!(error.kind(), io::ErrorKind::PermissionDenied);
            assert!(
                error
                    .to_string()
                    .contains(&denied_path.display().to_string())
            );
            let missing = powercap(&root, true).err().unwrap();
            assert_eq!(missing.kind(), io::ErrorKind::NotFound);
            std::fs::remove_dir(&unknown).unwrap();
            assert!(powercap(&root, true).is_ok());
        }
        std::fs::remove_dir_all(root).unwrap();
    }
    #[test]
    fn rapl_gpu_energy_requires_integrated_evidence_one_die_and_correct_units() {
        let root = std::env::temp_dir().join(format!("pulse-rapl-{}", std::process::id()));
        let pmu = root.join("sys/bus/event_source/devices/power");
        std::fs::create_dir_all(pmu.join("events")).unwrap();
        std::fs::create_dir_all(pmu.join("format")).unwrap();
        for (path, value) in [
            ("type", "19"),
            ("cpumask", "0"),
            ("format/event", "config:0-7"),
            ("events/energy-gpu", "event=0x04"),
            ("events/energy-gpu.unit", "Joules"),
            ("events/energy-gpu.scale", "2.3283064365386962890625e-10"),
        ] {
            std::fs::write(pmu.join(path), value).unwrap();
        }
        let cpu = root.join("sys/devices/system/cpu/cpu0/topology");
        std::fs::create_dir_all(&cpu).unwrap();
        std::fs::write(cpu.join("physical_package_id"), "0").unwrap();
        std::fs::write(cpu.join("die_id"), "0").unwrap();
        let d = Device {
            pci: "0000:00:02.0".into(),
            driver: "i915".into(),
            path: root.join("device"),
            cards: vec![],
        };
        assert!(specification(&root, &d, false).is_err());
        let s = specification(&root, &d, true).unwrap();
        assert_eq!(s.active, 4);
        assert!(s.scope.contains("PP1"));
        assert!(s.scope.contains("package 0"));
        std::fs::write(pmu.join("cpumask"), "0,8").unwrap();
        assert!(specification(&root, &d, true).is_err());
        std::fs::write(pmu.join("cpumask"), "0").unwrap();
        std::fs::write(pmu.join("events/energy-gpu.unit"), "Watts").unwrap();
        assert!(specification(&root, &d, true).is_err());
        std::fs::remove_dir_all(root).unwrap();
    }
}
