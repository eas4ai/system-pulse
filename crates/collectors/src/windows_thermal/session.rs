use super::protocol::{Frame, Result};
use std::{
    sync::{
        Mutex,
        atomic::{AtomicBool, AtomicU64, Ordering},
    },
    time::{Duration, Instant},
};
pub(super) const MAX_AGE: Duration = Duration::from_secs(3);
#[derive(Clone, Debug)]
pub(super) enum Latest {
    Off,
    Pending,
    Failed(String),
    Sample(Frame, Instant),
}
struct State {
    active: bool,
    latest: Latest,
}
pub(crate) struct Control {
    generation: AtomicU64,
    running: AtomicBool,
    state: Mutex<State>,
}
impl Default for Control {
    fn default() -> Self {
        Self {
            generation: AtomicU64::new(0),
            running: AtomicBool::new(false),
            state: Mutex::new(State {
                active: false,
                latest: Latest::Off,
            }),
        }
    }
}
impl Control {
    pub(crate) fn enabled(&self) -> bool {
        self.state.lock().unwrap_or_else(|e| e.into_inner()).active
    }
    pub(super) fn begin(&self) -> Result<Option<u64>> {
        let mut state = self.state.lock().unwrap_or_else(|e| e.into_inner());
        if state.active {
            return Ok(None);
        }
        if self.running.swap(true, Ordering::AcqRel) {
            return Err("Previous CPU temperature authorization is still closing; dismiss its prompt before retrying".into());
        }
        let generation = self
            .generation
            .fetch_add(1, Ordering::AcqRel)
            .wrapping_add(1);
        state.active = true;
        state.latest = Latest::Pending;
        Ok(Some(generation))
    }
    pub(crate) fn disable(&self) {
        let mut state = self.state.lock().unwrap_or_else(|e| e.into_inner());
        self.generation.fetch_add(1, Ordering::AcqRel);
        state.active = false;
        state.latest = Latest::Off;
    }
    pub(super) fn current(&self, generation: u64) -> bool {
        self.generation.load(Ordering::Acquire) == generation
    }
    pub(super) fn publish(&self, generation: u64, latest: Latest) {
        let mut state = self.state.lock().unwrap_or_else(|e| e.into_inner());
        if self.current(generation) && state.active {
            state.latest = latest;
        }
    }
    pub(super) fn finish(&self, generation: u64, reason: String) {
        let mut state = self.state.lock().unwrap_or_else(|e| e.into_inner());
        if self.current(generation) {
            state.active = false;
            state.latest = Latest::Failed(reason);
        }
        self.running.store(false, Ordering::Release);
    }
    pub(super) fn latest(&self, now: Instant) -> Latest {
        let state = self.state.lock().unwrap_or_else(|e| e.into_inner());
        match &state.latest {
            Latest::Sample(_, received) if now.saturating_duration_since(*received) > MAX_AGE => {
                Latest::Failed(
                    "CPU package temperature is stale; disable and enable to retry".into(),
                )
            }
            latest => latest.clone(),
        }
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Arc;
    fn frame() -> Frame {
        Frame {
            sequence: 1,
            target: 100 << 16,
            status: (1 << 31) | (65 << 16),
            before: 1,
            after: 2,
            frequency: 10,
            error: 0,
        }
    }
    #[test]
    fn duplicate_enable_and_disabled_pending_launch_are_bounded() {
        let c = Control::default();
        let g = c.begin().unwrap().unwrap();
        assert!(c.enabled());
        assert_eq!(c.begin().unwrap(), None);
        c.disable();
        assert!(!c.enabled());
        assert!(!c.current(g));
        assert!(c.begin().is_err());
        c.finish(g, "cancelled".into());
        assert!(matches!(c.latest(Instant::now()), Latest::Off));
        assert!(c.begin().unwrap().is_some());
    }
    #[test]
    fn cancelled_generation_cannot_publish_or_clobber_retry() {
        let c = Control::default();
        let g = c.begin().unwrap().unwrap();
        c.disable();
        c.publish(g, Latest::Sample(frame(), Instant::now()));
        assert!(matches!(c.latest(Instant::now()), Latest::Off));
        c.finish(g, "old failure".into());
        let new = c.begin().unwrap().unwrap();
        c.publish(g, Latest::Failed("late failure".into()));
        assert!(c.current(new));
        assert!(matches!(c.latest(Instant::now()), Latest::Pending));
    }
    #[test]
    fn samples_expire_and_failures_clear_values() {
        let c = Control::default();
        let g = c.begin().unwrap().unwrap();
        let now = Instant::now();
        c.publish(g, Latest::Sample(frame(), now));
        assert!(matches!(c.latest(now), Latest::Sample(_, _)));
        assert!(matches!(
            c.latest(now + MAX_AGE + Duration::from_millis(1)),
            Latest::Failed(_)
        ));
        c.finish(g, "helper exited".into());
        assert!(matches!(c.latest(now), Latest::Failed(_)));
        assert!(c.begin().unwrap().is_some());
    }
    #[test]
    fn blocked_authorization_does_not_block_reads_or_disable() {
        let c = Arc::new(Control::default());
        let g = c.begin().unwrap().unwrap();
        let (tx, rx) = std::sync::mpsc::channel();
        let worker = c.clone();
        let join = std::thread::spawn(move || {
            rx.recv().unwrap();
            worker.finish(g, "denied".into());
        });
        let start = Instant::now();
        for _ in 0..100 {
            c.latest(Instant::now());
        }
        c.disable();
        assert!(start.elapsed() < Duration::from_secs(1));
        tx.send(()).unwrap();
        join.join().unwrap();
    }
}
