# Mac performance measurement and implementation

Status: Agreed 2026-09-07

## Fixed comparison

- Host: the same eight-core M1 Pro MacBook, awake on the same power source.
- Reference: locked release of `af243cf2dba5eb6c4cb19397c522c38eda640f45`.
- Candidate: locked release of the committed optimization; record both hashes.
- Workload: default isolated settings, one-second collection, Summary at
  1280 by 880 logical pixels; tray-only means zero dashboard windows.
- Warm up for at least 30 seconds before each timed window. Measure three
  60-second windows for each binary in each mode. Alternate reference and
  candidate order across repetitions; run only one monitor instance at a time.
- Use independent native process CPU counters and monotonic elapsed time.
  CPU percent is 100 times CPU seconds divided by elapsed seconds. Aggregate
  each binary/mode by summing CPU seconds and elapsed seconds across all three
  repetitions. The candidate/reference ratio must be at most 0.5 in both modes.
- Record each repetition, process identity, executable hash, OS/hardware,
  configured interval, native window state and process census. Do not discard
  an unfavorable valid run. An interrupted or invalid set is retained and a
  complete replacement set is required. Explain material workload differences.
- No compiler, profiler, snapshot writer or deliberate stress workload runs
  during scored intervals. Settings are isolated from the developer's files.
- Native close, reopen, history/reading inspection and quit happen outside
  scored intervals. Shut down each owned process and wake lock on every exit.

## Implementation order

1. Preserve the reference binary and establish failing comparison checks.
2. Reuse temperature-sensor connections while refreshing readings every sample.
   Test failed reads, disappearance, recovery and bounded inventory handling.
3. Avoid repeated account enumeration without freezing per-process user identity.
   Bound cache lifetime and negative lookup behavior.
4. Investigate disk discovery only with evidence. Retaining a disk object whose
   refresh silently keeps old values is not an acceptable optimization.
5. Re-measure the whole release after each coherent change. Touch rendering only
   if a subsequent profile justifies it; do not reduce interaction refresh rate.
6. Run three paired native repetitions, affected native Mac/Linux tests, strict
   Clippy and formatting; review measurement integrity and cache recovery.

The [performance contract](../spec/performance.md) owns the pass/fail conditions.
Existing missing Intel hardware evidence is not required to claim a reduction
on this MacBook and must not be relabeled as verified by these measurements.
