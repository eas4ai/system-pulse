//! Bind BSD birth time to the kernel PID version before signaling.
use super::*;

// ABI declarations for PROC_PIDT_BSDINFOWITHUNIQID from Apple's XNU
// bsd/sys/proc_info.h. The SDK omits these private interfaces; unsupported
// versions fail closed. No fallback to kill(pid, signal) is permitted.
#[repr(C)]
#[derive(Default)]
struct UniqueIdentity {
    executable_uuid: [u8; 16],
    unique_id: u64,
    parent_unique_id: u64,
    pid_version: i32,
    reserved2: u32,
    reserved3: u64,
    reserved4: u64,
}

#[repr(C)]
struct BsdIdentity {
    bsd: libc::proc_bsdinfo,
    unique: UniqueIdentity,
}

#[repr(C)]
struct AuditToken([u32; 8]);

type SignalWithToken = unsafe extern "C" fn(*const AuditToken, libc::c_int) -> libc::c_int;

fn signal_function() -> Result<SignalWithToken, ActionError> {
    // SAFETY: the symbol is resolved from the system library namespace and is
    // never unloaded. Apple's libproc.h declares this exact C ABI.
    let symbol =
        unsafe { libc::dlsym(libc::RTLD_DEFAULT, c"proc_signal_with_audittoken".as_ptr()) };
    if symbol.is_null() {
        return Err("This macOS version does not support identity-safe process actions".into());
    }
    // SAFETY: non-null system symbol has the documented function signature.
    Ok(unsafe { std::mem::transmute::<*mut libc::c_void, SignalWithToken>(symbol) })
}

fn read_identity(pid: u32) -> Result<BsdIdentity, ActionError> {
    let mut info = std::mem::MaybeUninit::<BsdIdentity>::zeroed();
    // SAFETY: proc_pidinfo receives a correctly aligned writable buffer and its
    // exact size. Flavor 18 returns BSD and unique identity in one observation.
    let count = unsafe {
        libc::proc_pidinfo(
            pid as i32,
            18,
            0,
            info.as_mut_ptr().cast(),
            std::mem::size_of::<BsdIdentity>() as i32,
        )
    };
    if count <= 0 {
        return Err(os_error(
            "Read selected process identity",
            std::io::Error::last_os_error(),
        ));
    }
    if count as usize != std::mem::size_of::<BsdIdentity>() {
        return Err("macOS returned an unsupported process identity record".into());
    }
    // SAFETY: the system filled the complete C record; all fields are integers.
    Ok(unsafe { info.assume_init() })
}

fn token_for(identity: &ProcessIdentity, info: &BsdIdentity) -> Result<AuditToken, ActionError> {
    let start = info
        .bsd
        .pbi_start_tvsec
        .checked_mul(1_000_000)
        .and_then(|seconds| seconds.checked_add(info.bsd.pbi_start_tvusec));
    if info.bsd.pbi_pid != identity.pid
        || info.bsd.pbi_start_tvusec >= 1_000_000
        || start != Some(identity.start_time_ticks)
        || identity.start_time_ticks == 0
    {
        return Err("The selected process exited or its PID now belongs to another process".into());
    }
    // The target lookup uses audit token PID (word 5) and PID version (word 7).
    // Other fields describe credentials and are not used to authorize the
    // caller: the kernel independently checks the signaling process's rights.
    let mut token = AuditToken([0; 8]);
    token.0[5] = identity.pid;
    token.0[7] = info.unique.pid_version as u32;
    Ok(token)
}

pub(super) fn send(identity: &ProcessIdentity, signal: ProcessSignal) -> Result<(), ActionError> {
    let signal_function = signal_function()?;
    let token = token_for(identity, &read_identity(identity.pid)?)?;
    let number = match signal {
        ProcessSignal::Terminate => libc::SIGTERM,
        ProcessSignal::Kill => libc::SIGKILL,
    };
    // SAFETY: the live token has the exact ABI. The kernel resolves and holds
    // the matching PID version before checking permission and delivering the
    // signal. Exit/reuse after read_identity cannot redirect the request.
    let error = unsafe { signal_function(&token, number) };
    if error == 0 {
        Ok(())
    } else {
        // libproc returns the errno value directly, not -1 with thread errno.
        Err(os_error(
            "Signal selected process",
            std::io::Error::from_raw_os_error(error),
        ))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn token_rejects_subsecond_identity_changes_and_invalid_records() {
        let info = read_identity(std::process::id()).unwrap();
        let identity = ProcessIdentity {
            pid: info.bsd.pbi_pid,
            start_time_ticks: info.bsd.pbi_start_tvsec * 1_000_000 + info.bsd.pbi_start_tvusec,
        };
        let token = token_for(&identity, &info).unwrap();
        assert_eq!(token.0[5], identity.pid);
        assert_eq!(token.0[7], info.unique.pid_version as u32);
        assert!(
            token_for(
                &ProcessIdentity {
                    start_time_ticks: identity.start_time_ticks + 1,
                    ..identity.clone()
                },
                &info
            )
            .is_err()
        );
        assert!(
            token_for(
                &ProcessIdentity {
                    pid: identity.pid + 1,
                    ..identity
                },
                &info
            )
            .is_err()
        );
        assert_eq!(std::mem::size_of::<UniqueIdentity>(), 56);
    }

    #[test]
    fn stale_pid_version_cannot_signal_an_owned_process() {
        let mut child = std::process::Command::new("/bin/sleep")
            .arg("10")
            .spawn()
            .unwrap();
        let result = (|| {
            let info = read_identity(child.id())?;
            let identity = ProcessIdentity {
                pid: child.id(),
                start_time_ticks: info.bsd.pbi_start_tvsec * 1_000_000 + info.bsd.pbi_start_tvusec,
            };
            let mut token = token_for(&identity, &info)?;
            token.0[7] = token.0[7].wrapping_add(1);
            let function = signal_function()?;
            // SAFETY: valid token ABI with a deliberately wrong generation.
            let result = unsafe { function(&token, libc::SIGKILL) };
            assert_ne!(result, 0);
            assert!(child.try_wait().unwrap().is_none());
            Ok::<_, ActionError>(())
        })();
        let _ = child.kill();
        let _ = child.wait();
        result.unwrap();
    }
}
