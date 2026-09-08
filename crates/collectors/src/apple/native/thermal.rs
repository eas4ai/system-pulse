//! Independent optional SMC and HID temperature queries. No writes or fan controls.
use super::super::{RawObservation, SourceFailure, SourceResult, decode_smc, raw_window};
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
    let keys = super::super::smc_keys(name);
    if keys.is_empty() {
        return vec![(
            "smc".into(),
            "SMC/GPU temperature".into(),
            Err(SourceFailure::unavailable(
                "No evidenced SMC key profile for this Metal GPU model",
            )),
        )];
    }
    let connection = Connection::open();
    keys.iter()
        .copied()
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
}

pub(super) struct HidConnection {
    // Drop the client before unloading the functions used by its implementation.
    client: Cf,
    api: HidApi,
}

pub(super) trait HidBackend: Sized {
    fn connect() -> SourceResult<Self>;
    fn query(&mut self, origin: Instant) -> SourceResult<Temperatures>;
}

impl HidBackend for HidConnection {
    fn connect() -> SourceResult<Self> {
        let api = HidApi::load()?;
        let criteria = Cf::hid_matching()?;
        let client = unsafe { Cf::owned((api.create)(ptr::null()))? };
        unsafe { (api.matching)(client.ptr(), criteria.ptr()) };
        Ok(Self { client, api })
    }

    fn query(&mut self, origin: Instant) -> SourceResult<Temperatures> {
        let api = &self.api;
        let services = unsafe { Cf::owned((api.services)(self.client.ptr()))? };
        let key = Cf::string("Product")?;
        let mut results = BTreeMap::new();
        for service in services.borrow().array(4096)? {
            let product = unsafe { (api.property)(service.ptr(), key.ptr()) };
            if product.is_null() {
                continue;
            }
            let product = unsafe { Cf::owned(product)? };
            let product = product.borrow().text()?;
            if !super::super::attributed_hid(&product) {
                continue;
            }
            let start = now(origin);
            let event = unsafe { Cf::owned((api.event)(service.ptr(), 15, 0, 0)) };
            let end = now(origin);
            let reading = event
                .and_then(|event| {
                    let value = unsafe { (api.value)(event.ptr(), 15 << 16) };
                    if !value.is_finite() {
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
pub(super) struct Hid<T = HidConnection> {
    connection: Option<T>,
}

impl<T> Default for Hid<T> {
    fn default() -> Self {
        Self { connection: None }
    }
}

impl<T> Hid<T> {
    pub(super) fn reset(&mut self) {
        self.connection = None;
    }
}

impl<T: HidBackend> Hid<T> {
    pub(super) fn read(&mut self, origin: Instant) -> Temperatures {
        let result = (|| {
            if self.connection.is_none() {
                self.connection = Some(T::connect()?);
            }
            self.connection
                .as_mut()
                .expect("connected above")
                .query(origin)
        })();
        if !result.as_ref().is_ok_and(|values| {
            !values.is_empty() && values.iter().all(|(_, _, value)| value.is_ok())
        }) {
            self.reset();
        }
        match result {
            Ok(values) => values,
            Err(e) => vec![(
                "hid".into(),
                "HID/GPU MTR Temp Sensor;Celsius".into(),
                Err(e),
            )],
        }
    }
}

#[cfg(test)]
mod hid_tests {
    use super::*;

    struct Backend {
        reads: u64,
        next: Option<SourceResult<Temperatures>>,
    }

    impl HidBackend for Backend {
        fn connect() -> SourceResult<Self> {
            Ok(Self {
                reads: 0,
                next: None,
            })
        }

        fn query(&mut self, _: Instant) -> SourceResult<Temperatures> {
            self.reads += 1;
            self.next.take().unwrap_or_else(|| {
                Ok(vec![(
                    "sensor".into(),
                    "test source".into(),
                    Ok(raw_window(
                        "test source",
                        self.reads,
                        self.reads,
                        [("value", self.reads)],
                    )),
                )])
            })
        }
    }

    #[test]
    fn healthy_connection_reads_again_and_replaces_discovered_sensors() {
        let mut hid = Hid::<Backend>::default();
        let origin = Instant::now();
        assert_eq!(hid.read(origin)[0].2.as_ref().unwrap().captured_ns, 1);
        assert_eq!(hid.read(origin)[0].2.as_ref().unwrap().captured_ns, 2);
        hid.connection.as_mut().unwrap().next = Some(Ok(vec![(
            "replacement".into(),
            "new source".into(),
            Ok(raw_window("new source", 3, 3, [("value", 42)])),
        )]));
        let readings = hid.read(origin);
        assert_eq!(readings.len(), 1);
        assert_eq!(readings[0].0, "replacement");
        assert_eq!(hid.connection.as_ref().unwrap().reads, 3);
        hid.reset();
        assert!(hid.connection.is_none());
        assert_eq!(hid.read(origin)[0].2.as_ref().unwrap().captured_ns, 1);
    }

    #[test]
    fn failed_or_empty_discovery_discards_connection_and_recovers() {
        let mut hid = Hid::<Backend>::default();
        let origin = Instant::now();
        for next in [
            Err(SourceFailure::unavailable("disconnected")),
            Ok(vec![]),
            Ok(vec![(
                "sensor".into(),
                "source".into(),
                Err("read failed".into()),
            )]),
        ] {
            hid.read(origin);
            hid.connection.as_mut().unwrap().next = Some(next);
            let readings = hid.read(origin);
            assert!(readings.iter().all(|(_, _, value)| value.is_err()));
            assert!(hid.connection.is_none());
            assert_eq!(hid.read(origin)[0].2.as_ref().unwrap().captured_ns, 1);
        }
    }

    struct Disconnected;

    impl HidBackend for Disconnected {
        fn connect() -> SourceResult<Self> {
            Err(SourceFailure::unavailable("HID unavailable"))
        }

        fn query(&mut self, _: Instant) -> SourceResult<Temperatures> {
            panic!("failed connection must not be queried")
        }
    }

    #[test]
    fn repeated_connection_failure_retains_no_state_or_successful_reading() {
        let mut hid = Hid::<Disconnected>::default();
        for _ in 0..100 {
            let readings = hid.read(Instant::now());
            assert_eq!(readings.len(), 1);
            assert_eq!(
                readings[0].2.as_ref().unwrap_err().reason,
                "HID unavailable"
            );
            assert!(hid.connection.is_none());
        }
    }
}
