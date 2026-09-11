//! No caller-selected registers, module paths, or operations cross this boundary.
use super::{
    identity::{own, raw},
    protocol::{package_affinity, supported_cpu},
};
use std::os::windows::io::OwnedHandle;
use windows::{
    Win32::{
        Storage::FileSystem::{
            CreateFileW, FILE_FLAGS_AND_ATTRIBUTES, FILE_SHARE_READ, FILE_SHARE_WRITE,
            OPEN_EXISTING,
        },
        System::{
            IO::DeviceIoControl,
            SystemInformation::{
                GROUP_AFFINITY, GetLogicalProcessorInformationEx, RelationProcessorPackage,
            },
            Threading::{GetCurrentThread, SetThreadGroupAffinity},
        },
    },
    core::w,
};
const MODULE: &[u8] = include_bytes!("../../../../vendor/pawnio-intel-msr/IntelMSR.bin");
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
pub(super) struct Driver {
    handle: OwnedHandle,
    group: u16,
    mask: u64,
}
impl Driver {
    pub fn open() -> std::result::Result<Self, u64> {
        #[cfg(not(target_arch = "x86_64"))]
        {
            return Err(1);
        }
        #[cfg(target_arch = "x86_64")]
        {
            // CPUID is supported on x86_64. Leaf availability is checked before use.
            let root = std::arch::x86_64::__cpuid(0);
            if root.eax < 6 {
                return Err(1);
            }
            let vendor: [u8; 12] = [
                root.ebx.to_le_bytes(),
                root.edx.to_le_bytes(),
                root.ecx.to_le_bytes(),
            ]
            .concat()
            .try_into()
            .expect("12 vendor bytes");
            let signature = std::arch::x86_64::__cpuid(1).eax;
            let thermal = std::arch::x86_64::__cpuid(6).eax;
            if !supported_cpu(&vendor, signature, thermal) {
                return Err(1);
            }
            // Fixed bounded buffer avoids an unbounded topology-allocation/retry loop.
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
            let bytes = unsafe {
                std::slice::from_raw_parts(storage.as_ptr().cast::<u8>(), length as usize)
            };
            let (group, mask) = package_affinity(bytes).map_err(|_| 2u64)?;
            let _affinity = Affinity::pin(group, mask)?;
            // SAFETY: fixed device name and read/write transport access. No install or tuning IOCTL.
            let handle = own(unsafe {
                CreateFileW(
                    w!("\\\\?\\GLOBALROOT\\Device\\PawnIO"),
                    3,
                    FILE_SHARE_READ | FILE_SHARE_WRITE,
                    None,
                    OPEN_EXISTING,
                    FILE_FLAGS_AND_ATTRIBUTES(0),
                    None,
                )
            }
            .map_err(|_| 3u64)?);
            let mut returned = 0;
            // SAFETY: immutable embedded signed module, exact input size, no output buffer.
            unsafe {
                DeviceIoControl(
                    raw(&handle),
                    0xA1B22084,
                    Some(MODULE.as_ptr().cast()),
                    MODULE.len() as u32,
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
            Ok(Self {
                handle,
                group,
                mask,
            })
        }
    }
    pub fn sample(&self) -> std::result::Result<(u64, u64), u64> {
        let _affinity = Affinity::pin(self.group, self.mask)?;
        Ok((self.read_fixed(0x1a2)?, self.read_fixed(0x1b1)?))
    }
    fn read_fixed(&self, register: u64) -> std::result::Result<u64, u64> {
        // Defense in depth: only these two read-only operations are implemented here.
        if !matches!(register, 0x1a2 | 0x1b1) {
            return Err(5);
        }
        let mut input = [0u8; 40];
        input[..14].copy_from_slice(b"ioctl_read_msr\0");
        input[32..].copy_from_slice(&register.to_le_bytes());
        let mut output = [0u8; 8];
        let mut returned = 0;
        // SAFETY: fixed initialized buffers; synchronous IOCTL owns them for the call.
        unsafe {
            DeviceIoControl(
                raw(&self.handle),
                0xA1B22104,
                Some(input.as_ptr().cast()),
                input.len() as u32,
                Some(output.as_mut_ptr().cast()),
                output.len() as u32,
                Some(&mut returned),
                None,
            )
        }
        .map_err(|_| 5u64)?;
        if returned != 8 {
            return Err(5);
        }
        Ok(u64::from_le_bytes(output))
    }
}
