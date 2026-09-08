use super::*;
use crate::UpdateKind;

fn retained_process() -> ProcessInner {
    // This PID cannot provide metadata. A successful refresh must have skipped
    // the native argument query, rather than quietly succeeding through it.
    let mut process = ProcessInner::new_empty(Pid::from_u32(u32::MAX));
    process.name = "retained-name".into();
    process
}

#[test]
fn unrequested_arguments_do_not_require_a_native_read() {
    let mut process = retained_process();
    assert!(unsafe { get_process_infos(&mut process, ProcessRefreshKind::nothing()) });
    assert_eq!(process.name, "retained-name");
    assert!(process.exe.is_none());
    assert!(process.cmd.is_empty());
    assert!(process.environ.is_empty());
}

#[test]
fn a_missing_name_still_requires_native_metadata() {
    let mut process = retained_process();
    process.name.clear();
    assert!(!unsafe { get_process_infos(&mut process, ProcessRefreshKind::nothing()) });
    assert!(process.name.is_empty());
}

#[test]
fn requested_missing_metadata_and_always_refresh_still_read() {
    for kind in [UpdateKind::Always, UpdateKind::OnlyIfNotSet] {
        for refresh in [
            ProcessRefreshKind::nothing().with_exe(kind),
            ProcessRefreshKind::nothing().with_cmd(kind),
            ProcessRefreshKind::nothing().with_environ(kind),
        ] {
            assert!(!unsafe { get_process_infos(&mut retained_process(), refresh) });
        }
    }
    let mut process = retained_process();
    process.exe = Some("/retained/executable".into());
    process.cmd = vec!["retained-argument".into()];
    process.environ = vec!["RETAINED=value".into()];
    for refresh in [
        ProcessRefreshKind::nothing().with_exe(UpdateKind::Always),
        ProcessRefreshKind::nothing().with_cmd(UpdateKind::Always),
        ProcessRefreshKind::nothing().with_environ(UpdateKind::Always),
    ] {
        assert!(!unsafe { get_process_infos(&mut process, refresh) });
    }
}

#[test]
fn populated_metadata_respects_only_if_not_set() {
    let mut process = retained_process();
    process.exe = Some("/retained/executable".into());
    process.cmd = vec!["retained-argument".into()];
    process.environ = vec!["RETAINED=value".into()];
    let refresh = ProcessRefreshKind::nothing()
        .with_exe(UpdateKind::OnlyIfNotSet)
        .with_cmd(UpdateKind::OnlyIfNotSet)
        .with_environ(UpdateKind::OnlyIfNotSet);
    assert!(unsafe { get_process_infos(&mut process, refresh) });
    assert_eq!(process.exe, Some("/retained/executable".into()));
    assert_eq!(process.cmd, [OsString::from("retained-argument")]);
    assert_eq!(process.environ, [OsString::from("RETAINED=value")]);
}

#[test]
fn native_current_process_metadata_still_populates() {
    let mut process = ProcessInner::new_empty(crate::get_current_pid().unwrap());
    assert!(unsafe { get_process_infos(&mut process, ProcessRefreshKind::nothing()) });
    assert!(!process.name.is_empty());
    assert!(process.cmd.is_empty());
    assert!(process.environ.is_empty());
    assert!(unsafe {
        get_process_infos(
            &mut process,
            ProcessRefreshKind::nothing()
                .with_exe(UpdateKind::Always)
                .with_cmd(UpdateKind::Always)
                .with_environ(UpdateKind::Always),
        )
    });
    assert!(process.exe.is_some());
    assert!(!process.cmd.is_empty());
    assert!(!process.environ.is_empty());
}

#[test]
fn retained_process_counters_and_replaced_identity_refresh() {
    use crate::{ProcessesToUpdate, System};
    let pid = crate::get_current_pid().unwrap();
    let mut system = System::new();
    let refresh = ProcessRefreshKind::nothing()
        .with_cpu()
        .with_memory()
        .with_disk_usage()
        .with_user(UpdateKind::Always);
    system.refresh_processes_specifics(ProcessesToUpdate::Some(&[pid]), true, refresh);
    let original = system.process(pid).unwrap();
    let started = original.start_time();
    let cpu = original.accumulated_cpu_time();
    let user = original.user_id().cloned();
    let deadline = std::time::Instant::now() + std::time::Duration::from_millis(30);
    while std::time::Instant::now() < deadline {
        std::hint::spin_loop();
    }
    system.refresh_processes_specifics(ProcessesToUpdate::Some(&[pid]), true, refresh);
    let updated = system.process(pid).unwrap();
    assert!(updated.accumulated_cpu_time() > cpu);
    assert!(updated.memory() > 0);
    assert_eq!(updated.start_time(), started);
    assert_eq!(updated.user_id(), user.as_ref());
    let stale = system.inner.processes_mut().get_mut(&pid).unwrap();
    stale.inner.start_time = 0;
    stale.inner.name = "replaced-process-must-not-survive".into();
    system.refresh_processes_specifics(ProcessesToUpdate::Some(&[pid]), true, refresh);
    let replaced = system.process(pid).unwrap();
    assert_eq!(replaced.start_time(), started);
    assert_ne!(replaced.name(), "replaced-process-must-not-survive");
    assert_eq!(replaced.user_id(), user.as_ref());
}

#[test]
fn same_pid_exec_refreshes_requested_metadata_and_exit_removes_process() {
    use crate::{ProcessesToUpdate, System};
    use std::io::Write;
    use std::process::{Child, Command, Stdio};
    struct OwnedChild(Child);
    impl Drop for OwnedChild {
        fn drop(&mut self) {
            let _ = self.0.kill();
            let _ = self.0.wait();
        }
    }
    let mut child = OwnedChild(
        Command::new("/bin/sh")
            .args(["-c", "read gate; exec /bin/sleep 30"])
            .stdin(Stdio::piped())
            .spawn()
            .unwrap(),
    );
    let pid = Pid::from_u32(child.0.id());
    let refresh = ProcessRefreshKind::nothing()
        .with_exe(UpdateKind::Always)
        .with_cmd(UpdateKind::Always);
    let mut system = System::new();
    system.refresh_processes_specifics(ProcessesToUpdate::Some(&[pid]), true, refresh);
    assert!(!system.process(pid).unwrap().name().is_empty());
    child.0.stdin.take().unwrap().write_all(b"go\n").unwrap();
    let deadline = std::time::Instant::now() + std::time::Duration::from_secs(3);
    loop {
        system.refresh_processes_specifics(ProcessesToUpdate::Some(&[pid]), true, refresh);
        let process = system.process(pid).unwrap();
        if process.exe().and_then(|p| p.file_name()) == Some(OsStr::new("sleep")) {
            assert!(process.cmd().iter().any(|arg| arg == "30"));
            break;
        }
        assert!(
            std::time::Instant::now() < deadline,
            "exec metadata did not refresh"
        );
        std::thread::sleep(std::time::Duration::from_millis(10));
    }
    child.0.kill().unwrap();
    child.0.wait().unwrap();
    system.refresh_processes_specifics(ProcessesToUpdate::All, true, refresh);
    assert!(system.process(pid).is_none());
}
