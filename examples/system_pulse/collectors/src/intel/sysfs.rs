//! Read only sysfs measurements. Names identify channels, never hwmon/card ordinals.
use super::{Clock, Device, numbered};
use crate::{
    counters::*,
    host::{diagnostic, sensor},
    types::*,
};
use std::{
    collections::BTreeMap,
    fs,
    io::{self, Read},
    path::{Path, PathBuf},
};

pub(super) fn text(path: &Path) -> io::Result<String> {
    let mut s = String::new();
    fs::File::open(path)?.take(4097).read_to_string(&mut s)?;
    if s.len() > 4096 {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "sysfs value exceeds 4096 bytes",
        ));
    }
    Ok(s.trim().into())
}
pub(super) fn entries(path: &Path) -> io::Result<Vec<PathBuf>> {
    let mut result = Vec::new();
    for entry in fs::read_dir(path)? {
        if result.len() == 512 {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "sysfs directory exceeds 512 entries",
            ));
        }
        result.push(entry?.path());
    }
    result.sort();
    Ok(result)
}
#[derive(Clone)]
pub(super) struct Field {
    path: PathBuf,
    card: Option<PathBuf>,
    title: String,
    scope: String,
    kind: SensorKind,
    unit: Unit,
    source_unit: &'static str,
    numerator: u64,
    denominator: u64,
    signed: bool,
    energy: bool,
}
impl Field {
    pub(super) fn energy(path: PathBuf, title: String, scope: String) -> Self {
        Self {
            path,
            card: None,
            title,
            scope,
            kind: SensorKind::Power,
            unit: Unit::Watts,
            source_unit: "microjoules",
            numerator: 1,
            denominator: 1_000_000,
            signed: false,
            energy: true,
        }
    }
}
fn frequency(
    fields: &mut BTreeMap<String, Field>,
    prefix: &str,
    path: &Path,
    actual: &str,
    requested: &str,
    card: Option<&Path>,
) {
    for (semantics, name) in [("actual", actual), ("requested", requested)] {
        fields.insert(
            format!("{prefix}-frequency-{semantics}"),
            Field {
                path: path.join(name),
                card: card.map(Path::to_path_buf),
                title: format!("{prefix} {semantics} frequency"),
                scope: format!("GT {prefix}; {semantics} clock"),
                kind: SensorKind::Frequency,
                unit: Unit::Hertz,
                source_unit: "MHz",
                numerator: 1_000_000,
                denominator: 1,
                signed: false,
                energy: false,
            },
        );
    }
}
fn scan(path: &Path, diagnostics: &mut Vec<BackendDiagnostic>) -> Vec<PathBuf> {
    match entries(path) {
        Ok(paths) => paths,
        Err(e) => {
            diagnostics.push(BackendDiagnostic {
                backend: "intel sysfs".into(),
                availability: super::drm::error_availability(&e),
                reason: format!("{}: {e}", path.display()),
            });
            vec![]
        }
    }
}
fn find_fields(
    device: &Device,
    diagnostics: &mut Vec<BackendDiagnostic>,
) -> BTreeMap<String, Field> {
    let mut fields = BTreeMap::new();
    if device.driver == "i915" {
        for card in &device.cards {
            if !card
                .file_name()
                .is_some_and(|n| numbered(&n.to_string_lossy(), "card"))
            {
                continue;
            }
            for gt in scan(&card.join("gt"), diagnostics) {
                let name = gt.file_name().unwrap().to_string_lossy();
                if numbered(&name, "gt") {
                    frequency(
                        &mut fields,
                        &name,
                        &gt,
                        "rps_act_freq_mhz",
                        "rps_cur_freq_mhz",
                        Some(card),
                    );
                }
            }
        }
        if fields.is_empty()
            && let Some(card) = device.cards.iter().find(|p| {
                p.file_name()
                    .is_some_and(|n| numbered(&n.to_string_lossy(), "card"))
            })
        {
            frequency(
                &mut fields,
                "gt0",
                card,
                "gt_act_freq_mhz",
                "gt_cur_freq_mhz",
                Some(card),
            );
        }
    } else {
        for tile in scan(&device.path, diagnostics) {
            let tile_name = tile.file_name().unwrap().to_string_lossy();
            if !numbered(&tile_name, "tile") {
                continue;
            }
            for gt in scan(&tile, diagnostics) {
                let gt_name = gt.file_name().unwrap().to_string_lossy();
                if numbered(&gt_name, "gt") {
                    frequency(
                        &mut fields,
                        &format!("{tile_name}-{gt_name}"),
                        &gt.join("freq0"),
                        "act_freq",
                        "cur_freq",
                        None,
                    );
                }
            }
        }
    }
    // Parent membership attributes the provider. CPU coretemp/powercap are deliberately absent.
    let mut providers = BTreeMap::<String, Vec<PathBuf>>::new();
    let mut identities_complete = true;
    for hw in scan(&device.path.join("hwmon"), diagnostics) {
        match text(&hw.join("name")) {
            Ok(name)
                if name == device.driver || numbered(&name, &format!("{}_gt", device.driver)) =>
            {
                providers.entry(name).or_default().push(hw);
            }
            Ok(_) => {}
            Err(e) => {
                identities_complete = false;
                diagnostics.push(BackendDiagnostic {
                    backend: "intel sysfs".into(),
                    availability: super::drm::error_availability(&e),
                    reason: format!("{}: {e}", hw.join("name").display()),
                });
            }
        }
    }
    // An unreadable peer might have the same provider name. The remaining
    // readable provider cannot establish uniqueness from an incomplete scan.
    if !identities_complete {
        return fields;
    }
    for (name, paths) in providers {
        // Repeated names without a physical subdevice key do not support safe persistence.
        if paths.len() != 1 {
            diagnostics.push(BackendDiagnostic {
                backend: "intel sysfs".into(),
                availability: Availability::Unavailable,
                reason: format!(
                    "Ambiguous hwmon provider {name}: no stable physical subdevice key"
                ),
            });
            continue;
        }
        let hw = &paths[0];
        for path in scan(hw, diagnostics) {
            let file = path.file_name().unwrap().to_string_lossy().into_owned();
            let Some((channel, attr)) = file.split_once('_') else {
                continue;
            };
            let (kind, unit, source_unit, denominator, signed, energy) =
                if numbered(channel, "temp") && attr == "input" {
                    (
                        SensorKind::Temperature,
                        Unit::Celsius,
                        "millidegree Celsius",
                        1000,
                        true,
                        false,
                    )
                } else if numbered(channel, "power") && matches!(attr, "input" | "average") {
                    (
                        SensorKind::Power,
                        Unit::Watts,
                        "microwatts",
                        1_000_000,
                        false,
                        false,
                    )
                } else if numbered(channel, "energy") && attr == "input" {
                    (
                        SensorKind::Power,
                        Unit::Watts,
                        "microjoules",
                        1_000_000,
                        false,
                        true,
                    )
                } else if numbered(channel, "fan") && attr == "input" {
                    (SensorKind::Fan, Unit::Rpm, "RPM", 1, false, false)
                } else {
                    continue;
                };
            let scope = channel_scope(&device.driver, &name, channel);
            let label =
                text(&hw.join(format!("{channel}_label"))).unwrap_or_else(|_| scope.clone());
            fields.insert(
                format!("hwmon-{name}-{file}{}", if energy { "-power" } else { "" }),
                Field {
                    path,
                    card: None,
                    title: format!(
                        "{label} {channel}{}",
                        if energy { " power from energy" } else { "" }
                    ),
                    scope,
                    kind,
                    unit,
                    source_unit,
                    numerator: 1,
                    denominator,
                    signed,
                    energy,
                },
            );
        }
    }
    fields
}
fn channel_scope(driver: &str, provider: &str, channel: &str) -> String {
    if provider != driver {
        return format!("GT provider {provider}");
    }
    match (driver, channel) {
        ("i915", "temp1") | ("xe", "temp2" | "energy2" | "power2") => "Package of this GPU; not GPU die".into(),
        ("xe", "temp3") => "Device VRAM".into(),
        ("xe", "temp4") => "Device memory controller average".into(),
        ("xe", "temp5") => "Device PCIe".into(),
        (_, c) if c.starts_with("fan") => "Device tachometer channel; shared tach lines can read zero independently of fan rotation".into(),
        (_, c) if c.starts_with("energy") || c.starts_with("power") => "Whole graphics card".into(),
        _ => format!("Device hwmon channel {channel}; no die attribution"),
    }
}
pub(super) fn collect(
    s: &mut Snapshot,
    device: &Device,
    id: &str,
    clock: &Clock,
    fields: &mut BTreeMap<String, Field>,
    counters: &mut Counters,
) {
    let mut diagnostics = Vec::new();
    let discovered = find_fields(device, &mut diagnostics);
    // Remember descriptors for unavailable readings, but authorize hwmon access anew
    // each frame: a reused ordinal, failed name, or ambiguous name is not a binding.
    let valid_hwmon = discovered
        .keys()
        .cloned()
        .collect::<std::collections::BTreeSet<_>>();
    let binding_errors = diagnostics
        .iter()
        .map(|d| d.reason.as_str())
        .collect::<Vec<_>>()
        .join("; ");
    let binding_failed = diagnostics
        .iter()
        .any(|d| d.availability == Availability::Failed);
    for (key, field) in discovered {
        if fields.len() >= 512 && !fields.contains_key(&key) {
            diagnostic(s, "intel sysfs", "512-field bound exceeded".into());
            break;
        }
        fields.insert(key, field);
    }
    for (suffix, title, kind, unit, source) in [
        (
            "temperature",
            "GPU temperature",
            SensorKind::Temperature,
            Unit::Celsius,
            "Intel device hwmon temperature",
        ),
        (
            "power",
            "GPU power",
            SensorKind::Power,
            Unit::Watts,
            "Intel device hwmon energy/power; attributable RAPL graphics domain where available",
        ),
        (
            "fan",
            "GPU fan",
            SensorKind::Fan,
            Unit::Rpm,
            "Intel device hwmon tachometer",
        ),
        (
            "frequency-actual",
            "Actual GT frequency",
            SensorKind::Frequency,
            Unit::Hertz,
            "i915/xe GT sysfs actual frequency",
        ),
    ] {
        if !fields.values().any(|f| f.kind == kind) {
            let reason = format!(
                "No attributable {source} channel discovered{}",
                diagnostics
                    .iter()
                    .map(|d| format!("; {}", d.reason))
                    .collect::<String>()
            );
            let status = if diagnostics
                .iter()
                .any(|d| d.availability == Availability::Failed)
            {
                Availability::Failed
            } else {
                Availability::Unavailable
            };
            let r = missing(&format!("{id}/{suffix}"), status, reason);
            sensor(
                s,
                id,
                suffix,
                title,
                kind,
                unit,
                source,
                "Physical GPU; no package/die or system-fan substitution",
                r,
            );
        }
    }
    s.diagnostics.extend(diagnostics);
    for (key, field) in fields {
        let sid = format!("{id}/{key}");
        let source = format!("{} ({})", field.path.display(), field.source_unit);
        let start = clock.now();
        let result = (|| {
            if key.starts_with("hwmon-") && !valid_hwmon.contains(key) {
                return Err(io::Error::new(
                    if binding_failed { io::ErrorKind::InvalidData } else { io::ErrorKind::NotFound },
                    format!("Hwmon provider/channel identity is no longer uniquely verified: {binding_errors}"),
                ));
            }
            if let Some(card) = &field.card
                && card.join("device").canonicalize()? != device.path
            {
                return Err(io::Error::new(
                    io::ErrorKind::NotFound,
                    "DRM alias no longer belongs to this physical GPU",
                ));
            }
            text(&field.path)
        })()
        .and_then(|v| {
            let mut o = raw_window(
                &source,
                start,
                clock.now(),
                [
                    ("numerator", field.numerator),
                    ("denominator", field.denominator),
                ],
            );
            if field.signed {
                let v = v
                    .parse::<i64>()
                    .map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e))?;
                o.integers.insert("magnitude".into(), v.unsigned_abs());
                o.integers.insert("negative".into(), u64::from(v < 0));
            } else {
                let v = v
                    .parse::<u64>()
                    .map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e))?;
                v.checked_mul(field.numerator).ok_or_else(|| {
                    io::Error::new(io::ErrorKind::InvalidData, "unit conversion overflow")
                })?;
                o.integers.insert("value".into(), v);
            }
            Ok(o)
        });
        let error = result
            .as_ref()
            .err()
            .map(|e| (e.kind(), format!("{source}: {e}")));
        let mut r = if field.energy {
            counters.derive(
                &sid,
                result.map_err(|e| format!("{source}: {e}")),
                |a, b, elapsed| Ok(delta(a, b, "value")? as f64 / 1e6 / elapsed),
            )
        } else {
            match result {
                Ok(o) => {
                    let value = if field.signed {
                        o.integers["magnitude"] as f64
                            * if o.integers["negative"] == 1 {
                                -1.0
                            } else {
                                1.0
                            }
                    } else {
                        o.integers["value"] as f64
                    };
                    let mut r = measured(
                        &sid,
                        value * field.numerator as f64 / field.denominator as f64,
                        None,
                    );
                    r.observations.push(o);
                    r
                }
                Err(e) => missing(&sid, Availability::Failed, format!("{source}: {e}")),
            }
        };
        if let Some((kind, reason)) = error {
            r.availability = if matches!(
                kind,
                io::ErrorKind::NotFound | io::ErrorKind::PermissionDenied
            ) {
                Availability::Unavailable
            } else {
                Availability::Failed
            };
            r.reason = Some(reason);
        }
        sensor(
            s,
            id,
            key,
            &field.title,
            field.kind.clone(),
            field.unit.clone(),
            &source,
            &field.scope,
            r,
        );
    }
}
