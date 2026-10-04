//! Fixed-operation access to the approved PawnIO CPU temperature modules.
use super::{
    identity::{own, raw},
    protocol::{Backend, package_affinity},
};
use std::os::windows::io::OwnedHandle;
use windows::{
    Win32::{
        Foundation::{WAIT_ABANDONED, WAIT_OBJECT_0, WAIT_TIMEOUT},
        Storage::FileSystem::{
            CreateFileW, FILE_FLAGS_AND_ATTRIBUTES, FILE_SHARE_READ, FILE_SHARE_WRITE,
            OPEN_EXISTING,
        },
        System::{
            IO::DeviceIoControl,
            SystemInformation::{
                GROUP_AFFINITY, GetLogicalProcessorInformationEx, RelationProcessorPackage,
            },
            Threading::{
                CreateMutexExW, GetCurrentThread, MUTEX_MODIFY_STATE, ReleaseMutex,
                SYNCHRONIZATION_SYNCHRONIZE, SetThreadGroupAffinity, WaitForSingleObject,
            },
        },
    },
    core::{HRESULT, PCWSTR, w},
};

const INTEL_MODULE: &[u8] = include_bytes!("../../../../vendor/pawnio-intel-msr/IntelMSR.bin");
const AMD_MODULE: &[u8] = include_bytes!("../../../../vendor/pawnio-amd-smn/AMDFamily17.bin");
const AMD_SMN_TEMPERATURE_OFFSET: u64 = 0x59800;
const PCI_MUTEX_TIMEOUT_MS: u32 = 250;
const IOCTL_LOAD_MODULE: u32 = 0xA1B22084;
const IOCTL_EXECUTE_MODULE: u32 = 0xA1B22104;

struct Affinity(GROUP_AFFINITY);

impl Affinity {
    fn pin(group: u16, mask: u64) -> std::result::Result<Self, u64> {
        let desired = GROUP_AFFINITY {
            Mask: mask as usize,
            Group: group,
            ..Default::default()
        };
        let mut previous = GROUP_AFFINITY::default();
        // SAFETY: both structures are live; current-thread pseudo handle is borrowed.
        unsafe { SetThreadGroupAffinity(GetCurrentThread(), &desired, Some(&mut previous)) }
            .ok()
            .map_err(|_| 6u64)?;
        Ok(Self(previous))
    }
}

impl Drop for Affinity {
    fn drop(&mut self) {
        // SAFETY: used and dropped on the same helper thread, restoring its saved affinity.
        let _ = unsafe { SetThreadGroupAffinity(GetCurrentThread(), &self.0, None) };
    }
}

/// Owns the cross-process PCI mutex while one fixed SMN read is in progress.
struct PciMutex(OwnedHandle);

impl PciMutex {
    /// Acquires the global PawnIO/PCI mutex with the minimum rights and a fixed timeout.
    fn acquire() -> std::result::Result<Self, u64> {
        Self::acquire_named(w!("Global\\Access_PCI"), PCI_MUTEX_TIMEOUT_MS)
    }

    fn acquire_named(name: PCWSTR, timeout_ms: u32) -> std::result::Result<Self, u64> {
        let rights = SYNCHRONIZATION_SYNCHRONIZE | MUTEX_MODIFY_STATE;
        // SAFETY: caller supplies a NUL-terminated constant/test name; no initial ownership,
        // with only wait/release rights requested.
        let handle = own(unsafe { CreateMutexExW(None, name, 0, rights.0) }.map_err(|_| 5u64)?);
        // WAIT_ABANDONED also grants ownership; the module rewrites the SMN index per read.
        let wait = unsafe { WaitForSingleObject(raw(&handle), timeout_ms) };
        map_pci_mutex_wait(wait).map(|()| Self(handle))
    }
}

impl Drop for PciMutex {
    fn drop(&mut self) {
        // SAFETY: this guard is constructed only after this helper thread owns the mutex.
        let _ = unsafe { ReleaseMutex(raw(&self.0)) };
    }
}

pub(super) struct Driver {
    handle: OwnedHandle,
    backend: Backend,
    package_affinity: (u16, u64),
}

impl Driver {
    /// Selects an approved CPUID backend and checks only whether the PawnIO device exists.
    /// This read-only preflight performs no module load, register read, service start, or install.
    pub fn preflight() -> std::result::Result<Backend, String> {
        let backend = current_backend().ok_or_else(|| {
            "CPU temperature supports Intel Alder Lake model 0x9a or AMD Zen 3 family 0x19 model 0x21".to_owned()
        })?;
        match open_device(0) {
            Ok(_device) => {}
            Err(error) if is_access_denied(error.code()) => {}
            Err(error) => {
                return Err(format!(
                    "PawnIO device is missing or unavailable; install the approved driver separately: {error}"
                ));
            }
        }
        Ok(backend)
    }

    pub fn backend(&self) -> Backend {
        self.backend
    }

    pub fn open() -> std::result::Result<Self, u64> {
        let backend = current_backend().ok_or(1u64)?;
        let package_affinity = read_package_affinity()?;
        let _thread_affinity = if backend == Backend::Intel {
            Some(Affinity::pin(package_affinity.0, package_affinity.1)?)
        } else {
            None
        };
        let handle = open_device(3).map_err(|_| 3u64)?;
        let module = match backend {
            Backend::Intel => INTEL_MODULE,
            Backend::AmdZen3 => AMD_MODULE,
        };
        load_module(&handle, module)?;
        Ok(Self {
            handle,
            backend,
            package_affinity,
        })
    }

    pub fn sample(&self) -> std::result::Result<(u64, u64), u64> {
        match self.backend {
            Backend::Intel => {
                let (group, mask) = self.package_affinity;
                let _affinity = Affinity::pin(group, mask)?;
                Ok((self.read_fixed_msr(0x1a2)?, self.read_fixed_msr(0x1b1)?))
            }
            Backend::AmdZen3 => {
                let _pci_mutex = PciMutex::acquire()?;
                Ok((self.read_fixed_smn(AMD_SMN_TEMPERATURE_OFFSET)?, 0))
            }
        }
    }

    fn read_fixed_msr(&self, register: u64) -> std::result::Result<u64, u64> {
        if !matches!(register, 0x1a2 | 0x1b1) {
            return Err(5);
        }
        let mut input = [0u8; 40];
        let command = b"ioctl_read_msr\0";
        input[..command.len()].copy_from_slice(command);
        input[32..].copy_from_slice(&register.to_le_bytes());
        let mut output = [0u8; 8];
        let mut returned = 0;
        // SAFETY: fixed initialized buffers; synchronous IOCTL owns them for the call.
        unsafe {
            DeviceIoControl(
                raw(&self.handle),
                IOCTL_EXECUTE_MODULE,
                Some(input.as_ptr().cast()),
                input.len() as u32,
                Some(output.as_mut_ptr().cast()),
                output.len() as u32,
                Some(&mut returned),
                None,
            )
        }
        .map_err(|_| 5u64)?;
        decode_module_output(output, returned)
    }

    fn read_fixed_smn(&self, offset: u64) -> std::result::Result<u64, u64> {
        let input = build_smn_read_input(offset)?;
        let mut output = [0u8; 8];
        let mut returned = 0;
        // SAFETY: fixed command/offset, initialized buffers, and a held PCI mutex.
        unsafe {
            DeviceIoControl(
                raw(&self.handle),
                IOCTL_EXECUTE_MODULE,
                Some(input.as_ptr().cast()),
                input.len() as u32,
                Some(output.as_mut_ptr().cast()),
                output.len() as u32,
                Some(&mut returned),
                None,
            )
        }
        .map_err(|_| 5u64)?;
        decode_module_output(output, returned)
    }
}

/// Returns a backend only for CPU signatures approved by the thermal protocol.
pub(super) fn current_backend() -> Option<Backend> {
    #[cfg(target_arch = "x86_64")]
    {
        // CPUID leaf 1 exists on x86_64; leaf 6 is optional for AMD but required for Intel.
        let root = std::arch::x86_64::__cpuid(0);
        if root.eax < 1 {
            return None;
        }
        let mut vendor = [0; 12];
        vendor[..4].copy_from_slice(&root.ebx.to_le_bytes());
        vendor[4..8].copy_from_slice(&root.edx.to_le_bytes());
        vendor[8..].copy_from_slice(&root.ecx.to_le_bytes());
        let signature = std::arch::x86_64::__cpuid(1).eax;
        let thermal = if root.eax >= 6 {
            std::arch::x86_64::__cpuid(6).eax
        } else {
            0
        };
        Backend::for_cpu(&vendor, signature, thermal)
    }
    #[cfg(not(target_arch = "x86_64"))]
    {
        None
    }
}

/// Uses a no-access open to detect the fixed PawnIO device without reading driver state.
fn open_device(access: u32) -> std::result::Result<OwnedHandle, windows::core::Error> {
    // SAFETY: fixed device name; preflight passes zero desired access and open passes only
    // the existing read/write transport access required by the approved PawnIO client.
    let handle = unsafe {
        CreateFileW(
            w!("\\\\?\\GLOBALROOT\\Device\\PawnIO"),
            access,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            FILE_FLAGS_AND_ATTRIBUTES(0),
            None,
        )
    }?;
    Ok(own(handle))
}

/// Recognizes only Win32 access denied so preflight can preserve a later UAC retry.
fn is_access_denied(code: HRESULT) -> bool {
    code.0 as u32 == 0x8007_0005
}

/// Loads exactly one embedded official module and rejects unexpected output bytes.
fn load_module(handle: &OwnedHandle, module: &[u8]) -> std::result::Result<(), u64> {
    let input_length = u32::try_from(module.len()).map_err(|_| 4u64)?;
    let mut returned = 0;
    // SAFETY: immutable embedded signed module, checked input size, and no output buffer.
    unsafe {
        DeviceIoControl(
            raw(handle),
            IOCTL_LOAD_MODULE,
            Some(module.as_ptr().cast()),
            input_length,
            None,
            0,
            Some(&mut returned),
            None,
        )
    }
    .map_err(|_| 4u64)?;
    if returned != 0 {
        return Err(4);
    }
    Ok(())
}

/// Reads the bounded topology and rejects anything except one physical CPU package.
fn read_package_affinity() -> std::result::Result<(u16, u64), u64> {
    let mut storage = vec![0u64; 8192];
    let mut length = 65536u32;
    // SAFETY: u64-aligned 64 KiB output; parser validates every consumed length.
    unsafe {
        GetLogicalProcessorInformationEx(
            RelationProcessorPackage,
            Some(storage.as_mut_ptr().cast()),
            &mut length,
        )
    }
    .map_err(|_| 2u64)?;
    if length > 65536 {
        return Err(2);
    }
    let bytes =
        unsafe { std::slice::from_raw_parts(storage.as_ptr().cast::<u8>(), length as usize) };
    package_affinity(bytes).map_err(|_| 2u64)
}

/// Encodes the one approved 32-byte PawnIO command plus its little-endian u64 argument.
fn build_smn_read_input(offset: u64) -> std::result::Result<[u8; 40], u64> {
    if offset != AMD_SMN_TEMPERATURE_OFFSET {
        return Err(5);
    }
    let mut input = [0; 40];
    let command = b"ioctl_read_smn\0";
    input[..command.len()].copy_from_slice(command);
    input[32..].copy_from_slice(&offset.to_le_bytes());
    Ok(input)
}

/// Accepts only the exact eight-byte PawnIO result used by both fixed backends.
fn decode_module_output(output: [u8; 8], returned: u32) -> std::result::Result<u64, u64> {
    if returned != output.len() as u32 {
        return Err(5);
    }
    Ok(u64::from_le_bytes(output))
}

/// Distinguishes the bounded lock timeout from mutex API or wait failures.
fn map_pci_mutex_wait(
    wait: windows::Win32::Foundation::WAIT_EVENT,
) -> std::result::Result<(), u64> {
    if wait == WAIT_OBJECT_0 || wait == WAIT_ABANDONED {
        Ok(())
    } else if wait == WAIT_TIMEOUT {
        Err(8)
    } else {
        Err(5)
    }
}

#[cfg(test)]
mod tests {
    use super::{
        AMD_SMN_TEMPERATURE_OFFSET, PciMutex, build_smn_read_input, decode_module_output,
        is_access_denied,
    };
    use std::{
        sync::mpsc,
        thread,
        time::{Duration, Instant, SystemTime, UNIX_EPOCH},
    };
    use windows::{
        Win32::{
            Foundation::{WAIT_ABANDONED, WAIT_OBJECT_0},
            System::Threading::{
                CreateMutexExW, MUTEX_MODIFY_STATE, ReleaseMutex, SYNCHRONIZATION_SYNCHRONIZE,
                WaitForSingleObject,
            },
        },
        core::{HRESULT, PCWSTR},
    };

    #[test]
    fn smn_request_has_fixed_command_padding_and_little_endian_offset() {
        let mut expected = [0u8; 40];
        expected[..15].copy_from_slice(b"ioctl_read_smn\0");
        expected[32..].copy_from_slice(&AMD_SMN_TEMPERATURE_OFFSET.to_le_bytes());
        assert_eq!(
            build_smn_read_input(AMD_SMN_TEMPERATURE_OFFSET),
            Ok(expected)
        );
    }

    #[test]
    fn smn_request_rejects_every_other_offset() {
        for offset in [
            0,
            AMD_SMN_TEMPERATURE_OFFSET - 4,
            AMD_SMN_TEMPERATURE_OFFSET + 4,
            u64::MAX,
        ] {
            assert_eq!(build_smn_read_input(offset), Err(5));
        }
    }

    #[test]
    fn module_output_requires_exactly_eight_bytes() {
        let value = 0x1234_5678_9abc_def0u64;
        assert_eq!(decode_module_output(value.to_le_bytes(), 8), Ok(value));
        assert_eq!(decode_module_output([0; 8], 7), Err(5));
    }

    #[test]
    fn probe_access_denied_preserves_the_elevation_retry_path() {
        assert!(is_access_denied(HRESULT(0x8007_0005u32 as i32)));
        assert!(!is_access_denied(HRESULT(0x8007_0002u32 as i32)));
    }

    #[test]
    fn pci_mutex_acquisition_times_out_while_another_thread_owns_it() {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map_or(0, |duration| duration.as_nanos());
        let name = format!("Local\\RamagPciMutexTest-{}-{nonce}", std::process::id());
        let name_wide: Vec<u16> = name.encode_utf16().chain(std::iter::once(0)).collect();
        let owner_name = name_wide.clone();
        let (ready_tx, ready_rx) = mpsc::channel();
        let (release_tx, release_rx) = mpsc::channel();
        let owner = thread::spawn(move || {
            let rights = SYNCHRONIZATION_SYNCHRONIZE | MUTEX_MODIFY_STATE;
            // SAFETY: the test owns a unique NUL-terminated name and closes its owned handle.
            let created = unsafe { CreateMutexExW(None, PCWSTR(owner_name.as_ptr()), 0, rights.0) };
            let Ok(created) = created else {
                let _ = ready_tx.send(false);
                return;
            };
            let handle = super::own(created);
            let wait = unsafe { WaitForSingleObject(super::raw(&handle), 0) };
            if wait != WAIT_OBJECT_0 && wait != WAIT_ABANDONED {
                let _ = ready_tx.send(false);
                return;
            }
            if ready_tx.send(true).is_err() {
                let _ = unsafe { ReleaseMutex(super::raw(&handle)) };
                return;
            }
            let _ = release_rx.recv_timeout(Duration::from_secs(2));
            let _ = unsafe { ReleaseMutex(super::raw(&handle)) };
        });

        let owner_ready = ready_rx
            .recv_timeout(Duration::from_secs(1))
            .unwrap_or(false);
        let started = Instant::now();
        let result = if owner_ready {
            PciMutex::acquire_named(PCWSTR(name_wide.as_ptr()), 30).map(|_| ())
        } else {
            Err(5)
        };
        let elapsed = started.elapsed();
        let _ = release_tx.send(());
        assert!(owner.join().is_ok(), "mutex owner thread panicked");
        assert!(owner_ready, "could not establish the test mutex owner");
        assert_eq!(result, Err(8));
        assert!(elapsed < Duration::from_secs(1));
    }
}
