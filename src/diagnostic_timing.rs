//! Bounded observation only. All offsets use this writer's Instant origin.
use serde::Serialize;
use std::{collections::VecDeque, sync::Arc, time::Instant};

pub(super) const CAPACITY: usize = 64;
const ERROR_BYTES: usize = 512;

#[derive(Serialize)]
pub(crate) struct Clock {
    pub application_pid: u32,
    pub session_id: String,
    monotonic_clock: &'static str,
    origin_wall_before_unix_ns: u64,
    origin_wall_after_unix_ns: u64,
    #[serde(skip)]
    origin: Instant,
}

impl Clock {
    pub(super) fn new() -> Self {
        let before = crate::live::unix_ns();
        let origin = Instant::now();
        let after = crate::live::unix_ns();
        let application_pid = std::process::id();
        Self {
            application_pid,
            session_id: format!("{application_pid}-{before}-{after}"),
            monotonic_clock: "std::time::Instant nanoseconds since writer origin; not harness monotonic_ns",
            origin_wall_before_unix_ns: before,
            origin_wall_after_unix_ns: after,
            origin,
        }
    }

    pub(crate) fn now(&self) -> u64 {
        self.origin.elapsed().as_nanos().min(u64::MAX as u128) as u64
    }
}

#[derive(Clone, Copy, Default, Serialize)]
pub(crate) struct Stages {
    pub acceptance_started_ns: Option<u64>,
    pub model_completed_ns: Option<u64>,
    pub construction_started_ns: Option<u64>,
    pub construction_completed_ns: Option<u64>,
    pub submission_started_ns: Option<u64>,
    pub submission_completed_ns: Option<u64>,
    pub dequeue_ns: Option<u64>,
    pub json_conversion_started_ns: Option<u64>,
    pub json_conversion_completed_ns: Option<u64>,
    pub serialization_started_ns: Option<u64>,
    pub serialization_completed_ns: Option<u64>,
    pub temp_write_started_ns: Option<u64>,
    pub temp_write_completed_ns: Option<u64>,
    pub rename_started_ns: Option<u64>,
    pub rename_completed_ns: Option<u64>,
}

#[derive(Clone, Serialize)]
pub(crate) struct Timing {
    #[serde(skip)]
    pub clock: Arc<Clock>,
    pub sequence: u64,
    pub render_revision: u64,
    pub accepted_unix_ns: u64,
    pub stages: Stages,
    pub bytes: Option<u64>,
    pub temp_device: Option<u64>,
    pub temp_inode: Option<u64>,
    pub outcome: &'static str,
    pub primary_error: Option<String>,
    pub trace_error: Option<String>,
}

impl Timing {
    pub(super) fn new(clock: Arc<Clock>, sequence: u64, revision: u64, accepted: u64) -> Self {
        Self {
            clock,
            sequence,
            render_revision: revision,
            accepted_unix_ns: accepted,
            stages: Stages::default(),
            bytes: None,
            temp_device: None,
            temp_inode: None,
            outcome: "submitted",
            primary_error: None,
            trace_error: None,
        }
    }
}

pub(crate) fn bounded_error(error: &str) -> String {
    if error.len() <= ERROR_BYTES {
        return error.to_owned();
    }
    let suffix = " [truncated]";
    let mut end = ERROR_BYTES - suffix.len();
    while !error.is_char_boundary(end) {
        end -= 1;
    }
    format!("{}{suffix}", &error[..end])
}

#[derive(Clone, Serialize)]
pub(super) struct History {
    pub records: VecDeque<Timing>,
    pub submitted: u64,
    pub dequeued: u64,
    pub overwritten_before_dequeue: u64,
    pub evicted: u64,
    pub sidecar_errors: u64,
    pub last_sidecar_error: Option<String>,
}

impl Default for History {
    fn default() -> Self {
        Self {
            records: VecDeque::with_capacity(CAPACITY),
            submitted: 0,
            dequeued: 0,
            overwritten_before_dequeue: 0,
            evicted: 0,
            sidecar_errors: 0,
            last_sidecar_error: None,
        }
    }
}

impl History {
    pub(super) fn submit(&mut self, timing: Timing, overwritten_revision: Option<u64>) {
        self.submitted = self.submitted.saturating_add(1);
        if let Some(revision) = overwritten_revision {
            self.overwritten_before_dequeue = self.overwritten_before_dequeue.saturating_add(1);
            if let Some(record) = self
                .records
                .iter_mut()
                .find(|r| r.render_revision == revision)
            {
                record.outcome = "overwritten_before_dequeue";
            }
        }
        if self.records.len() == CAPACITY {
            self.records.pop_front();
            self.evicted = self.evicted.saturating_add(1);
        }
        self.records.push_back(timing);
    }

    pub(super) fn update(&mut self, timing: Timing) {
        // An old in-flight completion cannot resurrect an evicted record.
        if let Some(record) = self
            .records
            .iter_mut()
            .find(|r| r.render_revision == timing.render_revision)
        {
            *record = timing;
        }
    }
}
