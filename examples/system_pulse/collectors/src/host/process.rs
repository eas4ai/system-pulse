use super::*;
#[derive(Debug)]
struct Stat {
    name: String,
    start: u64,
    ticks: u64,
    user_ticks: u64,
    system_ticks: u64,
    threads: u64,
    rss_pages: u64,
}
fn parse_stat(text: &str) -> Result<Stat, String> {
    let open = text.find('(').ok_or("missing process name")?;
    let close = text.rfind(')').ok_or("missing process name terminator")?;
    let values = text[close + 1..].split_whitespace().collect::<Vec<_>>();
    let n = |index: usize| -> Result<u64, String> {
        values
            .get(index)
            .ok_or_else(|| format!("missing stat field {}", index + 3))?
            .parse()
            .map_err(|e| format!("invalid stat field {}: {e}", index + 3))
    };
    Ok(Stat {
        name: text[open + 1..close].into(),
        start: n(19)?,
        ticks: n(11)?.checked_add(n(12)?).ok_or("process tick overflow")?,
        user_ticks: n(11)?,
        system_ticks: n(12)?,
        threads: n(17)?,
        rss_pages: n(21)?,
    })
}
impl HostCollector {
    pub(super) fn collect_processes(&mut self, s: &mut Snapshot) {
        let pids = match self.entries("/proc") {
            Ok(v) => v
                .into_iter()
                .filter_map(|v| v.parse::<u32>().ok())
                .collect::<Vec<_>>(),
            Err(e) => {
                diagnostic(s, "linux-processes", e);
                return;
            }
        };
        let users = self.read("/etc/passwd").map(|text| {
            text.lines()
                .filter_map(|l| {
                    let words = l.split(':').collect::<Vec<_>>();
                    Some((
                        words.get(2)?.parse::<u64>().ok()?,
                        words.first()?.to_string(),
                    ))
                })
                .collect::<BTreeMap<_, _>>()
        });
        let process_count = pids.len() as u64;
        let mut threads = 0u64;
        let mut thread_error = None;
        for pid in pids {
            let path = format!("/proc/{pid}/stat");
            let stat_started = self.now();
            let stat = match self
                .read(&path)
                .and_then(|t| parse_stat(&t).map_err(|e| format!("{path}: {e}")))
            {
                Ok(v) => v,
                Err(e) => {
                    thread_error = Some(e.clone());
                    diagnostic(s, "linux-process", e);
                    continue;
                }
            };
            let stat_finished = self.now();
            let identity = ProcessIdentity {
                pid,
                start_time_ticks: stat.start,
            };
            let key = format!("process:{pid}:{}/", stat.start);
            let cpu_id = format!("{key}cpu");
            let obs = raw_window(
                &path,
                stat_started,
                stat_finished,
                [
                    ("ticks", stat.ticks),
                    ("utime_ticks", stat.user_ticks),
                    ("stime_ticks", stat.system_ticks),
                    ("ticks_per_second", self.ticks_per_second),
                    ("start_time_ticks", stat.start),
                ],
            );
            let cpu_percent = self.counters.derive(&cpu_id, Ok(obs), |a, b, elapsed| {
                let ticks = b.integers["ticks_per_second"];
                if ticks == 0 {
                    return Err("clock tick frequency unavailable".into());
                }
                Ok(100.0 * delta(a, b, "ticks")? as f64 / ticks as f64 / elapsed)
            });
            let io_path = format!("/proc/{pid}/io");
            let io_started = self.now();
            let io = self.read(&io_path).map(|t| fields(&t));
            let io_ns = self.now();
            let mut rate = |suffix: &str, field_name: &str| {
                let id = format!("{key}{suffix}");
                let o = io
                    .clone()
                    .and_then(|m| field(&m, field_name, &io_path))
                    .map(|v| raw_window(&io_path, io_started, io_ns, [("bytes", v)]));
                self.counters
                    .derive(&id, o, |a, b, e| Ok(delta(a, b, "bytes")? as f64 / e))
            };
            let read_bytes_per_second = rate("read", "read_bytes");
            let write_bytes_per_second = rate("write", "write_bytes");
            let status_path = format!("/proc/{pid}/status");
            let uid = self
                .read(&status_path)
                .map(|t| fields(&t))
                .and_then(|m| field(&m, "Uid", &status_path));
            let (user, user_reason) = match uid {
                Ok(uid) => (
                    Some(
                        users
                            .as_ref()
                            .ok()
                            .and_then(|u| u.get(&uid))
                            .cloned()
                            .unwrap_or_else(|| uid.to_string()),
                    ),
                    None,
                ),
                Err(e) => (None, Some(e)),
            };
            // Check identity again after reading multiple process files, so a recycled PID cannot mix rows.
            match self.read(&path).and_then(|t| parse_stat(&t)) {
                Ok(end) if end.start == stat.start => {}
                _ => {
                    thread_error = Some(format!(
                        "{path}: process exited or PID changed during capture"
                    ));
                    continue;
                }
            }
            threads = match threads.checked_add(stat.threads) {
                Some(v) => v,
                None => {
                    thread_error = Some("thread count overflow".into());
                    threads
                }
            };
            let mut memory_bytes = self.integer(
                &format!("{key}memory"),
                &path,
                stat.rss_pages
                    .checked_mul(self.page_size)
                    .ok_or("RSS byte overflow".into()),
                1.0,
            );
            memory_bytes.observations = vec![raw_window(
                &path,
                stat_started,
                stat_finished,
                [("rss_pages", stat.rss_pages), ("page_size", self.page_size)],
            )];
            let mut thread_reading =
                self.integer(&format!("{key}threads"), &path, Ok(stat.threads), 1.0);
            thread_reading.observations = vec![raw_window(
                &path,
                stat_started,
                stat_finished,
                [("value", stat.threads)],
            )];
            s.processes.push(ProcessRow {
                identity,
                name: stat.name,
                user,
                user_reason,
                cpu_percent,
                memory_bytes,
                read_bytes_per_second,
                write_bytes_per_second,
                threads: thread_reading,
            });
        }
        s.processes.sort_by_key(|p| p.identity.pid);
        let r = self.integer(
            "cpu:host/processes",
            "/proc numeric directories",
            Ok(process_count),
            1.0,
        );
        sensor(
            s,
            "cpu:host",
            "processes",
            "Processes",
            SensorKind::Counter,
            Unit::Count,
            "/proc",
            "All enumerated process IDs",
            r,
        );
        let r = self.integer(
            "cpu:host/threads",
            "/proc/[pid]/stat:num_threads",
            thread_error.map_or(Ok(threads), Err),
            1.0,
        );
        sensor(
            s,
            "cpu:host",
            "threads",
            "Threads",
            SensorKind::Counter,
            Unit::Count,
            "/proc/[pid]/stat:num_threads",
            "Sum over process thread counts; unavailable if enumeration is incomplete",
            r,
        );
    }
}
