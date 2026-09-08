# Reduce native Mac monitoring overhead

Status: Suspended by developer 2026-09-08; CPU targets unmet
Slug: macos-performance
Requirements: PERF-001, PERF-002, PERF-003, PERF-004, PERF-005, PERF-006

The developer approved the proposal to halve native release CPU use in both
Summary and tray-only modes while retaining the one-second interval, real
readings, history and interaction. Work begins with the measured collector,
then returns to profiling before any wider optimization.

Source changes belong in the application collector and directly affected tests.
On 2026-09-08 the developer extended this scope to the narrow sysinfo process
argument-refresh fix, its tests, Cargo patch/lock changes and package provenance.
The approved [proposal](../execution/macos-performance/process-refresh-proposal.md)
preserves the existing CPU targets and native verification requirements.
On 2026-09-08 the developer also approved application snapshot acceptance,
derived presentation and panel notification changes in `src/`, with directly
affected tests, under the [presentation proposal](../execution/macos-performance/presentation-work-proposal.md).
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

The developer agreed to stop after the final comparison. Summary CPU was
21.7% lower and tray-only CPU 34.0% lower; neither met the 50% requirement.
PERF-003 through PERF-006 passed the committed gate. This commitment remains
incomplete. See the [stop decision](../decisions/stop-mac-optimization-after-the-final-paired-comparison.md)
and [final measurements](../execution/macos-performance/evidence/measurements.json).
