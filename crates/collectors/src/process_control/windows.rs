//! Windows process actions keep an independently verified process object alive.
use super::windows_protocol::{self, Failure, Request};
use super::{ProcessActionOutcome, ProcessIdentity, ProcessSignal};
use ::windows::{
    Win32::{
        Foundation::{
            BOOL, ERROR_ACCESS_DENIED, ERROR_CANCELLED, ERROR_FAIL_SHUTDOWN,
            ERROR_INVALID_PARAMETER, ERROR_SUCCESS, FILETIME, HANDLE, HWND, LPARAM, WAIT_FAILED,
            WAIT_OBJECT_0, WAIT_TIMEOUT, WIN32_ERROR,
        },
        Security::{GetTokenInformation, TOKEN_ELEVATION, TOKEN_QUERY, TokenElevation},
        Storage::FileSystem::{
            BY_HANDLE_FILE_INFORMATION, FILE_READ_ATTRIBUTES, GetFileInformationByHandle,
        },
        System::{
            Com::{
                COINIT_APARTMENTTHREADED, COINIT_DISABLE_OLE1DDE, CoInitializeEx, CoUninitialize,
            },
            RestartManager::{
                CCH_RM_SESSION_KEY, RM_PROCESS_INFO, RM_UNIQUE_PROCESS, RmCritical, RmEndSession,
                RmGetList, RmMainWindow, RmRebootReasonPermissionDenied, RmRegisterResources,
                RmShutdown, RmStartSession,
            },
            Threading::{
                GetCurrentProcess, GetExitCodeProcess, GetProcessId, GetProcessInformation,
                GetProcessTimes, IsProcessCritical, OpenProcess, OpenProcessToken,
                PROCESS_ACCESS_RIGHTS, PROCESS_NAME_WIN32, PROCESS_PROTECTION_LEVEL_INFORMATION,
                PROCESS_QUERY_LIMITED_INFORMATION, PROCESS_SYNCHRONIZE, PROCESS_TERMINATE,
                PROTECTION_LEVEL_NONE, ProcessProtectionLevelInfo, QueryFullProcessImageNameW,
                TerminateProcess, WaitForSingleObject,
            },
        },
        UI::{
            Shell::{
                SEE_MASK_FLAG_NO_UI, SEE_MASK_NOASYNC, SEE_MASK_NOCLOSEPROCESS, SHELLEXECUTEINFOW,
                ShellExecuteExW,
            },
            WindowsAndMessaging::{EnumWindows, GetWindowThreadProcessId, SW_HIDE},
        },
    },
    core::{PCWSTR, PWSTR, w},
};
use std::{
    ffi::OsString,
    fs::OpenOptions,
    os::windows::{
        ffi::{OsStrExt, OsStringExt},
        fs::OpenOptionsExt,
        io::{AsRawHandle, FromRawHandle, OwnedHandle},
    },
    path::PathBuf,
};

const OBSERVE_EXIT_MS: u32 = 1_500;
const HELPER_WAIT_MS: u32 = 120_000;

fn native_error(operation: &'static str, error: ::windows::core::Error) -> Failure {
    native_code(operation, WIN32_ERROR(error.code().0 as u32 & 0xffff))
}

fn native_code(operation: &'static str, code: WIN32_ERROR) -> Failure {
    if code == ERROR_ACCESS_DENIED {
        Failure::PermissionDenied
    } else {
        Failure::OperatingSystem {
            operation,
            code: code.0,
        }
    }
}

fn raw(handle: &OwnedHandle) -> HANDLE {
    HANDLE(handle.as_raw_handle())
}

fn filetime(value: FILETIME) -> u64 {
    (u64::from(value.dwHighDateTime) << 32) | u64::from(value.dwLowDateTime)
}

fn creation_time(handle: HANDLE) -> Result<u64, Failure> {
    let (mut created, mut exited, mut kernel, mut user) = (
        FILETIME::default(),
        FILETIME::default(),
        FILETIME::default(),
        FILETIME::default(),
    );
    // SAFETY: the caller retains the process handle; all output pointers are distinct and valid.
    unsafe { GetProcessTimes(handle, &mut created, &mut exited, &mut kernel, &mut user) }
        .map_err(|e| native_error("Read process creation time", e))?;
    let ticks = filetime(created);
    if ticks == 0 {
        Err(Failure::IdentityChanged)
    } else {
        Ok(ticks)
    }
}

struct VerifiedProcess {
    handle: OwnedHandle,
    identity: ProcessIdentity,
}

impl VerifiedProcess {
    fn open(identity: &ProcessIdentity, rights: PROCESS_ACCESS_RIGHTS) -> Result<Self, Failure> {
        super::validate_identity(identity).map_err(|_| Failure::InvalidRequest)?;
        if identity.pid == 4 {
            return Err(Failure::Protected);
        }
        // SAFETY: the PID and access mask are values; inheritance is disabled.
        let handle = unsafe { OpenProcess(rights, false, identity.pid) }.map_err(|e| {
            let code = WIN32_ERROR(e.code().0 as u32 & 0xffff);
            if code == ERROR_INVALID_PARAMETER {
                Failure::TargetExited
            } else {
                native_code("Open selected process", code)
            }
        })?;
        // SAFETY: OpenProcess returned one new owned, non-null kernel handle.
        let handle = unsafe { OwnedHandle::from_raw_handle(handle.0) };
        // GetProcessId also rejects numeric PID aliases accepted by some kernels.
        if unsafe { GetProcessId(raw(&handle)) } != identity.pid
            || creation_time(raw(&handle))? != identity.start_time_ticks
        {
            return Err(Failure::IdentityChanged);
        }
        let process = Self {
            handle,
            identity: identity.clone(),
        };
        if process.exited(0)? {
            return Err(Failure::TargetExited);
        }
        Ok(process)
    }

    fn exited(&self, timeout: u32) -> Result<bool, Failure> {
        // SAFETY: this object owns a handle opened with SYNCHRONIZE throughout the wait.
        match unsafe { WaitForSingleObject(raw(&self.handle), timeout) } {
            WAIT_OBJECT_0 => Ok(true),
            WAIT_TIMEOUT => Ok(false),
            WAIT_FAILED => Err(native_error(
                "Observe process exit",
                ::windows::core::Error::from_win32(),
            )),
            _ => Err(Failure::UnknownOutcome),
        }
    }

    fn protect_target(&self) -> Result<(), Failure> {
        let mut critical = BOOL::default();
        // SAFETY: the retained process handle and output structure remain valid.
        unsafe { IsProcessCritical(raw(&self.handle), &mut critical) }
            .map_err(|e| native_error("Check critical process protection", e))?;
        let mut protection = PROCESS_PROTECTION_LEVEL_INFORMATION::default();
        unsafe {
            GetProcessInformation(
                raw(&self.handle),
                ProcessProtectionLevelInfo,
                (&mut protection as *mut PROCESS_PROTECTION_LEVEL_INFORMATION).cast(),
                std::mem::size_of_val(&protection) as u32,
            )
        }
        .map_err(|e| native_error("Check process protection level", e))?;
        if critical.as_bool()
            || protection.ProtectionLevel != PROTECTION_LEVEL_NONE
            || self.is_application()?
        {
            return Err(Failure::Protected);
        }
        Ok(())
    }

    fn is_application(&self) -> Result<bool, Failure> {
        let mut buffer = vec![0u16; 32_768];
        let mut length = buffer.len() as u32;
        // SAFETY: the mutable buffer has the declared capacity and the handle remains owned.
        unsafe {
            QueryFullProcessImageNameW(
                raw(&self.handle),
                PROCESS_NAME_WIN32,
                PWSTR(buffer.as_mut_ptr()),
                &mut length,
            )
        }
        .map_err(|e| native_error("Read process executable identity", e))?;
        if length == 0 || length as usize >= buffer.len() {
            return Err(Failure::InvalidRequest);
        }
        let target = PathBuf::from(OsString::from_wide(&buffer[..length as usize]));
        let current = std::env::current_exe().map_err(|e| Failure::OperatingSystem {
            operation: "Locate application executable",
            code: e.raw_os_error().unwrap_or(0) as u32,
        })?;
        Ok(executable_identity(&target)? == executable_identity(&current)?)
    }

    fn terminate(&self) -> Result<ProcessActionOutcome, Failure> {
        // SAFETY: this is the same identity-checked handle, opened with PROCESS_TERMINATE.
        let result = unsafe { TerminateProcess(raw(&self.handle), 1) };
        if let Err(error) = result {
            if self.exited(0)? {
                return Ok(ProcessActionOutcome::ExitObserved);
            }
            return Err(native_error("Terminate selected process", error));
        }
        if self.exited(OBSERVE_EXIT_MS)? {
            Ok(ProcessActionOutcome::ExitObserved)
        } else {
            Ok(ProcessActionOutcome::TerminationPending)
        }
    }

    fn close(&self) -> Result<ProcessActionOutcome, Failure> {
        // Window discovery is only a support check, never an action destination.
        // A background target must not prompt merely because termination needs
        // permission. Restart Manager still validates the full identity below.
        if !self.has_window()? {
            if self.exited(0)? {
                return Ok(ProcessActionOutcome::ExitObserved);
            }
            return Err(Failure::GracefulUnavailable);
        }
        let session = RestartSession::new()?;
        let result = self.close_in_session(&session);
        // End the private registration even when the action was refused.
        session.finish()?;
        result
    }

    fn has_window(&self) -> Result<bool, Failure> {
        struct Probe {
            pid: u32,
            found: bool,
        }
        unsafe extern "system" fn visit(window: HWND, context: LPARAM) -> BOOL {
            // SAFETY: EnumWindows synchronously borrows the stack-owned Probe.
            let probe = unsafe { &mut *(context.0 as *mut Probe) };
            let mut owner = 0;
            unsafe { GetWindowThreadProcessId(window, Some(&mut owner)) };
            if owner == probe.pid {
                probe.found = true;
                BOOL(0)
            } else {
                BOOL(1)
            }
        }
        let mut probe = Probe {
            pid: self.identity.pid,
            found: false,
        };
        // The retained process handle pins its PID. No HWND escapes this call.
        let result =
            unsafe { EnumWindows(Some(visit), LPARAM((&mut probe as *mut Probe) as isize)) };
        if probe.found {
            Ok(true)
        } else {
            result.map_err(|e| Failure::OperatingSystem {
                operation: "Discover selected application windows",
                code: e.code().0 as u32 & 0xffff,
            })?;
            Ok(false)
        }
    }

    fn close_in_session(&self, session: &RestartSession) -> Result<ProcessActionOutcome, Failure> {
        let ticks = self.identity.start_time_ticks;
        let application = RM_UNIQUE_PROCESS {
            dwProcessId: self.identity.pid,
            ProcessStartTime: FILETIME {
                dwLowDateTime: ticks as u32,
                dwHighDateTime: (ticks >> 32) as u32,
            },
        };
        // Register only this process, never filenames or services that expand the affected set.
        // SAFETY: all inputs are initialized; the session and process handle stay live.
        let code = unsafe { RmRegisterResources(session.id(), None, Some(&[application]), None) };
        if code != ERROR_SUCCESS {
            return Err(native_code("Register selected GUI process", code));
        }
        let (mut needed, mut count, mut reasons) = (0, 1, 0);
        let mut affected = RM_PROCESS_INFO::default();
        let code = unsafe {
            RmGetList(
                session.id(),
                &mut needed,
                &mut count,
                Some(&mut affected),
                &mut reasons,
            )
        };
        if self.exited(0)? {
            return Ok(ProcessActionOutcome::ExitObserved);
        }
        if code != ERROR_SUCCESS || count != 1 || needed > 1 {
            return Err(Failure::GracefulUnavailable);
        }
        if affected.Process.dwProcessId != self.identity.pid
            || filetime(affected.Process.ProcessStartTime) != ticks
        {
            return Err(Failure::IdentityChanged);
        }
        if reasons == RmRebootReasonPermissionDenied.0 as u32
            && affected.ApplicationType == RmCritical
        {
            return Err(Failure::PermissionDenied);
        }
        if reasons != 0
            || affected.ApplicationType != RmMainWindow
            || affected.strServiceShortName[0] != 0
        {
            return Err(Failure::GracefulUnavailable);
        }
        // Our retained handle prevents PID reuse even after exit. Restart Manager receives
        // a process registration, not a cached HWND. Flags zero never force refusal to exit.
        // SAFETY: the private session and verified process remain owned through the call.
        let code = unsafe { RmShutdown(session.id(), 0, None) };
        if self.exited(OBSERVE_EXIT_MS)? {
            return Ok(ProcessActionOutcome::ExitObserved);
        }
        match code {
            ERROR_SUCCESS => Ok(ProcessActionOutcome::CloseRequested),
            ERROR_FAIL_SHUTDOWN => Err(Failure::CloseRefused),
            // A failure after shutdown started may have effects. Never elevate/retry it.
            _ => Err(Failure::OperatingSystem {
                operation: "Request application closure",
                code: code.0,
            }),
        }
    }
}

fn executable_identity(path: &std::path::Path) -> Result<(u32, u64), Failure> {
    let file = OpenOptions::new()
        .access_mode(FILE_READ_ATTRIBUTES.0)
        .open(path)
        .map_err(|e| {
            native_code(
                "Read executable file identity",
                WIN32_ERROR(e.raw_os_error().unwrap_or(0) as u32),
            )
        })?;
    let mut info = BY_HANDLE_FILE_INFORMATION::default();
    // SAFETY: file owns a readable-attributes handle and info is an initialized output.
    unsafe { GetFileInformationByHandle(HANDLE(file.as_raw_handle()), &mut info) }
        .map_err(|e| native_error("Compare executable file identity", e))?;
    Ok((
        info.dwVolumeSerialNumber,
        (u64::from(info.nFileIndexHigh) << 32) | u64::from(info.nFileIndexLow),
    ))
}

struct RestartSession(Option<u32>);
impl RestartSession {
    fn new() -> Result<Self, Failure> {
        let mut id = 0;
        let mut key = vec![0u16; CCH_RM_SESSION_KEY as usize + 1];
        // SAFETY: outputs have the documented sizes; flags zero create a private session.
        let code = unsafe { RmStartSession(&mut id, 0, PWSTR(key.as_mut_ptr())) };
        if code == ERROR_SUCCESS {
            Ok(Self(Some(id)))
        } else {
            Err(native_code("Start graceful-close session", code))
        }
    }
    fn id(&self) -> u32 {
        self.0.expect("live Restart Manager session")
    }
    fn finish(mut self) -> Result<(), Failure> {
        let id = self.0.take().expect("live Restart Manager session");
        // SAFETY: this object owns the session and ends it exactly once.
        let code = unsafe { RmEndSession(id) };
        if code == ERROR_SUCCESS {
            Ok(())
        } else {
            Err(Failure::OperatingSystem {
                operation: "End graceful-close session",
                code: code.0,
            })
        }
    }
}
impl Drop for RestartSession {
    fn drop(&mut self) {
        if let Some(id) = self.0.take() {
            // SAFETY: unwind-only fallback for this object's owned session.
            let _ = unsafe { RmEndSession(id) };
        }
    }
}

pub(super) fn send(
    identity: &ProcessIdentity,
    signal: ProcessSignal,
) -> Result<ProcessActionOutcome, Failure> {
    let mut rights = PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_SYNCHRONIZE;
    if signal == ProcessSignal::Kill {
        rights |= PROCESS_TERMINATE;
    }
    let process = match VerifiedProcess::open(identity, rights) {
        Err(Failure::PermissionDenied) if signal == ProcessSignal::Kill => {
            // Failure to obtain termination rights says nothing about whether
            // this is a protected or stale target. Verify those facts through a
            // read-only handle before offering authorization. Never reopen by
            // PID to act through this handle; the helper verifies its own handle.
            let candidate = VerifiedProcess::open(
                identity,
                PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_SYNCHRONIZE,
            )
            .map_err(verification_error)?;
            candidate.protect_target().map_err(verification_error)?;
            return Err(Failure::PermissionDenied);
        }
        result => result.map_err(verification_error)?,
    };
    process.protect_target().map_err(verification_error)?;
    match signal {
        ProcessSignal::Kill => process.terminate(),
        ProcessSignal::Terminate => process.close(),
    }
}

fn verification_error(error: Failure) -> Failure {
    match error {
        Failure::PermissionDenied => Failure::OperatingSystem {
            operation: "Verify that the selected process is safe to control",
            code: ERROR_ACCESS_DENIED.0,
        },
        error => error,
    }
}

fn elevated() -> Result<bool, Failure> {
    let mut token = HANDLE::default();
    // SAFETY: GetCurrentProcess is a borrowed pseudo handle; OpenProcessToken returns a new handle.
    unsafe { OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &mut token) }
        .map_err(|e| native_error("Read current process token", e))?;
    let token = unsafe { OwnedHandle::from_raw_handle(token.0) };
    let mut elevation = TOKEN_ELEVATION::default();
    let mut length = 0;
    unsafe {
        GetTokenInformation(
            raw(&token),
            TokenElevation,
            Some((&mut elevation as *mut TOKEN_ELEVATION).cast()),
            std::mem::size_of_val(&elevation) as u32,
            &mut length,
        )
    }
    .map_err(|e| native_error("Read token elevation", e))?;
    Ok(elevation.TokenIsElevated != 0)
}

pub(super) fn helper_entry(arguments: &[OsString]) -> i32 {
    windows_protocol::encode_result((|| {
        let request = Request::parse(arguments)?;
        if !elevated()? {
            return Err(Failure::InvalidRequest);
        }
        let caller = VerifiedProcess::open(
            &request.caller,
            PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_SYNCHRONIZE,
        )?;
        if !caller.is_application()? {
            return Err(Failure::InvalidRequest);
        }
        // Keep the caller pinned as well; it cannot become a different process during the action.
        send(&request.target, request.signal)
    })())
}

pub(super) fn authenticate(
    identity: &ProcessIdentity,
    signal: ProcessSignal,
) -> Result<ProcessActionOutcome, String> {
    let result = (|| {
        if elevated()? {
            return Err(Failure::PermissionDenied);
        }
        let caller = ProcessIdentity {
            pid: std::process::id(),
            start_time_ticks: creation_time(unsafe { GetCurrentProcess() })?,
        };
        let request = Request {
            target: identity.clone(),
            signal,
            caller,
        };
        // A dedicated STA avoids inheriting an unrelated apartment from a reused pool thread.
        std::thread::spawn(move || authenticate_in_apartment(request))
            .join()
            .unwrap_or(Err(Failure::UnknownOutcome))
    })();
    result.map_err(|error| error.to_string())
}

struct Apartment;
impl Drop for Apartment {
    fn drop(&mut self) {
        unsafe { CoUninitialize() };
    }
}

fn authenticate_in_apartment(request: Request) -> Result<ProcessActionOutcome, Failure> {
    // SAFETY: this is a fresh owned thread, paired with CoUninitialize on every return.
    unsafe { CoInitializeEx(None, COINIT_APARTMENTTHREADED | COINIT_DISABLE_OLE1DDE) }
        .ok()
        .map_err(|e| native_error("Initialize Windows authorization", e))?;
    let _apartment = Apartment;
    let path = std::env::current_exe()
        .and_then(std::fs::canonicalize)
        .map_err(|e| {
            native_code(
                "Locate authorization helper",
                WIN32_ERROR(e.raw_os_error().unwrap_or(0) as u32),
            )
        })?;
    if !path.is_absolute() {
        return Err(Failure::InvalidRequest);
    }
    let mut executable = path.as_os_str().encode_wide().collect::<Vec<_>>();
    // Rust canonical paths use the extended prefix; the shell expects the absolute DOS/UNC form.
    if executable.starts_with(&[92, 92, 63, 92, 85, 78, 67, 92]) {
        executable.splice(..8, [92, 92]);
    } else if executable.starts_with(&[92, 92, 63, 92]) {
        executable.drain(..4);
    }
    if executable.contains(&0) {
        return Err(Failure::InvalidRequest);
    }
    executable.push(0);
    let parameters = request
        .parameters()
        .encode_utf16()
        .chain([0])
        .collect::<Vec<_>>();
    let mut info = SHELLEXECUTEINFOW {
        cbSize: std::mem::size_of::<SHELLEXECUTEINFOW>() as u32,
        fMask: SEE_MASK_NOCLOSEPROCESS | SEE_MASK_NOASYNC | SEE_MASK_FLAG_NO_UI,
        lpVerb: w!("runas"),
        lpFile: PCWSTR(executable.as_ptr()),
        lpParameters: PCWSTR(parameters.as_ptr()),
        nShow: SW_HIDE.0,
        ..Default::default()
    };
    // SAFETY: all UTF-16 strings are NUL-terminated and remain live for the synchronous launch.
    if let Err(error) = unsafe { ShellExecuteExW(&mut info) } {
        let code = WIN32_ERROR(error.code().0 as u32 & 0xffff);
        return Err(if code == ERROR_CANCELLED {
            Failure::Cancelled
        } else {
            native_code("Start Windows authorization", code)
        });
    }
    if info.hProcess.is_invalid() {
        return Err(Failure::UnknownOutcome);
    }
    // SAFETY: SEE_MASK_NOCLOSEPROCESS transfers this new process handle to the caller.
    let helper = unsafe { OwnedHandle::from_raw_handle(info.hProcess.0) };
    match unsafe { WaitForSingleObject(raw(&helper), HELPER_WAIT_MS) } {
        WAIT_OBJECT_0 => {
            let mut code = 0;
            unsafe { GetExitCodeProcess(raw(&helper), &mut code) }
                .map_err(|_| Failure::UnknownOutcome)?;
            windows_protocol::decode_result(code)
        }
        _ => Err(Failure::UnknownOutcome),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::process::{Child, Command, Stdio};
    use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

    struct OwnedChild(Child);
    impl Drop for OwnedChild {
        fn drop(&mut self) {
            let _ = self.0.kill();
            let _ = self.0.wait();
        }
    }

    fn child() -> (OwnedChild, ProcessIdentity) {
        let executable = PathBuf::from(std::env::var_os("WINDIR").unwrap())
            .join("System32/WindowsPowerShell/v1.0/powershell.exe");
        let child = OwnedChild(
            Command::new(executable)
                .args([
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    "Start-Sleep -Seconds 60",
                ])
                .stdin(Stdio::null())
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .spawn()
                .unwrap(),
        );
        let identity = ProcessIdentity {
            pid: child.0.id(),
            start_time_ticks: creation_time(HANDLE(child.0.as_raw_handle())).unwrap(),
        };
        (child, identity)
    }

    #[test]
    fn denied_safety_verification_does_not_request_authorization() {
        let denied = verification_error(Failure::PermissionDenied);
        assert!(matches!(
            super::super::ActionError::from(denied),
            super::super::ActionError::Failed(_)
        ));
        for error in [
            Failure::Protected,
            Failure::IdentityChanged,
            Failure::TargetExited,
        ] {
            assert_eq!(verification_error(error.clone()), error);
        }
        assert_eq!(
            super::super::ActionError::from(Failure::PermissionDenied),
            super::super::ActionError::PermissionDenied
        );
    }

    #[test]
    fn native_collection_preserves_all_creation_ticks_and_rejects_one_tick_mismatch() {
        let (mut child, identity) = child();
        let mut system = sysinfo::System::new();
        system.refresh_processes_specifics(
            sysinfo::ProcessesToUpdate::Some(&[sysinfo::Pid::from_u32(identity.pid)]),
            true,
            sysinfo::ProcessRefreshKind::nothing(),
        );
        let observed = system
            .process(sysinfo::Pid::from_u32(identity.pid))
            .unwrap();
        assert_eq!(observed.start_time_filetime(), identity.start_time_ticks);
        assert!(identity.start_time_ticks > 100_000_000_000_000_000);
        for ticks in [
            0,
            identity.start_time_ticks - 1,
            identity.start_time_ticks + 1,
        ] {
            let wrong = ProcessIdentity {
                start_time_ticks: ticks,
                ..identity.clone()
            };
            assert!(send(&wrong, ProcessSignal::Kill).is_err());
            assert!(
                child.0.try_wait().unwrap().is_none(),
                "wrong identity changed owned child"
            );
        }
        assert_eq!(
            send(&identity, ProcessSignal::Kill),
            Ok(ProcessActionOutcome::ExitObserved)
        );
        assert!(child.0.try_wait().unwrap().is_some());
    }

    #[test]
    fn native_exited_and_protected_targets_are_refused() {
        let (mut child, identity) = child();
        child.0.kill().unwrap();
        child.0.wait().unwrap();
        assert_eq!(
            send(&identity, ProcessSignal::Kill),
            Err(Failure::TargetExited)
        );
        for pid in [0, 1, 4, std::process::id(), u32::MAX] {
            assert!(
                send(
                    &ProcessIdentity {
                        pid,
                        start_time_ticks: 1
                    },
                    ProcessSignal::Kill
                )
                .is_err()
            );
        }
    }

    #[test]
    fn native_pinned_process_and_file_identity_survive_path_aliases() {
        let (child, identity) = child();
        let process = VerifiedProcess::open(
            &identity,
            PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_SYNCHRONIZE | PROCESS_TERMINATE,
        )
        .unwrap();
        process.protect_target().unwrap();
        assert_eq!(
            creation_time(raw(&process.handle)).unwrap(),
            identity.start_time_ticks
        );
        assert!(!process.is_application().unwrap());
        assert_eq!(unsafe { GetProcessId(raw(&process.handle)) }, child.0.id());
        let executable = std::env::current_exe().unwrap();
        assert_eq!(
            executable_identity(&executable).unwrap(),
            executable_identity(&std::fs::canonicalize(executable).unwrap()).unwrap()
        );
    }

    #[test]
    fn native_graceful_close_honors_refusal_and_never_messages_an_unrelated_process() {
        let directory = std::env::temp_dir().join(format!(
            "pulse-owned-gui-{}-{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir(&directory).unwrap();
        let source = directory.join("fixture.cs");
        std::fs::write(
            &source,
            include_str!(concat!(
                env!("CARGO_MANIFEST_DIR"),
                "/../../scripts/system-pulse/windows_process_fixture.cs"
            )),
        )
        .unwrap();
        let executable = directory.join("process fixture.exe");
        let compiler = PathBuf::from(std::env::var_os("WINDIR").unwrap())
            .join("Microsoft.NET/Framework64/v4.0.30319/csc.exe");
        let status = Command::new(compiler)
            .args([
                "/nologo",
                "/target:winexe",
                "/reference:System.Windows.Forms.dll",
            ])
            .arg(format!("/out:{}", executable.display()))
            .arg(&source)
            .status()
            .unwrap();
        assert!(status.success(), "compile disposable GUI fixture");
        let start = |mode: &str, label: &str| {
            let log = directory.join(format!("{label}.log"));
            let child = OwnedChild(
                Command::new(&executable)
                    .arg(mode)
                    .arg(&log)
                    .spawn()
                    .unwrap(),
            );
            let deadline = Instant::now() + Duration::from_secs(15);
            while !log.exists() {
                assert!(
                    Instant::now() < deadline,
                    "GUI fixture did not become ready"
                );
                std::thread::sleep(Duration::from_millis(30));
            }
            let identity = ProcessIdentity {
                pid: child.0.id(),
                start_time_ticks: creation_time(HANDLE(child.0.as_raw_handle())).unwrap(),
            };
            (child, identity, log)
        };
        {
            let (mut control, _, control_log) = start("cooperative", "control");
            for (mode, expected) in [
                ("cooperative", Ok(ProcessActionOutcome::ExitObserved)),
                ("refusing", Err(Failure::CloseRefused)),
                ("windowless", Err(Failure::GracefulUnavailable)),
            ] {
                let (mut target, identity, log) = start(mode, mode);
                let wrong = ProcessIdentity {
                    start_time_ticks: identity.start_time_ticks + 1,
                    ..identity.clone()
                };
                assert_eq!(
                    send(&wrong, ProcessSignal::Terminate),
                    Err(Failure::IdentityChanged)
                );
                assert!(target.0.try_wait().unwrap().is_none());
                assert_eq!(std::fs::read_to_string(&log).unwrap(), "ready\n");
                assert_eq!(send(&identity, ProcessSignal::Terminate), expected);
                assert!(control.0.try_wait().unwrap().is_none());
                assert_eq!(std::fs::read_to_string(&control_log).unwrap(), "ready\n");
                if mode != "cooperative" {
                    assert!(target.0.try_wait().unwrap().is_none());
                }
            }
        }
        std::fs::remove_dir_all(directory).unwrap();
    }
}
