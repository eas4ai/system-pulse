//! Independent lifetime enforcement remains runnable during a blocked driver call.
use std::{
    sync::{
        Arc, Mutex,
        atomic::{AtomicBool, Ordering},
    },
    thread::{self, JoinHandle},
    time::{Duration, Instant},
};
const POLL: Duration = Duration::from_millis(25);
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(super) enum StopReason {
    CallerExited,
    OperationExpired,
    SessionExpired,
}
impl StopReason {
    pub fn exit_code(self) -> u32 {
        match self {
            Self::CallerExited => 81,
            Self::OperationExpired => 82,
            Self::SessionExpired => 83,
        }
    }
}
struct State {
    cancelled: AtomicBool,
    operation_deadline: Mutex<Option<Instant>>,
}
pub(super) struct Watchdog {
    state: Arc<State>,
    worker: Option<JoinHandle<()>>,
    operation_limit: Duration,
}
impl Watchdog {
    pub fn start(
        parent_alive: impl Fn() -> bool + Send + 'static,
        terminate: impl FnOnce(StopReason) + Send + 'static,
        operation_limit: Duration,
        session_limit: Duration,
    ) -> Result<Self, String> {
        let longest = Duration::from_secs(24 * 60 * 60);
        if operation_limit.is_zero()
            || session_limit.is_zero()
            || operation_limit > longest
            || session_limit > longest
        {
            return Err("Invalid thermal watchdog deadlines".into());
        }
        let state = Arc::new(State {
            cancelled: AtomicBool::new(false),
            operation_deadline: Mutex::new(None),
        });
        let inner = state.clone();
        let session_deadline = Instant::now() + session_limit;
        let worker = thread::Builder::new()
            .name("pulse-thermal-watchdog".into())
            .spawn(move || {
                loop {
                    if inner.cancelled.load(Ordering::Acquire) {
                        break;
                    }
                    let now = Instant::now();
                    let operation_expired = inner
                        .operation_deadline
                        .lock()
                        .unwrap_or_else(|e| e.into_inner())
                        .is_some_and(|deadline| now >= deadline);
                    let reason = if !parent_alive() {
                        Some(StopReason::CallerExited)
                    } else if now >= session_deadline {
                        Some(StopReason::SessionExpired)
                    } else if operation_expired {
                        Some(StopReason::OperationExpired)
                    } else {
                        None
                    };
                    if let Some(reason) = reason {
                        if !inner.cancelled.load(Ordering::Acquire) {
                            terminate(reason);
                        }
                        break;
                    }
                    thread::sleep(POLL);
                }
            })
            .map_err(|e| format!("Start thermal helper watchdog: {e}"))?;
        Ok(Self {
            state,
            worker: Some(worker),
            operation_limit,
        })
    }
    pub fn operation<T>(&self, operation: impl FnOnce() -> T) -> T {
        *self
            .state
            .operation_deadline
            .lock()
            .unwrap_or_else(|e| e.into_inner()) = Some(Instant::now() + self.operation_limit);
        let _reset = OperationDeadline(&self.state);
        operation()
    }
}
struct OperationDeadline<'a>(&'a State);
impl Drop for OperationDeadline<'_> {
    fn drop(&mut self) {
        *self
            .0
            .operation_deadline
            .lock()
            .unwrap_or_else(|e| e.into_inner()) = None;
    }
}
impl Drop for Watchdog {
    fn drop(&mut self) {
        self.state.cancelled.store(true, Ordering::Release);
        if let Some(worker) = self.worker.take() {
            let _ = worker.join();
        }
    }
}

#[cfg(target_os = "windows")]
pub(super) fn terminate_helper(reason: StopReason) {
    use windows::Win32::System::Threading::{GetCurrentProcess, TerminateProcess};
    // SAFETY: only the current helper process is terminated, using its pseudo handle.
    // This bypasses DLL teardown and does not need rights from ShellExecute's handle.
    let _ = unsafe { TerminateProcess(GetCurrentProcess(), reason.exit_code()) };
    // A successful self-termination does not return. Fail closed if Windows rejects it.
    std::process::abort();
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::process::{Child, Command, Stdio};
    use std::sync::mpsc;
    const CHILD_MODE: &str = "SYSTEM_PULSE_TEST_THERMAL_WATCHDOG";
    struct ChildGuard(Child);
    impl Drop for ChildGuard {
        fn drop(&mut self) {
            let _ = self.0.kill();
            let _ = self.0.wait();
        }
    }

    #[test]
    fn watchdog_process_child() {
        let Ok(mode) = std::env::var(CHILD_MODE) else {
            return;
        };
        #[cfg(target_os = "windows")]
        if mode == "parent" {
            thread::sleep(Duration::from_secs(30));
            return;
        }
        #[cfg(target_os = "windows")]
        if mode == "caller" {
            native_caller_child();
            return;
        }
        let session = if mode == "session" {
            Duration::from_millis(100)
        } else {
            Duration::from_secs(30)
        };
        let watchdog = Watchdog::start(
            || true,
            |reason| {
                #[cfg(target_os = "windows")]
                terminate_helper(reason);
                #[cfg(not(target_os = "windows"))]
                std::process::exit(reason.exit_code() as i32);
            },
            Duration::from_millis(100),
            session,
        )
        .unwrap();
        if mode == "operation" {
            watchdog.operation(|| thread::sleep(Duration::from_secs(30)));
        } else {
            thread::sleep(Duration::from_secs(30));
        }
        panic!("watchdog failed to terminate the stalled test process");
    }

    #[test]
    fn stalled_process_is_terminated_for_operation_and_session_expiry() {
        for (mode, expected) in [
            ("operation", StopReason::OperationExpired),
            ("session", StopReason::SessionExpired),
        ] {
            let mut child = ChildGuard(
                Command::new(std::env::current_exe().unwrap())
                    .args([
                        "--exact",
                        "windows_thermal::watchdog::tests::watchdog_process_child",
                        "--nocapture",
                    ])
                    .env(CHILD_MODE, mode)
                    .stdin(Stdio::null())
                    .stdout(Stdio::null())
                    .stderr(Stdio::null())
                    .spawn()
                    .unwrap(),
            );
            let deadline = Instant::now() + Duration::from_secs(5);
            let result = loop {
                if let Some(status) = child.0.try_wait().unwrap() {
                    break status;
                }
                assert!(
                    Instant::now() < deadline,
                    "stalled watchdog child remained alive"
                );
                thread::sleep(Duration::from_millis(10));
            };
            assert_eq!(result.code(), Some(expected.exit_code() as i32), "{mode}");
        }
    }

    #[cfg(target_os = "windows")]
    fn native_caller_child() {
        use crate::windows_thermal::identity::{Caller, alive, creation_time, own, raw};
        use std::io::Write;
        use windows::Win32::System::Threading::{
            OpenProcess, PROCESS_QUERY_LIMITED_INFORMATION, PROCESS_SYNCHRONIZE,
        };
        let pid = std::env::var("SYSTEM_PULSE_TEST_WATCHDOG_CALLER")
            .unwrap()
            .parse()
            .unwrap();
        let retained = own(unsafe {
            OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_SYNCHRONIZE,
                false,
                pid,
            )
        }
        .unwrap());
        let caller = Caller::open(pid, creation_time(raw(&retained)).unwrap()).unwrap();
        let watchdog = Watchdog::start(
            move || alive(raw(&caller.handle)),
            terminate_helper,
            Duration::from_secs(30),
            Duration::from_secs(30),
        )
        .unwrap();
        println!("watching-caller");
        std::io::stdout().flush().unwrap();
        watchdog.operation(|| thread::sleep(Duration::from_secs(30)));
        panic!("caller exited but stalled helper survived");
    }

    #[cfg(target_os = "windows")]
    #[test]
    fn native_exited_caller_terminates_helper_during_stalled_read() {
        use std::io::{BufRead, BufReader};
        let executable = std::env::current_exe().unwrap();
        let args = [
            "--exact",
            "windows_thermal::watchdog::tests::watchdog_process_child",
            "--nocapture",
        ];
        let mut parent = ChildGuard(
            Command::new(&executable)
                .args(args)
                .env(CHILD_MODE, "parent")
                .stdin(Stdio::null())
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .spawn()
                .unwrap(),
        );
        let mut watcher = ChildGuard(
            Command::new(&executable)
                .args(args)
                .env(CHILD_MODE, "caller")
                .env(
                    "SYSTEM_PULSE_TEST_WATCHDOG_CALLER",
                    parent.0.id().to_string(),
                )
                .stdin(Stdio::null())
                .stdout(Stdio::piped())
                .stderr(Stdio::null())
                .spawn()
                .unwrap(),
        );
        let output = watcher.0.stdout.take().unwrap();
        let (tx, rx) = mpsc::channel();
        let reader = thread::spawn(move || {
            for line in BufReader::new(output).lines() {
                if line.unwrap().contains("watching-caller") {
                    let _ = tx.send(());
                    break;
                }
            }
        });
        rx.recv_timeout(Duration::from_secs(5))
            .expect("watchdog child did not pin caller");
        reader.join().unwrap();
        parent.0.kill().unwrap();
        parent.0.wait().unwrap();
        let deadline = Instant::now() + Duration::from_secs(5);
        let status = loop {
            if let Some(status) = watcher.0.try_wait().unwrap() {
                break status;
            }
            assert!(
                Instant::now() < deadline,
                "stalled helper survived caller exit"
            );
            thread::sleep(Duration::from_millis(10));
        };
        assert_eq!(
            status.code(),
            Some(StopReason::CallerExited.exit_code() as i32)
        );
    }

    #[test]
    fn blocked_operation_still_reaches_deadline_callback() {
        let (tx, rx) = mpsc::channel();
        let watchdog = Watchdog::start(
            || true,
            move |reason| tx.send(reason).unwrap(),
            Duration::from_millis(40),
            Duration::from_secs(10),
        )
        .unwrap();
        watchdog.operation(|| {
            assert_eq!(
                rx.recv_timeout(Duration::from_secs(1)).unwrap(),
                StopReason::OperationExpired
            )
        });
    }

    #[test]
    fn caller_exit_is_observed_during_an_operation() {
        let alive = Arc::new(AtomicBool::new(true));
        let parent = alive.clone();
        let (tx, rx) = mpsc::channel();
        let watchdog = Watchdog::start(
            move || parent.load(Ordering::Acquire),
            move |reason| tx.send(reason).unwrap(),
            Duration::from_secs(10),
            Duration::from_secs(10),
        )
        .unwrap();
        watchdog.operation(|| {
            alive.store(false, Ordering::Release);
            assert_eq!(
                rx.recv_timeout(Duration::from_secs(1)).unwrap(),
                StopReason::CallerExited
            );
        });
    }

    #[test]
    fn session_deadline_applies_without_active_driver_work() {
        let (tx, rx) = mpsc::channel();
        let _watchdog = Watchdog::start(
            || true,
            move |reason| tx.send(reason).unwrap(),
            Duration::from_secs(10),
            Duration::from_millis(40),
        )
        .unwrap();
        assert_eq!(
            rx.recv_timeout(Duration::from_secs(1)).unwrap(),
            StopReason::SessionExpired
        );
    }

    #[test]
    fn completed_operation_clears_its_deadline_and_drop_cancels_watchdog() {
        let (tx, rx) = mpsc::channel();
        let watchdog = Watchdog::start(
            || true,
            move |reason| tx.send(reason).unwrap(),
            Duration::from_millis(40),
            Duration::from_secs(10),
        )
        .unwrap();
        assert_eq!(watchdog.operation(|| 42), 42);
        assert!(rx.recv_timeout(Duration::from_millis(100)).is_err());
        let started = Instant::now();
        drop(watchdog);
        assert!(started.elapsed() < Duration::from_secs(1));
        assert!(matches!(
            rx.try_recv(),
            Err(mpsc::TryRecvError::Disconnected)
        ));
    }
}
