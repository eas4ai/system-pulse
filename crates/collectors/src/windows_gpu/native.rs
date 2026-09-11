//! Windows API boundary. Discovery does not depend on graphics telemetry calls.
use super::*;
use windows::{
    Wdk::Graphics::Direct3D::*,
    Win32::{
        Devices::{DeviceAndDriverInstallation::*, Display::GUID_DISPLAY_DEVICE_ARRIVAL},
        Foundation::{ERROR_NO_MORE_ITEMS, HWND, LUID, NTSTATUS},
        System::Registry::{REG_DWORD, REG_SZ, REG_VALUE_TYPE},
    },
    core::PCWSTR,
};

pub(super) struct Native;
const MAX_ADAPTERS: u32 = 128;
const MAX_NODES: u32 = 64;
const MAX_SEGMENTS: u32 = 64;

fn win_error(operation: &str, error: windows::core::Error) -> Failure {
    Failure::failed(format!("{operation}: {error}"))
}
fn status(operation: &str, result: NTSTATUS) -> Result<()> {
    if result.0 >= 0 {
        Ok(())
    } else {
        Err(Failure::failed(format!(
            "{operation}: NTSTATUS 0x{:08x}",
            result.0 as u32
        )))
    }
}
fn now(origin: Instant) -> u64 {
    origin.elapsed().as_nanos().min(u64::MAX as u128) as u64
}

struct DeviceSet(HDEVINFO);
impl Drop for DeviceSet {
    fn drop(&mut self) {
        // SAFETY: this object owns the device set returned by SetupDiGetClassDevsW.
        let _ = unsafe { SetupDiDestroyDeviceInfoList(self.0) };
    }
}

impl Backend for Native {
    fn inventory(&mut self) -> Result<Vec<Adapter>> {
        // SAFETY: the class GUID is valid, and no window/enumerator is borrowed.
        let devices = DeviceSet(
            unsafe {
                SetupDiGetClassDevsW(
                    Some(&GUID_DEVCLASS_DISPLAY),
                    PCWSTR::null(),
                    HWND::default(),
                    DIGCF_PRESENT,
                )
            }
            .map_err(|e| win_error("Enumerate present display adapters", e))?,
        );
        let mut adapters = Vec::new();
        for index in 0..MAX_ADAPTERS {
            let mut device = SP_DEVINFO_DATA {
                cbSize: std::mem::size_of::<SP_DEVINFO_DATA>() as u32,
                ..Default::default()
            };
            // SAFETY: the owned set remains live and the output has its documented size.
            if let Err(error) = unsafe { SetupDiEnumDeviceInfo(devices.0, index, &mut device) } {
                if error.code() == windows::core::HRESULT::from_win32(ERROR_NO_MORE_ITEMS.0) {
                    return Ok(adapters);
                }
                return Err(win_error("Read display adapter entry", error));
            }
            let mut id = [0u16; 512];
            unsafe { SetupDiGetDeviceInstanceIdW(devices.0, &device, Some(&mut id), None) }
                .map_err(|e| win_error("Read display adapter PnP identity", e))?;
            let instance_id = wide_string(&id)?;
            let Some(vendor) = vendor_id(&instance_id) else {
                continue;
            };
            if !matches!(vendor, 0x8086 | 0x1002 | 0x10de) {
                continue;
            }
            // Metadata is optional: a driver lacking a name/LUID/address still has a device.
            let name = registry(&devices, &device, SPDRP_DEVICEDESC, REG_SZ)
                .and_then(|bytes| {
                    if bytes.len() % 2 != 0 {
                        return Err(Failure::failed("Odd-length display name"));
                    }
                    wide_string(
                        &bytes
                            .chunks_exact(2)
                            .map(|v| u16::from_le_bytes([v[0], v[1]]))
                            .collect::<Vec<_>>(),
                    )
                })
                .unwrap_or_else(|_| {
                    format!(
                        "{} graphics adapter",
                        match vendor {
                            0x8086 => "Intel",
                            0x1002 => "AMD",
                            _ => "NVIDIA",
                        }
                    )
                });
            let pci = registry_u32(&devices, &device, SPDRP_BUSNUMBER)
                .ok()
                .zip(registry_u32(&devices, &device, SPDRP_ADDRESS).ok())
                .and_then(|(bus, address)| {
                    let (device, function) = (address >> 16, address & 0xffff);
                    (bus <= 255 && device < 32 && function < 8)
                        .then_some((0, bus, device, function))
                });
            let luid = adapter_luid(&instance_id).ok();
            adapters.push(Adapter {
                instance_id,
                name,
                vendor,
                pci,
                luid,
            });
        }
        Err(Failure::failed(
            "Windows display adapter enumeration exceeded its bound",
        ))
    }

    fn sample(&mut self, adapter: &Adapter, origin: Instant) -> Metrics {
        let Some(luid) = adapter.luid else {
            return Metrics::failed(Failure::unavailable(
                "Windows exposes no adapter LUID; GPU telemetry is unavailable",
            ));
        };
        let handle = match GraphicsAdapter::open(luid) {
            Ok(handle) => handle,
            Err(error) => return Metrics::failed(error),
        };
        let mut metrics = handle.sample(origin);
        if let Err(error) = handle.finish() {
            metrics = Metrics::failed(error);
        }
        metrics
    }
}

fn wide_string(buffer: &[u16]) -> Result<String> {
    let end = buffer
        .iter()
        .position(|&c| c == 0)
        .ok_or_else(|| Failure::failed("Unterminated Windows GPU string"))?;
    if end == 0 {
        return Err(Failure::failed("Empty Windows GPU string"));
    }
    String::from_utf16(&buffer[..end])
        .map_err(|e| Failure::failed(format!("Invalid Windows GPU UTF-16: {e}")))
}

fn vendor_id(instance: &str) -> Option<u32> {
    let instance = instance.to_ascii_uppercase();
    let component = instance.strip_prefix("PCI\\VEN_")?.get(..4)?;
    u32::from_str_radix(component, 16).ok()
}

fn registry(
    set: &DeviceSet,
    device: &SP_DEVINFO_DATA,
    property: SETUP_DI_REGISTRY_PROPERTY,
    expected_type: REG_VALUE_TYPE,
) -> Result<Vec<u8>> {
    let mut buffer = vec![0u8; 4096];
    let mut needed = 0;
    let mut kind = 0;
    // SAFETY: the byte buffer capacity and output pointers are valid; no casted alignment assumptions.
    unsafe {
        SetupDiGetDeviceRegistryPropertyW(
            set.0,
            device,
            property,
            Some(&mut kind),
            Some(&mut buffer),
            Some(&mut needed),
        )
    }
    .map_err(|e| win_error("Read display adapter property", e))?;
    if kind != expected_type.0 {
        return Err(Failure::failed("Invalid display adapter property type"));
    }
    if needed == 0 || needed as usize > buffer.len() {
        return Err(Failure::failed("Invalid display adapter property length"));
    }
    buffer.truncate(needed as usize);
    Ok(buffer)
}
fn registry_u32(
    set: &DeviceSet,
    device: &SP_DEVINFO_DATA,
    property: SETUP_DI_REGISTRY_PROPERTY,
) -> Result<u32> {
    let bytes = registry(set, device, property, REG_DWORD)?;
    let value: [u8; 4] = bytes
        .try_into()
        .map_err(|_| Failure::failed("Invalid GPU PCI property size"))?;
    Ok(u32::from_le_bytes(value))
}
fn adapter_luid(instance_id: &str) -> Result<u64> {
    let device: Vec<u16> = instance_id.encode_utf16().chain(Some(0)).collect();
    let mut size = 0;
    // Filter by the exact PnP ID. Never derive an interface path from its spelling.
    let result = unsafe {
        CM_Get_Device_Interface_List_SizeW(
            &mut size,
            &GUID_DISPLAY_DEVICE_ARRIVAL,
            PCWSTR(device.as_ptr()),
            CM_GET_DEVICE_INTERFACE_LIST_PRESENT,
        )
    };
    if result != CR_SUCCESS || size == 0 || size > 65536 {
        return Err(Failure::failed(format!(
            "Read GPU interface list size: CONFIGRET {} / {size}",
            result.0
        )));
    }
    let mut interfaces = vec![0u16; size as usize];
    let result = unsafe {
        CM_Get_Device_Interface_ListW(
            &GUID_DISPLAY_DEVICE_ARRIVAL,
            PCWSTR(device.as_ptr()),
            &mut interfaces,
            CM_GET_DEVICE_INTERFACE_LIST_PRESENT,
        )
    };
    if result != CR_SUCCESS {
        return Err(Failure::failed(format!(
            "Read GPU interface list: CONFIGRET {}",
            result.0
        )));
    }
    let mut found = None;
    let mut remaining = interfaces.as_slice();
    for _ in 0..MAX_ADAPTERS {
        let end = remaining
            .iter()
            .position(|&c| c == 0)
            .ok_or_else(|| Failure::failed("Unterminated GPU interface list"))?;
        if end == 0 {
            return found.ok_or_else(|| Failure::unavailable("No present GPU display interface"));
        }
        let handle = GraphicsAdapter::from_device_name(&remaining[..=end])?;
        let luid = (u64::from(handle.luid.HighPart as u32) << 32) | u64::from(handle.luid.LowPart);
        handle.finish()?;
        if found.is_some_and(|previous| previous != luid) {
            return Err(Failure::failed(
                "One PnP adapter resolved to conflicting GPU LUIDs",
            ));
        }
        found = Some(luid);
        remaining = &remaining[end + 1..];
    }
    Err(Failure::failed("GPU interface count exceeded its bound"))
}

struct GraphicsAdapter {
    handle: Option<u32>,
    luid: LUID,
}
impl GraphicsAdapter {
    fn from_device_name(name: &[u16]) -> Result<Self> {
        let mut request = D3DKMT_OPENADAPTERFROMDEVICENAME {
            pDeviceName: PCWSTR(name.as_ptr()),
            ..Default::default()
        };
        // SAFETY: name includes its terminator and remains live during the call.
        status("Open GPU display interface", unsafe {
            D3DKMTOpenAdapterFromDeviceName(&mut request)
        })?;
        Ok(Self {
            handle: Some(request.hAdapter),
            luid: request.AdapterLuid,
        })
    }

    fn open(value: u64) -> Result<Self> {
        let luid = LUID {
            LowPart: value as u32,
            HighPart: (value >> 32) as i32,
        };
        let mut request = D3DKMT_OPENADAPTERFROMLUID {
            AdapterLuid: luid,
            ..Default::default()
        };
        // SAFETY: initialized native request; successful call returns one owned adapter handle.
        status("Open graphics adapter", unsafe {
            D3DKMTOpenAdapterFromLuid(&mut request)
        })?;
        Ok(Self {
            handle: Some(request.hAdapter),
            luid,
        })
    }

    fn statistics(
        &self,
        kind: D3DKMT_QUERYSTATISTICS_TYPE,
        index: u32,
    ) -> Result<D3DKMT_QUERYSTATISTICS_RESULT> {
        let mut query = D3DKMT_QUERYSTATISTICS {
            Type: kind,
            AdapterLuid: self.luid,
            ..Default::default()
        };
        query.Anonymous = if kind == D3DKMT_QUERYSTATISTICS_NODE {
            D3DKMT_QUERYSTATISTICS_0 {
                QueryNode: D3DKMT_QUERYSTATISTICS_QUERY_NODE { NodeId: index },
            }
        } else {
            D3DKMT_QUERYSTATISTICS_0 {
                QuerySegment: D3DKMT_QUERYSTATISTICS_QUERY_SEGMENT { SegmentId: index },
            }
        };
        // SAFETY: the SDK uses a const parameter but writes QueryResult. Supply a mutable
        // allocation; only the successful result's discriminated union member is read.
        status("Query graphics statistics", unsafe {
            D3DKMTQueryStatistics(std::ptr::addr_of_mut!(query))
        })?;
        Ok(query.QueryResult)
    }

    fn segment_sizes(&self) -> Result<D3DKMT_SEGMENTSIZEINFO> {
        let mut sizes = D3DKMT_SEGMENTSIZEINFO::default();
        let mut query = D3DKMT_QUERYADAPTERINFO {
            hAdapter: self.handle.expect("owned adapter"),
            Type: KMTQAITYPE_GETSEGMENTSIZE,
            pPrivateDriverData: (&mut sizes as *mut D3DKMT_SEGMENTSIZEINFO).cast(),
            PrivateDriverDataSize: std::mem::size_of_val(&sizes) as u32,
        };
        // SAFETY: query type, output layout and size agree and the adapter remains owned.
        status("Read graphics segment sizes", unsafe {
            D3DKMTQueryAdapterInfo(&mut query)
        })?;
        Ok(sizes)
    }

    fn sample(&self, origin: Instant) -> Metrics {
        let information = match self.statistics(D3DKMT_QUERYSTATISTICS_ADAPTER, 0) {
            Ok(result) => unsafe { result.AdapterInformation },
            Err(error) => return Metrics::failed(error),
        };
        let nodes = (|| {
            if information.NodeCount > MAX_NODES {
                return Err(Failure::failed("GPU node count exceeds bound"));
            }
            (0..information.NodeCount)
                .map(|id| {
                    let started_ns = now(origin);
                    let result = self.statistics(D3DKMT_QUERYSTATISTICS_NODE, id)?;
                    let ended_ns = now(origin);
                    let ticks = unsafe { result.NodeInformation.GlobalInformation.RunningTime };
                    let running_ticks = u64::try_from(ticks)
                        .map_err(|_| Failure::failed("Negative GPU running time"))?;
                    Ok(Node {
                        id,
                        running_ticks,
                        started_ns,
                        ended_ns,
                    })
                })
                .collect()
        })();
        let memory = (|| {
            if information.NbSegments == 0 {
                return Err(Failure::unavailable(
                    "Windows exposes no GPU memory segments",
                ));
            }
            if information.NbSegments > MAX_SEGMENTS {
                return Err(Failure::failed("GPU segment count exceeds bound"));
            }
            let started_ns = now(origin);
            let sizes = self.segment_sizes()?;
            let (mut dedicated, mut shared) = (0u64, 0u64);
            for id in 0..information.NbSegments {
                let result = self.statistics(D3DKMT_QUERYSTATISTICS_SEGMENT, id)?;
                let segment = unsafe { result.SegmentInformation };
                let destination = match segment.Aperture {
                    0 => &mut dedicated,
                    1 => &mut shared,
                    _ => return Err(Failure::failed("Invalid GPU memory segment aperture")),
                };
                *destination = destination
                    .checked_add(segment.BytesResident)
                    .ok_or_else(|| Failure::failed("GPU resident memory overflow"))?;
            }
            let dedicated_limit = sizes
                .DedicatedVideoMemorySize
                .checked_add(sizes.DedicatedSystemMemorySize)
                .ok_or_else(|| Failure::failed("GPU dedicated limit overflow"))?;
            Ok(Memory {
                dedicated,
                shared,
                dedicated_limit,
                shared_limit: sizes.SharedSystemMemorySize,
                started_ns,
                ended_ns: now(origin),
            })
        })();
        Metrics { nodes, memory }
    }

    fn finish(mut self) -> Result<()> {
        let request = D3DKMT_CLOSEADAPTER {
            hAdapter: self.handle.take().expect("owned adapter"),
        };
        status("Close graphics adapter", unsafe {
            D3DKMTCloseAdapter(&request)
        })
    }
}
impl Drop for GraphicsAdapter {
    fn drop(&mut self) {
        if let Some(handle) = self.handle.take() {
            // SAFETY: unwind fallback; normal completion explicitly checks close status.
            let _ = unsafe { D3DKMTCloseAdapter(&D3DKMT_CLOSEADAPTER { hAdapter: handle }) };
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    #[ignore = "requires a native Windows host with a healthy WDDM GPU"]
    fn present_wddm_adapter_provides_current_scheduler_and_memory_readings() {
        let mut collector = WindowsGpuCollector::new();
        let origin = Instant::now();
        collector.collect(&mut Snapshot::default(), origin);
        std::thread::sleep(std::time::Duration::from_millis(250));
        let mut snapshot = Snapshot::default();
        collector.collect(&mut snapshot, origin);
        assert!(
            !snapshot.monitors.is_empty(),
            "no physical adapter on this test host"
        );
        for monitor in &snapshot.monitors {
            for suffix in ["usage", "vram", "shared-used"] {
                let sensor = format!("{}/{suffix}", monitor.id);
                let reading = snapshot
                    .readings
                    .iter()
                    .find(|r| r.sensor_id == sensor)
                    .unwrap();
                assert_eq!(reading.availability, Availability::Available, "{reading:?}");
                assert!(!reading.observations.is_empty());
            }
        }
    }

    #[test]
    fn windows_pci_ids_and_strings_are_validated() {
        assert_eq!(vendor_id(r"PCI\VEN_8086&DEV_9A49\instance"), Some(0x8086));
        assert_eq!(vendor_id(r"PCI\VEN_1002&DEV_1\instance"), Some(0x1002));
        assert_eq!(vendor_id(r"PCI\VEN_10DE&DEV_1\instance"), Some(0x10de));
        assert_eq!(vendor_id(r"ROOT\BasicRender\0000"), None);
        assert!(wide_string(&[65]).is_err());
        assert!(wide_string(&[0xd800, 0]).is_err());
        assert_eq!(wide_string(&[65, 0]).unwrap(), "A");
    }
}
