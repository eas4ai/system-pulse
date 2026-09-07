//! Optional IOReport subscription. The output dictionary and library outlive samples.
use super::super::{
    Outcome, RawObservation, SourceFailure, SourceResult, bounded_count, raw_window, validate,
};
use super::ffi::{Cf, Ptr, Ref};
use libloading::Library;
use std::{collections::BTreeMap, ptr, time::Instant};

type TextGetter = unsafe extern "C" fn(Ptr) -> Ptr;
type NumberGetter = unsafe extern "C" fn(Ptr) -> u64;
struct Api {
    copy: unsafe extern "C" fn(u64, u64) -> Ptr,
    subscribe: unsafe extern "C" fn(Ptr, Ptr, *mut Ptr, u64, Ptr) -> Ptr,
    sample: unsafe extern "C" fn(Ptr, Ptr, Ptr) -> Ptr,
    group: TextGetter,
    subgroup: TextGetter,
    name: TextGetter,
    unit_label: TextGetter,
    driver: NumberGetter,
    channel: NumberGetter,
    unit: NumberGetter,
    format: unsafe extern "C" fn(Ptr) -> u8,
    state_count: unsafe extern "C" fn(Ptr) -> i32,
    state_name: unsafe extern "C" fn(Ptr, i32) -> Ptr,
    residency: unsafe extern "C" fn(Ptr, i32) -> i64,
    integer: unsafe extern "C" fn(Ptr, i32) -> i64,
    _library: Library,
}
impl Api {
    fn load() -> SourceResult<Self> {
        // SAFETY: fixed system library path; function signatures follow probed native ABI.
        unsafe {
            let library = Library::new("/usr/lib/libIOReport.dylib").map_err(|e| {
                SourceFailure::unavailable(format!("IOReport API unavailable: {e}"))
            })?;
            macro_rules! symbol {
                ($name:literal) => {
                    *library.get(concat!($name, "\0").as_bytes()).map_err(|e| {
                        SourceFailure::unavailable(format!(
                            "IOReport API {} unavailable: {e}",
                            $name
                        ))
                    })?
                };
            }
            Ok(Self {
                copy: symbol!("IOReportCopyAllChannels"),
                subscribe: symbol!("IOReportCreateSubscription"),
                sample: symbol!("IOReportCreateSamples"),
                group: symbol!("IOReportChannelGetGroup"),
                subgroup: symbol!("IOReportChannelGetSubGroup"),
                name: symbol!("IOReportChannelGetChannelName"),
                unit_label: symbol!("IOReportChannelGetUnitLabel"),
                driver: symbol!("IOReportChannelGetDriverID"),
                channel: symbol!("IOReportChannelGetChannelID"),
                unit: symbol!("IOReportChannelGetUnit"),
                format: symbol!("IOReportChannelGetFormat"),
                state_count: symbol!("IOReportStateGetCount"),
                state_name: symbol!("IOReportStateGetNameForIndex"),
                residency: symbol!("IOReportStateGetResidency"),
                integer: symbol!("IOReportSimpleGetIntegerValue"),
                _library: library,
            })
        }
    }
    fn text(&self, row: Ref<'_>, getter: TextGetter) -> Outcome<String> {
        unsafe { row.child(getter(row.ptr()))?.text() }
    }
    fn selected(&self, row: Ref<'_>, drivers: &[u64]) -> Outcome<bool> {
        row.dictionary()?;
        let driver = unsafe { (self.driver)(row.ptr()) };
        if !drivers.contains(&driver) {
            return Ok(false);
        }
        let name = self.text(row, self.name)?;
        Ok(name == "GPUPH" || name == "GPU Energy")
    }
}
pub(super) type Channels = BTreeMap<(u64, bool), SourceResult<RawObservation>>;
pub(super) struct Report {
    subscription: Cf,
    channels: Cf,
    api: Api,
}
impl Report {
    pub(super) fn new(drivers: &[u64]) -> SourceResult<Self> {
        let api = Api::load()?;
        let all = unsafe { Cf::owned((api.copy)(0, 0))? };
        let selected = Cf::array()?;
        let rows = all
            .borrow()
            .get("IOReportChannels")?
            .ok_or("Missing IOReport channel array")?
            .array(100_000)?;
        let mut count = 0;
        for row in rows {
            if api.selected(row, drivers)? {
                selected.append(row);
                count += 1;
            }
        }
        if count == 0 {
            return Err(SourceFailure::unavailable(
                "No directly attributed GPUPH/GPU Energy channels",
            ));
        }
        let request = Cf::dictionary_copy(all.borrow())?;
        let key = Cf::string("IOReportChannels")?;
        request.set(&key, &selected);
        let mut output = ptr::null();
        let subscription_ptr =
            unsafe { (api.subscribe)(ptr::null(), request.ptr(), &mut output, 0, ptr::null()) };
        // Adopt both outputs before either validation can return, including partial failures.
        let subscription = unsafe { Cf::owned(subscription_ptr) };
        let channels = unsafe { Cf::owned(output) };
        let subscription = subscription?;
        let channels = channels?;
        channels.borrow().dictionary()?;
        Ok(Self {
            subscription,
            channels,
            api,
        })
    }
    pub(super) fn sample(&self, origin: Instant) -> SourceResult<Channels> {
        let start = super::now(origin);
        let sample = unsafe {
            Cf::owned((self.api.sample)(
                self.subscription.ptr(),
                self.channels.ptr(),
                ptr::null(),
            ))?
        };
        let end = super::now(origin);
        let rows = sample
            .borrow()
            .get("IOReportChannels")?
            .ok_or("Sample channel array missing")?
            .array(1024)?;
        let mut result = BTreeMap::new();
        for row in rows {
            row.dictionary()?;
            let driver = unsafe { (self.api.driver)(row.ptr()) };
            let name = self.api.text(row, self.api.name)?;
            let states = match name.as_str() {
                "GPUPH" => true,
                "GPU Energy" => false,
                _ => continue,
            };
            let observation = self
                .read(row, driver, states, start, end)
                .map_err(SourceFailure::from);
            if result.insert((driver, states), observation).is_some() {
                result.insert(
                    (driver, states),
                    Err("Multiple matching IOReport channels; attribution ambiguous".into()),
                );
            }
        }
        Ok(result)
    }
    fn read(
        &self,
        row: Ref<'_>,
        driver: u64,
        states: bool,
        start: u64,
        end: u64,
    ) -> Outcome<RawObservation> {
        let group = self.api.text(row, self.api.group)?;
        if group != if states { "GPU Stats" } else { "Energy Model" } {
            return Err("IOReport channel group mismatch".into());
        }
        if states && self.api.text(row, self.api.subgroup)? != "GPU Performance States" {
            return Err("IOReport performance-state subgroup mismatch".into());
        }
        let label = self.api.text(row, self.api.unit_label)?;
        if label != if states { "24Mticks" } else { "nJ" } {
            return Err(format!("IOReport source unit label mismatch: {label}"));
        }
        let mut observation = raw_window(
            &format!(
                "IOReport/{group}/{};{label}",
                if states {
                    "GPU Performance States/GPUPH"
                } else {
                    "GPU Energy"
                }
            ),
            start,
            end,
            [
                ("driver_id", driver),
                ("channel_id", unsafe { (self.api.channel)(row.ptr()) }),
                ("format", unsafe { (self.api.format)(row.ptr()) } as u64),
                ("encoded_unit", unsafe { (self.api.unit)(row.ptr()) }),
            ],
        );
        // Check metadata before choosing a getter that interprets the payload layout.
        let expected_format = if states { 2 } else { 1 };
        let expected_unit = if states {
            super::super::RESIDENCY_UNIT
        } else {
            super::super::ENERGY_UNIT
        };
        if observation.integers["format"] != expected_format
            || observation.integers["encoded_unit"] != expected_unit
        {
            return Err("IOReport payload format/unit mismatch".into());
        }
        if states {
            let count = bounded_count(unsafe { (self.api.state_count)(row.ptr()) } as isize, 128)?;
            observation
                .integers
                .insert("state_count".into(), count as u64);
            for i in 0..count {
                let name = unsafe {
                    row.child((self.api.state_name)(row.ptr(), i as i32))?
                        .text()?
                };
                let value = u64::try_from(unsafe { (self.api.residency)(row.ptr(), i as i32) })
                    .map_err(|_| "Invalid negative IOReport residency")?;
                if observation
                    .integers
                    .insert(format!("ticks/{name}"), value)
                    .is_some()
                {
                    return Err("Duplicate IOReport state names".into());
                }
            }
        } else {
            let value = u64::try_from(unsafe { (self.api.integer)(row.ptr(), 0) })
                .map_err(|_| "Invalid negative IOReport energy")?;
            observation.integers.insert("energy_nj".into(), value);
        }
        validate(&observation, driver, states)?;
        Ok(observation)
    }
}
