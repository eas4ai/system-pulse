//! One worker owns all native handles and refreshes inventory on every capture.
mod ffi;
mod report;
mod thermal;
use super::{
    Collector, DeviceInput, Outcome, RawObservation, Snapshot, SourceFailure, SourceResult,
    decode_table, raw_window,
};
use ffi::*;
use std::{collections::BTreeMap, time::Instant};

#[derive(Default)]
pub(crate) struct AppleCollector {
    collector: Collector,
    report: Option<report::Report>,
    drivers: Vec<u64>,
}
impl AppleCollector {
    pub(crate) fn collect(&mut self, snapshot: &mut Snapshot, origin: Instant) {
        // First local, last dropped: drain native temporaries on every return and unwind.
        let _pool = AutoreleasePool::new();
        let devices = match inventory() {
            Ok(devices) => devices,
            Err(e) => {
                self.report = None;
                self.drivers.clear();
                self.collector.append(snapshot, Err(e));
                return;
            }
        };
        let mut drivers: Vec<_> = devices.iter().map(|device| device.runtime).collect();
        drivers.sort_unstable();
        if self.drivers != drivers {
            self.report = None;
            self.drivers = drivers;
        }
        let channels = if devices.is_empty() {
            Ok(BTreeMap::new())
        } else {
            if self.report.is_none() {
                match report::Report::new(&self.drivers) {
                    Ok(report) => self.report = Some(report),
                    Err(e) => {
                        self.collect_devices(snapshot, devices, Err(e), origin);
                        return;
                    }
                }
            }
            self.report
                .as_ref()
                .ok_or_else(|| SourceFailure::from("IOReport initialization missing"))
                .and_then(|report| report.sample(origin))
        };
        if channels.is_err() {
            self.report = None;
        }
        self.collect_devices(snapshot, devices, channels, origin);
    }
    fn collect_devices(
        &mut self,
        snapshot: &mut Snapshot,
        devices: Vec<Device>,
        channels: SourceResult<report::Channels>,
        origin: Instant,
    ) {
        let single = devices.len() == 1;
        let table = if single {
            frequency_table(origin)
        } else {
            Err(SourceFailure::unavailable(
                "Multiple physical GPUs: global pmgr table has no unique association",
            ))
        };
        let mut inputs = Vec::new();
        for device in devices {
            let get = |states| match &channels {
                Ok(channels) => channels
                    .get(&(device.runtime, states))
                    .cloned()
                    .unwrap_or_else(|| {
                        Err(SourceFailure::unavailable(if states {
                            "GPUPH channel absent"
                        } else {
                            "GPU Energy channel absent"
                        }))
                    }),
                Err(e) => Err(e.clone()),
            };
            let mut states = get(true);
            let energy = get(false);
            if states.is_err() || energy.is_err() {
                self.report = None;
            }
            if let Ok(states) = &mut states {
                match &table {
                    Ok((frequencies, raw)) => {
                        for (index, hz) in frequencies.iter().enumerate() {
                            states
                                .integers
                                .insert(format!("hz/{}", super::state_name(index as u64)), *hz);
                        }
                        for (key, value) in &raw.integers {
                            states.integers.insert(format!("table/{key}"), *value);
                        }
                        states.integers.insert(
                            "table/read_started_ns".into(),
                            raw.read_started_ns.unwrap_or(raw.captured_ns),
                        );
                        states
                            .integers
                            .insert("table/captured_ns".into(), raw.captured_ns);
                        states.source.push_str(&format!(" + {}", raw.source));
                    }
                    Err(e) => states
                        .source
                        .push_str(&format!("; frequency table unavailable: {}", e.reason)),
                }
            }
            let (allocated, in_use) = memory(&device, origin);
            let mut temperatures = if single {
                thermal::smc(&device.name, origin)
            } else {
                vec![(
                    "smc".into(),
                    "SMC/GPU temperature".into(),
                    Err(SourceFailure::unavailable(
                        "Multiple GPUs: SMC keys have no unique device attribution",
                    )),
                )]
            };
            temperatures.extend(if single {
                thermal::hid(origin)
            } else {
                vec![(
                    "hid".into(),
                    "HID/GPU MTR Temp Sensor;Celsius".into(),
                    Err(SourceFailure::unavailable(
                        "Multiple GPUs: HID temperatures have no unique device attribution",
                    )),
                )]
            });
            inputs.push(DeviceInput {
                path: device.path,
                name: device.name,
                runtime: device.runtime,
                unified: device.unified,
                states,
                energy,
                allocated,
                in_use,
                temperatures,
            });
        }
        self.collector.append(snapshot, Ok(inputs));
    }
}
pub(super) fn now(origin: Instant) -> u64 {
    origin.elapsed().as_nanos().min(u64::MAX as u128) as u64
}
struct Device {
    entry: Io,
    path: String,
    name: String,
    runtime: u64,
    unified: bool,
}
fn inventory() -> Outcome<Vec<Device>> {
    let devices = unsafe { Cf::owned(MTLCopyAllDevices())? };
    let mut output = Vec::new();
    for device in devices.borrow().array(16)? {
        let runtime = device.metal_id();
        let name = device.metal_name()?;
        let unified = device.metal_unified();
        let criteria = unsafe { IORegistryEntryIDMatching(runtime) };
        if criteria.is_null() {
            return Err("Metal registry matching dictionary absent".into());
        }
        // IOKit consumes matching dictionaries even on failure.
        let entry = Io::owned(unsafe { IOServiceGetMatchingService(0, criteria) })?;
        if entry.id()? != runtime {
            return Err("Metal/IOKit registry ID mismatch".into());
        }
        let path = physical_path(&entry)?;
        super::identity(&path, runtime, unified)?;
        output.push(Device {
            entry,
            path,
            name,
            runtime,
            unified,
        });
    }
    Ok(output)
}
fn physical_path(entry: &Io) -> Outcome<String> {
    if let Ok(path) = entry.path(c"IODeviceTree") {
        return Ok(path);
    }
    let mut parent = entry.parent()?;
    for _ in 0..32 {
        if let Ok(path) = parent.path(c"IODeviceTree") {
            return Ok(path);
        }
        parent = parent.parent()?;
    }
    Err("GPU registry ancestry exceeds bound".into())
}
fn frequency_table(origin: Instant) -> SourceResult<(Vec<u64>, RawObservation)> {
    let start = now(origin);
    let matching = unsafe { IOServiceNameMatching(c"pmgr".as_ptr()) };
    if matching.is_null() {
        return Err(SourceFailure::unavailable(
            "pmgr registry matching unavailable",
        ));
    }
    let mut iterator = 0;
    let code = unsafe { IOServiceGetMatchingServices(0, matching, &mut iterator) };
    let iterator = Io::owned(iterator);
    check(code, "pmgr enumeration")?;
    let iterator = iterator?;
    let mut entries = Vec::new();
    for _ in 0..16 {
        let entry = unsafe { IOIteratorNext(iterator.0) };
        if entry == 0 {
            break;
        }
        entries.push(Io::owned(entry)?);
    }
    let extra = Io::owned(unsafe { IOIteratorNext(iterator.0) }).ok();
    if extra.is_some() || entries.len() > 1 {
        return Err("pmgr source association ambiguous".into());
    }
    let entry = entries
        .first()
        .ok_or_else(|| SourceFailure::unavailable("pmgr frequency table source absent"))?;
    let path = entry.path(c"IODeviceTree")?;
    if !path.starts_with("IODeviceTree:/arm-io/") {
        return Err("pmgr is outside supported physical GPU tree".into());
    }
    let value = entry
        .property("voltage-states9")?
        .ok_or_else(|| SourceFailure::unavailable("pmgr voltage-states9 absent"))?;
    let bytes = value.borrow().data(1024)?;
    let table = decode_table(bytes)?;
    let end = now(origin);
    let mut raw = raw_window(
        &format!("IOKit/{path}/voltage-states9;little-endian frequency Hz,voltage native"),
        start,
        end,
        [
            ("driver_id", entry.id()?),
            ("byte_length", bytes.len() as u64),
        ],
    );
    for (i, chunk) in bytes.chunks_exact(8).enumerate() {
        raw.integers.insert(
            format!("pair_le/{i}"),
            u64::from_le_bytes(chunk.try_into().map_err(|_| "Invalid table pair")?),
        );
    }
    Ok((table, raw))
}
fn memory(
    device: &Device,
    origin: Instant,
) -> (SourceResult<RawObservation>, SourceResult<RawObservation>) {
    let start = now(origin);
    let statistics = device
        .entry
        .property("PerformanceStatistics")
        .map_err(SourceFailure::from)
        .and_then(|v| {
            v.ok_or_else(|| {
                SourceFailure::unavailable("Matched accelerator PerformanceStatistics absent")
            })
        });
    let end = now(origin);
    let field = |key: &str| -> SourceResult<RawObservation> {
        let statistics = statistics.as_ref().map_err(Clone::clone)?;
        let value = statistics
            .borrow()
            .get(key)?
            .ok_or_else(|| SourceFailure::unavailable(format!("Matched accelerator {key} absent")))?
            .integer()?;
        Ok(raw_window(
            &format!("IOKit/{}/PerformanceStatistics/{key};bytes", device.path),
            start,
            end,
            [
                ("bytes", value),
                ("driver_id", device.runtime),
                ("has_unified_memory", u64::from(device.unified)),
            ],
        ))
    };
    (field("Alloc system memory"), field("In use system memory"))
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn core_foundation_types_and_create_failures_are_checked() {
        assert!(unsafe { Cf::owned(std::ptr::null()) }.is_err());
        // The null registry entry must report its native failure, not look like an absent key.
        assert!(Io(0).property("PerformanceStatistics").is_err());
        let value = Cf::string("native boundary").unwrap();
        assert_eq!(value.borrow().text().unwrap(), "native boundary");
        assert!(value.borrow().array(4).is_err());
        assert!(value.borrow().dictionary().is_err());
        assert!(value.borrow().integer().is_err());
        assert!(value.borrow().data(4).is_err());
        let array = Cf::array().unwrap();
        array.append(value.borrow());
        assert!(array.borrow().array(0).is_err());
        assert_eq!(
            array.borrow().array(1).unwrap()[0].text().unwrap(),
            "native boundary"
        );
    }
}

#[cfg(test)]
mod pool_tests;
