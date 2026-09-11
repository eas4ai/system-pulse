//! Retained caller and executable identities for the temperature session only.
use super::protocol::Result;
use std::{
    fs::{File, OpenOptions},
    os::windows::{
        ffi::OsStringExt,
        fs::OpenOptionsExt,
        io::{AsRawHandle, FromRawHandle, OwnedHandle},
    },
    path::{Path, PathBuf},
};
use windows::{
    Win32::{
        Foundation::{FILETIME, HANDLE, WAIT_TIMEOUT},
        Security::{GetTokenInformation, TOKEN_ELEVATION, TOKEN_QUERY, TokenElevation},
        Storage::FileSystem::{
            FILE_ID_INFO, FILE_READ_ATTRIBUTES, FILE_SHARE_READ, FileIdInfo,
            GetFileInformationByHandleEx,
        },
        System::Threading::{
            GetCurrentProcess, GetProcessId, GetProcessTimes, OpenProcess, OpenProcessToken,
            PROCESS_NAME_WIN32, PROCESS_QUERY_LIMITED_INFORMATION, PROCESS_SYNCHRONIZE,
            QueryFullProcessImageNameW, WaitForSingleObject,
        },
    },
    core::PWSTR,
};
pub(super) fn raw(handle: &OwnedHandle) -> HANDLE {
    HANDLE(handle.as_raw_handle())
}
pub(super) fn own(handle: HANDLE) -> OwnedHandle {
    // SAFETY: callers pass newly returned, valid owned Win32 handles exactly once.
    unsafe { OwnedHandle::from_raw_handle(handle.0) }
}
pub(super) fn creation_time(handle: HANDLE) -> Result<u64> {
    let (mut created, mut exit, mut kernel, mut user) = (
        FILETIME::default(),
        FILETIME::default(),
        FILETIME::default(),
        FILETIME::default(),
    );
    // SAFETY: caller retains the handle; output slots are live and distinct.
    unsafe { GetProcessTimes(handle, &mut created, &mut exit, &mut kernel, &mut user) }
        .map_err(|e| format!("Read caller creation time: {e}"))?;
    let ticks = (u64::from(created.dwHighDateTime) << 32) | u64::from(created.dwLowDateTime);
    if ticks == 0 {
        return Err("Zero caller creation time".into());
    }
    Ok(ticks)
}
pub(super) fn alive(handle: HANDLE) -> bool {
    // SAFETY: caller retains a process handle with synchronization access.
    unsafe { WaitForSingleObject(handle, 0) == WAIT_TIMEOUT }
}
pub(super) struct LockedExecutable {
    _file: File,
    identity: (u64, [u8; 16]),
    pub path: PathBuf,
}
impl LockedExecutable {
    pub fn open(path: &Path) -> Result<Self> {
        let path =
            std::fs::canonicalize(path).map_err(|e| format!("Resolve helper executable: {e}"))?;
        // Share only reading: retain the file against replacement, writes and deletion.
        let file = OpenOptions::new()
            .access_mode(FILE_READ_ATTRIBUTES.0)
            .share_mode(FILE_SHARE_READ.0)
            .open(&path)
            .map_err(|e| format!("Pin helper executable: {e}"))?;
        let mut info = FILE_ID_INFO::default();
        // SAFETY: live file handle; aligned output and matching documented class/size.
        unsafe {
            GetFileInformationByHandleEx(
                HANDLE(file.as_raw_handle()),
                FileIdInfo,
                (&mut info as *mut FILE_ID_INFO).cast(),
                std::mem::size_of_val(&info) as u32,
            )
        }
        .map_err(|e| format!("Read helper file identity: {e}"))?;
        Ok(Self {
            _file: file,
            identity: (info.VolumeSerialNumber, info.FileId.Identifier),
            path,
        })
    }
    pub fn current() -> Result<Self> {
        Self::open(&std::env::current_exe().map_err(|e| format!("Locate helper executable: {e}"))?)
    }
    pub fn matches(&self, other: &Self) -> bool {
        self.identity == other.identity
    }
}
pub(super) struct Caller {
    pub handle: OwnedHandle,
    _executable: LockedExecutable,
    _own_executable: LockedExecutable,
}
impl Caller {
    pub fn open(pid: u32, created: u64) -> Result<Self> {
        // SAFETY: value-only PID, no inheritance; resulting process object remains owned.
        let handle = own(unsafe {
            OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_SYNCHRONIZE,
                false,
                pid,
            )
        }
        .map_err(|e| format!("Open temperature caller: {e}"))?);
        if unsafe { GetProcessId(raw(&handle)) } != pid
            || creation_time(raw(&handle))? != created
            || !alive(raw(&handle))
        {
            return Err("Temperature caller identity changed or exited".into());
        }
        let mut path = vec![0u16; 32768];
        let mut length = path.len() as u32;
        // SAFETY: sized, writable UTF-16 buffer and retained process handle.
        unsafe {
            QueryFullProcessImageNameW(
                raw(&handle),
                PROCESS_NAME_WIN32,
                PWSTR(path.as_mut_ptr()),
                &mut length,
            )
        }
        .map_err(|e| format!("Locate caller executable: {e}"))?;
        let executable = LockedExecutable::open(&PathBuf::from(std::ffi::OsString::from_wide(
            &path[..length as usize],
        )))?;
        let own_executable = LockedExecutable::current()?;
        if !executable.matches(&own_executable) {
            return Err("Temperature caller is a different executable".into());
        }
        Ok(Self {
            handle,
            _executable: executable,
            _own_executable: own_executable,
        })
    }
}
pub(super) fn token() -> Result<OwnedHandle> {
    let mut token = HANDLE::default();
    // SAFETY: current process is a borrowed pseudo handle; token output transfers ownership.
    unsafe { OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &mut token) }
        .map_err(|e| format!("Open current token: {e}"))?;
    Ok(own(token))
}
pub(super) fn elevated() -> Result<bool> {
    let token = token()?;
    let mut elevation = TOKEN_ELEVATION::default();
    let mut length = 0;
    // SAFETY: matching token information class, aligned output and exact size.
    unsafe {
        GetTokenInformation(
            raw(&token),
            TokenElevation,
            Some((&mut elevation as *mut TOKEN_ELEVATION).cast()),
            std::mem::size_of_val(&elevation) as u32,
            &mut length,
        )
    }
    .map_err(|e| format!("Read elevation: {e}"))?;
    Ok(elevation.TokenIsElevated != 0)
}
