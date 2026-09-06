commitment: real-system-readings
commit: bb87134b978f8c2400ff1cbed755ca5ee9615d28
examined:
  - LIVE-001 through LIVE-013 and every current falsifier
  - examples/system_pulse/collectors/: discovery, physical counters, process identity, AMD/NVML and sampling service
  - examples/system_pulse/src/ and model/: live state, meters, history, selection, workspace and persistence
  - scripts/system-pulse/: host coverage, process-exit classification, native completion and exact input/selection proof
  - full committed aggregate system-pulse-acceptance-pr8gjqwq and current Cairn receipts
findings:
  - closed: earlier process-exit mechanism and correction findings; their independent verification is retained below.
  - closed: final adversarial code review found no actionable defect.
  - closed: root independently verified complete mandatory host/native artifacts, identity, hashes and cleanup.

## Final independent review — 2026-09-06

Independent reviewer `review_publication_quality` reported PASS for the accepted
source revision. No code changed during review, and no full suite, native session
or build reran. Later documentation and receipt commits leave the accepted inputs
unchanged. This review covers the complete LIVE commitment beyond the most recent
navigation correction.

| Attack | Finding and source evidence |
| --- | --- |
| Invented measurements or hidden failed reads | Errors retain reasons/status instead of successful synthetic zero. Inventory validation requires complete monitor/sensor/reading/source/unit agreement. [Collector](../../examples/system_pulse/collectors/src/host/mod.rs:55), [live state](../../examples/system_pulse/src/live.rs:129), [inventory verifier](../../scripts/system-pulse/host_capture.py:703). |
| Cross-device baseline or PID reuse | Device identity keys counter state; process collection checks start ticks after multi-file reads; UI selection follows PID/start and clears on removal/reuse. [Process collector](../../examples/system_pulse/collectors/src/host/process.rs:144), [selection](../../examples/system_pulse/src/live.rs:332), [workspace](../../examples/system_pulse/src/workspace.rs:550). |
| Incorrect rates, units or scales | Checked deltas and measured elapsed time reject invalid baselines; latency remains unavailable without operations; physical units and compatible meters are retained. [Counters](../../examples/system_pulse/collectors/src/counters.rs:34), [devices](../../examples/system_pulse/collectors/src/host/devices.rs:501), [readings](../../examples/system_pulse/model/src/readings.rs:144), [meters](../../examples/system_pulse/src/meters.rs:50). |
| UI pressure, unbounded history or damaged saved state | One worker and latest-only delivery bound snapshots; absent history keys are evicted separately from stable preferences. Separate-panel validation, fixture rejection, shared size limits and rejected-original autosave blocking protect restoration. [Service](../../examples/system_pulse/collectors/src/service.rs:60), [history retention](../../examples/system_pulse/src/live.rs:315), [validation](../../examples/system_pulse/src/workspace.rs:95), [autosave](../../examples/system_pulse/src/workspace.rs:1056), [persistence](../../examples/system_pulse/model/src/persistence.rs:35), [storage](../../examples/system_pulse/src/storage.rs:54). |
| Missing comparisons or false native ACK | Controlled coverage cannot use ordinary-process exit exceptions. Retained raw host evidence is recomputed. Native acceptance requires all cases, sixteen child comparisons, exact selection and current-panel exit proof. Traced/focused preparation cannot count as full acceptance. [Process evidence](../../scripts/system-pulse/process_evidence.py:127), [host comparison](../../scripts/system-pulse/host_capture.py:1307), [aggregate](../../scripts/system-pulse/acceptance.py:232), [native process case](../../scripts/system-pulse/native_replay.py:890), [selection proof](../../scripts/system-pulse/native_driver.py:1755). |

Four independent in-memory probes passed in 0.008 seconds, covering sixteen
negative cases: missing controlled fields/brackets, wrong PID/start identity,
permission/reuse/early-terminal exit evidence, incorrect scaling, one-ULP errors,
zero elapsed time, omitted native cases, repeated/stale held sequences, watcher
errors and lost input. These attacks produced no false acceptance.

## Independent artifact audit

Root checked all 154 declared artifacts and command-log hashes, 242 retained file
hashes, all sixteen exact controlled-child comparisons, eight joined held-input
observers, seven application sessions and the private transport. Every application
and transport exited zero without a surviving process. Source and running binary
hashes matched the accepted revision. Captured physical-chart and recalled-workspace
screenshots were inspected. The [full report](../../docs/execution/real-system-readings/final-acceptance-pass.md)
and [record](../../docs/execution/real-system-readings/final-acceptance-pass.json)
retain counts, sources, actual recoveries and limits. All thirteen current Cairn
receipts pass; historical failures retain their actual results.

## Limits and closure

The four independently explained ordinary-process exit gaps remain unverified
comparisons under the agreed policy. NVIDIA hardware accuracy, macOS/Windows
native behavior and physical device removal remain unverified. The missing-device
case uses a stopped-app configuration specimen. Direct diagnostic access to every
retained history point is unavailable; model/app checks, accepted sequences and
visual chart inspection supply that evidence. Service shutdown joins its worker;
an in-flight OS/driver call cannot itself be cancelled. No stronger cancellation
or unavailable-platform guarantee is claimed.

The final review has no open finding. The [production self-audit](../../docs/execution/real-system-readings/production-self-audit.md)
records the fourteen-rule release check. Cairn determines the final Done verdict.

## Historical mechanism review

The following records concern the earlier candidate
`2af88777383dd82139846cc23d00cf4dbacf98ea` and its reviewed corrections.

## Mechanism review for revised LIVE-013

Requirement digest: sha256:ca3fad2f6558d9d189fefaa74561f534b8fc04b3c8cab886496f044ea45919f4

Independent read-only review found the four mismatches above. No code changed during review and no tests or native capture ran. Corrective implementation is a separate action. The agreed specification and plan describe the approved change; this review is not final commitment acceptance.

Preserve exact arithmetic and check_counter. A permitted missing after comparison requires matching independent before evidence, an actual later terminal stat read, consistent PID/start identity, no relevant permission or conflicting identity, and satisfaction of observed lower bounds. Never infer a counter from exit. Controlled child and non-process comparisons remain mandatory. Retain ordinary-only disappearance attempts in the existing bounded observation path, and validate new coverage artifacts before reporting host passes.

## First correction review

Candidate: `37bc9c37`, with build configuration `6e6963b3`. Independent SPEC review ran 61 focused tests successfully but reproduced both additional findings above: a child artifact lacking mandatory fields or containing permission failure/wrong rows was accepted; a terminal stat window with start after end was classified as proven exit. Corrective work is separate from this read-only review. QUALITY review has not started.

## Correction verification

Candidate `9e12415c` passed independent SPEC then QUALITY. SPEC ran 65 focused tests and original defect probes; QUALITY ran 59 focused plus 28 reporting tests and eight additional negative probes. All passed. The four mechanism mismatches and two initial SPEC findings are closed. See docs/execution/real-system-readings/process-exit-review.md. This historical mechanism review did not satisfy final commitment review; that separate review is recorded above.
