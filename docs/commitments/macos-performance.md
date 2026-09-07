# Reduce native Mac monitoring overhead

Status: Agreed 2026-09-07
Slug: macos-performance
Requirements: PERF-001, PERF-002, PERF-003, PERF-004, PERF-005, PERF-006

The developer approved the proposal to halve native release CPU use in both
Summary and tray-only modes while retaining the one-second interval, real
readings, history and interaction. Work begins with the measured collector,
then returns to profiling before any wider optimization.

Source changes belong in the application collector and directly affected tests.
Verification helpers belong in scripts/system-pulse. Evidence and the review
belong in docs/execution/macos-performance and .cairn/reviews. The
[protocol](../plans/macos-performance.md) specifies the native comparison.

Done requires all six requirements passing against committed source, the
applicable Linux and Mac checks, a review of failure/recovery and measurement
integrity, and an optimized Mac release with its hash and measurements.

This commitment does not complete the older finish-application or GPU hardware
commitments. Their pending evidence and historical scope reconciliation remain
recorded in the [recon](../recon.md) and backlog. Switching current work does not
grant a retrospective pass or an exception for their recorded history.
