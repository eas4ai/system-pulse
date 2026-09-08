//! Explicit process actions, separate from the read-only sampling worker.
use crate::ProcessIdentity;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ProcessSignal {
    Terminate,
    Kill,
}

mod authentication;
pub use authentication::{helper_entry, send_signal_with_authentication};

#[cfg(target_os = "macos")]
mod macos;

#[derive(Debug, PartialEq, Eq)]
enum ActionError {
    PermissionDenied,
    Failed(String),
}

impl From<String> for ActionError {
    fn from(message: String) -> Self {
        Self::Failed(message)
    }
}

impl From<&str> for ActionError {
    fn from(message: &str) -> Self {
        Self::Failed(message.into())
    }
}

impl std::fmt::Display for ActionError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::PermissionDenied => {
                formatter.write_str("Permission denied; the process was not changed")
            }
            Self::Failed(message) => formatter.write_str(message),
        }
    }
}

#[cfg(unix)]
fn os_error(operation: &str, error: std::io::Error) -> ActionError {
    match error.raw_os_error() {
        Some(libc::EPERM | libc::EACCES) => ActionError::PermissionDenied,
        Some(libc::ESRCH | libc::ENOENT) => "The selected process has already exited".into(),
        Some(libc::ENOSYS) => "This kernel does not support identity-safe process actions".into(),
        _ => format!("{operation}: {error}").into(),
    }
}

fn validate_identity(identity: &ProcessIdentity) -> Result<(), ActionError> {
    if identity.pid <= 1 || identity.pid == std::process::id() || identity.pid > i32::MAX as u32 {
        return Err("This process is protected from task actions".into());
    }
    if identity.start_time_ticks == 0 {
        return Err("The selected process has no verified start identity".into());
    }
    Ok(())
}

pub fn send_signal(identity: &ProcessIdentity, signal: ProcessSignal) -> Result<(), String> {
    send(identity, signal).map_err(|error| error.to_string())
}

fn send(identity: &ProcessIdentity, signal: ProcessSignal) -> Result<(), ActionError> {
    validate_identity(identity)?;
    #[cfg(target_os = "linux")]
    return linux::send(identity, signal);
    #[cfg(target_os = "macos")]
    return macos::send(identity, signal);
    #[cfg(not(any(target_os = "linux", target_os = "macos")))]
    {
        let _ = signal;
        Err("Identity-safe process actions are not supported on this platform yet".into())
    }
}

#[cfg(target_os = "linux")]
mod linux {
    use super::*;
    use std::{
        fs::File,
        io::Read,
        os::fd::{AsRawFd, FromRawFd, OwnedFd},
    };

    fn error(operation: &str) -> ActionError {
        os_error(operation, std::io::Error::last_os_error())
    }

    pub(super) fn send(
        identity: &ProcessIdentity,
        signal: ProcessSignal,
    ) -> Result<(), ActionError> {
        // A pidfd pins the target across exit/PID reuse. Verify start time after
        // acquiring it, then signal the handle rather than the numeric PID.
        // https://man7.org/linux/man-pages/man2/pidfd_send_signal.2.html
        // SAFETY: integer arguments match pidfd_open(2); flags are zero.
        let fd = unsafe { libc::syscall(libc::SYS_pidfd_open, identity.pid as libc::pid_t, 0_u32) };
        if fd < 0 {
            return Err(error("Open selected process"));
        }
        // SAFETY: a successful pidfd_open returns a new owned descriptor.
        let fd = unsafe { OwnedFd::from_raw_fd(fd as i32) };
        let mut text = String::new();
        File::open(format!("/proc/{}/stat", identity.pid))
            .map_err(|e| os_error("Read selected process identity", e))?
            .take(4096)
            .read_to_string(&mut text)
            .map_err(|e| os_error("Read selected process identity", e))?;
        if text.len() >= 4096 {
            return Err("Selected process identity exceeds its read limit".into());
        }
        if parse_identity(&text)? != *identity {
            return Err(
                "The selected process exited or its PID now belongs to another process".into(),
            );
        }
        let signal = match signal {
            ProcessSignal::Terminate => libc::SIGTERM,
            ProcessSignal::Kill => libc::SIGKILL,
        };
        // SAFETY: fd remains owned, signal is one of the two supported signals,
        // null siginfo requests kernel-generated metadata, and flags are zero.
        let result = unsafe {
            libc::syscall(
                libc::SYS_pidfd_send_signal,
                fd.as_raw_fd(),
                signal,
                std::ptr::null::<libc::siginfo_t>(),
                0_u32,
            )
        };
        if result < 0 {
            return Err(error("Signal selected process"));
        }
        Ok(())
    }

    fn parse_identity(text: &str) -> Result<ProcessIdentity, String> {
        let open = text.find('(').ok_or("Process identity has no name")?;
        let close = text
            .rfind(')')
            .filter(|close| *close > open)
            .ok_or("Process identity has an invalid name")?;
        let pid = text[..open]
            .trim()
            .parse()
            .map_err(|_| "Process identity has an invalid PID")?;
        let start_time_ticks = text[close + 1..]
            .split_whitespace()
            .nth(19)
            .ok_or("Process identity has no start time")?
            .parse()
            .map_err(|_| "Process identity has an invalid start time")?;
        Ok(ProcessIdentity {
            pid,
            start_time_ticks,
        })
    }

    #[cfg(test)]
    mod tests {
        use super::*;

        #[test]
        fn malformed_identity_is_rejected_without_panicking() {
            for text in ["", ")(", "1 ()", "no (name) S", "1 (name) S"] {
                assert!(parse_identity(text).is_err());
            }
            let fields = std::iter::once("S")
                .chain(std::iter::repeat_n("0", 18))
                .chain(["123"])
                .collect::<Vec<_>>()
                .join(" ");
            assert_eq!(
                parse_identity(&format!("42 (odd ) (name) {fields}")).unwrap(),
                ProcessIdentity {
                    pid: 42,
                    start_time_ticks: 123
                }
            );
        }
    }
}

#[cfg(all(test, any(target_os = "linux", target_os = "macos")))]
mod tests {
    use super::*;
    use std::{
        os::unix::process::ExitStatusExt,
        process::{Child, Command},
        time::{Duration, Instant},
    };

    struct OwnedChild(Child);
    impl Drop for OwnedChild {
        fn drop(&mut self) {
            let _ = self.0.kill();
            let _ = self.0.wait();
        }
    }

    fn child() -> (OwnedChild, ProcessIdentity) {
        let child = OwnedChild(Command::new("sleep").arg("10").spawn().unwrap());
        #[cfg(target_os = "linux")]
        let stat = std::fs::read_to_string(format!("/proc/{}/stat", child.0.id())).unwrap();
        #[cfg(target_os = "linux")]
        let start_time_ticks = stat[stat.rfind(')').unwrap() + 1..]
            .split_whitespace()
            .nth(19)
            .unwrap()
            .parse()
            .unwrap();
        #[cfg(target_os = "macos")]
        let start_time_ticks = {
            let mut system = sysinfo::System::new();
            system.refresh_processes_specifics(
                sysinfo::ProcessesToUpdate::Some(&[sysinfo::Pid::from_u32(child.0.id())]),
                true,
                sysinfo::ProcessRefreshKind::nothing(),
            );
            system
                .process(sysinfo::Pid::from_u32(child.0.id()))
                .unwrap()
                .start_time_microseconds()
        };
        let identity = ProcessIdentity {
            pid: child.0.id(),
            start_time_ticks,
        };
        (child, identity)
    }

    fn wait(child: &mut Child) -> std::process::ExitStatus {
        let deadline = Instant::now() + Duration::from_secs(2);
        loop {
            if let Some(status) = child.try_wait().unwrap() {
                return status;
            }
            assert!(Instant::now() < deadline, "signaled child did not exit");
            std::thread::sleep(Duration::from_millis(10));
        }
    }

    #[test]
    fn only_the_matching_owned_identity_receives_each_signal() {
        for (signal, expected) in [(ProcessSignal::Terminate, 15), (ProcessSignal::Kill, 9)] {
            let (mut child, identity) = child();
            let wrong = ProcessIdentity {
                start_time_ticks: identity.start_time_ticks + 1,
                ..identity.clone()
            };
            assert!(send_signal(&wrong, signal).is_err());
            assert!(
                child.0.try_wait().unwrap().is_none(),
                "wrong start identity killed child"
            );
            send_signal(&identity, signal).unwrap();
            assert_eq!(wait(&mut child.0).signal(), Some(expected));
        }
    }

    #[test]
    fn exited_process_and_protected_targets_are_rejected() {
        let (mut child, identity) = child();
        child.0.kill().unwrap();
        child.0.wait().unwrap();
        assert!(send_signal(&identity, ProcessSignal::Kill).is_err());
        for pid in [0, 1, std::process::id(), u32::MAX] {
            assert!(
                send_signal(
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
}
