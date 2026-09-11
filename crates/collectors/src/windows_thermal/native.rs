//! One-way bounded pipe. Only this supervisor launches an elevated helper.
use super::{
    HELPER_FLAG,
    driver::Driver,
    identity::{self, Caller, LockedExecutable, alive, own, raw},
    protocol::{Frame, Request, Result},
    session::{Control, Latest, MAX_AGE},
    watchdog::{Watchdog, terminate_helper},
};
use std::{
    os::windows::{ffi::OsStrExt, io::OwnedHandle},
    sync::Arc,
    time::{Duration, Instant},
};
use windows::{
    Win32::{
        Foundation::{
            BOOL, ERROR_CANCELLED, ERROR_NO_DATA, ERROR_PIPE_CONNECTED, ERROR_PIPE_LISTENING,
            GetLastError, HLOCAL, LocalFree,
        },
        Security::{
            Authorization::{
                ConvertSidToStringSidW, ConvertStringSecurityDescriptorToSecurityDescriptorW,
                SDDL_REVISION_1,
            },
            Cryptography::{BCRYPT_ALG_HANDLE, BCRYPT_USE_SYSTEM_PREFERRED_RNG, BCryptGenRandom},
            GetTokenInformation, PSECURITY_DESCRIPTOR, SECURITY_ATTRIBUTES, TOKEN_USER, TokenUser,
        },
        Storage::FileSystem::{
            CreateFileW, FILE_FLAG_FIRST_PIPE_INSTANCE, FILE_FLAGS_AND_ATTRIBUTES, FILE_SHARE_NONE,
            FILE_WRITE_ATTRIBUTES, FILE_WRITE_DATA, OPEN_EXISTING, PIPE_ACCESS_INBOUND, ReadFile,
            WriteFile,
        },
        System::{
            Com::{
                COINIT_APARTMENTTHREADED, COINIT_DISABLE_OLE1DDE, CoInitializeEx, CoUninitialize,
            },
            Performance::{QueryPerformanceCounter, QueryPerformanceFrequency},
            Pipes::{
                ConnectNamedPipe, CreateNamedPipeW, GetNamedPipeClientProcessId,
                GetNamedPipeServerProcessId, PIPE_NOWAIT, PIPE_READMODE_MESSAGE,
                PIPE_REJECT_REMOTE_CLIENTS, PIPE_TYPE_MESSAGE, SetNamedPipeHandleState,
            },
            Threading::{GetCurrentProcess, GetProcessId},
        },
        UI::{
            Shell::{
                SEE_MASK_FLAG_NO_UI, SEE_MASK_NOASYNC, SEE_MASK_NOCLOSEPROCESS, SHELLEXECUTEINFOW,
                ShellExecuteExW,
            },
            WindowsAndMessaging::SW_HIDE,
        },
    },
    core::{PCWSTR, PWSTR, w},
};
const POLL: Duration = Duration::from_millis(50);
const STARTUP: Duration = Duration::from_secs(30);
const MAX_SESSION: Duration = Duration::from_secs(24 * 60 * 60);
fn wide(text: &str) -> Vec<u16> {
    text.encode_utf16().chain([0]).collect()
}
fn pipe_name(request: &Request) -> Vec<u16> {
    wide(&format!(
        "\\\\.\\pipe\\SystemPulse.CpuTemperature.{}.{}",
        request.pid, request.nonce
    ))
}
fn code(error: &windows::core::Error) -> u32 {
    error.code().0 as u32 & 0xffff
}
struct Local(HLOCAL);
impl Drop for Local {
    fn drop(&mut self) {
        unsafe {
            LocalFree(self.0);
        }
    }
}
struct Apartment;
impl Drop for Apartment {
    fn drop(&mut self) {
        unsafe {
            CoUninitialize();
        }
    }
}
fn create_pipe(request: &Request) -> Result<OwnedHandle> {
    let token = identity::token()?;
    let mut data = [0usize; 512];
    let mut used = 0;
    // SAFETY: aligned bounded output for TOKEN_USER and its inline SID storage.
    unsafe {
        GetTokenInformation(
            raw(&token),
            TokenUser,
            Some(data.as_mut_ptr().cast()),
            std::mem::size_of_val(&data) as u32,
            &mut used,
        )
    }
    .map_err(|e| format!("Read pipe owner SID: {e}"))?;
    if (used as usize) < std::mem::size_of::<TOKEN_USER>()
        || used as usize > std::mem::size_of_val(&data)
    {
        return Err("Invalid token user size".into());
    }
    let user = unsafe { &*data.as_ptr().cast::<TOKEN_USER>() };
    let mut sid = PWSTR::null();
    // SAFETY: SID belongs to the retained token-information buffer; API allocates output.
    unsafe { ConvertSidToStringSidW(user.User.Sid, &mut sid) }
        .map_err(|e| format!("Format pipe SID: {e}"))?;
    let _sid_memory = Local(HLOCAL(sid.0.cast()));
    let sid = unsafe { sid.to_string() }.map_err(|e| format!("Read pipe SID text: {e}"))?;
    // User: generic read + data write + attribute write, explicitly excluding bit 4
    // (FILE_CREATE_PIPE_INSTANCE). No Everyone/Authenticated Users ACE is inherited.
    let sddl = wide(&format!("D:P(A;;GA;;;SY)(A;;GA;;;BA)(A;;0x12018b;;;{sid})"));
    let mut descriptor = PSECURITY_DESCRIPTOR::default();
    unsafe {
        ConvertStringSecurityDescriptorToSecurityDescriptorW(
            PCWSTR(sddl.as_ptr()),
            SDDL_REVISION_1,
            &mut descriptor,
            None,
        )
    }
    .map_err(|e| format!("Build temperature pipe ACL: {e}"))?;
    let _descriptor_memory = Local(HLOCAL(descriptor.0));
    let security = SECURITY_ATTRIBUTES {
        nLength: std::mem::size_of::<SECURITY_ATTRIBUTES>() as u32,
        lpSecurityDescriptor: descriptor.0,
        bInheritHandle: BOOL(0),
    };
    let name = pipe_name(request);
    // SAFETY: fixed one-instance, local-only message pipe, explicit ACL and live strings.
    let pipe = unsafe {
        CreateNamedPipeW(
            PCWSTR(name.as_ptr()),
            PIPE_ACCESS_INBOUND | FILE_FLAG_FIRST_PIPE_INSTANCE,
            PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_NOWAIT | PIPE_REJECT_REMOTE_CLIENTS,
            1,
            64,
            64,
            0,
            Some(&security),
        )
    };
    if pipe.is_invalid() {
        return Err(format!(
            "Create temperature pipe: {}",
            unsafe { GetLastError() }.0
        ));
    }
    Ok(own(pipe))
}
pub(super) fn supervise(control: Arc<Control>, generation: u64) {
    let result = supervise_inner(&control, generation);
    control.finish(
        generation,
        result
            .err()
            .unwrap_or_else(|| "CPU temperature session ended; enable to start again".into()),
    );
}
fn supervise_inner(control: &Control, generation: u64) -> Result<()> {
    // SAFETY: dedicated fresh supervisor thread owns this STA through all shell operations.
    unsafe { CoInitializeEx(None, COINIT_APARTMENTTHREADED | COINIT_DISABLE_OLE1DDE) }
        .ok()
        .map_err(|e| format!("Initialize temperature authorization: {e}"))?;
    let _apartment = Apartment;
    let executable = LockedExecutable::current()?;
    let mut random = [0u8; 16];
    // SAFETY: system RNG writes exactly the provided fixed buffer; no persisted nonce.
    unsafe {
        BCryptGenRandom(
            BCRYPT_ALG_HANDLE::default(),
            &mut random,
            BCRYPT_USE_SYSTEM_PREFERRED_RNG,
        )
    }
    .ok()
    .map_err(|e| format!("Generate temperature session nonce: {e}"))?;
    let request = Request {
        pid: std::process::id(),
        created: identity::creation_time(unsafe { GetCurrentProcess() })?,
        nonce: random.iter().map(|b| format!("{b:02x}")).collect(),
    };
    let pipe = create_pipe(&request)?;
    if !control.current(generation) {
        return Ok(());
    }
    let helper = launch(&executable, &request)?;
    // UAC may block above. Cancellation never waits for it and is checked before using results.
    if !control.current(generation) {
        return Ok(());
    }
    let pid = unsafe { GetProcessId(raw(&helper)) };
    if pid == 0 {
        return Err("Temperature helper returned no process identity".into());
    }
    let started = Instant::now();
    let frequency = frequency()?;
    let mut previous_after = 0;
    let mut connected = false;
    let mut sequence = 0;
    let mut received = None;
    loop {
        if !control.current(generation) {
            return Ok(());
        }
        if started.elapsed() > MAX_SESSION {
            return Err("CPU temperature session reached 24 hours; enable to renew".into());
        }
        if !connected {
            // NOWAIT never blocks: the first successful/connected result authenticates once.
            match unsafe { ConnectNamedPipe(raw(&pipe), None) } {
                Ok(()) => connected = true,
                Err(e) if code(&e) == ERROR_PIPE_CONNECTED.0 => connected = true,
                Err(e) if code(&e) == ERROR_PIPE_LISTENING.0 => {}
                Err(e) => return Err(format!("Connect temperature helper: {e}")),
            }
            if connected {
                let mut client = 0;
                unsafe { GetNamedPipeClientProcessId(raw(&pipe), &mut client) }
                    .map_err(|e| format!("Verify temperature helper pipe client: {e}"))?;
                if client != pid {
                    return Err("Temperature pipe client is not the launched helper".into());
                }
            }
        }
        if connected {
            let mut bytes = [0u8; 64];
            let mut count = 0;
            match unsafe { ReadFile(raw(&pipe), Some(&mut bytes), Some(&mut count), None) } {
                Ok(()) if count != 0 => {
                    let frame = Frame::decode(&bytes[..count as usize], sequence)?;
                    frame.validate_clock(counter()?, frequency, previous_after)?;
                    frame.temperature()?;
                    previous_after = frame.after;
                    sequence = frame.sequence;
                    let now = Instant::now();
                    received = Some(now);
                    control.publish(generation, Latest::Sample(frame, now));
                }
                Ok(()) => {}
                Err(e) if code(&e) == ERROR_NO_DATA.0 => {}
                Err(e) => return Err(format!("Read CPU temperature helper: {e}")),
            }
        }
        if !alive(raw(&helper)) {
            return Err("CPU temperature helper exited; enable to retry".into());
        }
        if received.is_some_and(|last: Instant| last.elapsed() > MAX_AGE) {
            return Err("CPU package temperature stopped updating; enable to retry".into());
        }
        if received.is_none() && started.elapsed() > STARTUP {
            return Err("CPU temperature helper startup timed out; enable to retry".into());
        }
        std::thread::sleep(POLL);
    }
}
fn launch(executable: &LockedExecutable, request: &Request) -> Result<OwnedHandle> {
    let mut path: Vec<u16> = executable.path.as_os_str().encode_wide().collect();
    if path.starts_with(&[92, 92, 63, 92, 85, 78, 67, 92]) {
        path.splice(..8, [92, 92]);
    } else if path.starts_with(&[92, 92, 63, 92]) {
        path.drain(..4);
    }
    if !executable.path.is_absolute() || path.contains(&0) {
        return Err("Invalid temperature helper executable path".into());
    }
    path.push(0);
    let parameters = wide(&format!(
        "{HELPER_FLAG} {} {} {}",
        request.pid, request.created, request.nonce
    ));
    let mut info = SHELLEXECUTEINFOW {
        cbSize: std::mem::size_of::<SHELLEXECUTEINFOW>() as u32,
        fMask: SEE_MASK_NOCLOSEPROCESS | SEE_MASK_NOASYNC | SEE_MASK_FLAG_NO_UI,
        lpVerb: w!("runas"),
        lpFile: PCWSTR(path.as_ptr()),
        lpParameters: PCWSTR(parameters.as_ptr()),
        nShow: SW_HIDE.0,
        ..Default::default()
    };
    // SAFETY: strings are retained for the synchronous shell launch; executable is locked.
    unsafe { ShellExecuteExW(&mut info) }.map_err(|e| {
        if code(&e) == ERROR_CANCELLED.0 {
            "CPU temperature authorization was denied or cancelled; enable to retry".into()
        } else {
            format!("Launch CPU temperature helper: {e}")
        }
    })?;
    if info.hProcess.is_invalid() {
        return Err("Windows did not return the temperature helper handle".into());
    }
    Ok(own(info.hProcess))
}
fn counter() -> Result<u64> {
    let mut value = 0i64;
    unsafe { QueryPerformanceCounter(&mut value) }
        .map_err(|e| format!("Read temperature query clock: {e}"))?;
    u64::try_from(value).map_err(|_| "Negative temperature query clock".into())
}
fn frequency() -> Result<u64> {
    let mut frequency = 0i64;
    unsafe { QueryPerformanceFrequency(&mut frequency) }
        .map_err(|e| format!("Read temperature query frequency: {e}"))?;
    u64::try_from(frequency)
        .ok()
        .filter(|f| *f > 0)
        .ok_or("Invalid temperature query frequency".into())
}
pub(super) fn helper(request: Request) -> Result<()> {
    if !identity::elevated()? {
        return Err("Temperature helper requires elevation".into());
    }
    let caller = Arc::new(Caller::open(request.pid, request.created)?);
    let name = pipe_name(&request);
    // Client never receives arbitrary operations, and does not request create-instance access.
    let pipe = own(unsafe {
        CreateFileW(
            PCWSTR(name.as_ptr()),
            (FILE_WRITE_DATA | FILE_WRITE_ATTRIBUTES).0,
            FILE_SHARE_NONE,
            None,
            OPEN_EXISTING,
            FILE_FLAGS_AND_ATTRIBUTES(0),
            None,
        )
    }
    .map_err(|e| format!("Open caller temperature pipe: {e}"))?);
    let mut server = 0;
    unsafe { GetNamedPipeServerProcessId(raw(&pipe), &mut server) }
        .map_err(|e| format!("Verify temperature pipe server: {e}"))?;
    if server != request.pid || !alive(raw(&caller.handle)) {
        return Err("Temperature pipe server is not the retained caller".into());
    }
    unsafe { SetNamedPipeHandleState(raw(&pipe), Some(&PIPE_NOWAIT), None, None) }
        .map_err(|e| format!("Set nonblocking temperature pipe: {e}"))?;
    let watched_caller = caller.clone();
    // The watchdog stays runnable even if a fixed driver call never returns. It owns
    // the verified caller object and terminates only its own elevated helper process.
    let watchdog = Watchdog::start(
        move || alive(raw(&watched_caller.handle)),
        terminate_helper,
        Duration::from_secs(5),
        MAX_SESSION,
    )?;
    let frequency = frequency()?;
    let started = Instant::now();
    let driver = watchdog.operation(Driver::open);
    let mut sequence = 0u64;
    loop {
        if !alive(raw(&caller.handle)) || started.elapsed() > MAX_SESSION {
            return Ok(());
        }
        sequence += 1;
        let before = counter()?;
        let result = watchdog.operation(|| match &driver {
            Ok(driver) => driver.sample(),
            Err(code) => Err(*code),
        });
        let after = counter()?;
        let (target, status, error) = match result {
            Ok((target, status)) => (target, status, 0),
            Err(code) => (0, 0, code),
        };
        let mut frame = Frame {
            sequence,
            target,
            status,
            before,
            after,
            frequency,
            error,
        };
        if frame.error == 0 && frame.temperature().is_err() {
            frame.target = 0;
            frame.status = 0;
            frame.error = 6;
        }
        let mut written = 0;
        // NOWAIT message write is bounded. A zero/partial write is backpressure, never success.
        unsafe { WriteFile(raw(&pipe), Some(&frame.encode()), Some(&mut written), None) }
            .map_err(|e| format!("Write CPU temperature frame: {e}"))?;
        if written != 64 {
            return Err("CPU temperature pipe disconnected or stopped accepting samples".into());
        }
        if frame.error != 0 {
            return Ok(());
        }
        // Small slices let caller exit shut the elevated helper down promptly.
        for _ in 0..10 {
            std::thread::sleep(POLL);
            if !alive(raw(&caller.handle)) {
                return Ok(());
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn native_local_pipe_has_exact_messages_and_does_not_wait_for_empty_reads() {
        let request = Request {
            pid: std::process::id(),
            created: identity::creation_time(unsafe { GetCurrentProcess() }).unwrap(),
            nonce: format!("{:032x}", counter().unwrap()),
        };
        let server = create_pipe(&request).unwrap();
        assert!(
            create_pipe(&request).is_err(),
            "first instance must be exclusive"
        );
        let name = pipe_name(&request);
        let client = own(unsafe {
            CreateFileW(
                PCWSTR(name.as_ptr()),
                (FILE_WRITE_DATA | FILE_WRITE_ATTRIBUTES).0,
                FILE_SHARE_NONE,
                None,
                OPEN_EXISTING,
                FILE_FLAGS_AND_ATTRIBUTES(0),
                None,
            )
        }
        .unwrap());
        match unsafe { ConnectNamedPipe(raw(&server), None) } {
            Ok(()) => {}
            Err(e) => assert_eq!(code(&e), ERROR_PIPE_CONNECTED.0),
        }
        let mut pid = 0;
        unsafe { GetNamedPipeClientProcessId(raw(&server), &mut pid) }.unwrap();
        assert_eq!(pid, std::process::id());
        unsafe { GetNamedPipeServerProcessId(raw(&client), &mut pid) }.unwrap();
        assert_eq!(pid, std::process::id());
        unsafe { SetNamedPipeHandleState(raw(&client), Some(&PIPE_NOWAIT), None, None) }.unwrap();
        let mut output = [0u8; 64];
        let mut count = 0;
        let start = Instant::now();
        let empty = unsafe { ReadFile(raw(&server), Some(&mut output), Some(&mut count), None) };
        assert!(start.elapsed() < Duration::from_secs(1));
        assert!(empty.is_err_and(|e| code(&e) == ERROR_NO_DATA.0));
        let bytes = [42u8; 64];
        unsafe { WriteFile(raw(&client), Some(&bytes), Some(&mut count), None) }.unwrap();
        assert_eq!(count, 64);
        unsafe { ReadFile(raw(&server), Some(&mut output), Some(&mut count), None) }.unwrap();
        assert_eq!(count, 64);
        assert_eq!(output, bytes);
        drop(server);
        assert!(unsafe { WriteFile(raw(&client), Some(&bytes), Some(&mut count), None) }.is_err());
    }

    #[test]
    fn native_caller_pins_full_creation_time_and_executable_identity() {
        let created = identity::creation_time(unsafe { GetCurrentProcess() }).unwrap();
        let caller = Caller::open(std::process::id(), created).unwrap();
        assert!(alive(raw(&caller.handle)));
        assert!(Caller::open(std::process::id(), created + 1).is_err());
        let executable = LockedExecutable::current().unwrap();
        assert!(executable.matches(&LockedExecutable::open(&executable.path).unwrap()));
    }
}
