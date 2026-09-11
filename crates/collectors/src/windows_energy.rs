//! Bounded Windows Energy Meter Interface observations and independent power domains.
use crate::{
    counters::{measured, missing, raw_window},
    host::sensor,
    types::*,
};
use std::{
    collections::{BTreeMap, BTreeSet},
    time::Instant,
};

#[cfg(target_os = "windows")]
mod native;
const MAX_DEVICES: usize = 128;
const MAX_CHANNELS: usize = 64;
const MAX_METADATA: usize = 65536;
type Result<T> = std::result::Result<T, String>;

#[derive(Clone, Debug, PartialEq, Eq)]
struct Metadata {
    version: u16,
    oem: String,
    model: String,
    revision: u16,
    channels: Vec<String>,
}

fn word(bytes: &[u8], at: usize) -> Result<u16> {
    let b = bytes.get(at..at + 2).ok_or("Truncated EMI metadata")?;
    Ok(u16::from_le_bytes([b[0], b[1]]))
}
fn text(bytes: &[u8]) -> Result<String> {
    if bytes.is_empty() || !bytes.len().is_multiple_of(2) {
        return Err("Invalid EMI UTF-16 length".into());
    }
    let words: Vec<_> = bytes
        .chunks_exact(2)
        .map(|b| u16::from_le_bytes([b[0], b[1]]))
        .collect();
    let end = words
        .iter()
        .position(|&v| v == 0)
        .ok_or("Unterminated EMI UTF-16")?;
    if end == 0 || words[end..].iter().any(|&v| v != 0) {
        return Err("Empty or ambiguously terminated EMI name".into());
    }
    String::from_utf16(&words[..end]).map_err(|e| format!("Invalid EMI UTF-16: {e}"))
}
fn unit(bytes: &[u8], at: usize) -> Result<()> {
    if bytes.get(at..at + 4) != Some(&[0, 0, 0, 0]) {
        return Err("EMI measurement unit is not picowatt-hours".into());
    }
    Ok(())
}
fn parse_metadata(version: u16, bytes: &[u8]) -> Result<Metadata> {
    if bytes.len() > MAX_METADATA {
        return Err("EMI metadata exceeds 64 KiB".into());
    }
    let (base, count, mut offset) = match version {
        1 => {
            unit(bytes, 0)?;
            (4, 1, 72)
        }
        2 => (0, usize::from(word(bytes, 66)?), 68),
        _ => return Err(format!("Unsupported EMI version {version}")),
    };
    if count == 0 || count > MAX_CHANNELS {
        return Err("EMI channel count outside 1..64".into());
    }
    let oem = text(bytes.get(base..base + 32).ok_or("Truncated EMI OEM")?)?;
    let model = text(
        bytes
            .get(base + 32..base + 64)
            .ok_or("Truncated EMI model")?,
    )?;
    let revision = word(bytes, base + 64)?;
    let mut channels = Vec::new();
    let mut identities = BTreeSet::new();
    for _ in 0..count {
        let size = if version == 1 {
            usize::from(word(bytes, 70)?)
        } else {
            unit(bytes, offset)?;
            let size = usize::from(word(bytes, offset + 4)?);
            offset += 6;
            size
        };
        let channel = text(
            bytes
                .get(offset..offset + size)
                .ok_or("Truncated EMI channel name")?,
        )?;
        if !identities.insert(channel.to_ascii_uppercase()) {
            return Err("Duplicate ambiguous EMI channel identity".into());
        }
        channels.push(channel);
        offset += size;
    }
    if offset != bytes.len() {
        return Err("Unexpected trailing EMI metadata".into());
    }
    Ok(Metadata {
        version,
        oem,
        model,
        revision,
        channels,
    })
}

#[derive(Clone, Debug)]
struct Device {
    instance: String,
    path: String,
}
impl Device {
    fn id(&self) -> String {
        format!(
            "{}:{}",
            self.instance.len(),
            self.instance.to_ascii_uppercase()
        )
    }
}
#[derive(Clone, Copy, Debug)]
struct Value {
    energy: u64,
    time: u64,
}
struct Sample {
    metadata: Metadata,
    values: Vec<Value>,
    started: u64,
    ended: u64,
}
fn parse_values(bytes: &[u8], count: usize) -> Result<Vec<Value>> {
    if count == 0 || count > MAX_CHANNELS || bytes.len() != count * 16 {
        return Err("Invalid EMI measurement reply length".into());
    }
    Ok(bytes
        .chunks_exact(16)
        .map(|b| Value {
            energy: u64::from_le_bytes(b[..8].try_into().expect("eight bytes")),
            time: u64::from_le_bytes(b[8..].try_into().expect("eight bytes")),
        })
        .collect())
}
trait Backend: Send {
    fn inventory(&mut self) -> Result<Vec<Device>>;
    fn sample(&mut self, device: &Device, origin: Instant) -> Result<Sample>;
}
#[derive(Default)]
struct State {
    metadata: Option<Metadata>,
    baselines: BTreeMap<String, (Value, u64, RawObservation)>,
}
pub(crate) struct WindowsEnergyCollector {
    backend: Box<dyn Backend>,
    devices: Vec<Device>,
    states: BTreeMap<String, State>,
}
impl WindowsEnergyCollector {
    #[cfg(target_os = "windows")]
    pub(crate) fn new() -> Self {
        Self {
            backend: Box::new(native::Native),
            devices: Vec::new(),
            states: BTreeMap::new(),
        }
    }
    pub(crate) fn collect(&mut self, snapshot: &mut Snapshot, origin: Instant) {
        let error = match self.backend.inventory().and_then(validate_inventory) {
            Ok(devices) => {
                let ids: BTreeSet<_> = devices.iter().map(Device::id).collect();
                self.states.retain(|id, _| ids.contains(id));
                self.devices = devices;
                snapshot.diagnostics.push(BackendDiagnostic {
                    backend: "windows-energy".into(),
                    availability: Availability::Available,
                    reason: format!(
                        "SetupAPI discovered {} present EMI devices",
                        self.devices.len()
                    ),
                });
                None
            }
            Err(error) => {
                snapshot.diagnostics.push(BackendDiagnostic {
                    backend: "windows-energy".into(),
                    availability: Availability::Failed,
                    reason: error.clone(),
                });
                Some(error)
            }
        };
        for device in &self.devices {
            let state = self.states.entry(device.id()).or_default();
            let sample = match &error {
                Some(error) => Err(error.clone()),
                None => self.backend.sample(device, origin),
            };
            publish(snapshot, device, state, sample);
        }
    }
}
fn validate_inventory(devices: Vec<Device>) -> Result<Vec<Device>> {
    if devices.len() > MAX_DEVICES {
        return Err("EMI device count exceeds 128".into());
    }
    let mut ids = BTreeSet::new();
    let mut paths = BTreeSet::new();
    for device in &devices {
        if device.instance.trim().is_empty()
            || device.path.trim().is_empty()
            || device.instance.contains('\0')
            || device.path.contains('\0')
            || !ids.insert(device.id())
            || !paths.insert(device.path.to_ascii_uppercase())
        {
            return Err("Invalid or ambiguous EMI device identity".into());
        }
    }
    Ok(devices)
}
fn domain(channel: &str) -> Option<&'static str> {
    let (package, domain) = channel.strip_prefix("RAPL_Package")?.split_once('_')?;
    if package.is_empty() || !package.bytes().all(|v| v.is_ascii_digit()) {
        return None;
    }
    match domain {
        "PKG" => Some("CPU package energy domain"),
        "DRAM" => Some("DRAM energy domain"),
        "PP0" => Some("CPU cores energy domain"),
        "PP1" => Some("Integrated GPU energy domain under CPU package"),
        _ => None,
    }
}
fn publish(snapshot: &mut Snapshot, device: &Device, state: &mut State, result: Result<Sample>) {
    let result = result.and_then(|sample| {
        if sample.values.len() != sample.metadata.channels.len() || sample.started > sample.ended {
            return Err("Invalid EMI sample count or query time window".into());
        }
        Ok(sample)
    });
    match &result {
        Ok(sample) => {
            if state.metadata.as_ref() != Some(&sample.metadata) {
                state.baselines.clear();
            }
            state.metadata = Some(sample.metadata.clone());
        }
        Err(_) => state.baselines.clear(),
    }
    let Some(metadata) = &state.metadata else {
        if let Err(reason) = result {
            snapshot.diagnostics.push(BackendDiagnostic {
                backend: "windows-energy".into(),
                availability: Availability::Failed,
                reason,
            });
        }
        return;
    };
    for (index, channel) in metadata.channels.iter().enumerate() {
        let Some(scope) = domain(channel) else {
            snapshot.diagnostics.push(BackendDiagnostic {
                backend: "windows-energy".into(),
                availability: Availability::Unavailable,
                reason: format!(
                    "Unsupported EMI channel scope: {} / {channel}",
                    device.instance
                ),
            });
            continue;
        };
        let suffix = format!("emi:{}:{}:{channel}/power", device.id(), channel.len());
        let id = format!("cpu:host/{suffix}");
        let reading = match &result {
            Err(error) => missing(&id, Availability::Failed, error.clone()),
            Ok(sample) => {
                let value = sample.values[index];
                let observation = raw_window(
                    "Windows EMI picowatt-hours and 100ns absolute time",
                    sample.started,
                    sample.ended,
                    [
                        ("absolute_energy_picowatt_hours", value.energy),
                        ("absolute_time_100ns", value.time),
                    ],
                );
                let previous = state.baselines.remove(channel);
                let mut reading = if let Some((before, ended, before_observation)) = previous {
                    if sample.started <= ended
                        || value.time <= before.time
                        || value.energy < before.energy
                    {
                        missing(
                            &id,
                            Availability::Failed,
                            "EMI counter rollback or nonadvancing time; baseline reset".into(),
                        )
                    } else {
                        state
                            .baselines
                            .insert(channel.clone(), (value, sample.ended, observation.clone()));
                        let watts = (value.energy - before.energy) as f64 * 0.036
                            / (value.time - before.time) as f64;
                        let mut reading = measured(&id, watts, None);
                        reading.observations.push(before_observation);
                        reading
                    }
                } else if value.energy == 0 {
                    missing(
                        &id,
                        Availability::Unavailable,
                        "EMI counter has not established nonzero energy support".into(),
                    )
                } else if value.time == 0 {
                    missing(
                        &id,
                        Availability::Failed,
                        "EMI absolute time is zero; baseline reset".into(),
                    )
                } else {
                    state
                        .baselines
                        .insert(channel.clone(), (value, sample.ended, observation.clone()));
                    missing(
                        &id,
                        Availability::WarmingUp,
                        "First valid EMI observation; waiting for energy delta".into(),
                    )
                };
                reading.observations.push(observation);
                reading
            }
        };
        sensor(
            snapshot,
            "cpu:host",
            &suffix,
            &format!("{channel} power"),
            SensorKind::Power,
            Unit::Watts,
            "Windows Energy Meter Interface",
            &format!(
                "{scope}; {} {} / {}; independent overlapping domain, never summed",
                metadata.oem, metadata.model, device.instance
            ),
            reading,
        );
    }
}
#[cfg(test)]
mod tests;
