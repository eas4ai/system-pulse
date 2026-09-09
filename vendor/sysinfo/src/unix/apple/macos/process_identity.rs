//! Read KERN_PROC_PID metadata when full libproc BSD info is denied.
//!
//! Darwin's LP64 kinfo_proc ABI is declared by sys/sysctl.h and sys/proc.h.
//! libc does not expose that type on Apple targets. Decode bytes instead of
//! casting an incomplete struct; require the full 648-byte record. The native
//! verification tests independently compare these fields with SDK C accessors.

const RECORD_SIZE: usize = 648;

pub(super) fn read(pid: i32) -> Option<libc::proc_bsdinfo> {
    let mut data = [0u8; RECORD_SIZE];
    let mut size = data.len();
    let mut mib = [libc::CTL_KERN, libc::KERN_PROC, libc::KERN_PROC_PID, pid];
    // SAFETY: all pointers reference writable buffers of the specified sizes;
    // no new value is supplied, so this is a read-only query.
    let result = unsafe {
        libc::sysctl(
            mib.as_mut_ptr(),
            mib.len() as _,
            data.as_mut_ptr().cast(),
            &mut size,
            std::ptr::null_mut(),
            0,
        )
    };
    if result != 0 || size != data.len() || std::mem::size_of::<usize>() != 8 {
        return None;
    }
    decode(pid, &data)
}

fn decode(pid: i32, data: &[u8; RECORD_SIZE]) -> Option<libc::proc_bsdinfo> {
    let word = |offset| u32::from_ne_bytes(data[offset..offset + 4].try_into().unwrap());
    let seconds = i64::from_ne_bytes(data[0..8].try_into().unwrap());
    let micros = word(8) as i32;
    if pid <= 0 || word(40) != pid as u32 || seconds <= 0 || !(0..1_000_000).contains(&micros) {
        return None;
    }
    // Only fields consumed by the process collector are populated. All come
    // from this one kernel record, including the birth time and credentials.
    // SAFETY: proc_bsdinfo consists entirely of integer and character fields.
    let mut info: libc::proc_bsdinfo = unsafe { std::mem::zeroed() };
    info.pbi_pid = pid as u32;
    info.pbi_ppid = word(560);
    info.pbi_status = data[36] as u32;
    info.pbi_uid = word(420);
    info.pbi_gid = word(428);
    info.pbi_ruid = word(392);
    info.pbi_rgid = word(400);
    info.pbi_svuid = word(396);
    info.pbi_svgid = word(404);
    info.pbi_start_tvsec = seconds as u64;
    info.pbi_start_tvusec = micros as u64;
    Some(info)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn restricted_metadata_matches_native_sdk_accessors() {
        let directory = tempfile::tempdir().unwrap();
        let source = directory.path().join("identity.c");
        let binary = directory.path().join("identity");
        std::fs::write(
            &source,
            include_str!("../../../../tests/macos_process_identity.c"),
        )
        .unwrap();
        assert!(
            std::process::Command::new("/usr/bin/clang")
                .args(["-Wall", "-Wextra", "-Werror"])
                .arg(&source)
                .arg("-o")
                .arg(&binary)
                .status()
                .unwrap()
                .success()
        );
        for pid in [1, std::process::id() as i32] {
            let output = std::process::Command::new(&binary)
                .arg(pid.to_string())
                .output()
                .unwrap();
            assert!(output.status.success());
            let sdk: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap();
            let info = read(pid).unwrap();
            for (field, value) in [
                ("pid", info.pbi_pid as u64),
                ("ppid", info.pbi_ppid as u64),
                ("uid", info.pbi_uid as u64),
                ("gid", info.pbi_gid as u64),
                ("ruid", info.pbi_ruid as u64),
                ("rgid", info.pbi_rgid as u64),
                ("svuid", info.pbi_svuid as u64),
                ("svgid", info.pbi_svgid as u64),
                ("seconds", info.pbi_start_tvsec),
                ("micros", info.pbi_start_tvusec),
            ] {
                assert_eq!(sdk[field].as_u64(), Some(value), "{pid}: {field}");
            }
        }
    }

    #[test]
    fn sysctl_matches_full_bsd_identity_for_current_process() {
        let pid = std::process::id() as i32;
        let mut bsd = std::mem::MaybeUninit::<libc::proc_bsdinfo>::zeroed();
        let size = std::mem::size_of::<libc::proc_bsdinfo>();
        let count = unsafe {
            libc::proc_pidinfo(
                pid,
                libc::PROC_PIDTBSDINFO,
                0,
                bsd.as_mut_ptr().cast(),
                size as i32,
            )
        };
        assert_eq!(count as usize, size);
        let bsd = unsafe { bsd.assume_init() };
        let fallback = read(pid).unwrap();
        assert_eq!(fallback.pbi_pid, bsd.pbi_pid);
        assert_eq!(fallback.pbi_ppid, bsd.pbi_ppid);
        assert_eq!(fallback.pbi_uid, bsd.pbi_uid);
        assert_eq!(fallback.pbi_gid, bsd.pbi_gid);
        assert_eq!(fallback.pbi_ruid, bsd.pbi_ruid);
        assert_eq!(fallback.pbi_rgid, bsd.pbi_rgid);
        assert_eq!(fallback.pbi_start_tvsec, bsd.pbi_start_tvsec);
        assert_eq!(fallback.pbi_start_tvusec, bsd.pbi_start_tvusec);
    }

    #[test]
    fn invalid_birth_or_pid_cannot_become_an_identity() {
        let mut data = [0; RECORD_SIZE];
        data[0..8].copy_from_slice(&123i64.to_ne_bytes());
        data[8..12].copy_from_slice(&456i32.to_ne_bytes());
        data[40..44].copy_from_slice(&42u32.to_ne_bytes());
        assert!(decode(42, &data).is_some());
        assert!(decode(43, &data).is_none());
        assert!(decode(0, &data).is_none());
        for micros in [-1i32, 1_000_000] {
            data[8..12].copy_from_slice(&micros.to_ne_bytes());
            assert!(decode(42, &data).is_none());
        }
        data[8..12].copy_from_slice(&0i32.to_ne_bytes());
        for seconds in [-1i64, 0] {
            data[0..8].copy_from_slice(&seconds.to_ne_bytes());
            assert!(decode(42, &data).is_none());
        }
    }

    #[test]
    fn exited_process_has_no_sysctl_identity() {
        let mut child = std::process::Command::new("/usr/bin/true").spawn().unwrap();
        let pid = child.id() as i32;
        child.wait().unwrap();
        assert!(read(pid).is_none());
    }
}
