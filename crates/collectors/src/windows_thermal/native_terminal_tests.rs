use super::test_helpers::read_test_temperature;
use super::*;
type TestResult<T = ()> = std::result::Result<T, String>;

fn checked<T, E: std::fmt::Display>(result: std::result::Result<T, E>) -> TestResult<T> {
    result.map_err(|error| error.to_string())
}

#[test]
fn native_real_driver_helper_child() -> TestResult {
    let Ok(pid) = std::env::var("SYSTEM_PULSE_TEST_REAL_HELPER_PID") else {
        return Ok(());
    };
    let request = Request::parse(&[
        pid.into(),
        std::env::var_os("SYSTEM_PULSE_TEST_REAL_HELPER_CREATED")
            .ok_or("missing helper creation time")?,
        std::env::var_os("SYSTEM_PULSE_TEST_REAL_HELPER_NONCE").ok_or("missing helper nonce")?,
    ])?;
    eprintln!("real helper child elevated={:?}", identity::elevated());
    let result = helper(request);
    eprintln!("real helper returned: {result:?}");
    // Parent intentionally closes the pipe after its first verified frame.
    // The parent's assertion determines whether the real helper delivered data.
    Ok(())
}

#[test]
fn native_real_driver_helper_session() -> TestResult {
    // Explicit opt-in: ordinary tests must not require or open the real driver.
    if std::env::var("SYSTEM_PULSE_TEST_REAL_HELPER").as_deref() != Ok("1") {
        return Ok(());
    }
    let executable = checked(LockedExecutable::current())?;
    let request = Request {
        pid: std::process::id(),
        created: checked(identity::creation_time(unsafe { GetCurrentProcess() }))?,
        nonce: format!("{:032x}", checked(counter())?),
    };
    let server = checked(create_pipe(&request))?;
    let mut child = std::process::Command::new(&executable.path)
        .args([
            "--exact",
            "windows_thermal::native::tests::native_real_driver_helper_child",
            "--nocapture",
        ])
        .env("SYSTEM_PULSE_TEST_REAL_HELPER_PID", request.pid.to_string())
        .env(
            "SYSTEM_PULSE_TEST_REAL_HELPER_CREATED",
            request.created.to_string(),
        )
        .env("SYSTEM_PULSE_TEST_REAL_HELPER_NONCE", &request.nonce)
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()
        .map_err(|error| error.to_string())?;
    eprintln!(
        "real helper parent elevated={:?}, child={}",
        identity::elevated(),
        child.id()
    );
    let result = read_test_temperature(&server, child.id());
    drop(server);
    let deadline = Instant::now() + Duration::from_secs(10);
    while child
        .try_wait()
        .map_err(|error| error.to_string())?
        .is_none()
        && Instant::now() < deadline
    {
        std::thread::sleep(POLL);
    }
    if child
        .try_wait()
        .map_err(|error| error.to_string())?
        .is_none()
    {
        child.kill().map_err(|error| error.to_string())?;
    }
    let output = child
        .wait_with_output()
        .map_err(|error| error.to_string())?;
    eprintln!(
        "real helper exit={}, stdout={}, stderr={}",
        output.status,
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    eprintln!("real helper observation={result:?}");
    assert!(
        result.is_ok(),
        "real driver helper did not deliver a temperature"
    );
    Ok(())
}

#[test]
fn native_local_pipe_has_exact_messages_and_does_not_wait_for_empty_reads() -> TestResult {
    let request = Request {
        pid: std::process::id(),
        created: checked(identity::creation_time(unsafe { GetCurrentProcess() }))?,
        nonce: format!("{:032x}", checked(counter())?),
    };
    let server = checked(create_pipe(&request))?;
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
    .map_err(|error| error.to_string())?);
    match unsafe { ConnectNamedPipe(raw(&server), None) } {
        Ok(()) => {}
        Err(e) => assert_eq!(code(&e), ERROR_PIPE_CONNECTED.0),
    }
    let mut pid = 0;
    checked(unsafe { GetNamedPipeClientProcessId(raw(&server), &mut pid) })?;
    assert_eq!(pid, std::process::id());
    checked(unsafe { GetNamedPipeServerProcessId(raw(&client), &mut pid) })?;
    assert_eq!(pid, std::process::id());
    checked(unsafe { SetNamedPipeHandleState(raw(&client), Some(&PIPE_NOWAIT), None, None) })?;
    let mut output = [0u8; 64];
    let mut count = 0;
    let start = Instant::now();
    let empty = unsafe { ReadFile(raw(&server), Some(&mut output), Some(&mut count), None) };
    assert!(start.elapsed() < Duration::from_secs(1));
    assert!(empty.is_err_and(|e| code(&e) == ERROR_NO_DATA.0));
    let bytes = [42u8; 64];
    checked(unsafe { WriteFile(raw(&client), Some(&bytes), Some(&mut count), None) })?;
    assert_eq!(count, 64);
    checked(unsafe { ReadFile(raw(&server), Some(&mut output), Some(&mut count), None) })?;
    assert_eq!(count, 64);
    assert_eq!(output, bytes);
    drop(server);
    assert!(unsafe { WriteFile(raw(&client), Some(&bytes), Some(&mut count), None) }.is_err());
    Ok(())
}

#[test]
fn native_caller_pins_full_creation_time_and_executable_identity() -> TestResult {
    let created = checked(identity::creation_time(unsafe { GetCurrentProcess() }))?;
    let caller = checked(Caller::open(std::process::id(), created))?;
    assert!(alive(raw(&caller.handle)));
    assert!(Caller::open(std::process::id(), created + 1).is_err());
    let executable = checked(LockedExecutable::current())?;
    assert!(executable.matches(&checked(LockedExecutable::open(&executable.path))?));
    Ok(())
}

fn terminal_test_request() -> TestResult<Request> {
    let mut random = [0u8; 16];
    unsafe {
        BCryptGenRandom(
            BCRYPT_ALG_HANDLE::default(),
            &mut random,
            BCRYPT_USE_SYSTEM_PREFERRED_RNG,
        )
    }
    .ok()
    .map_err(|error| error.to_string())?;
    Ok(Request {
        pid: std::process::id(),
        created: checked(identity::creation_time(unsafe { GetCurrentProcess() }))?,
        nonce: random.iter().map(|byte| format!("{byte:02x}")).collect(),
    })
}

fn launch_terminal_test_client(request: &Request, mode: &str) -> TestResult<u32> {
    let executable = checked(std::env::current_exe())?;
    let mut child = std::process::Command::new(executable)
        .args([
            "--exact",
            "windows_thermal::native::tests::terminal_pipe_client_child",
            "--nocapture",
        ])
        .env("SYSTEM_PULSE_TEST_TERMINAL_PID", request.pid.to_string())
        .env("SYSTEM_PULSE_TEST_TERMINAL_NONCE", &request.nonce)
        .env("SYSTEM_PULSE_TEST_TERMINAL_MODE", mode)
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .spawn()
        .map_err(|error| error.to_string())?;
    let pid = child.id();
    let deadline = Instant::now() + Duration::from_secs(STARTUP.as_secs());
    loop {
        if let Some(status) = child.try_wait().map_err(|error| error.to_string())? {
            return status
                .success()
                .then_some(pid)
                .ok_or_else(|| format!("terminal test client exited with {status}"));
        }
        if Instant::now() >= deadline {
            child.kill().map_err(|error| error.to_string())?;
            let _ = child.wait();
            return Err("terminal test client startup timed out".into());
        }
        std::thread::sleep(POLL);
    }
}

fn connect_until_helper_stops_listening(
    pipe: &OwnedHandle,
    expected_pid: u32,
) -> TestResult<PipeConnection> {
    let deadline = Instant::now() + STARTUP;
    loop {
        match connect_helper(pipe, expected_pid)? {
            PipeConnection::Listening if Instant::now() < deadline => {
                std::thread::sleep(POLL);
            }
            PipeConnection::Listening => return Err("terminal helper connection timed out".into()),
            connection => return Ok(connection),
        }
    }
}

#[test]
fn unconnected_pipe_remains_listening_without_client_identity_query() -> TestResult {
    let request = terminal_test_request()?;
    let server = checked(create_pipe(&request))?;
    assert_eq!(
        connect_helper(&server, u32::MAX)?,
        PipeConnection::Listening
    );
    Ok(())
}

#[test]
fn terminal_pipe_client_child() -> TestResult {
    let Ok(parent_pid) = std::env::var("SYSTEM_PULSE_TEST_TERMINAL_PID") else {
        return Ok(());
    };
    let nonce =
        std::env::var("SYSTEM_PULSE_TEST_TERMINAL_NONCE").map_err(|error| error.to_string())?;
    let mode =
        std::env::var("SYSTEM_PULSE_TEST_TERMINAL_MODE").map_err(|error| error.to_string())?;
    let request = Request {
        pid: parent_pid.parse().map_err(|error| format!("{error}"))?,
        created: 1,
        nonce,
    };
    let (backend, error) = match mode.as_str() {
        "error-frame" => (Backend::Intel, Some(3)),
        "amd-error-frame" => (Backend::AmdZen3, Some(3)),
        "disconnect" => (Backend::Intel, None),
        _ => return Err("unknown terminal test client mode".into()),
    };
    super::test_helpers::write_terminal_test_frame(&request, backend, error)
}

#[test]
fn short_lived_client_error_frame_survives_connect_pipe_race() -> TestResult {
    let request = terminal_test_request()?;
    let server = checked(create_pipe(&request))?;
    let client_pid = launch_terminal_test_client(&request, "error-frame")?;
    assert_eq!(
        connect_until_helper_stops_listening(&server, client_pid)?,
        PipeConnection::ClientClosed
    );
    let frame =
        read_helper_frame(&server, 0, true)?.ok_or("terminal error frame was not available")?;
    frame.validate_clock(checked(counter())?, checked(frequency())?, 0)?;
    frame.validate_backend(Backend::Intel)?;
    assert_eq!(
        frame.temperature(),
        Err("PawnIO driver is missing or could not be opened; install the approved driver separately".into())
    );
    Ok(())
}

#[test]
fn amd_terminal_error_keeps_its_backend_and_rejects_intel_expectation() -> TestResult {
    let request = terminal_test_request()?;
    let server = checked(create_pipe(&request))?;
    let client_pid = launch_terminal_test_client(&request, "amd-error-frame")?;
    assert_eq!(
        connect_until_helper_stops_listening(&server, client_pid)?,
        PipeConnection::ClientClosed
    );
    let frame =
        read_helper_frame(&server, 0, true)?.ok_or("terminal AMD error frame was not available")?;
    frame.validate_clock(checked(counter())?, checked(frequency())?, 0)?;
    assert_eq!(frame.backend, Backend::AmdZen3);
    frame.validate_backend(Backend::AmdZen3)?;
    assert!(frame.validate_backend(Backend::Intel).is_err());
    assert_eq!(
        frame.temperature(),
        Err("PawnIO driver is missing or could not be opened; install the approved driver separately".into())
    );
    Ok(())
}

#[test]
fn closed_pipe_client_with_wrong_pid_is_rejected_before_frame_read() -> TestResult {
    let request = terminal_test_request()?;
    let server = checked(create_pipe(&request))?;
    let client_pid = launch_terminal_test_client(&request, "error-frame")?;
    let wrong_pid = if client_pid == u32::MAX {
        client_pid - 1
    } else {
        client_pid + 1
    };
    assert_eq!(
        connect_until_helper_stops_listening(&server, wrong_pid)
            .err()
            .as_deref(),
        Some("Temperature pipe client is not the launched helper")
    );
    Ok(())
}

#[test]
fn closed_pipe_without_a_frame_reports_disconnect_reason() -> TestResult {
    let request = terminal_test_request()?;
    let server = checked(create_pipe(&request))?;
    let client_pid = launch_terminal_test_client(&request, "disconnect")?;
    assert_eq!(
        connect_until_helper_stops_listening(&server, client_pid)?,
        PipeConnection::ClientClosed
    );
    assert_eq!(
        read_helper_frame(&server, 0, true).err().as_deref(),
        Some("CPU temperature helper disconnected without a terminal frame")
    );
    Ok(())
}
