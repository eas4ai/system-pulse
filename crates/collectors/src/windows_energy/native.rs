//! Read-only SetupAPI/EMI boundary; all driver replies are length checked before parsing.
use super::*;
use windows::{
    Win32::{
        Devices::DeviceAndDriverInstallation::*,
        Foundation::{
            CloseHandle, ERROR_INSUFFICIENT_BUFFER, ERROR_NO_MORE_ITEMS, GENERIC_READ, HANDLE, HWND,
        },
        Storage::FileSystem::{
            CreateFileW, FILE_ATTRIBUTE_NORMAL, FILE_SHARE_READ, FILE_SHARE_WRITE, OPEN_EXISTING,
        },
        System::{IO::DeviceIoControl, Power::*},
    },
    core::{GUID, HRESULT, PCWSTR},
};

pub(super) struct Native;
const ENERGY_METER: GUID = GUID::from_u128(0x45bd8344_7ed6_49cf_a440_c276c933b053);
struct DeviceSet(HDEVINFO);
impl Drop for DeviceSet {
    fn drop(&mut self) {
        // SAFETY: this value exclusively owns the successful SetupAPI result.
        let _ = unsafe { SetupDiDestroyDeviceInfoList(self.0) };
    }
}
struct Meter(HANDLE);
impl Drop for Meter {
    fn drop(&mut self) {
        // SAFETY: this value exclusively owns the successful CreateFileW result.
        let _ = unsafe { CloseHandle(self.0) };
    }
}
fn error(operation: &str, e: windows::core::Error) -> String {
    format!("{operation}: {e}")
}
fn wide(words: &[u16]) -> Result<String> {
    let end = words
        .iter()
        .position(|&w| w == 0)
        .ok_or("Unterminated EMI device path or identity")?;
    if end == 0 {
        return Err("Empty EMI device path or identity".into());
    }
    String::from_utf16(&words[..end]).map_err(|e| format!("Invalid EMI device UTF-16: {e}"))
}
impl Backend for Native {
    fn inventory(&mut self) -> Result<Vec<Device>> {
        // SAFETY: valid GUID and no borrowed enumerator/window.
        let set = DeviceSet(
            unsafe {
                SetupDiGetClassDevsW(
                    Some(&ENERGY_METER),
                    PCWSTR::null(),
                    HWND::default(),
                    DIGCF_PRESENT | DIGCF_DEVICEINTERFACE,
                )
            }
            .map_err(|e| error("Discover present EMI interfaces", e))?,
        );
        let mut devices = Vec::new();
        for index in 0..=MAX_DEVICES {
            let mut interface = SP_DEVICE_INTERFACE_DATA {
                cbSize: std::mem::size_of::<SP_DEVICE_INTERFACE_DATA>() as u32,
                ..Default::default()
            };
            // SAFETY: initialized output and live device set.
            if let Err(e) = unsafe {
                SetupDiEnumDeviceInterfaces(
                    set.0,
                    None,
                    &ENERGY_METER,
                    index as u32,
                    &mut interface,
                )
            } {
                if e.code() == HRESULT::from_win32(ERROR_NO_MORE_ITEMS.0) {
                    return Ok(devices);
                }
                return Err(error("Read EMI interface entry", e));
            }
            if index == MAX_DEVICES {
                return Err("EMI interface enumeration exceeds 128 devices".into());
            }
            let mut needed = 0;
            // SAFETY: size query has no output buffer and a valid size pointer.
            let result = unsafe {
                SetupDiGetDeviceInterfaceDetailW(
                    set.0,
                    &interface,
                    None,
                    0,
                    Some(&mut needed),
                    None,
                )
            };
            match result {
                Err(e) if e.code() == HRESULT::from_win32(ERROR_INSUFFICIENT_BUFFER.0) => {}
                Err(e) => return Err(error("Read EMI interface detail size", e)),
                Ok(()) => {
                    return Err(
                        "EMI detail size query unexpectedly succeeded without a buffer".into(),
                    );
                }
            }
            if !(8..=65536).contains(&needed) {
                return Err("Invalid EMI interface detail size".into());
            }
            // u64 storage guarantees the native detail structure's alignment.
            let mut storage = vec![0u64; (needed as usize).div_ceil(8)];
            let detail = storage
                .as_mut_ptr()
                .cast::<SP_DEVICE_INTERFACE_DETAIL_DATA_W>();
            let mut info = SP_DEVINFO_DATA {
                cbSize: std::mem::size_of::<SP_DEVINFO_DATA>() as u32,
                ..Default::default()
            };
            let capacity = needed;
            // SAFETY: aligned allocation covers capacity bytes, and both cbSize fields agree with the SDK.
            unsafe {
                (*detail).cbSize = std::mem::size_of::<SP_DEVICE_INTERFACE_DETAIL_DATA_W>() as u32;
                SetupDiGetDeviceInterfaceDetailW(
                    set.0,
                    &interface,
                    Some(detail),
                    capacity,
                    Some(&mut needed),
                    Some(&mut info),
                )
            }
            .map_err(|e| error("Read EMI interface detail", e))?;
            if needed < 8 || needed > capacity || !needed.is_multiple_of(2) {
                return Err("Invalid returned EMI interface detail size".into());
            }
            // SAFETY: DevicePath starts at byte 4; the validated returned length bounds this read.
            let path_words = unsafe {
                std::slice::from_raw_parts(
                    std::ptr::addr_of!((*detail).DevicePath).cast::<u16>(),
                    (needed as usize - 4) / 2,
                )
            };
            let path = wide(path_words)?;
            let mut identity = [0u16; 512];
            let mut id_size = 0;
            // SAFETY: initialized bounded output and device entry belonging to the live set.
            unsafe {
                SetupDiGetDeviceInstanceIdW(set.0, &info, Some(&mut identity), Some(&mut id_size))
            }
            .map_err(|e| error("Read EMI PnP identity", e))?;
            if id_size == 0 || id_size as usize > identity.len() {
                return Err("Invalid EMI PnP identity length".into());
            }
            devices.push(Device {
                instance: wide(&identity[..id_size as usize])?,
                path,
            });
        }
        unreachable!("bounded enumeration always returns")
    }
    fn sample(&mut self, device: &Device, origin: Instant) -> Result<Sample> {
        let name: Vec<u16> = device.path.encode_utf16().chain(Some(0)).collect();
        // SAFETY: terminated path, no security/template pointers; successful handle is owned immediately.
        let meter = Meter(
            unsafe {
                CreateFileW(
                    PCWSTR(name.as_ptr()),
                    GENERIC_READ.0,
                    FILE_SHARE_READ | FILE_SHARE_WRITE,
                    None,
                    OPEN_EXISTING,
                    FILE_ATTRIBUTE_NORMAL,
                    HANDLE::default(),
                )
            }
            .map_err(|e| error("Open EMI interface read-only", e))?,
        );
        let version = meter.query(IOCTL_EMI_GET_VERSION, 2)?;
        let version = word(&version, 0)?;
        if !matches!(version, 1 | 2) {
            return Err(format!("Unsupported EMI version {version}"));
        }
        let size = meter.query(IOCTL_EMI_GET_METADATA_SIZE, 4)?;
        let size = u32::from_le_bytes(size.try_into().expect("validated four-byte reply")) as usize;
        if !(68..=MAX_METADATA).contains(&size) {
            return Err("EMI metadata size outside bounds".into());
        }
        let metadata = parse_metadata(version, &meter.query(IOCTL_EMI_GET_METADATA, size)?)?;
        let started = origin.elapsed().as_nanos().min(u64::MAX as u128) as u64;
        let bytes = meter.query(IOCTL_EMI_GET_MEASUREMENT, metadata.channels.len() * 16)?;
        let ended = origin.elapsed().as_nanos().min(u64::MAX as u128) as u64;
        let values = parse_values(&bytes, metadata.channels.len())?;
        Ok(Sample {
            metadata,
            values,
            started,
            ended,
        })
    }
}
impl Meter {
    fn query(&self, code: u32, size: usize) -> Result<Vec<u8>> {
        let mut bytes = vec![0u8; size];
        let mut returned = 0;
        // SAFETY: owned live handle, no input, synchronous call with valid bounded output and length pointer.
        unsafe {
            DeviceIoControl(
                self.0,
                code,
                None,
                0,
                Some(bytes.as_mut_ptr().cast()),
                size as u32,
                Some(&mut returned),
                None,
            )
        }
        .map_err(|e| error(&format!("EMI IOCTL 0x{code:x}"), e))?;
        if returned as usize != size {
            return Err(format!(
                "EMI IOCTL 0x{code:x} returned {returned} bytes; expected {size}"
            ));
        }
        Ok(bytes)
    }
}
