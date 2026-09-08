# Skip unrequested Mac process arguments in sysinfo refresh

Surfaced from: PERF-001
Captured: 2026-09-08T13:12:44.709Z

Native profiling attributes about 22.6 percent of candidate CPU samples to get_process_infos, which reads KERN_PROCARGS2 even when command/environment/executable fields are not requested. Reviewable proposal: docs/execution/macos-performance/process-refresh-proposal.md. Extend the collector-only commitment before any dependency patch or upgrade; preserve all live readings and verify fresh paired measurements.
