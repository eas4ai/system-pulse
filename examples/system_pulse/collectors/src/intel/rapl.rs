//! Optional Intel CPU graphics-domain energy, only with unambiguous physical attribution.
use super::{Device, pmu::Spec};
use std::{io, path::Path};
pub(super) fn powercap(root: &Path, integrated: bool) -> io::Result<(String, super::sysfs::Field)> {
    use super::sysfs::{Field, entries, text};
    let unavailable = |message: &str| io::Error::new(io::ErrorKind::Unsupported, message);
    if !integrated {
        return Err(unavailable("No integrated GPU association for RAPL"));
    }
    let mut packages = std::collections::BTreeMap::new();
    for path in entries(&root.join("sys/class/powercap"))? {
        if let Ok(name) = text(&path.join("name"))
            && name
                .strip_prefix("package-")
                .is_some_and(|id| id.parse::<u32>().is_ok())
        {
            packages.insert(path.canonicalize()?, name);
        }
    }
    if packages.len() != 1 {
        return Err(unavailable(
            "Powercap GPU attribution requires one package; multi-die/unknown zones are ambiguous",
        ));
    }
    let (package, name) = packages.into_iter().next().unwrap();
    let domains: Vec<_> = entries(&package)?
        .into_iter()
        .filter(|path| text(&path.join("name")).is_ok_and(|name| name == "uncore"))
        .collect();
    if domains.len() != 1 {
        return Err(unavailable("No unique Intel RAPL PP1 uncore domain"));
    }
    Ok((
        format!("rapl-{name}-uncore-power"),
        Field::energy(
            domains[0].join("energy_uj"),
            format!("RAPL {name} graphics-domain power"),
            format!(
                "CPU {name} PP1 graphics domain associated with the unique integrated i915 GPU; not CPU package energy or whole graphics-card power"
            ),
        ),
    ))
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
