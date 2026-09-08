use std::{time::{Duration, Instant}, hint::black_box};
use sysinfo::{System, CpuRefreshKind, MemoryRefreshKind, ProcessRefreshKind, ProcessesToUpdate, UpdateKind};
fn cpu_ns() -> u64 {
    let mut t = std::mem::MaybeUninit::<libc::timespec>::uninit();
    assert_eq!(unsafe { libc::clock_gettime(libc::CLOCK_THREAD_CPUTIME_ID, t.as_mut_ptr()) }, 0);
    let t = unsafe { t.assume_init() };
    t.tv_sec as u64 * 1_000_000_000 + t.tv_nsec as u64
}
macro_rules! stage {
    ($rows:expr, $name:literal, $body:expr) => {{
        let wall = Instant::now(); let cpu = cpu_ns();
        let count = black_box($body);
        $rows.push(($name, cpu_ns() - cpu, wall.elapsed().as_nanos(), count));
    }};
}
fn main() {
    let mut system = System::new();
    let mut components = sysinfo::Components::new_with_refreshed_list();
    let mut networks = sysinfo::Networks::new_with_refreshed_list();
    for iteration in 0..12 {
        let sample = Instant::now(); let mut rows = Vec::new();
        stage!(rows, "cpu", {system.refresh_cpu_specifics(CpuRefreshKind::everything()); system.cpus().len()});
        stage!(rows, "memory", {system.refresh_memory_specifics(MemoryRefreshKind::everything()); 1});
        stage!(rows, "processes", {system.refresh_processes_specifics(ProcessesToUpdate::All, true,
            ProcessRefreshKind::nothing().with_cpu().with_memory().with_disk_usage().with_user(UpdateKind::Always).with_tasks()); system.processes().len()});
        stage!(rows, "networks", {networks.refresh(true); networks.len()});
        stage!(rows, "temperatures", {components.refresh(true); components.len()});
        stage!(rows, "accounts", sysinfo::Users::new_with_refreshed_list().len());
        stage!(rows, "disks_without_capacity", sysinfo::Disks::new_with_refreshed_list_specifics(sysinfo::DiskRefreshKind::everything().without_storage()).len());
        for (name, cpu, wall, count) in rows {
            println!("iteration={iteration} stage={name} cpu_ns={cpu} wall_ns={wall} count={count}");
        }
        std::thread::sleep(Duration::from_secs(1).saturating_sub(sample.elapsed()));
    }
}
