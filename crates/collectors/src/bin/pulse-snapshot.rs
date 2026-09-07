use std::{
    io::{self, Write},
    time::{Duration, Instant},
};
use system_pulse_collectors::{HostCollector, SUPPORTED_INTERVALS};
#[derive(Debug, PartialEq)]
struct Options {
    count: usize,
    interval: Duration,
}
fn parse(args: impl IntoIterator<Item = String>) -> Result<Options, String> {
    let mut count = None;
    let mut interval = None;
    let mut args = args.into_iter();
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--count" if count.is_none() => {
                let n = args
                    .next()
                    .ok_or("--count requires a value")?
                    .parse::<usize>()
                    .map_err(|e| format!("Invalid count: {e}"))?;
                if !(1..=100_000).contains(&n) {
                    return Err("Count must be between 1 and 100000".into());
                }
                count = Some(n);
            }
            "--interval-ms" if interval.is_none() => {
                let n = args
                    .next()
                    .ok_or("--interval-ms requires a value")?
                    .parse::<u64>()
                    .map_err(|e| format!("Invalid interval: {e}"))?;
                let d = Duration::from_millis(n);
                if !SUPPORTED_INTERVALS.contains(&d) {
                    return Err("Interval must be 500, 1000, 2000, or 5000 milliseconds".into());
                }
                interval = Some(d);
            }
            _ => return Err(format!("Unknown or repeated option: {arg}")),
        }
    }
    Ok(Options {
        count: count.unwrap_or(3),
        interval: interval.unwrap_or(Duration::from_secs(1)),
    })
}
fn run() -> Result<(), String> {
    let args = std::env::args().skip(1).collect::<Vec<_>>();
    if args == ["--help"] {
        println!(
            "pulse-snapshot [--count 1..100000] [--interval-ms 500|1000|2000|5000]\nEmits JSON lines with owned host snapshots and raw observations."
        );
        return Ok(());
    }
    let options = parse(args)?;
    let mut collector = HostCollector::new();
    let stdout = io::stdout();
    let mut out = stdout.lock();
    let mut deadline = Instant::now();
    for i in 0..options.count {
        if i > 0 {
            std::thread::sleep(deadline.saturating_duration_since(Instant::now()));
        }
        let snapshot = collector.collect();
        serde_json::to_writer(&mut out, &snapshot)
            .map_err(|e| format!("Write snapshot JSON: {e}"))?;
        writeln!(out)
            .and_then(|_| out.flush())
            .map_err(|e| format!("Write snapshot: {e}"))?;
        deadline += options.interval;
        while deadline <= Instant::now() {
            deadline += options.interval;
        }
    }
    Ok(())
}
fn main() {
    if let Err(e) = run() {
        eprintln!("pulse-snapshot: {e}");
        std::process::exit(2);
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    fn args(a: &[&str]) -> Vec<String> {
        a.iter().map(|s| s.to_string()).collect()
    }
    #[test]
    fn validates_count_and_interval() {
        assert_eq!(
            parse(args(&["--count", "2", "--interval-ms", "500"])).unwrap(),
            Options {
                count: 2,
                interval: Duration::from_millis(500)
            }
        );
        for a in [
            vec!["--count", "0"],
            vec!["--count", "100001"],
            vec!["--count", "x"],
            vec!["--count"],
            vec!["--interval-ms", "42"],
            vec!["--unknown"],
            vec!["--count", "2", "--count", "3"],
        ] {
            assert!(parse(args(&a)).is_err(), "{a:?}");
        }
    }
}
