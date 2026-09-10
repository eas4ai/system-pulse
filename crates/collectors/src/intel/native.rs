//! Native read-only DRM and perf boundaries. No pointers are cast to response structs.
use super::{Device, sysfs};
use std::{
    fs::{File, OpenOptions},
    io,
    os::{
        fd::AsRawFd,
        unix::fs::{FileTypeExt, MetadataExt, OpenOptionsExt},
    },
    path::Path,
};
fn invalid(message: &str) -> io::Error {
    io::Error::new(io::ErrorKind::InvalidData, message)
}
fn query_buffer(
    mut query: impl FnMut(Option<&mut [u8]>) -> io::Result<i64>,
) -> io::Result<Vec<u8>> {
    let size = query(None)?;
    if size < 0 {
        return Err(io::Error::from_raw_os_error(
            size.checked_neg()
                .and_then(|v| v.try_into().ok())
                .unwrap_or(libc::EIO),
        ));
    }
    if size == 0 || size > 1024 * 1024 {
        return Err(invalid("DRM query size outside 1..=1 MiB"));
    }
    let mut bytes = vec![0; size as usize];
    let returned = query(Some(&mut bytes))?;
    if returned < 0 {
        return Err(io::Error::from_raw_os_error(
            returned
                .checked_neg()
                .and_then(|v| v.try_into().ok())
                .unwrap_or(libc::EIO),
        ));
    }
    if returned != size {
        return Err(invalid("DRM query changed size during read"));
    }
    Ok(bytes)
}
// Linux UAPI field layouts: include/uapi/drm/{i915,xe}_drm.h. See UAPI-NOTICE.
#[repr(C)]
#[derive(Default)]
struct I915Item {
    query_id: u64,
    length: i32,
    flags: u32,
    data_ptr: u64,
}
#[repr(C)]
struct I915Query {
    num_items: u32,
    flags: u32,
    items_ptr: u64,
}
#[repr(C)]
#[derive(Default)]
struct XeQuery {
    extensions: u64,
    query: u32,
    size: u32,
    data: u64,
    reserved: [u64; 2],
}
const _: () = {
    assert!(std::mem::size_of::<I915Item>() == 24);
    assert!(std::mem::size_of::<I915Query>() == 16);
    assert!(std::mem::size_of::<XeQuery>() == 40);
};
// rustix uses the target architecture's ioctl encoding.
fn iowr<T>(number: u8) -> libc::c_ulong {
    rustix::ioctl::opcode::read_write::<T>(b'd', number) as libc::c_ulong
}
pub(super) fn query(file: &File, driver: &str, id: u32) -> io::Result<Vec<u8>> {
    query_buffer(|buffer| {
        let (length, pointer) =
            buffer.map_or((0, 0), |b| (b.len() as u32, b.as_mut_ptr() as usize as u64));
        if driver == "i915" {
            let mut item = I915Item {
                query_id: id as u64,
                length: length as i32,
                data_ptr: pointer,
                ..I915Item::default()
            };
            let mut q = I915Query {
                num_items: 1,
                flags: 0,
                items_ptr: (&mut item as *mut I915Item) as usize as u64,
            };
            // SAFETY: q/item have the asserted C layouts and remain live for this synchronous ioctl.
            // The zeroed byte allocation passed through data_ptr is exactly length bytes and remains borrowed.
            let status = unsafe { libc::ioctl(file.as_raw_fd(), iowr::<I915Query>(0x79), &mut q) };
            if status < 0 {
                return Err(io::Error::last_os_error());
            }
            if status != 0 {
                return Err(invalid("unexpected i915 ioctl status"));
            }
            Ok(i64::from(item.length))
        } else {
            let mut q = XeQuery {
                query: id,
                size: length,
                data: pointer,
                ..XeQuery::default()
            };
            // SAFETY: q has the asserted C layout. data points to the borrowed, zeroed allocation,
            // or zero for the sizing query; size is its exact capacity. The call is synchronous.
            let status = unsafe { libc::ioctl(file.as_raw_fd(), iowr::<XeQuery>(0x40), &mut q) };
            if status < 0 {
                return Err(io::Error::last_os_error());
            }
            if status != 0 {
                return Err(invalid("unexpected xe ioctl status"));
            }
            Ok(i64::from(q.size))
        }
    })
}
pub(super) fn open_device(device: &Device, root: &Path) -> io::Result<File> {
    let mut nodes = device.cards.clone();
    nodes.sort_by_key(|p| {
        !p.file_name()
            .unwrap()
            .to_string_lossy()
            .starts_with("renderD")
    });
    let mut last = io::Error::new(io::ErrorKind::NotFound, "no DRM node for physical device");
    for card in nodes {
        let attempt = (|| {
            if card.join("device").canonicalize()? != device.path {
                return Err(invalid("DRM node changed physical device"));
            }
            let expected = sysfs::text(&card.join("dev"))?;
            let f = OpenOptions::new()
                .read(true)
                .custom_flags(libc::O_NONBLOCK)
                .open(root.join("dev/dri").join(card.file_name().unwrap()))?;
            let metadata = f.metadata()?;
            if !metadata.file_type().is_char_device()
                || expected
                    != format!(
                        "{}:{}",
                        libc::major(metadata.rdev()),
                        libc::minor(metadata.rdev())
                    )
            {
                return Err(invalid("DRM file does not match sysfs device number"));
            }
            Ok(f)
        })();
        match attempt {
            Ok(f) => return Ok(f),
            Err(e) => last = e,
        }
    }
    Err(last)
}

#[derive(Debug)]
pub(super) struct PerfRead {
    pub active: u64,
    pub total: u64,
    pub enabled: u64,
    pub running: u64,
}
fn parse_perf(bytes: &[u8], count: usize) -> io::Result<PerfRead> {
    if !(1..=2).contains(&count) || bytes.len() != (3 + count) * 8 {
        return Err(invalid("Truncated or unexpected perf group read"));
    }
    let values: Vec<u64> = bytes
        .as_chunks::<8>()
        .0
        .iter()
        .map(|bytes| u64::from_ne_bytes(*bytes))
        .collect();
    if values[0] != count as u64 || values[2] > values[1] {
        return Err(invalid("Invalid perf group count or time"));
    }
    Ok(PerfRead {
        enabled: values[1],
        running: values[2],
        active: values[3],
        total: if count == 2 { values[4] } else { 0 },
    })
}
pub(super) trait Counter: Send {
    fn read(&mut self) -> io::Result<PerfRead>;
}
pub(super) struct PerfCounter {
    leader: File,
    members: Vec<File>,
}
// perf_event_attr VER0 (64 bytes), include/uapi/linux/perf_event.h.
#[repr(C)]
#[derive(Default)]
struct PerfAttr {
    kind: u32,
    size: u32,
    config: u64,
    sample_period: u64,
    sample_type: u64,
    read_format: u64,
    flags: u64,
    wakeup: u32,
    bp_type: u32,
    config1: u64,
}
const _: () = assert!(std::mem::size_of::<PerfAttr>() == 64);
impl PerfCounter {
    pub(super) fn open(spec: &super::pmu::Spec) -> io::Result<Box<dyn Counter>> {
        use std::os::fd::FromRawFd;
        let open = |config: u64, group: i32| {
            let attr = PerfAttr {
                kind: spec.kind,
                size: 64,
                config,
                read_format: 1 | 2 | 8,
                ..PerfAttr::default()
            };
            // SAFETY: attr is a live initialized 64-byte perf_event_attr VER0; the kernel only
            // reads it. pid=-1 and an explicit online CPU request this device PMU, not a process.
            let fd = unsafe {
                libc::syscall(
                    libc::SYS_perf_event_open,
                    &attr,
                    -1i32,
                    spec.cpu,
                    group,
                    8 as libc::c_ulong,
                )
            };
            if fd < 0 {
                return Err(io::Error::last_os_error());
            }
            // SAFETY: successful perf_event_open returns an owned file descriptor. File closes it.
            Ok(unsafe { File::from_raw_fd(fd as i32) })
        };
        let leader = open(spec.active, -1)?;
        let mut members = Vec::new();
        if let Some(total) = spec.total {
            members.push(open(total, leader.as_raw_fd())?);
        }
        Ok(Box::new(Self { leader, members }))
    }
}
impl Counter for PerfCounter {
    fn read(&mut self) -> io::Result<PerfRead> {
        use std::io::Read;
        let mut bytes = [0u8; 40];
        let size = (4 + self.members.len()) * 8;
        let read = self.leader.read(&mut bytes[..size])?;
        parse_perf(&bytes[..read], 1 + self.members.len())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn query_validates_both_statuses_lengths_and_bound_before_allocation() {
        let mut calls = 0;
        let b = query_buffer(|buffer| {
            calls += 1;
            if let Some(b) = buffer {
                b.copy_from_slice(&[1, 2, 3, 4]);
            }
            Ok(4)
        })
        .unwrap();
        assert_eq!(calls, 2);
        assert_eq!(b, vec![1, 2, 3, 4]);
        for size in [-13, 0, 1024 * 1024 + 1, i64::MAX] {
            let mut calls = 0;
            assert!(
                query_buffer(|_| {
                    calls += 1;
                    Ok(size)
                })
                .is_err()
            );
            assert_eq!(calls, 1);
        }
        for size in [-13, 0, 3, 5] {
            assert!(query_buffer(|b| Ok(if b.is_none() { 4 } else { size })).is_err());
        }
        assert_eq!(
            query_buffer(|_| Err(io::Error::from(io::ErrorKind::PermissionDenied)))
                .unwrap_err()
                .kind(),
            io::ErrorKind::PermissionDenied
        );
        assert!(
            query_buffer(|b| if b.is_none() {
                Ok(4)
            } else {
                Err(io::Error::from(io::ErrorKind::PermissionDenied))
            })
            .is_err()
        );
    }
    #[test]
    fn perf_group_response_checks_count_length_and_time_operands() {
        let b: Vec<_> = [2u64, 1_000_000, 1_000_000, 75, 100]
            .into_iter()
            .flat_map(u64::to_ne_bytes)
            .collect();
        let p = parse_perf(&b, 2).unwrap();
        assert_eq!(p.active, 75);
        assert_eq!(p.total, 100);
        assert_eq!(p.enabled, 1_000_000);
        assert_eq!(p.running, 1_000_000);
        for length in 0..b.len() {
            assert!(parse_perf(&b[..length], 2).is_err());
        }
        assert!(parse_perf(&b, 1).is_err());
        assert!(parse_perf(&b, usize::MAX).is_err());
        let b: Vec<_> = [2u64, 10, 11, 75, 100]
            .into_iter()
            .flat_map(u64::to_ne_bytes)
            .collect();
        assert!(parse_perf(&b, 2).is_err());
    }
    #[test]
    fn pathological_negative_query_status_cannot_overflow() {
        assert!(query_buffer(|_| Ok(i64::MIN)).is_err());
    }
}
