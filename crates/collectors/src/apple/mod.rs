//! Native Apple GPU collection with platform-independent validation.
#[cfg(test)]
mod tests;
type Outcome<T> = Result<T, String>;
fn residency(states: &[(String, u64)], table: &[u64]) -> (Outcome<f64>, Outcome<f64>) {
    let calculate = || -> Outcome<(f64, Outcome<f64>)> {
        let mut total = 0u64;
        let mut active = 0u64;
        let mut weighted = 0u64;
        let mut frequency_error = None;
        for (index, (name, ticks)) in states.iter().enumerate() {
            if name
                != &if index == 0 {
                    "OFF".into()
                } else {
                    format!("P{index}")
                }
            {
                return Err("Unknown performance-state layout".into());
            }
            total = total.checked_add(*ticks).ok_or("Residency sum overflow")?;
            if index > 0 {
                active = active
                    .checked_add(*ticks)
                    .ok_or("Active residency overflow")?;
                if *ticks > 0 {
                    match table.get(index).filter(|hz| **hz > 0) {
                        Some(hz) => {
                            match ticks.checked_mul(*hz).and_then(|v| weighted.checked_add(v)) {
                                Some(v) => weighted = v,
                                None => frequency_error = Some("Weighted frequency overflow"),
                            }
                        }
                        None => {
                            frequency_error =
                                Some("Active state has no evidenced frequency mapping")
                        }
                    }
                }
            }
        }
        if total == 0 {
            return Err("No elapsed residency".into());
        }
        let frequency = if active == 0 {
            Err("No active residency".into())
        } else if let Some(e) = frequency_error {
            Err(e.into())
        } else {
            Ok(weighted as f64 / active as f64)
        };
        Ok((100.0 * active as f64 / total as f64, frequency))
    };
    match calculate() {
        Ok((usage, frequency)) => (Ok(usage), frequency),
        Err(e) => (Err(e.clone()), Err(e)),
    }
}
fn power(energy_nj: u64, elapsed_ns: u64) -> Outcome<f64> {
    if elapsed_ns == 0 {
        return Err("Nonpositive elapsed time".into());
    }
    Ok(energy_nj as f64 / elapsed_ns as f64)
}

fn decode_table(bytes: &[u8]) -> Outcome<Vec<u64>> {
    if bytes.is_empty() || bytes.len() > 128 * 8 || !bytes.len().is_multiple_of(8) {
        return Err("Invalid voltage-states9 byte layout".into());
    }
    let values: Vec<_> = bytes
        .as_chunks::<8>()
        .0
        .iter()
        .map(|pair| u32::from_le_bytes([pair[0], pair[1], pair[2], pair[3]]) as u64)
        .collect();
    if values[0] != 0 || values.windows(2).any(|v| v[0] >= v[1]) {
        return Err("Unknown voltage-states9 frequency ordering".into());
    }
    Ok(values)
}
fn identity(path: &str, runtime: u64, unified: bool) -> Outcome<String> {
    if !path.starts_with("IODeviceTree:/")
        || !path.contains("/sgx@")
        || path.len() > 4096
        || runtime == 0
        || !unified
    {
        return Err("No supported physical Apple GPU identity/memory-model facts".into());
    }
    Ok(format!("gpu:apple:{path}"))
}

use crate::{
    counters::{measured, missing, raw_window},
    types::*,
};
const ENERGY_UNIT: u64 = 216173288919924736;
const RESIDENCY_UNIT: u64 = 72058115876454424;
#[derive(Default)]
struct Baseline {
    previous: Option<RawObservation>,
}
fn integer(o: &RawObservation, key: &str) -> Outcome<u64> {
    o.integers
        .get(key)
        .copied()
        .ok_or_else(|| format!("Missing {key}"))
}
fn validate(o: &RawObservation, driver: u64, states: bool) -> Outcome<()> {
    if o.read_started_ns.is_none_or(|start| start > o.captured_ns) {
        return Err("Invalid source query window".into());
    }
    if integer(o, "driver_id")? != driver
        || integer(o, "channel_id")? == 0
        || integer(o, "format")? != if states { 2 } else { 1 }
        || integer(o, "encoded_unit")? != if states { RESIDENCY_UNIT } else { ENERGY_UNIT }
    {
        return Err("IOReport device, format or source-unit mismatch".into());
    }
    if states {
        let count = integer(o, "state_count")?;
        if !(1..=128).contains(&count) {
            return Err("Invalid performance state count".into());
        }
        if o.integers
            .keys()
            .filter(|k| k.starts_with("ticks/"))
            .count()
            != count as usize
        {
            return Err("Invalid performance state layout".into());
        }
        for i in 0..count {
            integer(o, &format!("ticks/{}", state_name(i)))?;
        }
    } else {
        integer(o, "energy_nj")?;
    }
    Ok(())
}
fn state_name(index: u64) -> String {
    if index == 0 {
        "OFF".into()
    } else {
        format!("P{index}")
    }
}
impl Baseline {
    fn read(
        &mut self,
        id: &str,
        current: SourceResult<RawObservation>,
        driver: u64,
        states: bool,
    ) -> (Reading, Option<Reading>) {
        let fail =
            |availability: Availability, reason: String, observations: Vec<RawObservation>| {
                let mut r = missing(id, availability, reason);
                r.observations = observations;
                let frequency = states.then(|| {
                    let mut f = r.clone();
                    f.sensor_id = id.replace("/usage", "/frequency");
                    f
                });
                (r, frequency)
            };
        let previous = self.previous.take();
        let current = match current {
            Ok(o) => o,
            Err(e) => return fail(e.availability, e.reason, vec![]),
        };
        if let Err(e) = validate(&current, driver, states) {
            return fail(Availability::Failed, e, vec![current]);
        }
        let Some(previous) = previous else {
            self.previous = Some(current.clone());
            return fail(
                Availability::WarmingUp,
                "Waiting for second native observation".into(),
                vec![current],
            );
        };
        let delta = || -> Outcome<(f64, Option<Outcome<f64>>)> {
            for key in ["driver_id", "channel_id", "format", "encoded_unit"] {
                if integer(&previous, key)? != integer(&current, key)? {
                    return Err(format!("Changed {key}; baseline reset"));
                }
            }
            let elapsed = current
                .captured_ns
                .checked_sub(previous.captured_ns)
                .filter(|v| *v > 0)
                .ok_or("Nonpositive elapsed time")?;
            if !states {
                let delta = integer(&current, "energy_nj")?
                    .checked_sub(integer(&previous, "energy_nj")?)
                    .ok_or("Energy counter regressed")?;
                return Ok((power(delta, elapsed)?, None));
            }
            let count = integer(&current, "state_count")?;
            if count != integer(&previous, "state_count")? {
                return Err("Changed state layout".into());
            }
            let mut deltas = Vec::new();
            let mut table = Vec::new();
            let mut table_changed = false;
            for i in 0..count {
                let name = state_name(i);
                let key = format!("ticks/{name}");
                deltas.push((
                    name.clone(),
                    integer(&current, &key)?
                        .checked_sub(integer(&previous, &key)?)
                        .ok_or("Residency counter regressed")?,
                ));
                let key = format!("hz/{name}");
                let frequency = current.integers.get(&key).copied();
                table_changed |= frequency != previous.integers.get(&key).copied();
                table.push(frequency.unwrap_or(0));
            }
            let (usage, frequency) = residency(&deltas, &table);
            Ok((
                usage?,
                Some(if table_changed {
                    Err("Frequency table changed".into())
                } else {
                    frequency
                }),
            ))
        };
        match delta() {
            Ok((value, frequency)) => {
                self.previous = Some(current.clone());
                let mut r = measured(id, value, None);
                r.observations = vec![previous, current];
                let frequency = frequency.map(|value| {
                    let id = id.replace("/usage", "/frequency");
                    let mut f = match value {
                        Ok(v) => measured(&id, v, None),
                        Err(e) => missing(&id, Availability::Unavailable, e),
                    };
                    f.observations = r.observations.clone();
                    f
                });
                (r, frequency)
            }
            Err(e) => fail(Availability::WarmingUp, e, vec![previous, current]),
        }
    }
}

struct DeviceInput {
    path: String,
    name: String,
    runtime: u64,
    unified: bool,
    states: SourceResult<RawObservation>,
    energy: SourceResult<RawObservation>,
    allocated: SourceResult<RawObservation>,
    in_use: SourceResult<RawObservation>,
    temperatures: Vec<(String, String, SourceResult<RawObservation>)>,
}
#[derive(Default)]
struct Collector {
    baselines: std::collections::BTreeMap<String, (u64, Baseline, Baseline)>,
}
impl Collector {
    fn append(&mut self, snapshot: &mut Snapshot, devices: Outcome<Vec<DeviceInput>>) {
        use crate::host::{diagnostic, monitor, sensor};
        let devices = match devices {
            Ok(v) => v,
            Err(e) => {
                self.baselines.clear();
                diagnostic(snapshot, "Apple Metal/IOKit", e);
                return;
            }
        };
        let mut counts = std::collections::BTreeMap::new();
        for d in &devices {
            *counts.entry(d.path.clone()).or_insert(0usize) += 1;
        }
        let mut devices = devices;
        devices.sort_by(|a, b| a.path.cmp(&b.path));
        let mut live = std::collections::BTreeSet::new();
        for d in devices {
            let id = match identity(&d.path, d.runtime, d.unified) {
                Ok(id) if counts[&d.path] == 1 => id,
                Ok(_) => {
                    diagnostic(
                        snapshot,
                        "Apple Metal/IOKit",
                        format!("Ambiguous physical GPU identity {}", d.path),
                    );
                    continue;
                }
                Err(e) => {
                    diagnostic(snapshot, "Apple Metal/IOKit", e);
                    continue;
                }
            };
            live.insert(id.clone());
            let state = self
                .baselines
                .entry(id.clone())
                .or_insert_with(|| (d.runtime, Baseline::default(), Baseline::default()));
            if state.0 != d.runtime {
                *state = (d.runtime, Baseline::default(), Baseline::default());
            }
            monitor(snapshot, &id, &d.name, MonitorKind::Gpu);
            let scope = format!(
                "{}; Metal registry ID {}; hasUnifiedMemory=true; physical GPU",
                d.path, d.runtime
            );
            let (usage, frequency) =
                state
                    .1
                    .read(&format!("{id}/usage"), d.states, d.runtime, true);
            sensor(
                snapshot,
                &id,
                "usage",
                "GPU activity",
                SensorKind::Percentage,
                Unit::Percent,
                "IOReport/GPU Stats/GPU Performance States/GPUPH;24Mticks",
                &scope,
                usage,
            );
            if let Some(frequency) = frequency {
                sensor(
                    snapshot,
                    &id,
                    "frequency",
                    "Active weighted GPU frequency",
                    SensorKind::Frequency,
                    Unit::Hertz,
                    "IOReport/GPUPH + IOKit/pmgr/voltage-states9;Hz",
                    &scope,
                    frequency,
                );
            }
            let power = state
                .2
                .read(&format!("{id}/power"), d.energy, d.runtime, false)
                .0;
            sensor(
                snapshot,
                &id,
                "power",
                "GPU power",
                SensorKind::Power,
                Unit::Watts,
                "IOReport/Energy Model/GPU Energy;nJ",
                &scope,
                power,
            );
            for (suffix, title, key, observation) in [
                (
                    "shared-allocated",
                    "GPU shared allocation",
                    "Alloc system memory",
                    d.allocated,
                ),
                (
                    "shared-in-use",
                    "GPU shared memory in use",
                    "In use system memory",
                    d.in_use,
                ),
            ] {
                let reading = scalar(
                    &format!("{id}/{suffix}"),
                    observation,
                    Some(d.runtime),
                    false,
                );
                sensor(
                    snapshot,
                    &id,
                    suffix,
                    title,
                    SensorKind::Scalar,
                    Unit::Bytes,
                    &format!("IOKit/PerformanceStatistics/{key};bytes"),
                    &format!("{scope}; GPU shared memory; no capacity total"),
                    reading,
                );
            }
            for (suffix, source, observation) in d.temperatures {
                let suffix = format!("temperature-{suffix}");
                let reading = if suffix.starts_with("temperature-smc-") {
                    smc_temperature(&format!("{id}/{suffix}"), observation)
                } else {
                    scalar(&format!("{id}/{suffix}"), observation, None, true)
                };
                sensor(
                    snapshot,
                    &id,
                    &suffix,
                    "GPU temperature",
                    SensorKind::Temperature,
                    Unit::Celsius,
                    &source,
                    &scope,
                    reading,
                );
            }
            sensor(
                snapshot,
                &id,
                "fan",
                "GPU fan",
                SensorKind::Fan,
                Unit::Rpm,
                "SMC/system fans",
                &scope,
                missing(
                    &format!("{id}/fan"),
                    Availability::Unavailable,
                    "SMC system fans have no established GPU attribution".into(),
                ),
            );
        }
        self.baselines.retain(|key, _| live.contains(key));
    }
}
fn scalar(
    id: &str,
    observation: SourceResult<RawObservation>,
    driver: Option<u64>,
    temperature: bool,
) -> Reading {
    let observation = match observation {
        Ok(v) => v,
        Err(e) => return missing(id, e.availability, e.reason),
    };
    let result = || -> Outcome<f64> {
        if observation
            .read_started_ns
            .is_none_or(|start| start > observation.captured_ns)
        {
            return Err("Invalid source query window".into());
        }
        if let Some(driver) = driver
            && integer(&observation, "driver_id")? != driver
        {
            return Err("Accelerator memory device mismatch".into());
        }
        if !temperature {
            let counter = if id.ends_with("/shared-allocated") {
                "Alloc system memory"
            } else {
                "In use system memory"
            };
            if !observation.source.starts_with("IOKit/")
                || !observation
                    .source
                    .ends_with(&format!("/PerformanceStatistics/{counter};bytes"))
                || integer(&observation, "has_unified_memory")? != 1
            {
                return Err("Accelerator memory source, unit or memory-model mismatch".into());
            }
        }
        let value = if temperature {
            *observation
                .decimals
                .get("celsius")
                .ok_or("Missing temperature")?
        } else {
            integer(&observation, "bytes")? as f64
        };
        if !value.is_finite() || (!temperature && value < 0.0) {
            return Err("Invalid physical scalar".into());
        }
        Ok(value)
    };
    let mut r = match result() {
        Ok(v) => measured(id, v, None),
        Err(e) => missing(id, Availability::Failed, e),
    };
    r.observations.push(observation);
    r
}

#[derive(Clone, Debug)]
struct SourceFailure {
    availability: Availability,
    reason: String,
}
type SourceResult<T> = Result<T, SourceFailure>;
impl From<String> for SourceFailure {
    fn from(reason: String) -> Self {
        Self {
            availability: Availability::Failed,
            reason,
        }
    }
}
impl From<&str> for SourceFailure {
    fn from(reason: &str) -> Self {
        reason.to_owned().into()
    }
}
impl SourceFailure {
    fn unavailable(reason: impl Into<String>) -> Self {
        Self {
            availability: Availability::Unavailable,
            reason: reason.into(),
        }
    }
}
fn smc_temperature(id: &str, observation: SourceResult<RawObservation>) -> Reading {
    let mut r = scalar(id, observation, None, true);
    if r.value.is_some_and(|v| v < 15.0) {
        r.value = None;
        r.availability = Availability::Unavailable;
        r.reason=Some("Conservative SMC software plausibility guard: below 15 Celsius; not a hardware validity signal".into());
    }
    r
}
fn decode_smc(
    kind: u32,
    bytes: &[u8],
    code: i32,
    size: usize,
    result: u8,
    status: u8,
) -> Outcome<f64> {
    if code != 0 || size != 80 || result != 0 || status != 0 {
        return Err(format!(
            "SMC native read failed: return={code}, size={size}, result={result}, status={status}"
        ));
    }
    if kind != u32::from_be_bytes(*b"flt ") || bytes.len() != 4 {
        return Err(
            "Unsupported SMC temperature type/size (expected flt little-endian Celsius)".into(),
        );
    }
    let value = f32::from_le_bytes([bytes[0], bytes[1], bytes[2], bytes[3]]) as f64;
    if !value.is_finite() {
        return Err("Non-finite SMC temperature".into());
    }
    Ok(value)
}
fn bounded_count(count: isize, limit: usize) -> Outcome<usize> {
    usize::try_from(count)
        .ok()
        .filter(|n| *n <= limit)
        .ok_or_else(|| format!("Native count {count} exceeds 0..={limit}"))
}

fn attributed_hid(name: &str) -> bool {
    name.strip_prefix("GPU MTR Temp Sensor")
        .is_some_and(|suffix| suffix.bytes().all(|b| b.is_ascii_digit()))
}

#[cfg(all(target_os = "macos", target_arch = "aarch64"))]
mod native;
#[cfg(all(target_os = "macos", target_arch = "aarch64"))]
pub(crate) use native::AppleCollector;

fn smc_keys(name: &str) -> &'static [&'static str] {
    // Exact profiles from pinned Stats source; see NOTICE.md. Names select only
    // the source profile, never device identity. No guessed key prefixes.
    match name {
        "Apple M1" | "Apple M1 Pro" | "Apple M1 Max" | "Apple M1 Ultra" => {
            &["Tg05", "Tg0D", "Tg0L", "Tg0T"]
        }
        "Apple M2" | "Apple M2 Pro" | "Apple M2 Max" | "Apple M2 Ultra" => &["Tg0f", "Tg0j"],
        "Apple M3" | "Apple M3 Pro" | "Apple M3 Max" | "Apple M3 Ultra" => &[
            "Tf14", "Tf18", "Tf19", "Tf1A", "Tf24", "Tf28", "Tf29", "Tf2A",
        ],
        "Apple M4" => &[
            "Tg0G", "Tg0H", "Tg0K", "Tg0L", "Tg0d", "Tg0e", "Tg0j", "Tg0k",
        ],
        "Apple M4 Pro" | "Apple M4 Max" | "Apple M4 Ultra" => &[
            "Tg1U", "Tg1k", "Tg0K", "Tg0L", "Tg0d", "Tg0e", "Tg0j", "Tg0k",
        ],
        "Apple M5" | "Apple M5 Pro" | "Apple M5 Max" | "Apple M5 Ultra" => &[
            "Tg0U", "Tg0X", "Tg0d", "Tg0g", "Tg0j", "Tg1Y", "Tg1c", "Tg1g",
        ],
        _ => &[],
    }
}
