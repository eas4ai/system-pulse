//! Bounded decoding of Linux i915 and xe UAPI query results.
use super::{Clock, Device, native};
use crate::{
    counters::*,
    host::{diagnostic, sensor},
    types::*,
};
use std::io;
use std::path::Path;
fn publish_memory(
    s: &mut Snapshot,
    id: &str,
    driver: &str,
    regions: &[Region],
    observation: &RawObservation,
) {
    for region in regions {
        let local = region.class == 1;
        let suffix = format!(
            "{}-region-{}",
            if local { "local" } else { "shared" },
            region.instance
        );
        let sid = format!("{id}/{suffix}");
        let scope = if local {
            "Dedicated device-local VRAM region; estimate of allocation, not visible-client sum"
        } else {
            "This device's TTM system-memory region allocation; not total system RAM or unique resident process memory"
        };
        let mut o = observation.clone();
        o.integers.extend([
            ("class".into(), region.class as u64),
            ("instance".into(), region.instance as u64),
            ("total_bytes".into(), region.total),
            ("count_bytes".into(), region.raw_count),
            ("cpu_visible_total_bytes".into(), region.visible_total),
            ("cpu_visible_count_bytes".into(), region.visible_count),
        ]);
        let mut r=match region.used {
            Some(used)=>measured(&sid,used as f64,local.then_some(region.total as f64)),
            None=>missing(&sid,Availability::Unavailable,if local {"i915 free equals total: restricted or older-kernel accounting is indistinguishable from idle; no measured zero"} else {"i915 system-region total/free does not measure GPU shared allocation"}.into()),
        };
        r.observations.push(o.clone());
        sensor(
            s,
            id,
            &suffix,
            &format!(
                "{} {} allocation",
                if local {
                    "VRAM region"
                } else {
                    "GPU shared region"
                },
                region.instance
            ),
            if local {
                SensorKind::Capacity
            } else {
                SensorKind::Counter
            },
            Unit::Bytes,
            &o.source,
            scope,
            r,
        );
        if local {
            let total_suffix = format!("{suffix}-total");
            let mut r = measured(&format!("{id}/{total_suffix}"), region.total as f64, None);
            r.observations.push(o.clone());
            sensor(
                s,
                id,
                &total_suffix,
                &format!("VRAM region {} total", region.instance),
                SensorKind::Counter,
                Unit::Bytes,
                &o.source,
                "Dedicated device-local VRAM capacity in bytes",
                r,
            );
            if region.visible_total > 0 {
                let visible_suffix = format!("{suffix}-cpu-visible");
                let used = if driver == "xe" {
                    Some(region.visible_count)
                } else if region.visible_count < region.visible_total {
                    Some(region.visible_total - region.visible_count)
                } else {
                    None
                };
                let mut r = used.map_or_else(
                    || {
                        missing(
                            &format!("{id}/{visible_suffix}"),
                            Availability::Unavailable,
                            "i915 CPU-visible free accounting may be restricted".into(),
                        )
                    },
                    |used| {
                        measured(
                            &format!("{id}/{visible_suffix}"),
                            used as f64,
                            Some(region.visible_total as f64),
                        )
                    },
                );
                r.observations.push(o.clone());
                sensor(
                    s,
                    id,
                    &visible_suffix,
                    &format!("VRAM region {} CPU-visible allocation", region.instance),
                    SensorKind::Capacity,
                    Unit::Bytes,
                    &o.source,
                    "CPU-accessible subset of this local VRAM region; overlaps the whole region",
                    r,
                );
            }
        }
    }
}
pub(super) fn error_availability(e: &io::Error) -> Availability {
    if matches!(
        e.kind(),
        io::ErrorKind::PermissionDenied | io::ErrorKind::NotFound | io::ErrorKind::Unsupported
    ) || matches!(
        e.raw_os_error(),
        Some(libc::ENODEV | libc::ENOTTY | libc::EOPNOTSUPP | libc::EINVAL)
    ) {
        Availability::Unavailable
    } else {
        Availability::Failed
    }
}
pub(super) fn collect(
    s: &mut Snapshot,
    device: &Device,
    root: &Path,
    id: &str,
    clock: &Clock,
) -> io::Result<Vec<Engine>> {
    let file = native::open_device(device, root);
    let source = format!(
        "DRM {} QUERY_MEMORY_REGIONS (bytes); PCI {}",
        device.driver, device.pci
    );
    let start = clock.now();
    let memory = file
        .as_ref()
        .map_err(|e| io::Error::new(e.kind(), e.to_string()))
        .and_then(|f| {
            native::query(
                f,
                &device.driver,
                if device.driver == "i915" { 4 } else { 1 },
            )
        })
        .and_then(|b| regions(&device.driver, &b));
    let o = raw_window(&source, start, clock.now(), []);
    match memory {
        Ok(regions) => {
            diagnostic_classification(s, device, &regions);
            publish_memory(s, id, &device.driver, &regions, &o);
        }
        Err(e) => {
            for (suffix, title, kind, scope) in [
                (
                    "local-memory",
                    "Dedicated VRAM allocation",
                    SensorKind::Capacity,
                    "Device-local regions unavailable",
                ),
                (
                    "shared-memory",
                    "GPU shared allocation",
                    SensorKind::Counter,
                    "Device system-memory allocation unavailable; not system RAM",
                ),
            ] {
                let r = missing(
                    &format!("{id}/{suffix}"),
                    error_availability(&e),
                    format!("{source}: {e}"),
                );
                sensor(s, id, suffix, title, kind, Unit::Bytes, &source, scope, r);
            }
        }
    }
    let topology = native::query(
        &file?,
        &device.driver,
        if device.driver == "i915" { 2 } else { 0 },
    )
    .and_then(|b| engines(&device.driver, &b));
    if let Err(e) = &topology {
        diagnostic(
            s,
            "intel engine topology",
            format!("PCI {}: {e}", device.pci),
        );
    }
    topology
}
fn diagnostic_classification(s: &mut Snapshot, device: &Device, regions: &[Region]) {
    s.diagnostics.push(BackendDiagnostic {backend:format!("intel identity {}",device.pci),availability:Availability::Available,reason:format!("{}; {}",device.driver,if regions.iter().any(|r|r.class==1) {"Discrete: DRM query reports device-local memory"} else {"No device-local region exposed; this query alone does not establish integrated/discrete classification"})});
}
#[derive(Debug, PartialEq)]
pub(super) struct Region {
    pub class: u16,
    pub instance: u16,
    pub total: u64,
    pub used: Option<u64>,
    pub raw_count: u64,
    pub visible_total: u64,
    pub visible_count: u64,
}
#[derive(Debug, PartialEq, Eq, PartialOrd, Ord, Clone)]
pub(super) struct Engine {
    pub class: u16,
    pub instance: u16,
    pub gt: u16,
}
fn invalid(message: &str) -> io::Error {
    io::Error::new(io::ErrorKind::InvalidData, message)
}
fn u16_at(b: &[u8], p: usize) -> io::Result<u16> {
    Ok(u16::from_ne_bytes(
        b.get(p..p + 2)
            .ok_or_else(|| invalid("truncated u16"))?
            .try_into()
            .unwrap(),
    ))
}
fn u32_at(b: &[u8], p: usize) -> io::Result<u32> {
    Ok(u32::from_ne_bytes(
        b.get(p..p + 4)
            .ok_or_else(|| invalid("truncated u32"))?
            .try_into()
            .unwrap(),
    ))
}
fn u64_at(b: &[u8], p: usize) -> io::Result<u64> {
    Ok(u64::from_ne_bytes(
        b.get(p..p + 8)
            .ok_or_else(|| invalid("truncated u64"))?
            .try_into()
            .unwrap(),
    ))
}
fn zero(b: &[u8]) -> io::Result<()> {
    if b.iter().any(|v| *v != 0) {
        Err(invalid("nonzero reserved field"))
    } else {
        Ok(())
    }
}
fn records(b: &[u8], header: usize, stride: usize) -> io::Result<std::slice::ChunksExact<'_, u8>> {
    let count = u32_at(b, 0)? as usize;
    if count == 0 || count > 512 || b.len() != header + count * stride {
        return Err(invalid("invalid query count or length"));
    }
    zero(&b[4..header])?;
    Ok(b[header..].chunks_exact(stride))
}
pub(super) fn regions(driver: &str, bytes: &[u8]) -> io::Result<Vec<Region>> {
    let mut result = Vec::new();
    let mut keys = std::collections::BTreeSet::new();
    for b in records(bytes, if driver == "i915" { 16 } else { 8 }, 88)? {
        let class = u16_at(b, 0)?;
        let instance = u16_at(b, 2)?;
        if class > 1 || !keys.insert((class, instance)) {
            return Err(invalid("unknown/duplicate memory region"));
        }
        if driver == "i915" {
            zero(&b[4..8])?;
        } else if !u32_at(b, 4)?.is_power_of_two() {
            return Err(invalid("invalid minimum page size"));
        }
        let total = u64_at(b, 8)?;
        let count = u64_at(b, 16)?;
        let visible_total = u64_at(b, 24)?;
        let visible_count = u64_at(b, 32)?;
        zero(&b[40..])?;
        if count == u64::MAX
            || (class == 1
                && (total == 0 || total == u64::MAX || count > total || visible_total > total))
            || visible_count > visible_total
        {
            return Err(invalid("invalid memory sizes"));
        }
        let used = if driver == "xe" {
            Some(count)
        } else if class == 1 && count < total {
            Some(total - count)
        } else {
            None
        };
        result.push(Region {
            class,
            instance,
            total,
            used,
            raw_count: count,
            visible_total,
            visible_count,
        });
    }
    Ok(result)
}
pub(super) fn engines(driver: &str, bytes: &[u8]) -> io::Result<Vec<Engine>> {
    let mut result = std::collections::BTreeSet::new();
    let (header, stride) = if driver == "i915" { (16, 56) } else { (8, 32) };
    for b in records(bytes, header, stride)? {
        let engine = Engine {
            class: u16_at(b, 0)?,
            instance: u16_at(b, 2)?,
            gt: if driver == "xe" { u16_at(b, 4)? } else { 0 },
        };
        if driver == "xe" {
            zero(&b[6..])?;
        } else {
            zero(&b[4..8])?;
            zero(&b[26..])?;
        }
        if engine.class > 4 || !result.insert(engine) {
            return Err(invalid("unknown/duplicate engine"));
        }
    }
    Ok(result.into_iter().collect())
}

#[cfg(test)]
mod tests {
    use super::*;
    fn put16(b: &mut [u8], offset: usize, v: u16) {
        b[offset..offset + 2].copy_from_slice(&v.to_ne_bytes());
    }
    fn put32(b: &mut [u8], offset: usize, v: u32) {
        b[offset..offset + 4].copy_from_slice(&v.to_ne_bytes());
    }
    fn put64(b: &mut [u8], offset: usize, v: u64) {
        b[offset..offset + 8].copy_from_slice(&v.to_ne_bytes());
    }
    fn memory(driver: &str) -> Vec<u8> {
        let header = if driver == "i915" { 16 } else { 8 };
        let mut b = vec![0; header + 88 * 3];
        put32(&mut b, 0, 3);
        for (n, (class, instance, total, count)) in
            [(0, 0, 16000, 16000), (1, 3, 8000, 2000), (1, 7, 4000, 1000)]
                .into_iter()
                .enumerate()
        {
            let p = header + n * 88;
            put16(&mut b, p, class);
            put16(&mut b, p + 2, instance);
            put64(&mut b, p + 8, total);
            put64(&mut b, p + 16, count);
            if driver == "xe" {
                put32(&mut b, p + 4, 4096);
            }
        }
        b
    }
    #[test]
    fn sparse_local_regions_and_xe_shared_allocations_retain_raw_bytes() {
        let r = regions("xe", &memory("xe")).unwrap();
        assert_eq!(r.len(), 3);
        assert_eq!(r[0].class, 0);
        assert_eq!(r[0].used, Some(16000));
        assert_eq!(r[1].instance, 3);
        assert_eq!(r[1].used, Some(2000));
        assert_eq!(r[2].instance, 7);
        let r = regions("i915", &memory("i915")).unwrap();
        assert_eq!(r[0].used, None);
        assert_eq!(r[1].used, Some(6000));
        assert_eq!(r[1].raw_count, 2000);
    }
    #[test]
    fn i915_restricted_free_never_becomes_zero_usage() {
        let mut b = memory("i915");
        put64(&mut b, 16 + 88 + 16, 8000);
        let r = regions("i915", &b).unwrap();
        assert_eq!(r[1].total, 8000);
        assert_eq!(r[1].used, None);
    }
    #[test]
    fn memory_rejects_truncated_huge_duplicate_reserved_and_invalid_sizes() {
        for driver in ["i915", "xe"] {
            let b = memory(driver);
            let h = if driver == "i915" { 16 } else { 8 };
            for len in 0..b.len() {
                assert!(regions(driver, &b[..len]).is_err(), "{driver} length {len}");
            }
            let mut bad = b.clone();
            put32(&mut bad, 0, u32::MAX);
            assert!(regions(driver, &bad).is_err());
            let mut bad = b.clone();
            put16(&mut bad, h + 88 + 2, 7);
            assert!(regions(driver, &bad).is_err());
            let mut bad = b.clone();
            bad[4] = 1;
            assert!(regions(driver, &bad).is_err());
            let mut bad = b.clone();
            put64(&mut bad, h + 88 + 8, 0);
            assert!(regions(driver, &bad).is_err());
            let mut bad = b.clone();
            put64(&mut bad, h + 88 + 16, 9000);
            assert!(regions(driver, &bad).is_err());
            let mut bad = b.clone();
            put64(&mut bad, h + 88 + 8, u64::MAX);
            assert!(regions(driver, &bad).is_err());
        }
    }
    #[test]
    fn engine_topology_preserves_sparse_gt_class_and_instance() {
        for driver in ["i915", "xe"] {
            let (h, stride) = if driver == "i915" { (16, 56) } else { (8, 32) };
            let mut b = vec![0; h + stride * 2];
            put32(&mut b, 0, 2);
            put16(&mut b, h, 0);
            put16(&mut b, h + 2, 3);
            put16(&mut b, h + stride, 4);
            put16(&mut b, h + stride + 2, 7);
            if driver == "xe" {
                put16(&mut b, h + 4, 5);
                put16(&mut b, h + stride + 4, 9);
            }
            let e = engines(driver, &b).unwrap();
            assert_eq!(e.len(), 2);
            assert_eq!(e[1].instance, 7);
            assert_eq!(e[1].gt, if driver == "xe" { 9 } else { 0 });
            assert!(engines(driver, &b[..b.len() - 1]).is_err());
            put32(&mut b, 0, u32::MAX);
            assert!(engines(driver, &b).is_err());
        }
    }
    #[test]
    fn memory_publication_keeps_shared_bytes_separate_from_local_capacity() {
        let mut s = Snapshot::default();
        let r = regions("xe", &memory("xe")).unwrap();
        let o = crate::counters::raw_window("DRM xe MEM_REGIONS (bytes)", 10, 20, []);
        publish_memory(&mut s, "intel-pci:test", "xe", &r, &o);
        let shared = s
            .readings
            .iter()
            .find(|r| r.sensor_id.ends_with("shared-region-0"))
            .expect("shared allocation reading");
        assert_eq!(shared.value, Some(16000.0));
        assert_eq!(shared.total, None);
        let local = s
            .readings
            .iter()
            .find(|r| r.sensor_id.ends_with("local-region-3"))
            .expect("local region reading");
        assert_eq!(local.value, Some(2000.0));
        assert_eq!(local.total, Some(8000.0));
        assert_eq!(local.observations[0].read_started_ns, Some(10));
        assert_eq!(local.observations[0].captured_ns, 20);
        assert_eq!(local.observations[0].integers["count_bytes"], 2000);
        assert!(
            s.sensors
                .iter()
                .find(|d| d.id.ends_with("shared-region-0"))
                .unwrap()
                .scope
                .contains("TTM")
        );
    }
    #[test]
    fn shared_allocation_does_not_require_a_system_memory_capacity() {
        let mut b = memory("xe");
        put64(&mut b, 8 + 8, 0);
        put64(&mut b, 8 + 16, 12345);
        let r = regions("xe", &b).unwrap();
        assert_eq!(r[0].used, Some(12345));
        let mut s = Snapshot::default();
        publish_memory(&mut s, "id", "xe", &r, &raw_window("xe query", 10, 20, []));
        let shared = s
            .readings
            .iter()
            .find(|r| r.sensor_id == "id/shared-region-0")
            .unwrap();
        assert_eq!(shared.value, Some(12345.0));
        assert_eq!(shared.total, None);
    }
}
