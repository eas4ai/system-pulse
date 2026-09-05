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

- [ ] Write a failing regression proving that one shared snapshot observation preserves interface/local-address ownership and TCP4/TCP6 local-address/state inputs, with source query windows and actual errors. Preserve raw local-address/state tokens before filtering so independent Python code can challenge byte order, established-state selection, mapped IPv6, wildcard exclusion and distinct-interface ownership. Omit ports, remote endpoints and socket owners.
- [ ] Add an optional defaulted snapshot field for the shared observation. Derive per-interface connection counts from those captured inputs without duplicating the tables in each reading. Preserve unavailable/failed semantics; no fake zero on input failure. Verify serialization and full app/model compatibility. Correct the README's overly broad passwd-lookup failure claim or implement the promised distinction; a truthful numeric UID fallback is acceptable when described accurately.
- [ ] Run focused regression, collector tests, formatting, strict Clippy and integration checks; commit only owned files. Independent spec then quality reviews must pass before Task 3 implementation.

## Task 3: Executable independent host and native acceptance

Create `scripts/system-pulse/acceptance.py`, `host_accuracy.py`, `test_host_accuracy.py`, and a tracked native driver/replay. Extend existing `verify.py` so its source guard is only one step in the full mandatory acceptance run. Evidence goes in `docs/execution/real-system-readings/`; large runtime artifacts may be external with precise hashes/paths. No unavailable test or missing adapter is a passing check.

### Predeclared comparison rules

Static device IDs, units, total quantities and formulas compare exactly to the same source observation. CPU = 100 * delta(total - idle - iowait) / delta(total), with guest fields excluded from total; process CPU uses one logical core's elapsed ticks as denominator. RAM used = MemTotal - MemAvailable, KiB times 1024. Network and disk rates recompute exact integer counter differences over each recorded monotonic observation interval. Read/write sectors multiply by 512. Disk latency is weighted completed-operation time / completed operations, unavailable at zero operations. AMD conversion divides temperature by 1000, power by 1,000,000; frequency is retained in Hz. NVML units are defined in its adapter tests and source metadata; fan percent remains percent.

Independent samples bracket each collector observation. For monotonic cumulative counters, the collector raw counter must lie within independent before/after counters. For memory and instantaneous GPU gauges, verify exact captured raw observations, parsing and conversions, then exact rendering of the consumed snapshot. Independent contemporaneous gauge samples provide supporting observations, not proof of equality at a different instant; never invent a percentage tolerance. Derived arithmetic is separately checked exactly from raw inputs. Capture source path, identity, monotonic times, raw values and bound before judging the output. Compare native formatted values to the snapshot at their capture sequence/age, allowing only documented rounding and explicitly captured later snapshots. Bind displayed snapshot identity to opt-in bounded diagnostic evidence of consumed snapshots, serialized off the UI path, and give metric text a natural-language accessible label identical to its visible formatted value. See ../execution/real-system-readings/verification-design.md.

- [ ] Write verifier regressions before implementation. Mutated byte unit (1000 versus 1024), CPU normalization, elapsed interval and out-of-bound gauge each fail; correct known observations pass. A capability missing any accessible required field fails. NVIDIA absence is recorded separately from adapter tests; it never produces a hardware-accuracy pass.
- [ ] Implement host capture and comparison using Python standard library proc/sysfs readers independent of Rust collector logic. Launch and exit a harmless named child and verify its real PID/identity appears/disappears in snapshots and the actual native Processes table. Record every required field's actual backend and permission/attribution limits.
- [ ] Reuse the proven private Xvfb/DBus/AT-SPI harness from the design repository artifact. Native replay proves no fixture controls/tabs, live numeric values, collapsed panel and sensor summaries/history, both-axis overflow, independent collapse, focus and keyboard navigation, mixed-state persistence and recovery while sampling continues.
- [ ] Make aggregate verification run collector/model/app tests, affected base dock/resizable and UI dock suites, vendored accessibility regression tests, formatting, strict Clippy, native build, verifier regressions, host capability/accuracy checks and native replay. Require nonzero test counts and fail on missing artifacts or steps.
- [ ] Commit the reviewed candidate before `rtk proxy cairn check`. Preserve baseline failing receipts. Fix any new finding with focused checks before rerunning the aggregate. Record a final independent adversarial review against the candidate and require `cairn wake` Done. Update glossary/recon/handoff to distinguish new observed live behavior from historical fixture evidence. Keep the feature branch/worktree; do not merge or push without instruction.

## Coverage self-review

Task 1 implements LIVE-002/004/006/008/009/012 and the explicit NVIDIA addition. Task 2 implements LIVE-001/003/005/007/010/011 and preserves Task 1 semantics at the UI boundary. Task 3 independently challenges every falsifier, including LIVE-013. Native NVIDIA and macOS/Windows evidence remain named limitations; accessible Linux measurements and the NVIDIA adapter itself cannot be deferred.
