//! One worker owns all OS handles. Delivery has one replaceable snapshot slot.
use crate::{HostCollector, Snapshot};
use std::{
    sync::{Arc, Condvar, Mutex},
    thread::{self, JoinHandle},
    time::{Duration, Instant},
};
pub const DEFAULT_INTERVAL: Duration = Duration::from_secs(1);
pub const SUPPORTED_INTERVALS: [Duration; 4] = [
    Duration::from_millis(500),
    Duration::from_secs(1),
    Duration::from_secs(2),
    Duration::from_secs(5),
];
struct State {
    interval: Duration,
    generation: u64,
    stop: bool,
    latest: Option<Snapshot>,
}
struct Shared {
    state: Mutex<State>,
    changed: Condvar,
}
pub struct SamplingService {
    shared: Arc<Shared>,
    worker: Option<JoinHandle<()>>,
    #[cfg(target_os = "windows")]
    thermal: Arc<crate::windows_thermal::Control>,
}
fn valid(interval: Duration) -> Result<(), String> {
    if SUPPORTED_INTERVALS.contains(&interval) {
        Ok(())
    } else {
        Err("Sampling interval must be 500, 1000, 2000, or 5000 milliseconds".into())
    }
}
impl SamplingService {
    pub fn start(interval: Duration) -> Result<Self, String> {
        valid(interval)?;
        #[cfg(target_os = "windows")]
        let thermal = Arc::new(crate::windows_thermal::Control::default());
        #[cfg(target_os = "windows")]
        let collector_control = thermal.clone();
        let service = Self::spawn(interval, move || {
            let mut host = HostCollector::new();
            #[cfg(target_os = "windows")]
            host.set_temperature_control(collector_control);
            move || host.collect()
        })?;
        #[cfg(target_os = "windows")]
        let service = {
            let mut service = service;
            service.thermal = thermal;
            service
        };
        Ok(service)
    }
    #[cfg(target_os = "windows")]
    pub fn enable_cpu_temperatures(&self) -> Result<(), String> {
        self.thermal.enable()
    }
    #[cfg(target_os = "windows")]
    pub fn disable_cpu_temperatures(&self) {
        self.thermal.disable();
    }
    #[cfg(target_os = "windows")]
    pub fn cpu_temperatures_enabled(&self) -> bool {
        self.thermal.enabled()
    }
    pub fn set_interval(&self, interval: Duration) -> Result<(), String> {
        valid(interval)?;
        let mut state = self.shared.state.lock().unwrap_or_else(|e| e.into_inner());
        state.interval = interval;
        state.generation = state.generation.wrapping_add(1);
        self.shared.changed.notify_one();
        Ok(())
    }
    pub fn take_latest(&self) -> Option<Snapshot> {
        self.shared
            .state
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .latest
            .take()
    }
    fn spawn<F, C>(interval: Duration, factory: F) -> Result<Self, String>
    where
        F: FnOnce() -> C + Send + 'static,
        C: FnMut() -> Snapshot + 'static,
    {
        let shared = Arc::new(Shared {
            state: Mutex::new(State {
                interval,
                generation: 0,
                stop: false,
                latest: None,
            }),
            changed: Condvar::new(),
        });
        let inner = shared.clone();
        let worker = thread::Builder::new()
            .name("pulse-collector".into())
            .spawn(move || {
                let mut collect = factory();
                loop {
                    if inner.state.lock().unwrap_or_else(|e| e.into_inner()).stop {
                        break;
                    }
                    let started = Instant::now();
                    let snapshot = collect();
                    let mut state = inner.state.lock().unwrap_or_else(|e| e.into_inner());
                    state.latest = Some(snapshot);
                    if state.stop {
                        break;
                    }
                    let mut generation = state.generation;
                    let mut next = started + state.interval;
                    // A slow backend skips missed sample slots. There is never a catch-up burst.
                    while next <= Instant::now() {
                        next += state.interval;
                    }
                    loop {
                        if state.stop {
                            return;
                        }
                        if state.generation != generation {
                            generation = state.generation;
                            next = started + state.interval;
                        }
                        let now = Instant::now();
                        if now >= next {
                            break;
                        }
                        let (updated, _) = inner
                            .changed
                            .wait_timeout(state, next - now)
                            .unwrap_or_else(|e| e.into_inner());
                        state = updated;
                    }
                }
            })
            .map_err(|e| format!("Could not start collector worker: {e}"))?;
        Ok(Self {
            shared,
            worker: Some(worker),
            #[cfg(target_os = "windows")]
            thermal: Arc::new(crate::windows_thermal::Control::default()),
        })
    }
}
impl Drop for SamplingService {
    fn drop(&mut self) {
        #[cfg(target_os = "windows")]
        self.thermal.disable();
        let mut state = self.shared.state.lock().unwrap_or_else(|e| e.into_inner());
        state.stop = true;
        self.shared.changed.notify_one();
        drop(state);
        if let Some(worker) = self.worker.take() {
            let _ = worker.join();
        }
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::{
        Arc, Mutex,
        atomic::{AtomicU64, AtomicUsize, Ordering},
        mpsc,
    };
    #[test]
    fn non_send_collector_is_created_used_and_dropped_on_worker() {
        struct Local {
            owner: thread::ThreadId,
            events: mpsc::Sender<(&'static str, thread::ThreadId)>,
        }
        impl Drop for Local {
            fn drop(&mut self) {
                self.events.send(("drop", thread::current().id())).unwrap();
                assert_eq!(self.owner, thread::current().id());
            }
        }
        let caller = thread::current().id();
        let (tx, rx) = mpsc::channel();
        let service = SamplingService::spawn(Duration::from_secs(5), move || {
            let local = std::rc::Rc::new(Local {
                owner: thread::current().id(),
                events: tx,
            });
            local
                .events
                .send(("create", thread::current().id()))
                .unwrap();
            move || {
                local.events.send(("use", thread::current().id())).unwrap();
                Snapshot::default()
            }
        })
        .unwrap();
        let created = rx.recv_timeout(Duration::from_secs(1)).unwrap();
        let used = rx.recv_timeout(Duration::from_secs(1)).unwrap();
        drop(service);
        let dropped = rx.recv_timeout(Duration::from_secs(1)).unwrap();
        assert_ne!(created.1, caller);
        assert_eq!(created.0, "create");
        assert_eq!(used, ("use", created.1));
        assert_eq!(dropped, ("drop", created.1));
    }
    #[test]
    fn rejects_other_intervals() {
        assert!(SamplingService::start(Duration::from_millis(42)).is_err());
    }
    #[test]
    fn factory_and_collection_run_on_worker() {
        let caller = std::thread::current().id();
        let (tx, rx) = mpsc::channel();
        let service = SamplingService::spawn(Duration::from_millis(5), move || {
            tx.send(std::thread::current().id()).unwrap();
            move || Snapshot::default()
        })
        .unwrap();
        assert_ne!(rx.recv_timeout(Duration::from_secs(1)).unwrap(), caller);
        drop(service);
    }
    #[test]
    fn slow_backend_never_overlaps_and_delivery_is_latest_only() {
        let active = Arc::new(AtomicUsize::new(0));
        let max = Arc::new(AtomicUsize::new(0));
        let (tx, rx) = mpsc::channel();
        let count = Arc::new(AtomicU64::new(0));
        let a = active.clone();
        let m = max.clone();
        let c = count.clone();
        let service = SamplingService::spawn(Duration::from_millis(1), move || {
            move || {
                let concurrent = a.fetch_add(1, Ordering::SeqCst) + 1;
                m.fetch_max(concurrent, Ordering::SeqCst);
                std::thread::sleep(Duration::from_millis(8));
                let sequence = c.fetch_add(1, Ordering::SeqCst) + 1;
                a.fetch_sub(1, Ordering::SeqCst);
                tx.send(sequence).unwrap();
                Snapshot {
                    sequence,
                    ..Snapshot::default()
                }
            }
        })
        .unwrap();
        for _ in 0..4 {
            rx.recv_timeout(Duration::from_secs(1)).unwrap();
        }
        std::thread::sleep(Duration::from_millis(2));
        let latest = service.take_latest().unwrap();
        assert!(latest.sequence >= 4);
        assert!(service.take_latest().is_none());
        assert_eq!(max.load(Ordering::SeqCst), 1);
        drop(service);
        assert_eq!(active.load(Ordering::SeqCst), 0);
    }
    #[test]
    fn interval_change_interrupts_wait_and_drop_joins() {
        let (tx, rx) = mpsc::channel();
        let service = SamplingService::spawn(Duration::from_secs(5), move || {
            move || {
                tx.send(()).unwrap();
                Snapshot::default()
            }
        })
        .unwrap();
        rx.recv_timeout(Duration::from_secs(1)).unwrap();
        service.set_interval(Duration::from_millis(500)).unwrap();
        rx.recv_timeout(Duration::from_secs(2)).unwrap();
        let start = std::time::Instant::now();
        drop(service);
        assert!(start.elapsed() < Duration::from_millis(250));
    }
    #[test]
    fn drop_waits_for_inflight_collection_and_stops_future_work() {
        let (started_tx, started_rx) = mpsc::channel();
        let (release_tx, release_rx) = mpsc::channel();
        let release = Arc::new(Mutex::new(release_rx));
        let done = Arc::new(AtomicUsize::new(0));
        let d = done.clone();
        let service = SamplingService::spawn(Duration::from_millis(1), move || {
            move || {
                started_tx.send(()).unwrap();
                release.lock().unwrap().recv().unwrap();
                d.fetch_add(1, Ordering::SeqCst);
                Snapshot::default()
            }
        })
        .unwrap();
        started_rx.recv_timeout(Duration::from_secs(1)).unwrap();
        let (dropped_tx, dropped_rx) = mpsc::channel();
        let join = std::thread::spawn(move || {
            drop(service);
            dropped_tx.send(()).unwrap();
        });
        assert!(dropped_rx.recv_timeout(Duration::from_millis(20)).is_err());
        release_tx.send(()).unwrap();
        dropped_rx.recv_timeout(Duration::from_secs(1)).unwrap();
        join.join().unwrap();
        assert_eq!(done.load(Ordering::SeqCst), 1);
    }
}
