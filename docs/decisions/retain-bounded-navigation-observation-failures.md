# Retain bounded navigation observation failures

Level: Judged
Decided by: agent
Rests on: LIVE-003, LIVE-010 and LIVE-013 require exact process identity, preserved navigation and explanations for missing mandatory proof. The sjpr0a2l trace failed during strict selection discovery with a live endpoint and later reindexing, but retained no intermediate scan or rejection context.
Would be wrong if: Observation changes read or input calls, acknowledgement or exit policy, any deadline/freshness bound, creates unbounded state or success-path I/O, hides primary failures, labels native selection as model state, or treats conditional offline recovery as proof of the live cause.
History: Publication tracing passed independent reviews and measured bounded downstream timings in one diagnostic, which did not reproduce stale freshness. Independent navigation review identifies an evidence gap rather than a supported behavior remedy. This adds failure context without relaxing acceptance or inferring a cause.

## Decision

Retain bounded context from the existing native navigation observations so the next failure distinguishes wrong or absent instantiated selection, partial discovery and rejected publication brackets. The sjpr0a2l traced diagnostic remains FAIL: its matching pre-dispatch endpoint remains present in the later snapshot at a changed index, and the screenshot retains the originally issued viewport position. It contains no per-observation proof or justified endpoint exit. Conditional offline recovery succeeds with retained selection and stable publications, but does not establish those conditions during the failed run. Publication stage timings do not explain the previous stale frame and authorize no performance remedy.

Use a fixed-capacity history of at most 64 observations scoped to the active navigation operation, with bounded fields and collections plus observed/evicted counts. Capture existing phase and issued PID/start/index, original deadlines, monotonic start/end and discovery/scan durations, actual before/after publications and panel-validation outcomes, observed native selected identity/count, partial or complete scan status and mapped row span, and explicit rejection or exception reason. Record only what the existing calls actually observed; null or missing stages mean unobserved. Instantiated native selection must never be described as model selection. Keep accessible objects and full process snapshots/lists out of retained history.

Instrumentation adds bounded timestamp and memory bookkeeping around existing reads and branches only. Add no accessibility or procfs reads, success-path filesystem I/O, physical input, retries, sleep, worker, polling loop, unbounded log or queue. Attach bounded records to the existing navigation failure artifact after failure; diagnostic serialization/storage errors cannot replace the original failure. No new tracing mode or application/Rust change is needed for ordinary harness failure context. The original single-read fail-fast freshness/PID checks, eight-second batch and 180-second total navigation deadlines, five-second metric/exit requirements, exact successful acknowledgements, independent pending-exit proof, all sixteen controlled child metric comparisons, controlled exit and held-input checks remain unchanged.

Write tests first for partial/complete scans, selected competitors versus no selection, changing publication brackets and recorded rejection causes; prove fixed retention and individual bounds, original errors/deadlines preserved, no invented completions and no added read/input calls. Run relevant/full Python verification and scoped lint/format/documentation checks, then independent SPEC followed by QUALITY review. Run one fresh focused native replay with publication tracing disabled and preserve its outcome. Record any cause-supported remedy as a separate decision before changing behavior. Fresh untraced full aggregate acceptance and final review remain mandatory.

Independent SPEC and QUALITY reviews passed after correcting guarded diagnostic
input extraction. See the [implementation](../execution/real-system-readings/native-navigation-observations-implementation.md)
and [review](../execution/real-system-readings/native-navigation-observations-review.md).
The fresh focused replay and full aggregate acceptance remain pending.

## Realized by

- 125971f244e58fe8020b97fbef0490a96a5ef6d4 test: retain bounded native navigation failure observations
- 2df34d14b6d0e2f2a37b7e4093f5ccee2c6c7a17 test: preserve scan errors on malformed observation frames
