//! Independent optional SMC and HID temperature queries. No writes or fan controls.
use super::super::{Outcome, RawObservation, SourceFailure, SourceResult, decode_smc, raw_window};
use super::{ffi::*, now};
use libloading::Library;
use std::{collections::BTreeMap, ptr, time::Instant};

// SMC request layout adapted from macmon's MIT source; see ../NOTICE.md.
#[repr(C)]
#[derive(Default, Clone, Copy)]
struct Version {
    major: u8,
    minor: u8,
    build: u8,
    reserved: u8,
    release: u16,
}
#[repr(C)]
#[derive(Default, Clone, Copy)]
struct Limits {
    version: u16,
    length: u16,
    cpu: u32,
    gpu: u32,
    memory: u32,
}
#[repr(C)]
#[derive(Default, Clone, Copy)]
struct KeyInfo {
    size: u32,
    kind: u32,
    attributes: u8,
}
#[repr(C)]
#[derive(Default)]
struct KeyData {
    key: u32,
    version: Version,
    limits: Limits,
    info: KeyInfo,
    result: u8,
    status: u8,
    command: u8,
    data: u32,
    bytes: [u8; 32],
}
const _: () = assert!(std::mem::size_of::<KeyData>() == 80);
struct Connection(u32);
impl Drop for Connection {
    fn drop(&mut self) {
        unsafe {
            IOServiceClose(self.0);
        }
    }
}
impl Connection {
    fn open() -> SourceResult<Self> {
        let matching = unsafe { IOServiceMatching(c"AppleSMC".as_ptr()) };
        if matching.is_null() {
            return Err(SourceFailure::unavailable(
                "AppleSMC matching API unavailable",
            ));
        }
        let mut iterator = 0;
        let code = unsafe { IOServiceGetMatchingServices(0, matching, &mut iterator) };
        let iterator = Io::owned(iterator);
        check(code, "AppleSMC enumeration")?;
        let iterator = iterator?;
        let mut candidates = Vec::new();
        for _ in 0..1024 {
            let entry = unsafe { IOIteratorNext(iterator.0) };
            if entry == 0 {
                break;
            }
            let entry = Io::owned(entry)?;
            if entry.name()? == "AppleSMCKeysEndpoint" {
                candidates.push(entry);
            }
        }
        // Probe one extra to distinguish reaching the bound from complete enumeration.
        let overflow = Io::owned(unsafe { IOIteratorNext(iterator.0) }).ok();
        if overflow.is_some() {
            return Err("AppleSMC enumeration exceeds bound".into());
        }
        if candidates.is_empty() {
            return Err(SourceFailure::unavailable("AppleSMCKeysEndpoint absent"));
        }
        if candidates.len() != 1 {
            return Err("Multiple AppleSMC endpoints; source attribution ambiguous".into());
        }
        let mut connection = 0;
        let code = unsafe { IOServiceOpen(candidates[0].0, mach_task_self(), 0, &mut connection) };
        let owned = (connection != 0).then_some(Self(connection));
        check(code, "AppleSMC IOServiceOpen")?;
        owned.ok_or_else(|| "AppleSMC connection absent".into())
    }
    fn call(&self, input: &KeyData) -> SourceResult<KeyData> {
        let mut output = KeyData::default();
        let mut size = std::mem::size_of::<KeyData>();
        let code = unsafe {
            IOConnectCallStructMethod(
                self.0,
                2,
                ptr::from_ref(input).cast(),
                std::mem::size_of::<KeyData>(),
                ptr::from_mut(&mut output).cast(),
                &mut size,
            )
        };
        if code == 0 && size == 80 && output.status == 0 && output.result == 132 {
            return Err(SourceFailure::unavailable(
                "SMC key absent (native result 0x84)",
            ));
        }
        if code != 0 || size != 80 || output.result != 0 || output.status != 0 {
            return Err(format!(
                "SMC native read failed: return={code:#x}, size={size}, result={}, status={}",
                output.result, output.status
            )
            .into());
        }
        Ok(output)
    }
    fn temperature(&self, key: &str, origin: Instant) -> SourceResult<RawObservation> {
        let bytes =
            <[u8; 4]>::try_from(key.as_bytes()).map_err(|_| "SMC key must be four bytes")?;
        let key_value = u32::from_be_bytes(bytes);
        let start = now(origin);
        let info = self
            .call(&KeyData {
                key: key_value,
                command: 9,
                ..KeyData::default()
            })?
            .info;
        if info.size != 4 || info.kind != u32::from_be_bytes(*b"flt ") {
            return Err(format!(
                "SMC {key} unsupported temperature type {:#x}/size {}",
                info.kind, info.size
            )
            .into());
        }
        let response = self.call(&KeyData {
            key: key_value,
            command: 5,
            info,
            ..KeyData::default()
        })?;
        let end = now(origin);
        let value = decode_smc(
            info.kind,
            &response.bytes[..4],
            0,
            80,
            response.result,
            response.status,
        )?;
        let mut observation = raw_window(
            &format!("SMC/{key};flt little-endian;Celsius"),
            start,
            end,
            [
                ("key_fourcc", key_value as u64),
                ("type_fourcc", info.kind as u64),
                ("size", info.size as u64),
                (
                    "bytes_le",
                    u32::from_le_bytes([
                        response.bytes[0],
                        response.bytes[1],
                        response.bytes[2],
                        response.bytes[3],
                    ]) as u64,
                ),
                ("return_code", 0),
                ("response_size", 80),
                ("result", response.result as u64),
                ("status", response.status as u64),
            ],
        );
        observation.decimals.insert("celsius".into(), value);
        Ok(observation)
    }
}
pub(super) type Temperatures = Vec<(String, String, SourceResult<RawObservation>)>;
pub(super) fn smc(name: &str, origin: Instant) -> Temperatures {
    // The pinned Stats table identifies these four M1-family GPU keys. Other generations
    // need their own native attribution evidence; a Tg prefix alone is not sufficient.
    if !name.starts_with("Apple M1") {
        return vec![(
            "smc".into(),
            "SMC/GPU temperature".into(),
            Err(SourceFailure::unavailable(
                "No native-validated SMC key mapping for this Apple GPU generation",
            )),
        )];
    }
    let connection = Connection::open();
    ["Tg05", "Tg0D", "Tg0L", "Tg0T"]
        .into_iter()
        .map(|key| {
            let reading = match &connection {
                Ok(connection) => connection.temperature(key, origin),
                Err(e) => Err(e.clone()),
            };
            (
                format!("smc-{key}"),
                format!("SMC/{key};flt little-endian;Celsius"),
                reading,
            )
        })
        .collect()
}
struct HidApi {
    create: unsafe extern "C" fn(Ptr) -> Ptr,
    matching: unsafe extern "C" fn(Ptr, Ptr),
    services: unsafe extern "C" fn(Ptr) -> Ptr,
    property: unsafe extern "C" fn(Ptr, Ptr) -> Ptr,
    event: unsafe extern "C" fn(Ptr, i64, i32, i64) -> Ptr,
    value: unsafe extern "C" fn(Ptr, u32) -> f64,
    _library: Library,
}
impl HidApi {
    fn load() -> SourceResult<Self> {
        unsafe {
            let library = Library::new("/System/Library/Frameworks/IOKit.framework/IOKit")
                .map_err(|e| SourceFailure::unavailable(format!("HID library unavailable: {e}")))?;
            macro_rules! symbol {
                ($name:literal) => {
                    *library.get(concat!($name, "\0").as_bytes()).map_err(|e| {
                        SourceFailure::unavailable(format!("HID API {} unavailable: {e}", $name))
                    })?
                };
            }
            Ok(Self {
                create: symbol!("IOHIDEventSystemClientCreate"),
                matching: symbol!("IOHIDEventSystemClientSetMatching"),
                services: symbol!("IOHIDEventSystemClientCopyServices"),
                property: symbol!("IOHIDServiceClientCopyProperty"),
                event: symbol!("IOHIDServiceClientCopyEvent"),
                value: symbol!("IOHIDEventGetFloatValue"),
                _library: library,
            })
        }
    }
    fn query(&self, origin: Instant) -> SourceResult<Temperatures> {
        let criteria = Cf::hid_matching()?;
        let client = unsafe { Cf::owned((self.create)(ptr::null()))? };
        unsafe { (self.matching)(client.ptr(), criteria.ptr()) };
        let services = unsafe { Cf::owned((self.services)(client.ptr()))? };
        let key = Cf::string("Product")?;
        let mut results = BTreeMap::new();
        for service in services.borrow().array(4096)? {
            let product = unsafe { (self.property)(service.ptr(), key.ptr()) };
            if product.is_null() {
                continue;
            }
            let product = unsafe { Cf::owned(product)? };
            let product = product.borrow().text()?;
            if !super::super::attributed_hid(&product) {
                continue;
            }
            let start = now(origin);
            let event = unsafe { Cf::owned((self.event)(service.ptr(), 15, 0, 0)) };
            let end = now(origin);
            let reading = event
                .and_then(|event| {
                    let value = unsafe { (self.value)(event.ptr(), 15 << 16) };
                    if !value.is_finite() || value < 0.0 {
                        return Err("Invalid HID temperature event".into());
                    }
                    let mut observation = raw_window(
                        &format!("HID/{product};Celsius"),
                        start,
                        end,
                        [("event_type", 15), ("event_field", 15 << 16)],
                    );
                    observation.decimals.insert("celsius".into(), value);
                    Ok(observation)
                })
                .map_err(SourceFailure::from);
            if results.insert(product.clone(), reading).is_some() {
                results.insert(product, Err("Duplicate HID temperature identity".into()));
            }
        }
        if results.is_empty() {
            return Err(SourceFailure::unavailable(
                "No attributable GPU MTR Temp Sensor HID service",
            ));
        }
        Ok(results
            .into_iter()
            .map(|(name, value)| (format!("hid-{name}"), format!("HID/{name};Celsius"), value))
            .collect())
    }
}
pub(super) fn hid(origin: Instant) -> Temperatures {
    match HidApi::load().and_then(|api| api.query(origin)) {
        Ok(values) => values,
        Err(e) => vec![(
            "hid".into(),
            "HID/GPU MTR Temp Sensor;Celsius".into(),
            Err(e),
        )],
    }
}
