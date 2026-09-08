//! One OS-authorized invocation; no password ever crosses this boundary.
use super::*;
use std::{
    ffi::OsString,
    path::Path,
    process::{Command, Stdio},
};

const HELPER_MODE: &str = "--system-pulse-process-action";

fn with_authentication(
    identity: &ProcessIdentity,
    signal: ProcessSignal,
    ordinary: impl FnOnce(&ProcessIdentity, ProcessSignal) -> Result<(), ActionError>,
    authenticate: impl FnOnce(&ProcessIdentity, ProcessSignal) -> Result<(), String>,
) -> Result<(), String> {
    validate_identity(identity).map_err(|error| error.to_string())?;
    match ordinary(identity, signal) {
        Ok(()) => Ok(()),
        Err(ActionError::PermissionDenied) => authenticate(identity, signal),
        Err(error) => Err(error.to_string()),
    }
}

/// Must run on a worker: the OS dialog waits for the user's response.
pub fn send_signal_with_authentication(
    identity: &ProcessIdentity,
    signal: ProcessSignal,
) -> Result<(), String> {
    with_authentication(identity, signal, send, authenticate)
}

fn helper_arguments(identity: &ProcessIdentity, signal: ProcessSignal) -> [String; 4] {
    [
        HELPER_MODE.into(),
        identity.pid.to_string(),
        identity.start_time_ticks.to_string(),
        match signal {
            ProcessSignal::Terminate => "terminate",
            ProcessSignal::Kill => "kill",
        }
        .into(),
    ]
}

fn parse_request(arguments: &[OsString]) -> Result<(ProcessIdentity, ProcessSignal), String> {
    if arguments.len() != 4 || arguments[0] != HELPER_MODE {
        return Err("Invalid process-action request".into());
    }
    let number = |index: usize| -> Result<u64, String> {
        let text = arguments[index]
            .to_str()
            .ok_or("Invalid process-action number")?;
        if text.is_empty() || !text.bytes().all(|byte| byte.is_ascii_digit()) {
            return Err("Invalid process-action number".into());
        }
        text.parse()
            .map_err(|_| "Process-action number is out of range".into())
    };
    let identity = ProcessIdentity {
        pid: u32::try_from(number(1)?).map_err(|_| "Process-action PID is out of range")?,
        start_time_ticks: number(2)?,
    };
    validate_identity(&identity).map_err(|error| error.to_string())?;
    let signal = match arguments[3].to_str() {
        Some("terminate") => ProcessSignal::Terminate,
        Some("kill") => ProcessSignal::Kill,
        _ => return Err("Unsupported process action".into()),
    };
    Ok((identity, signal))
}

/// Call before any GUI or application-state initialization. This entry point
/// performs at most one validated action and never asks for authentication.
pub fn helper_entry(arguments: impl IntoIterator<Item = OsString>) -> Option<i32> {
    let mut arguments = arguments.into_iter();
    if arguments.next().as_deref() != Some(std::ffi::OsStr::new(HELPER_MODE)) {
        return None;
    }
    let mut request = vec![OsString::from(HELPER_MODE)];
    request.extend(arguments.take(4));
    Some(match parse_request(&request) {
        Ok((identity, signal)) => match send(&identity, signal) {
            Ok(()) => 0,
            Err(ActionError::PermissionDenied) => 11,
            Err(_) => 12,
        },
        Err(_) => 13,
    })
}

fn helper_result(code: Option<i32>) -> Result<(), String> {
    match code {
        Some(0) => Ok(()),
        Some(11) => Err("The operating system denied this action even with administrative permission. The process was not changed.".into()),
        Some(12) => Err("The selected process exited, changed identity, or could not be safely signaled. The process was not changed.".into()),
        Some(13) => Err("The authenticated process-action request was invalid. The process was not changed.".into()),
        Some(126) => Err("Authentication was cancelled. The process was not changed.".into()),
        Some(127) => Err("Authentication failed or no system authentication agent is available. The process was not changed.".into()),
        _ => Err("The system process-action helper did not complete. Check the process list before trying again.".into()),
    }
}

#[cfg(target_os = "linux")]
fn authentication_command(
    executable: &Path,
    identity: &ProcessIdentity,
    signal: ProcessSignal,
) -> Command {
    let mut command = Command::new("/usr/bin/pkexec");
    command
        .arg("--disable-internal-agent")
        .arg(executable)
        .args(helper_arguments(identity, signal));
    command
}

#[cfg(target_os = "macos")]
const AUTHENTICATE_SCRIPT: &str = r#"on run argv
    set commandText to ""
    repeat with argument in argv
        set commandText to commandText & quoted form of (argument as text) & " "
    end repeat
    try
        return do shell script (commandText & "; result=$?; /usr/bin/printf '%s' \"$result\"") with administrator privileges
    on error messageText number errorNumber
        if errorNumber is -128 then return "126"
        return "127"
    end try
end run"#;

#[cfg(target_os = "macos")]
fn authentication_command(
    executable: &Path,
    identity: &ProcessIdentity,
    signal: ProcessSignal,
) -> Command {
    let mut command = Command::new("/usr/bin/osascript");
    command
        .args(["-e", AUTHENTICATE_SCRIPT, "--"])
        .arg(executable)
        .args(helper_arguments(identity, signal));
    command
}

#[cfg(any(target_os = "linux", target_os = "macos"))]
fn authenticate(identity: &ProcessIdentity, signal: ProcessSignal) -> Result<(), String> {
    let executable = std::env::current_exe()
        .and_then(std::fs::canonicalize)
        .map_err(|error| format!("Locate the process-action helper: {error}"))?;
    let mut command = authentication_command(&executable, identity, signal);
    // No terminal password fallback and no inherited diagnostic streams.
    command.stdin(Stdio::null()).stderr(Stdio::null());
    #[cfg(target_os = "linux")]
    {
        let status = command.stdout(Stdio::null()).status()
            .map_err(|error| format!("Start system authentication (install polkit and a desktop authentication agent): {error}"))?;
        helper_result(status.code())
    }
    #[cfg(target_os = "macos")]
    {
        let output = command
            .output()
            .map_err(|error| format!("Start system authentication: {error}"))?;
        if !output.status.success() {
            return Err("System authentication did not complete. Check the process list before trying again.".into());
        }
        helper_result(
            std::str::from_utf8(&output.stdout)
                .ok()
                .and_then(|text| text.trim().parse().ok()),
        )
    }
}

#[cfg(not(any(target_os = "linux", target_os = "macos")))]
fn authenticate(_: &ProcessIdentity, _: ProcessSignal) -> Result<(), String> {
    Err("System authentication is not supported on this platform".into())
}

#[cfg(test)]
mod tests {
    use super::*;
    fn identity() -> ProcessIdentity {
        ProcessIdentity {
            pid: 4242,
            start_time_ticks: 987654321,
        }
    }

    #[test]
    fn only_permission_denial_authenticates_and_preserves_the_request() {
        for signal in [ProcessSignal::Terminate, ProcessSignal::Kill] {
            with_authentication(
                &identity(),
                signal,
                |_, _| Ok(()),
                |_, _| panic!("ordinary success authenticated"),
            )
            .unwrap();
            assert!(
                with_authentication(
                    &identity(),
                    signal,
                    |_, _| Err("identity changed".into()),
                    |_, _| panic!("identity failure authenticated")
                )
                .is_err()
            );
            let result = with_authentication(
                &identity(),
                signal,
                |_, _| Err(ActionError::PermissionDenied),
                |request, action| {
                    assert_eq!(*request, identity());
                    assert_eq!(action, signal);
                    Err("cancelled".into())
                },
            );
            assert_eq!(result, Err("cancelled".into()));
        }
    }

    #[test]
    fn invalid_identity_never_dispatches_or_authenticates() {
        for request in [
            ProcessIdentity {
                pid: 1,
                ..identity()
            },
            ProcessIdentity {
                start_time_ticks: 0,
                ..identity()
            },
        ] {
            assert!(
                with_authentication(
                    &request,
                    ProcessSignal::Kill,
                    |_, _| panic!("dispatched"),
                    |_, _| panic!("authenticated")
                )
                .is_err()
            );
        }
    }

    #[test]
    fn helper_rejects_extra_missing_overflow_and_shell_input() {
        let valid = helper_arguments(&identity(), ProcessSignal::Kill).map(OsString::from);
        assert_eq!(
            parse_request(&valid).unwrap(),
            (identity(), ProcessSignal::Kill)
        );
        for (index, bad) in [
            (1, "0"),
            (1, "-1"),
            (1, "4294967296"),
            (1, "42;kill -9 1"),
            (2, "0"),
            (2, "18446744073709551616"),
            (3, "stop"),
        ] {
            let mut request = valid.clone();
            request[index] = bad.into();
            assert!(parse_request(&request).is_err());
        }
        assert!(parse_request(&valid[..3]).is_err());
        let mut extra = valid.to_vec();
        extra.push("extra".into());
        assert_eq!(helper_entry(extra), Some(13));
        assert_eq!(helper_entry([OsString::from("--unrelated")]), None);
    }

    #[test]
    fn cancellation_and_helper_failures_are_not_success() {
        assert!(helper_result(Some(0)).is_ok());
        for code in [
            Some(11),
            Some(12),
            Some(13),
            Some(126),
            Some(127),
            Some(1),
            None,
        ] {
            assert!(helper_result(code).is_err());
        }
        assert!(helper_result(Some(126)).unwrap_err().contains("cancelled"));
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn authentication_uses_fixed_program_and_separate_arguments() {
        let command = authentication_command(
            Path::new("/tmp/path with ' quotes/$literal/app"),
            &identity(),
            ProcessSignal::Terminate,
        );
        assert_eq!(command.get_program(), "/usr/bin/pkexec");
        assert_eq!(
            command.get_args().collect::<Vec<_>>(),
            [
                "--disable-internal-agent",
                "/tmp/path with ' quotes/$literal/app",
                HELPER_MODE,
                "4242",
                "987654321",
                "terminate"
            ]
        );
    }

    #[cfg(target_os = "macos")]
    #[test]
    fn applescript_preserves_arguments_and_returns_helper_exit_status() {
        // Exercise Apple's real parser and shell quoting without requesting
        // privileges. The production script differs only by the OS auth clause.
        let directory =
            std::env::temp_dir().join(format!("pulse-action-'-$literal-{}", std::process::id()));
        std::fs::create_dir_all(&directory).unwrap();
        let executable = directory.join("false helper");
        std::os::unix::fs::symlink("/usr/bin/false", &executable).unwrap();
        let output = Command::new("/usr/bin/osascript")
            .args([
                "-e",
                &AUTHENTICATE_SCRIPT.replace(" with administrator privileges", ""),
                "--",
            ])
            .arg(&executable)
            .args(helper_arguments(&identity(), ProcessSignal::Kill))
            .output()
            .unwrap();
        std::fs::remove_file(&executable).unwrap();
        std::fs::remove_dir(&directory).unwrap();
        assert!(
            output.status.success(),
            "{}",
            String::from_utf8_lossy(&output.stderr)
        );
        assert_eq!(String::from_utf8(output.stdout).unwrap().trim(), "1");
    }
}
