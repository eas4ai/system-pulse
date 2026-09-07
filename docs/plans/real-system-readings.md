# Real System Readings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Status:** Complete on 2026-09-06. All thirteen LIVE requirements pass; independent final review is clean and Cairn reports Done. See [completion](../execution/real-system-readings/completion.md).

**Goal:** Replace runtime simulation with accurately attributed host readings while preserving the approved workspace.

**Architecture:** A pure collector crate produces immutable, typed snapshots. One background sampling service owns OS handles and counter baselines and exposes only its latest result. GPUI applies snapshots, retains presentation by stable identity, and renders physical quantities; deterministic injection is test-only.

**Tech Stack:** Rust 2024, pinned sysinfo 0.37.2, serde/serde_json, Linux procfs/sysfs, runtime-loaded NVIDIA NVML, existing GPUI/gpui-component.

The contract is [LIVE-001–013](../spec/live-collection.md). NVIDIA support was explicitly added by the developer; live NVIDIA hardware verification is unavailable on this AMD host and must remain labeled as such. Use this tracked plan directory because this source repository ignores docs/superpowers. The earlier fixture acceptance is a preservation baseline, not live accuracy evidence.

## Ownership and sequencing

Only one source implementer works at a time. Give each fresh implementer its full task and relevant interfaces. Every implementation receives independent spec review followed by independent quality review; resolve findings before the next source task. Root may investigate host measurements and prepare evidence alongside an implementer. Preserve the existing reference example and framework patches.

- Collector worker: `crates/collectors/`, workspace membership and lockfile.
- Integration worker: `src/`, `crates/model/`, app manifest and lockfile changes needed for its collector dependency.
- Acceptance worker: `scripts/system-pulse/`, `docs/execution/real-system-readings/`, updated app README/acceptance instructions.

## Task 1: Host collectors, physical snapshot schema, and bounded service

Create package `system-pulse-collectors`, with `src/lib.rs` exports, `types.rs` quantities/descriptors, `counters.rs` measured deltas, `linux.rs` proc/sysfs collection (split CPU/memory/process/devices into focused modules as needed), `nvidia.rs` NVML adapter boundary, `service.rs` lifecycle, and `src/bin/pulse-snapshot.rs` JSON-line diagnostics. Add the crate to root `Cargo.toml`; use serde workspace dependencies and exact sysinfo 0.37.2. Keep this crate independent of GPUI and presentation persistence.

### Boundary contract

Export owned, serializable `Snapshot`, `MonitorDescriptor`, `SensorDescriptor`, `Reading`, `ProcessRow`, `ProcessIdentity`, `SensorKind`, `Unit`, and `Availability` types. A snapshot includes monotonic capture start/end timestamps, device/sensor descriptors, readings, complete process rows, and backend diagnostics. Each sensor has stable identity, title, physical kind/unit, source path/API, semantic scope, and optional capacity/scale. Readings carry optional raw numeric value, optional total, explicit availability/reason, and source observations sufficient to recompute deltas. Never store formatted strings as the only measurement. Retain actual integer counters where floating-point conversion could lose precision. A process identity combines PID with start time/ticks; CPU uses a documented one-core denominator and can exceed 100%.

Expose `HostCollector::new()` and `HostCollector::collect() -> Snapshot`. Expose `SamplingService::start(interval)`, `set_interval`, and `take_latest`; service drop signals stop and joins its single worker. The service owns the collector and uses a one-slot latest-snapshot buffer, an interruptible interval wait, and allowed intervals 500/1000/2000/5000 ms. Read-only lock duration is limited to swapping the snapshot. Backend tests inject the collection function without production fixture controls. Collection errors become per-field/backend diagnostics, not panics or zero values.

- [x] Write counter tests first. Known samples demonstrate 3000 bytes over 1500 ms = 2000 B/s; first sample and zero elapsed are warming/unavailable, a decreased counter invalidates that baseline, recovery starts from the new baseline, and failure never becomes zero. CPU deltas exclude guest double-counting and declare iowait treatment.

```rust
#[test]
fn irregular_elapsed_is_used() {
    let rate = checked_rate(1_000, 4_000, std::time::Duration::from_millis(1_500));
    assert_eq!(rate, Some(2_000.0));
    assert_eq!(checked_rate(4_000, 1_000, std::time::Duration::from_secs(1)), None);
    assert_eq!(checked_rate(1_000, 4_000, std::time::Duration::ZERO), None);
}
```

`checked_rate(previous: u64, current: u64, elapsed: Duration) -> Option<f64>` uses `current.checked_sub(previous)` and rejects zero duration before division. Baseline ownership remains in the collector keyed by stable device/process identity. Purge absent baseline keys on refresh.

- [x] Run `rtk cargo test -p system-pulse-collectors` and observe the new behavior fail before implementing it. Implement the arithmetic and physical schema; rerun focused tests.
- [x] Implement every accessible field in the contract matrix. CPU: `/proc/stat`, cpufreq/current frequency, labeled hwmon CPU temperature, `/proc/loadavg`, process/thread census, `/proc/uptime`. Memory: `/proc/meminfo` bytes (used = total - available), documented composition, swap, `/proc/vmstat` page faults. Processes: retained sysinfo refresh with no row cap, `/proc/<pid>/stat` start ticks, status threads/UID, io counters and explicit denied status; no command-line/environment capture.
- [x] Implement volumes with capacity and Linux mount/block-device mapping; diskstats sectors are 512 bytes, rates use measured time, IOPS use completed operations, mean latency is delta operation milliseconds / delta completed operations. Label shared backing-device I/O; unsupported mappings explain their scope. Discover interfaces from actual network devices, read byte counters with error-preserving sysfs reads, and derive rates from monotonic deltas. Attribute connection counts only when address/interface mapping supports them; wildcard/system-wide connections cannot be copied to each interface.
- [x] Implement AMD discovery using DRM vendor/device and stable `unique_id` (PCI fallback with explicit provenance). Read utilization/VRAM bytes, labeled hwmon temperatures in millidegrees C, average SoC power in microwatts, sclk/mclk frequencies in Hz, fan RPM. Do not treat legitimate sleeping GPU clock zero as an error. Sensors describe source semantics, not a stronger invented quantity.
- [x] Implement NVIDIA via optional runtime NVML loading, stable device UUIDs, per-field results and real device discovery. Cover utilization, memory, temperature, power, graphics/memory clocks and fan percentage. Missing library/driver/device must leave other collection operational. Test a fake NVML boundary for multiple/reordered devices, exact unit conversion, independently unsupported fields, permission failure, GPU loss, and recovery. Test injection does not enter the normal application interface.
- [x] Test discovery reorder/removal/reappearance, field permission failures, process PID reuse, empty and over-500 process snapshots, and all required capability entries. Test the single service with controlled slow collection: maximum concurrency one, latest-only delivery, interval change without another worker, and shutdown notification/join.
- [x] Implement `pulse-snapshot --count 3 --interval-ms 1000` to emit real JSON snapshots with raw counter observations and diagnostics. Reject invalid arguments; finite captures exit cleanly. Capture actual host output and enumerate every required field in a capability report.
- [x] Run collector tests, `rtk cargo clippy -p system-pulse-collectors --all-targets -- -D warnings`, and rustfmt. Commit owned files; independent spec then quality review must pass. Publish the exact final API to the integration worker.

## Task 2: Real snapshot application, physical meters, and identity-safe persistence

Modify app `src/lib.rs`, `main.rs`, `workspace.rs`, `panel.rs`, `meters.rs`, `storage.rs`, and model reading/presentation/persistence modules. Add focused `live.rs` integration helpers if needed to keep collection conversion out of rendering. Existing native tests use a test-only deterministic source. Normal launch title and toolbar identify System Pulse and sampling interval, with no fixture controls or identities.

- [x] Write failing model tests for physical scale: 4096 B/s is not clamped to 100; used 16 GiB / total 64 GiB yields one quarter; nonfinite data and negative values for nonnegative quantities cannot enter successful history; valid subzero temperatures remain valid; counters and compound summaries reject incompatible meters. Percentage bounds apply only to percentages with that semantic limit. Process CPU may exceed one core.
- [x] Implement physical kind/unit/total metadata, display formatting, compatible meter choices, and charts scaled to physical data. Use the product compatibility matrix: Percentage number/sparkline/line/bar/radial; Temperature number/sparkline/line/radial; Rate (including RPM) number/sparkline/line; Capacity number/bar; Counter number/sparkline. Additional frequency/power/load/duration kinds need physically sensible subsets and documented scales. Temperature radial scales must not imply an invented device safety limit. Keep compact collapsed values, units, availability/reason and stale status. History remains bounded per series and evicts series for absent devices; retained presentation is independent of history eviction.
- [x] Write failing stable-identity tests: reorder two actual device IDs without moving settings; remove/restore a device without rejecting saved dock structure; never map fixture IDs by ordinal; retain invalid original input. Use a separate live state directory `system-pulse` and preserve the old `system-pulse-fixture` file intact. `SYSTEM_PULSE_STATE_DIR` remains an explicit test/user override.
- [x] Apply owned descriptors and snapshots dynamically. Discover new devices without creating tab groups or changing user collapse/visibility decisions. Restore absent saved device placeholders with a truthful unavailable reason, preserving layout and preference state until reappearance. Initial real discovery must not accidentally destroy a saved layout before the first snapshot arrives.
- [x] Write failing process selection tests for PID/start identity through sort/reorder, exit and PID reuse; render the complete current process snapshot with PID/name/CPU/memory/disk I/O/threads/user. Replace fixed navigation bounds with actual row count and keep keyboard focus visible.
- [x] Start one `SamplingService` outside the UI update path. Apply its latest snapshot on a lightweight UI timer, mark delayed readings stale based on capture age, and expose global 0.5/1/2/5-second selection. Drop ownership stops collection. Collapsed/hidden panels continue sampling and history updates.
- [x] Gate `fixture` and deterministic construction with `cfg(test)`; update all old model/native test callers with explicit injection. Remove normal Advance fixture, fake discovery order and connect/disconnect controls. Retain save/recovery/presentation controls and Separate dock policy.
- [x] Run `rtk cargo test -p system-pulse-model`, `rtk cargo test -p system-pulse`, strict app/model Clippy, formatting, and native build. Replay focused native collapse/scroll/process interactions on real data. Commit and complete independent spec then quality review.

## Task 2a: Close the connection-attribution evidence finding

Read-only acceptance preparation found that connection readings preserve only the derived count. Before building the independent verifier, the collector worker owns a focused follow-up in `crates/collectors/`; first finish Task 2's spec and quality reviews. This is required evidence for the existing LIVE-013 contract, not new product scope.

- [x] Write a failing regression proving that one shared snapshot observation preserves interface/local-address ownership and TCP4/TCP6 local-address/state inputs, with source query windows and actual errors. Preserve raw local-address/state tokens before filtering so independent Python code can challenge byte order, established-state selection, mapped IPv6, wildcard exclusion and distinct-interface ownership. Omit ports, remote endpoints and socket owners.
- [x] Add an optional defaulted snapshot field for the shared observation. Derive per-interface connection counts from those captured inputs without duplicating the tables in each reading. Preserve unavailable/failed semantics; no fake zero on input failure. Verify serialization and full app/model compatibility. Correct the README's overly broad passwd-lookup failure claim or implement the promised distinction; a truthful numeric UID fallback is acceptable when described accurately.
- [x] Run focused regression, collector tests, formatting, strict Clippy and integration checks; commit only owned files. Independent spec then quality reviews must pass before Task 3 implementation.

## Task 2b: Prevent native keyboard input from starving live delivery

The real native probe found a finite X11 key backlog: each navigation key synchronously redraws the large workspace before foreground delivery can run. Ordinary 25 Hz key repeat held for three seconds caused more than fourteen seconds of stale accepted data. See `../execution/real-system-readings/native-freeze.md`. Finish Task 2a reviews before handing production source back to the app implementer.

- [x] Reproduce and retain the ordinary held-key failure and stack evidence. Compare condition-paced navigation so the final harness waits for actual selection acknowledgement instead of adding unprocessed batches.
- [x] Use the pinned GPUI next-frame scheduling API to coalesce navigation repaint requests with one pending request per owning view. Preserve every selection and scroll update immediately. Cover table vertical/horizontal navigation and outer Alt navigation when they share the same demonstrated synchronous pattern. Avoid dependency or unrelated framework rewrites.
- [x] Add a focused regression for accumulated selection/scroll state and bounded repaint scheduling. Run app/model and relevant existing focus/scroll tests, scoped Clippy/format/build. Repeat actual held-key and child-table navigation with current snapshots and clean shutdown; preserve the declared freshness bounds. Commit owned source; independent spec then quality review must pass.

## Task 3: Executable independent host and native acceptance

Create `scripts/system-pulse/acceptance.py`, `host_accuracy.py`, `test_host_accuracy.py`, and a tracked native driver/replay. Extend existing `verify.py` so its source guard is only one step in the full mandatory acceptance run. Evidence goes in `docs/execution/real-system-readings/`; large runtime artifacts may be external with precise hashes/paths. No unavailable test or missing adapter is a passing check.

### Native visibility evidence repair

Root screenshot review found a GPU label behind the toolbar even though its bounds fit inside the window. The native ancestor tree omits the workspace clipping viewport. Before the final native replay, the acceptance worker owns a minimal app follow-up: expose stable semantic accessibility identities and bounds for the workspace viewport and, if needed, the nested process viewport. Add a regression that rejects a window-contained label outside its actual clipping viewport. Verify actual native bounds and visible GPU headers; keep readings and diagnostic schemas unchanged. This separate source candidate receives spec then quality review. Any demonstrated focus-reveal defect must be reported before expanding the change.

The minimal source follow-up is complete at `217941e5`, with independent spec and quality PASS; see [viewport review](../execution/real-system-readings/viewport-review.md). Full Task 3 acceptance remains pending.

### Host census coverage repair

The first reviewed aggregate passed the automated suites but missed two CPU
counter endpoints for a PID absent from every independent census. The collector
observed it between censuses separated by about 75 ms. Preserve that failed
receipt and its [diagnosis](../execution/real-system-readings/aggregate-attempt-2026-09-05.md).

The acceptance worker may refresh the census during long process sweeps on a
prospective 20 ms schedule, immediately sample newly discovered PIDs, and retain
repeated observations through disappearance, even after full sweeps also read the PID. Keep all ordinary PID
reads and every supplemental observation with its identity, query window, census,
and clock anchors. Use one thread and a predeclared 4,096 supplemental-observation
limit alongside the existing capture limits. Exhaustion and missing brackets fail;
this cadence is not a relaxed comparison bound or a guarantee of every lifetime.

Test the between-census appearance, repeated observations, preservation of ordinary
reads, cadence, and limit failures before implementation. Recheck retained host08
compatibility and one coordinated fresh focused capture. Commit the correction
and complete independent SPEC then QUALITY review before rerunning Cairn.

### Preserve supplemental reads through process exit

The resumed aggregate at `204780f2` passed all 430 automated tests but missed
four endpoints for PID/start `1322913:69430231`. Supplemental sampling retired
that identity after the first full sweep. A later supplemental census still
contained it after the collector query but did not read its counters.
Retain the existing fast observations through a direct terminal read rather than
retiring them at ordinary-sweep handoff. Preserve ordinary sampling, identity,
query windows, actual errors and all existing limits. Census presence does not
prove a counter value. Test handoff persistence, disappearance, PID reuse and
budget failures before implementation; obtain SPEC then QUALITY review and a
fresh committed full aggregate. See the judged decision
`retain-supplemental-process-observation-until-exit` and retained
`docs/execution/real-system-readings/resumed-host-exit-gap.json`.

### Missing-device specimen repair

The developer authorized resuming the recorded `live-001` escalation on
2026-09-05. The last aggregate passed 400 tests, fresh host checks, and thirteen
native cases; the final specimen combined an early expanded CPU dock size with
later collapsed panel preferences. See
[retained failure](../execution/real-system-readings/aggregate-attempt-2-2026-09-05.md).

Capture a consistent actual pre-split workspace for the specimen's dock and
presentation preferences. Replace the chosen actual GPU identity with a saved
absent identity, keeping the original actual GPU saved-hidden. Preserve actual
metadata, sensor choices, strict dock equality, and all native unavailable-value
assertions. Add a regression that reproduces the inconsistent composition before
fixing it. Complete focused checks and independent spec then quality review,
followed by a focused native case and the full committed acceptance run.

### Cairn per-requirement evidence

Cairn now accepts `cairn: LIVE-001: pass` result lines. Adapt the shared runner
using existing evidence, preserving every aggregate requirement and failure exit.
All automated steps remain prerequisites. Validate host artifacts before reporting
LIVE-004/012/013. Validate primary native cases through restart, their artifacts,
the first two normal shutdowns and shared transport cleanup before reporting
LIVE-001/002/003/005/008/009/011. Report LIVE-006/007/010 only after all remaining
recovery and missing-device cases, required artifacts and shutdowns pass.

Never print passes from provisional step progress. Missing or interrupted native
proof stays unverified; do not infer a requirement failure from a free-text
harness exception. Reuse the same checks in full and partial paths. Regressions
must reject omitted artifacts, cleanup failures, focused preparations, missing
cases, and early pass publication; the full passing run must emit all thirteen
requirements exactly once. The mechanism declares `results: per-requirement`, so zero known result lines
leave every requirement unverified while preserving the command failure and
execution diagnostics. Legacy receipts retain their original classifications.
Preserve original aggregate failures and raw artifacts.

### Native process exit synchronization

The aggregate at `bc5237d1` passed host verification but inspected the native
Processes tree immediately after diagnostic snapshot publication. Diagnostics
precede redraw scheduling and cannot acknowledge an accessibility update.
Preserve that failed capture in `native-exit-failure.md/json`. Wait for both a
newer snapshot without the exited PID/start identity and its actual absence
from a live native Processes subtree. Share the original five-second exit
deadline across both observations and traversal. A missing/defunct subtree or
slow traversal cannot count as absence. Add deterministic delayed-removal,
permanent-retention, stale-snapshot, missing-subtree and deadline regressions.
Complete independent SPEC then QUALITY review before a fresh committed run.
No product behavior, freshness bound or exit budget changes.

### Independently proven process exits

The developer approved the process observation proposal on 2026-09-05. Keep every
existing comparison and bound. Retain stat observations for previously observed
PID/start identities through an actual terminal read, within existing capture
and observation budgets. Resolve only missing after-counter brackets with valid
independent before evidence and a later terminal stat observation for the same
identity; reject permission failures, identity ambiguity/reuse, missing-before,
known out-of-bound values, and unexplained gaps. A census omission is insufficient.
Record allowed gaps separately as unverified with complete query windows and
source/identity evidence; do not count them in successful bracket totals.

Predeclare the existing owned child as mandatory controlled process coverage.
Require its successful CPU and I/O counter brackets throughout capture plus all
other existing child, host and native assertions. Missing controlled-process or
non-process brackets remain failures. Make the aggregate validate the new
coverage artifacts and child obligations before reporting any host requirement
pass. Preserve old capture outcomes. Add meaningful rejection/recovery and
artifact-gate tests, run the exact gate Python suite, obtain independent SPEC
then QUALITY review, and perform fresh committed host/native acceptance.

### Predeclared comparison rules

Static device IDs, units, total quantities and formulas compare exactly to the same source observation. CPU = 100 * delta(total - idle - iowait) / delta(total), with guest fields excluded from total; process CPU uses one logical core's elapsed ticks as denominator. RAM used = MemTotal - MemAvailable, KiB times 1024. Network and disk rates recompute exact integer counter differences over each recorded monotonic observation interval. Read/write sectors multiply by 512. Disk latency is weighted completed-operation time / completed operations, unavailable at zero operations. AMD conversion divides temperature by 1000, power by 1,000,000; frequency is retained in Hz. NVML units are defined in its adapter tests and source metadata; fan percent remains percent.

Independent samples bracket each collector observation except the explicitly unverified after-counter gaps allowed by the agreed process-exit policy in LIVE-013. For monotonic cumulative counters, the collector raw counter must lie within independent before/after counters. For memory and instantaneous GPU gauges, verify exact captured raw observations, parsing and conversions, then exact rendering of the consumed snapshot. Independent contemporaneous gauge samples provide supporting observations, not proof of equality at a different instant; never invent a percentage tolerance. Derived arithmetic is separately checked exactly from raw inputs. Capture source path, identity, monotonic times, raw values and bound before judging the output. Compare native formatted values to the snapshot at their capture sequence/age, allowing only documented rounding and explicitly captured later snapshots. Bind displayed snapshot identity to opt-in bounded diagnostic evidence of consumed snapshots, serialized off the UI path, and give metric text a natural-language accessible label identical to its visible formatted value. See ../execution/real-system-readings/verification-design.md.

- [x] Write verifier regressions before implementation. Mutated byte unit (1000 versus 1024), CPU normalization, elapsed interval and out-of-bound gauge each fail; correct known observations pass. A capability missing any accessible required field fails. NVIDIA absence is recorded separately from adapter tests; it never produces a hardware-accuracy pass.
- [x] Implement host capture and comparison using Python standard library proc/sysfs readers independent of Rust collector logic. Launch and exit a harmless named child and verify its real PID/identity appears/disappears in snapshots and the actual native Processes table. Record every required field's actual backend and permission/attribution limits.
- [x] Reuse the proven private Xvfb/DBus/AT-SPI harness from the design repository artifact. Native replay proves no fixture controls/tabs, live numeric values, collapsed panel and sensor summaries/history, both-axis overflow, independent collapse, focus and keyboard navigation, mixed-state persistence and recovery while sampling continues.
- [x] Make aggregate verification run collector/model/app tests, affected base dock/resizable and UI dock suites, vendored accessibility regression tests, formatting, strict Clippy, native build, verifier regressions, host capability/accuracy checks and native replay. Require nonzero test counts and fail on missing artifacts or steps.
- [x] Commit the reviewed candidate before `rtk proxy cairn check`. Preserve baseline failing receipts. Fix any new finding with focused checks before rerunning the aggregate. Record a final independent adversarial review against the candidate and require `cairn wake` Done. Update glossary/recon/handoff to distinguish new observed live behavior from historical fixture evidence. Keep the feature branch/worktree; do not merge or push without instruction.

## Coverage self-review

Task 1 implements LIVE-002/004/006/008/009/012 and the explicit NVIDIA addition. Task 2 implements LIVE-001/003/005/007/010/011 and preserves Task 1 semantics at the UI boundary. Task 3 independently challenges every falsifier, including LIVE-013. Native NVIDIA and macOS/Windows evidence remain named limitations; accessible Linux measurements and the NVIDIA adapter itself cannot be deferred.


### Scope native process cell rediscovery

Aggregate `098d2b2e` passed host verification and 481 tests, then a direct
process cell lookup fell back to a full application traversal and ignored
the caller's five-second deadline. The app continued accepting fresh samples.
See [the diagnosis](../execution/real-system-readings/native-cell-discovery-failure.md)
and [decision](../decisions/scope-process-cell-discovery-to-its-native-row.md).

- [x] Extract the existing metric process-row lookup for shared use by cell
  visibility navigation. Carry the original absolute deadline through row
  reacquisition, cell discovery, and movement. Preserve identity, uniqueness,
  node bounds, generic lookup, strict exit traversal, and all comparisons.
- [x] Test stale cells and rows, unrelated branches, duplicate and missing
  cells, PID reuse, and exhaustion of the original deadline. Verify the actual
  replay call boundary, then pass independent SPEC and QUALITY reviews.
- [x] Run focused native process acceptance and fresh committed aggregate
  acceptance. Preserve failed receipts; final review remains pending.


### Publish transient diagnostics without a durability flush

The focused native run retained a complete newer diagnostic temporary file
while the published file became stale. A bounded trace did not reproduce
the specific stall. Source confirms both diagnostic and durable workspace
saves currently wait for sync_all before rename. See
[the decision](../decisions/publish-transient-diagnostics-without-a-durability-flush.md)
and [trace limits](../execution/real-system-readings/diagnostic-publication-trace.md).

- [x] Keep complete atomic diagnostic replacement, revision ordering,
  errors, and cleanup while removing its durability-flush dependency.
  Preserve durable workspace/preset writes and configuration bounds.
- [x] Verify publication policies, failed replacement, stale revisions,
  and complete JSON; run scoped Rust checks/build, then independent
  specification and quality review.
- [x] Run fresh untraced native and committed aggregate acceptance.
  Do not claim the earlier stalled syscall has been identified.


### Prune monitor contents during native panel discovery

The membership-safe helper still exhausts its 15-second discovery deadline
on this host's 151-monitor tree. Preserve current membership checks while
using the observed monitor body viewport boundary to skip its contents
during panel discovery. See [observations](../execution/real-system-readings/native-publication-watch.md).

- [x] Add opt-in body pruning validated against the traversed named parent
  monitor and actual native `panel` roles. Keep workspace/layout traversal,
  all sibling panels, and default generic/strict exit behavior unchanged.
- [x] Test valid and malformed boundaries, duplicate sibling panels,
  detached membership, and shared deadline/node bounds. Complete focused
  and full Python checks, then independent SPEC and QUALITY reviews.
- [x] Verify fresh native timing and complete committed acceptance.
  Earlier intermittent freshness failures remain unexplained.


### Avoid repeated full discovery within a cell scroll gesture

The pruned lookup passed all initial cell comparisons but was repeated
between every arrow movement, exhausting column five's original deadline.
See [the observed failure](../execution/real-system-readings/native-cell-gesture-failure.md).

- [x] Retain the initially verified live cell during the gesture; reacquire
  on replacement or identity change within the original deadline. Keep
  the final metric call's fresh membership and comparison checks intact.
- [x] Reproduce the three-step cost failure, test replacement and timeout
  behavior, run focused/full checks, and pass independent reviews.
- [x] Verify the native process case and full committed acceptance.

### Navigate independently of collector cadence

The [diagnostic capture](../execution/real-system-readings/native-navigation-exit-diagnostic.md)
spent 116.612 seconds waiting for newer samples across 176 two-key batches,
then indexed a selected identity absent from the next snapshot. The
controlled target remained present. See the judged decision
`navigate-live-processes-independently-of-collection-cadence`.

- [x] Keep two-key batches and exact native endpoint acknowledgement.
  Validate fresh frames between batches without forcing a new collector
  sequence each time. Preserve the total and batch deadlines.
- [x] Reconcile an exited selection against current native selection and
  snapshot membership. Retry transient retention of the exited identity;
  after observing no instantiated selected row, reestablish Home/End
  physically within the same deadline; this does not prove model clearing.
  Reject any unexplained transfer to a different selected identity, target
  loss, PID reuse, ambiguous selection, stale frames, and incomplete native
  observations.
- [x] If reusing a panel for intermediate input pacing, validate actual
  current parent-child links before and after strict selection scans.
  Rediscover the unique current panel at start, invalidation, and final
  target proof. Keep final metric membership checks independent.
- [x] Test lifecycle, unchanged-sequence, freshness, acknowledgement ordering,
  current membership, realistic lookup cost, and deadline cases; run
  focused/full checks and independent reviews.
- [x] Run fresh untraced native and full committed acceptance. Earlier
  intermittent focus, burst, and freshness failures remain unproven.

### Respect the native application root boundary

The [retained failure](../execution/real-system-readings/native-application-membership-failure.md)
shows a registered application with null parent and index -1, as the pinned
adapter specifies. Ordinary links succeed; treating the desktop boundary
the same way causes repeated complete discovery until timeout.

- [x] Keep ordinary link checks through the application, then validate its
  current desktop registration by bounded child enumeration, exact native
  identity, liveness, and PID. Preserve final uniqueness and deadlines.
- [x] Reproduce actual root semantics and reject missing/replaced/duplicate
  or incomplete registration, wrong PID, and deadline exhaustion. Pass
  focused/full checks and independent SPEC then QUALITY review.
- [x] Run fresh untraced native and committed aggregate acceptance.

### Retain validated membership during pacing retries

The [retry observations](../execution/real-system-readings/native-navigation-retry-observations.md)
identify local membership discarded after otherwise valid scans when
publication changes. Exact failure causation remains unmeasured because
the diagnostic stopped at an earlier held-input failure.

- [x] Reproduce unnecessary discovery cost during frame/selected-node
  retries, then retain only the validated panel path for intermediate
  pacing. Repeat strict selection, identity, and fresh-frame observations.
- [x] Keep invalidation on broken links or incomplete/exceptional scans.
  Preserve fresh full uniqueness on final proof retries; reject duplicate
  panels, target loss, PID reuse, transfer, and deadline overruns.
- [x] Pass focused/full checks and independent SPEC then QUALITY reviews.
- [x] Resolve the separate virtualized-selection evidence limitation, then
  verify actual untraced navigation and full committed acceptance.

### Observe held movement before subsequent collection

The failed coherence diagnostic delayed its first movement observation
until three subsequent collection sequences. The native table is virtualized;
its later missing selection does not identify the state at release. Preserve
the failed capture and avoid attributing its cause without evidence.

- [x] Reproduce the observation ordering, then read signed movement just
  after release and before sequence waiting. Keep the publication observer
  active across both checks and retain the exact observed process identity.
- [x] Preserve all movement/freshness budgets, three fresh sequences, exact
  64-key burst count and expected endpoint acknowledgement. Test failures
  as well as ordering and finish independent SPEC then QUALITY review.
- [x] Run fresh untraced native and full committed acceptance.

### Prove selection state at the correct boundary

The virtualized native tree cannot prove automatic model clearing. The
superseding decision `recover-native-navigation-without-claiming-model-selection-evidence`
keeps explicit Home/End recovery and all existing rejection/budget rules.

- [x] Correct reconciliation comments to state the actual visible-row
  observation. Add a GPUI integration regression through accept_snapshot
  proving selection remains on identity through reordering and clears on
  removal and PID reuse before further input.
- [x] Make the selected-child exit check reject another instantiated
  selected identity during its existing strict current-tree proof, before
  further input and within the original five-second deadline. Test this
  rejection without treating unrendered rows as observed.
- [x] Run relevant Python/Rust checks and independent SPEC then QUALITY review.
- [x] Run fresh untraced native and full committed acceptance.

### Require current panel membership for native exit

Independent review reproduced false success from a live detached cached
panel while the current panel still contained the child. See the recorded
`prove-process-exit-in-the-current-native-panel` decision.

- [x] Reproduce that false pass, replace cached-panel trust with fresh
  navigation_panel discovery on each attempt, and validate its current
  membership after complete strict scanning. Reuse established helpers.
- [x] Test detachment, replacement during scanning, duplicate panels, and
  incomplete membership under the original five-second deadline. Preserve
  newer child-free snapshots and visible-transfer rejection.
- [x] Pass focused/full checks and independent SPEC then QUALITY review.
- [x] Run fresh untraced native and full committed acceptance.

### Retain both existing input sequence observations

The focused run reached the exact burst endpoint but lost the third main
reader observation when it stopped the independent watcher. This correction
completes the existing held-observation plan without changing its bounds.

- [x] Record each existing Native.sequences observation's age at read time.
  Append its actual sequence/age records to the input evidence before
  watcher shutdown; retain every watcher record and error.
- [x] Reproduce the watcher-misses-third race and reject watcher errors
  after merging. Preserve three actual distinct sequences, freshness,
  original reads/wait, and all non-input sequences callers. Complete
  focused/full checks and independent SPEC then QUALITY review.
- [x] Run fresh untraced native and full committed acceptance.

### Reveal an endpoint displaced by collection

Independent contract review approved the bounded observation recovery in
`reveal-a-navigation-endpoint-shifted-outside-native-visibility`. This is
not a demonstrated cause-specific fix for the old timeout; diagnostic
visibility retries recovered and the separate freshness limit still holds.

- [x] Retain immutable expected PID/start and its key-issue snapshot index.
  Permit recovery only with fresh coherent/current complete evidence: no
  selected row, expected outside the instantiated span, changed index, and
  the original numeric endpoint index inside that span. Map identities into
  that same snapshot; ambiguous or incomplete evidence is ineligible.
- [x] Reveal with nonselecting vertical scrolling inside the clipped
  Processes viewport and then prove the exact selected endpoint afresh.
  Keep original deadlines, independent metric proof, production behavior,
  and held-input movement untouched. Record the recovery honestly.
- [x] Reproduce bounded recovery and reject invalid eligibility, visible
  unselected endpoints, foreign selection, identity loss/reuse, stale or
  incomplete membership, and deadline exhaustion. Pass focused/full checks
  and independent SPEC then QUALITY review.
- [x] Run fresh untraced native and full committed acceptance.

### Retain the issued endpoint through final navigation proof

The [fresh final-confirmation failure](../execution/real-system-readings/native-final-selection-failure.md)
retains a one-row displacement after intermediate exact-target acknowledgement.
The final proof omits the issued endpoint index required by the existing
navigation recovery decision. This correction completes that decision.

- [x] Pass the existing immutable endpoint_index into final navigation proof.
  Preserve fresh_panel, reconciliation, the existing batch deadline, every
  recovery guard, and current final-frame inspection acknowledgement.
- [x] Reproduce displacement between intermediate and final acknowledgement.
  Verify index provenance, unchanged-index/original-slot-outside-span
  rejection, and fresh uniqueness after final-proof retries. Run focused/full
  checks and independent SPEC then QUALITY reviews.
- [x] Run fresh untraced native process and full committed acceptance.

### Distinguish interrupted pending batches from successful endpoints

The [pending-endpoint failure](../execution/real-system-readings/native-pending-endpoint-failure.md)
and [independent assessments](../execution/real-system-readings/native-pending-endpoint-review.md)
support the new Judged decision recover-a-pending-navigation-batch-after-proven-endpoint-exit.
The old capture stays failed; the new protocol is prospective.

- [x] Reproduce disappearance after issuing an intermediate arrow batch but
  before acknowledgement, and the false acknowledgement/crash from a flag-only
  shortcut. Keep the exact controlled target and recovery endpoint mandatory.
- [x] Observe the eligible expected PID/start independently before dispatch,
  retaining raw stat, source, parsed identity and monotonic query window.
  Predispatch disappearance sends no keys and replans within the same remaining
  deadline; malformed/permission/PID-reuse evidence fails. Reuse stat-only
  observation/parser helpers and preserve generic process reads.
- [x] Add an explicit interrupted/unverified outcome only after fresh coherent
  complete strict unique/current native evidence, no instantiated selection,
  expected snapshot absence, surviving controlled identity, and independent
  terminal ENOENT/ESRCH. Retain before/terminal and frozen issue evidence;
  revalidate publication/membership after terminal observation. Never turn
  absence into selected acknowledgement or model-clear evidence, including
  existing post-ack absence journals. Keep other wait callers unchanged.
- [x] Recover physically with Home/End and exact new endpoint proof under the
  SAME remaining eight-second batch and 180-second total deadlines. Do not
  recursively excuse recovery loss, reset time during replanning/interruption,
  or dispatch after evidence journaling exhausts the deadline. Retain final
  target/inspection/metric/exit proof and held-input evidence unchanged.
- [x] Test live endpoint omission, PID reuse, missing/wrong identity baseline,
  permissions, malformed/reversed windows, target loss, selected competitors,
  stale/incomplete/detached/duplicate trees, before-dispatch disappearance,
  late journaling, budget exhaustion and failed recovery acknowledgement.
  Run focused/full checks, then independent SPEC and QUALITY reviews.
- [x] Run fresh untraced native process and committed aggregate acceptance;
  retain actual observation costs and every interrupted batch as unverified.

### Retain freshness read identity and timing

Independent review found the latest failure cannot distinguish delayed
publication from a read of the superseded inode. The current frame method
fails immediately and has no caller-deadline argument. Preserve that
verdict; do not add a freshness retry or wait based on this evidence.

- [x] Retain read start, read/parse completion, and age-check times, the
  opened file's fstat identity, and pathname identity immediately before
  age validation. Save these with the existing stale-frame evidence and
  its sequence/acceptance/age metadata. No added frame read or wait.
- [x] Verify timing/order and unchanged freshness failures, including an
  atomic replacement fixture. Metadata failures must not replace the
  original verdict. Run focused/full checks and independent reviews.
- [x] Use the next actual failure, if any, to distinguish the observation
  cases. Full capture 78w90voc proves replacement during the read and short
  parsing; publication stage latency remains unmeasured. No prior false
  verdict or specific publication stall is claimed.

### Reveal the acknowledged child during later cell inspection

The [fresh failure](../execution/real-system-readings/native-cell-displacement-failure.md)
retains the same child identity one row above the viewport after successful
navigation and column 3 comparison. The separately recorded decision
`reveal-an-acknowledged-process-shifted-during-cell-inspection` permits
bounded nonselecting inspection preparation, not product viewport anchoring.

- [x] Capture explicit caller-owned target acknowledgement evidence from
  the existing coherent final navigation proof. Seed the positive observation
  there; update it only after successful metric verification, and freeze it
  during each inspection. Distinguish its index from a key-issued endpoint.
- [x] Add opt-in missing-row preparation to controlled-child lookup paths.
  Non-strict lookup absence only triggers independent strict, coherent,
  unique eligibility. Reuse bounded vertical recovery and exact selected
  proof, then repeat normal cell lookup and all metric comparisons. Keep
  generic callers and held input unchanged. Share the original 15-second
  initial-discovery and five-second gesture/reacquisition deadlines.
- [x] After the existing three-sequence wait, use the same inspection-owned
  strict exact-selection proof before child shutdown, with the frozen last
  successful metric reference and existing five-second deadline. Reproduce
  detached-cache false acknowledgement and displaced-row timeout. Preserve
  generic/held acknowledgement, stop_child, and the strict exit check.
- [x] Reproduce the one-row displacement and reject missing/wrong prior
  acknowledgement, unchanged indices, reference slot outside span, selected
  competitors, instantiated unselected target, identity loss/reuse, stale or
  incomplete membership, provisional permission reuse, and late dispatch.
  Prove successful metrics alone advance the inspection reference. Run
  focused/full checks, then independent SPEC and QUALITY reviews.
- [x] Run fresh untraced process acceptance and full committed acceptance.

### Trace diagnostic publication stages without changing acceptance

The [independent investigation](../execution/real-system-readings/native-full-stale-frame-review.md)
identifies missing downstream timing after a retained stale old-inode read.
The failed aggregate remains failed. This is diagnostic instrumentation.

- [x] Add opt-in timing in the existing diagnostic writer: bounded clock and
  memory bookkeeping around acceptance/model/record construction, submission,
  dequeue, JSON conversion/serialization, temporary write and rename. Correlate
  app/session, sequence/revision and original acceptance time. Document monotonic
  clock identity and bounded wall-clock anchors; do not compare unrelated clocks.
- [x] Keep a fixed-capacity history (at most 64 records) with bounded fields,
  overwritten-record counts and partial stage failures. Retain byte count,
  temporary device/inode and rename start/completion. Publish its optional
  sidecar only on the existing worker, with no new UI filesystem I/O, fsync,
  thread, polling loop or unbounded queue. Trace errors are distinct and never
  replace primary publication errors. Preserve atomic replacement and cleanup.
- [x] Retain trace artifacts through the existing native harness only when
  explicitly enabled. Mark instrumented metadata and reject traced sessions as
  final aggregate acceptance. Keep Native.frame's single read, fail-fast age
  check, PID checks, all deadlines and every mandatory native proof unchanged.
- [x] Reproduce stage-order, bounded-history, overwritten-record, disabled-path,
  failure/cleanup/error precedence and traced-acceptance rejection cases. Run
  relevant Python/Rust checks, formatting and strict Clippy, then independent
  SPEC and QUALITY review. No source performance remedy is inferred yet.
- [x] Run one instrumented diagnostic, preserve all outcomes, and identify the
  observed delay only to the extent recorded timings support. Record any remedy
    separately; fresh untraced full acceptance and final review remain required.

The [instrumented capture](../execution/real-system-readings/native-publication-diagnostic-failure.md)
failed on an intermediate navigation deadline. Its retained publication stages
do not explain the earlier stale frame; no performance remedy is inferred.
Navigation diagnosis and fresh untraced full acceptance remain open.

### Retain bounded navigation observation failures

The [independent traced-failure review](../execution/real-system-readings/native-publication-navigation-review.md)
cannot distinguish competing selection, incomplete discovery and changing
publication brackets from the current artifacts. This is observation work only.

- [x] Add a fixed-capacity history of at most 64 navigation observations, scoped
  to the active navigation operation. Bound every retained field and collection;
  retain evicted/observed counts. Capture existing operation/phase, exact issued
  identity/index and original deadlines, monotonic start/end, discovery and scan
  durations, before/after publication, panel-validation outcome, native selected
  identity/count, partial/complete row scan and mapped span, and rejection reason.
  Null or missing means unobserved. Native selection is not model selection.
- [x] Observe existing reads and decisions without adding accessibility/procfs
  reads, snapshot copies, input, retry, sleep or policy changes. Add no success-path
  filesystem I/O, thread, polling loop, unbounded log or queue. Serialize bounded
  failure context through the existing failure artifact path; diagnostic errors
  must not replace the original failure. Do not retain accessible objects or full
  process lists in the history. Keep the current freshness and 8/180/5-second
  deadlines, exact successful acknowledgements, proven-exit requirements, all
  sixteen child metrics, controlled exit and held-input proofs unchanged.
- [x] Write failing tests for complete/rejected/partial observations, wrong or
  absent native selection, changing publication brackets, original exception and
  deadline preservation, bounded retention/fields and no added read/input calls.
  Verify relevant/full Python tests, scoped Ruff and documentation; commit and
  complete independent SPEC then QUALITY review. No Rust/product change is needed
  merely to observe existing native decisions.
- [x] Run one fresh focused native replay with publication tracing disabled,
  retain its outcome and new failure context if any. Record any evidence-supported
  remedy separately. Fresh full aggregate acceptance and final review remain open.

The [fresh untraced capture](../execution/real-system-readings/native-navigation-observation-stale-failure.md)
failed freshness before the next native scan. Its independent review supports
one combined diagnostic using the existing publication tracing switch and
navigation observations; it supports no behavior remedy.

- [x] Run the combined supporting diagnostic and retain its actual outcome.
  Fresh untraced full aggregate acceptance and final review remain required.

The [combined diagnostic](../execution/real-system-readings/native-combined-inspection-failure.md)
failed during visible-column-five inspection recovery, after thirteen child
metric artifacts. Publication tracing did not reproduce stale freshness. The
first recovery scroll used 3.337 seconds of the original five-second budget;
independent source review is checking repeated discovery before that input.

### Consolidate fresh missing-row inspection eligibility

The [independent review](../execution/real-system-readings/native-combined-inspection-review.md)
establishes that missing-row inspection repeats fresh strict uniqueness before
its first wheel. The [decision](../decisions/consolidate-fresh-missing-row-inspection-eligibility.md)
removes that inherited duplicate proof only from the explicit missing-row callback.
The failed capture does not quantify traversal cost or prove the timeout cause.

- [x] Let one fresh complete strict unique coherent inspection observation both
  establish all existing eligibility guards and dispatch the first nonselecting
  reveal. Keep final publication/membership/clipped-viewport checks and original
  post-journal dispatch deadlines. Rejection must discard provisional permission.
- [x] Retain separate fresh strict exact selected-child proof after the wheel,
  ordinary unique cell lookup and every metric/clipping comparison. Keep pre-exit,
  generic navigation, pending-exit recovery and held-input defaults unchanged.
- [x] Reproduce duplicate traversal with bounded simulated costs, and cover all
  guard, stale/partial/ambiguous/publication-change, rejection-reset, post-wheel
  proof and journal-expiry paths. Run focused/full Python tests, relevant Ruff,
  diff and documentation checks, then independent SPEC followed by QUALITY review.
- [x] Run one fresh untraced focused replay and preserve its actual outcome.
  Fresh full aggregate acceptance and final review remain required.

The [fresh untraced result](../execution/real-system-readings/native-inspection-eligibility-focused-result.md)
failed earlier in an intermediate arrow batch. Cell inspection was not reached.
Its retained observations identify the exactly prior acknowledged selection as
the permanent recovery-blocking trigger, followed by complete coherent absence
and endpoint reindexing. Independent review is evaluating a narrowly bounded
prior-acknowledgement case; no new behavior is implemented yet.

### Recognize prior selection during intermediate arrow observation

The [independent review](../execution/real-system-readings/native-prior-acknowledgement-review.md)
and [decision](../decisions/recognize-prior-selection-during-intermediate-arrow-observation.md)
distinguish only an initial exactly prior-ACK selection in the issued publication.
The failed capture proves blocked qualification, not successful recovery.

- [x] Capture bounded prior positive ACK identity/index/publication from the
  already returned coherent proof. Bind it to the frozen intermediate arrow
  envelope, unique issue-frame identities/indices, expected endpoint, direction,
  count and dispatch. Add no reads, full snapshot copies or native retention.
  Do not derive proof from diagnostic selection, observation history or journals.
- [x] Exempt only the initial prior-selection prefix in the same issued
  publication from setting a new block. Expire on coherent absence, another
  selection or publication advance. Missing evidence keeps old behavior;
  malformed/mismatched supplied evidence fails closed. Never clear an existing
  block or authorize input/ACK from an exempt observation.
- [x] Preserve permanent blocking for distinct competitors and instantiated
  unselected expected rows. Keep all fresh strict qualification and post-wheel
  exact proof, journal/input deadline checks, and default Home/End/reconcile/
  final-target/inspection/pre-exit/held behavior. Keep every mandatory comparison
  and controlled exit; do not infer hidden model selection.
- [x] Reproduce the retained prefix/absence/reindex sequence and test binding,
  prefix expiry, publication advance, hard-block, existing-block, wrong final
  selection and deadline cases. Run focused/full Python tests, relevant Ruff,
  whitespace/doc links, then independent SPEC followed by QUALITY review.
- [x] Run one fresh untraced focused replay and retain its actual outcome.
  Fresh full aggregate acceptance and final review remain required.

The [fresh untraced focused run](../execution/real-system-readings/native-prior-selection-focused-pass.md)
passed all sixteen child comparisons, controlled exit and held/exact-input checks.
It exercised inspection recovery under a fifteen-second discovery deadline, with
no intermediate navigation recovery event. Full committed acceptance remains open.

The [full committed aggregate](../execution/real-system-readings/native-prior-selection-full-failure.md)
passed 743 automated checks and host comparisons, then failed intermediate process
navigation after a prior-selection block. The independent diagnosis below supports
a bounded correction; fresh replay follows its implementation and reviews.

### Defer visible endpoint blocking during proven prior selection

The [read-only diagnosis](../execution/real-system-readings/native-prior-visible-endpoint-review.md)
and [Judged decision](../decisions/defer-visible-endpoint-blocking-during-proven-prior-selection.md)
identify an initial valid prior-selected prefix containing the unselected endpoint.

- [x] Reproduce that prefix before correction; defer only its new block whether
  expected is present or absent. Preserve proof binding, expiry, existing blocks,
  separate no-selection/visible-expected blocking and all later exact proof.
- [x] Cover success, persistent prefix, lost keys, expiry, malformed/missing proof,
  arbitrary selection, existing blocks, defaults and deadlines. Run focused/full
  Python, relevant Ruff, whitespace and documentation checks; SPEC then QUALITY.
- [x] Run one fresh untraced focused replay and full committed aggregate, preserving
  actual outcomes and all mandatory metrics/exit. Final adversarial review follows
  only when the full requirement set passes.

The [fresh focused run](../execution/real-system-readings/native-prior-visible-endpoint-focused-pass.md)
passed all sixteen child comparisons, verified exit and held/exact input. It
exercised inspection recovery under a fifteen-second discovery deadline, without
intermediate navigation recovery. Full committed acceptance remains in progress.

The [full committed aggregate](../execution/real-system-readings/final-acceptance-pass.md)
passed 745 tests and all host/native stages; actual Cairn receipts pass all thirteen
LIVE requirements. Earlier unchecked fresh focused/full verification items are
now satisfied by the retained current runs, not by reclassifying historical failures.
Final adversarial review passed and Cairn returned Done.
