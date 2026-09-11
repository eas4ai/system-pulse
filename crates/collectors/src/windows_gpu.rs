//! PnP discovery owns adapter identity; optional graphics telemetry cannot hide it.
use crate::{
    counters::{Counters, delta, measured, missing, raw_window},
    host::{diagnostic, monitor, sensor},
    types::*,
};
use std::{collections::BTreeMap, time::Instant};

#[cfg(target_os = "windows")]
mod native;

use crate::nvidia::PciAddress;

#[derive(Clone, Debug, PartialEq, Eq)]
struct Adapter {
    instance_id: String,
    name: String,
    vendor: u32,
    pci: Option<PciAddress>,
    luid: Option<u64>,
}

impl Adapter {
    fn id(&self) -> String {
        format!("windows-gpu:{}", self.instance_id.to_ascii_uppercase())
    }
}

#[derive(Clone, Debug)]
struct Failure {
    availability: Availability,
    reason: String,
}
impl Failure {
    fn failed(reason: impl Into<String>) -> Self {
        Self {
            availability: Availability::Failed,
            reason: reason.into(),
        }
    }
    fn unavailable(reason: impl Into<String>) -> Self {
        Self {
            availability: Availability::Unavailable,
            reason: reason.into(),
        }
    }
    fn reading(&self, id: &str) -> Reading {
        missing(id, self.availability.clone(), self.reason.clone())
    }
}
type Result<T> = std::result::Result<T, Failure>;

struct Node {
    id: u32,
    running_ticks: u64,
    started_ns: u64,
    ended_ns: u64,
}
struct Memory {
    dedicated: u64,
    shared: u64,
    dedicated_limit: u64,
    shared_limit: u64,
    started_ns: u64,
    ended_ns: u64,
}
struct Metrics {
    nodes: Result<Vec<Node>>,
    memory: Result<Memory>,
}
impl Metrics {
    fn failed(error: Failure) -> Self {
        Self {
            nodes: Err(error.clone()),
            memory: Err(error),
        }
    }
}

trait Backend: Send {
    fn inventory(&mut self) -> Result<Vec<Adapter>>;
    fn sample(&mut self, adapter: &Adapter, origin: Instant) -> Metrics;
}

pub(crate) struct WindowsGpuCollector {
    backend: Box<dyn Backend>,
    inventory: Vec<Adapter>,
    inventory_current: bool,
    counters: Counters,
}

impl WindowsGpuCollector {
    #[cfg(target_os = "windows")]
    pub(crate) fn new() -> Self {
        Self {
            backend: Box::new(native::Native),
            inventory: Vec::new(),
            inventory_current: false,
            counters: Counters::default(),
        }
    }

    pub(crate) fn collect(&mut self, snapshot: &mut Snapshot, origin: Instant) {
        let discovery_error = match self.backend.inventory().and_then(validate_inventory) {
            Ok(adapters) => {
                self.inventory = adapters;
                self.inventory_current = true;
                snapshot.diagnostics.push(BackendDiagnostic {
                    backend: "windows-gpu".into(),
                    availability: Availability::Available,
                    reason: format!(
                        "SetupAPI discovered {} present graphics adapters",
                        self.inventory.len()
                    ),
                });
                None
            }
            Err(error) => {
                self.inventory_current = false;
                diagnostic(snapshot, "windows-gpu", error.reason.clone());
                Some(error)
            }
        };
        self.counters.begin();
        for adapter in &self.inventory {
            let id = adapter.id();
            monitor(snapshot, &id, &adapter.name, MonitorKind::Gpu);
            let metrics = match &discovery_error {
                Some(error) => Metrics::failed(error.clone()),
                None => self.backend.sample(adapter, origin),
            };
            publish(snapshot, adapter, metrics, &mut self.counters);
        }
        self.counters.finish();
    }

    /// Only unambiguous, present NVIDIA PCI identities may receive NVML data.
    pub(crate) fn nvidia_identities(&self) -> BTreeMap<PciAddress, String> {
        if !self.inventory_current {
            return BTreeMap::new();
        }
        let mut candidates = BTreeMap::<PciAddress, Vec<String>>::new();
        for adapter in &self.inventory {
            if adapter.vendor == 0x10de
                && let Some(pci) = adapter.pci
            {
                candidates.entry(pci).or_default().push(adapter.id());
            }
        }
        candidates
            .into_iter()
            .filter_map(|(pci, ids)| (ids.len() == 1).then(|| (pci, ids[0].clone())))
            .collect()
    }
}

fn validate_inventory(adapters: Vec<Adapter>) -> Result<Vec<Adapter>> {
    let mut distinct = BTreeMap::new();
    for adapter in adapters {
        if adapter.instance_id.trim().is_empty() || adapter.instance_id.contains('\0') {
            return Err(Failure::failed(
                "Windows GPU inventory returned an invalid PnP instance ID",
            ));
        }
        let id = adapter.id();
        if let Some(previous) = distinct.insert(id, adapter.clone())
            && previous != adapter
        {
            return Err(Failure::failed(
                "Windows GPU inventory returned conflicting PnP identities",
            ));
        }
    }
    Ok(distinct.into_values().collect())
}

fn utilization(
    id: &str,
    luid: Option<u64>,
    nodes: Result<Vec<Node>>,
    counters: &mut Counters,
) -> Reading {
    let nodes = match nodes {
        Ok(nodes) if !nodes.is_empty() => nodes,
        Ok(_) => return Failure::unavailable("Windows exposes no GPU scheduler nodes").reading(id),
        Err(error) => return error.reading(id),
    };
    let Some(luid) = luid else {
        return Failure::unavailable("Windows exposes no current adapter LUID").reading(id);
    };
    let mut readings = Vec::new();
    for node in nodes {
        let key = format!("{id}/{luid:016x}/node-{}", node.id);
        let observation = raw_window(
            "D3DKMTQueryStatistics global node running time (100ns)",
            node.started_ns,
            node.ended_ns,
            [
                ("running_ticks", node.running_ticks),
                ("node_id", u64::from(node.id)),
                ("adapter_luid", luid),
            ],
        );
        readings.push(counters.derive(&key, Ok(observation), |a, b, elapsed| {
            let percent = delta(a, b, "running_ticks")? as f64 * 1e-5 / elapsed;
            if percent > 100.5 {
                return Err("GPU scheduler delta exceeds elapsed time; baseline reset".into());
            }
            Ok(percent.min(100.0))
        }));
    }
    let mut summary = if let Some(failed) = readings
        .iter()
        .find(|r| r.availability != Availability::Available)
    {
        missing(
            id,
            failed.availability.clone(),
            failed.reason.clone().unwrap_or_default(),
        )
    } else {
        measured(
            id,
            readings.iter().filter_map(|r| r.value).fold(0.0, f64::max),
            None,
        )
    };
    summary.observations = readings.into_iter().flat_map(|r| r.observations).collect();
    summary
}

fn publish(snapshot: &mut Snapshot, adapter: &Adapter, metrics: Metrics, counters: &mut Counters) {
    let id = adapter.id();
    let usage = utilization(
        &format!("{id}/usage"),
        adapter.luid,
        metrics.nodes,
        counters,
    );
    sensor(
        snapshot,
        &id,
        "usage",
        "GPU utilization",
        SensorKind::Percentage,
        Unit::Percent,
        "Windows graphics scheduler",
        "Busiest GPU scheduler engine, across all processes; not the sum of engines",
        usage,
    );
    for (suffix, title, kind, scope, shared) in [
        (
            "vram",
            "Dedicated GPU memory",
            SensorKind::Capacity,
            "Resident dedicated GPU segments, including reserved system memory on integrated GPUs; not necessarily discrete VRAM",
            false,
        ),
        (
            "shared-used",
            "Shared GPU memory",
            SensorKind::Scalar,
            "Resident shared system-memory GPU segments; not dedicated VRAM or total system RAM",
            true,
        ),
    ] {
        let sid = format!("{id}/{suffix}");
        let reading = match &metrics.memory {
            Ok(memory) => {
                let used = if shared {
                    memory.shared
                } else {
                    memory.dedicated
                };
                let total = (!shared && memory.dedicated_limit > 0)
                    .then_some(memory.dedicated_limit as f64);
                let mut reading = if !shared && memory.dedicated > memory.dedicated_limit {
                    Failure::failed("Windows resident dedicated memory exceeds its reported limit")
                        .reading(&sid)
                } else {
                    measured(&sid, used as f64, total)
                };
                reading.observations.push(raw_window(
                    "D3DKMT resident segment bytes and segment sizes",
                    memory.started_ns,
                    memory.ended_ns,
                    [
                        ("dedicated_bytes", memory.dedicated),
                        ("shared_bytes", memory.shared),
                        ("dedicated_limit_bytes", memory.dedicated_limit),
                        ("shared_limit_bytes", memory.shared_limit),
                    ],
                ));
                reading
            }
            Err(error) => error.reading(&sid),
        };
        sensor(
            snapshot,
            &id,
            suffix,
            title,
            kind,
            Unit::Bytes,
            "Windows graphics memory manager",
            scope,
            reading,
        );
    }
    for (suffix, title, kind, unit) in [
        (
            "temperature",
            "GPU temperature",
            SensorKind::Temperature,
            Unit::Celsius,
        ),
        ("power", "GPU power", SensorKind::Power, Unit::Watts),
        (
            "clock-graphics",
            "Graphics clock",
            SensorKind::Frequency,
            Unit::Hertz,
        ),
        (
            "clock-memory",
            "Memory clock",
            SensorKind::Frequency,
            Unit::Hertz,
        ),
    ] {
        sensor(
            snapshot,
            &id,
            suffix,
            title,
            kind,
            unit,
            "Optional vendor GPU telemetry",
            "This detected physical adapter",
            Failure::unavailable("No supported vendor reading is available for this adapter")
                .reading(&format!("{id}/{suffix}")),
        );
    }
}

/// Prefer a real vendor field, but preserve a working Windows field if NVML fails.
pub(crate) fn merge_vendor(snapshot: &mut Snapshot, vendor: Snapshot) {
    snapshot.diagnostics.extend(vendor.diagnostics);
    for (descriptor, reading) in vendor.sensors.into_iter().zip(vendor.readings) {
        if !snapshot
            .monitors
            .iter()
            .any(|m| m.id == descriptor.monitor_id)
        {
            continue;
        }
        if let Some(index) = snapshot.sensors.iter().position(|s| s.id == descriptor.id) {
            let Some(reading_index) = snapshot
                .readings
                .iter()
                .position(|r| r.sensor_id == descriptor.id)
            else {
                continue;
            };
            if reading.availability == Availability::Available
                || snapshot.readings[reading_index].availability != Availability::Available
            {
                snapshot.sensors[index] = descriptor;
                snapshot.readings[reading_index] = reading;
            }
        } else {
            snapshot.sensors.push(descriptor);
            snapshot.readings.push(reading);
        }
    }
}

#[cfg(test)]
mod tests;
