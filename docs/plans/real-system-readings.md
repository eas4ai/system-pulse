# Real System Readings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Replace runtime simulation with accurately attributed host readings while preserving the approved workspace.

**Architecture:** A pure collector crate produces immutable, typed snapshots. One background sampling service owns OS handles and counter baselines and exposes only its latest result. GPUI applies snapshots, retains presentation by stable identity, and renders physical quantities; deterministic injection is test-only.

**Tech Stack:** Rust 2024, pinned sysinfo 0.37.2, serde/serde_json, Linux procfs/sysfs, runtime-loaded NVIDIA NVML, existing GPUI/gpui-component.

The contract is [LIVE-001–013](../spec/live-collection.md). NVIDIA support was explicitly added by the developer; live NVIDIA hardware verification is unavailable on this AMD host and must remain labeled as such. Use this tracked plan directory because this source repository ignores docs/superpowers. The earlier fixture acceptance is a preservation baseline, not live accuracy evidence.

## Ownership and sequencing

Only one source implementer works at a time. Give each fresh implementer its full task and relevant interfaces. Every implementation receives independent spec review followed by independent quality review; resolve findings before the next source task. Root may investigate host measurements and prepare evidence alongside an implementer. Preserve the existing reference example and framework patches.

- Collector worker: `examples/system_pulse/collectors/`, workspace membership and lockfile.
- Integration worker: `examples/system_pulse/src/`, `examples/system_pulse/model/`, app manifest and lockfile changes needed for its collector dependency.
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

Read-only acceptance preparation found that connection readings preserve only the derived count. Before building the independent verifier, the collector worker owns a focused follow-up in `examples/system_pulse/collectors/`; first finish Task 2's spec and quality reviews. This is required evidence for the existing LIVE-013 contract, not new product scope.

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

- [ ] Write verifier regressions before implementation. Mutated byte unit (1000 versus 1024), CPU normalization, elapsed interval and out-of-bound gauge each fail; correct known observations pass. A capability missing any accessible required field fails. NVIDIA absence is recorded separately from adapter tests; it never produces a hardware-accuracy pass.
- [ ] Implement host capture and comparison using Python standard library proc/sysfs readers independent of Rust collector logic. Launch and exit a harmless named child and verify its real PID/identity appears/disappears in snapshots and the actual native Processes table. Record every required field's actual backend and permission/attribution limits.
- [ ] Reuse the proven private Xvfb/DBus/AT-SPI harness from the design repository artifact. Native replay proves no fixture controls/tabs, live numeric values, collapsed panel and sensor summaries/history, both-axis overflow, independent collapse, focus and keyboard navigation, mixed-state persistence and recovery while sampling continues.
- [ ] Make aggregate verification run collector/model/app tests, affected base dock/resizable and UI dock suites, vendored accessibility regression tests, formatting, strict Clippy, native build, verifier regressions, host capability/accuracy checks and native replay. Require nonzero test counts and fail on missing artifacts or steps.
- [ ] Commit the reviewed candidate before `rtk proxy cairn check`. Preserve baseline failing receipts. Fix any new finding with focused checks before rerunning the aggregate. Record a final independent adversarial review against the candidate and require `cairn wake` Done. Update glossary/recon/handoff to distinguish new observed live behavior from historical fixture evidence. Keep the feature branch/worktree; do not merge or push without instruction.

## Coverage self-review

Task 1 implements LIVE-002/004/006/008/009/012 and the explicit NVIDIA addition. Task 2 implements LIVE-001/003/005/007/010/011 and preserves Task 1 semantics at the UI boundary. Task 3 independently challenges every falsifier, including LIVE-013. Native NVIDIA and macOS/Windows evidence remain named limitations; accessible Linux measurements and the NVIDIA adapter itself cannot be deferred.


### Scope native process cell rediscovery

Aggregate `098d2b2e` passed host verification and 481 tests, then a direct
process cell lookup fell back to a full application traversal and ignored
the caller's five-second deadline. The app continued accepting fresh samples.
See [the diagnosis](../execution/real-system-readings/native-cell-discovery-failure.md)
and [decision](../decisions/scope-process-cell-discovery-to-its-native-row.md).

- [ ] Extract the existing metric process-row lookup for shared use by cell
  visibility navigation. Carry the original absolute deadline through row
  reacquisition, cell discovery, and movement. Preserve identity, uniqueness,
  node bounds, generic lookup, strict exit traversal, and all comparisons.
- [ ] Test stale cells and rows, unrelated branches, duplicate and missing
  cells, PID reuse, and exhaustion of the original deadline. Verify the actual
  replay call boundary, then pass independent SPEC and QUALITY reviews.
- [ ] Run focused native process acceptance and fresh committed aggregate
  acceptance. Preserve failed receipts; final review remains pending.
