# Intel and Apple GPU Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. One source implementer works at a time; independent specification review precedes independent quality review. Root orchestration may inspect sources and maintain execution documents alongside implementation.

**Goal:** Implement and verify [GPU-001 through GPU-009](../spec/gpu-collection.md) in the existing System Pulse application.

**Architecture:** Separate Intel Linux and Apple native adapters produce the current `MonitorDescriptor`, `SensorDescriptor`, `Reading` and `RawObservation` types. `HostCollector` invokes them from its existing worker; platform handles, baselines and retry state stay with that collector. Source records and tests establish quantity scope before the UI renders a value.

**Tech Stack:** Rust, Linux DRM/sysfs and PMU/device-query APIs, macOS IOReport/IOKit/SMC/HID, GPUI, Python acceptance and Cairn.

## Working state

- [x] Confirm the GPU contract and acceptance matrix with the developer.
- [x] Verify keyed SSH to the M1 Pro MacBook and clean user-authorized stale Cargo outputs.
- [x] Commit activation, source decision, plan and mechanism declaration; verify spec/link checks and the actual Cairn action (`66ea860f`).
- [ ] Implement and review Task 1: Intel Linux collection.
- [ ] Implement and review Task 2: Apple Silicon collection.
- [ ] Implement and review Task 3: memory semantics and integration.
- [ ] Implement and review Task 4: independent GPU acceptance.
- [ ] Run Task 5: actual native/aggregate evidence and final review.

Task 1, Intel Linux collection, is the single item currently in progress. A task remains open until its code and required verification/reviews are complete. Native hardware evidence is separate from deterministic adapter tests.

## Task 1: Intel Linux collection

**Own:** New `examples/system_pulse/collectors/src/intel/` modules and their tests; Linux hooks in `collectors/src/lib.rs` and `collectors/src/host/mod.rs`; focused host integration tests; collector dependencies/lockfile only when a required native interface needs them; Intel source/capability notes in `docs/execution/intel-and-apple-gpus/`.

**Preserve:** AMD dispatch and IDs, NVML behavior, process/network/volume collection, the existing snapshot JSON fields, and the single sampling service.

- [ ] Add this host-level discovery regression to `collectors/src/host/tests.rs`, using its existing `Fixture`, `HostCollector::rooted` and `collect_at` helpers, and run it before production edits:

```rust
#[test]
fn intel_pci_device_is_discovered_without_card_index_identity() {
    use std::os::unix::fs::symlink;
    let fixture = Fixture::new();
    fixture.base();
    let device = "sys/devices/pci0000:00/0000:00:02.0";
    fixture.put(&format!("{device}/vendor"), "0x8086\n");
    fixture.put(&format!("{device}/device"), "0x46a6\n");
    fixture.put(
        &format!("{device}/uevent"),
        "DRIVER=i915\nPCI_SLOT_NAME=0000:00:02.0\n",
    );
    fixture.put("sys/bus/pci/drivers/i915/fixture-marker", "");
    symlink(
        fixture.0.join("sys/bus/pci/drivers/i915"),
        fixture.0.join(format!("{device}/driver")),
    ).unwrap();
    fs::create_dir_all(fixture.0.join("sys/class/drm/card7")).unwrap();
    symlink(
        fixture.0.join(device),
        fixture.0.join("sys/class/drm/card7/device"),
    ).unwrap();
    let snapshot = HostCollector::rooted(fixture.0.clone()).collect_at(1);
    assert_eq!(
        snapshot.monitors.iter().filter(|monitor| monitor.kind == MonitorKind::Gpu)
            .map(|monitor| monitor.id.as_str()).collect::<Vec<_>>(),
        vec!["intel-pci:0000:00:02.0"],
    );
}
```

```sh
rtk cargo test --locked -p system-pulse-collectors --lib host::tests::intel_pci_device_is_discovered_without_card_index_identity -- --exact
```

Expected baseline: the assertion fails because the Intel monitor is absent; exactly one test executes.

- [ ] Implement PCI-backed discovery for both drivers. Deduplicate card/render nodes by canonical physical device, preserve nonsequential GT/region identities, and keep the monitor present when an optional field fails. Do not infer integrated/discrete classification from VGA class, card number or a marketing-name table.
- [ ] Read actual/requested i915 and xe GT frequencies separately. Retain source MHz integers and convert to hertz. Enumerate attributable hwmon temperatures, power/energy and fan readings with their original labels and units; do not relabel package sensors as GPU-die readings.
- [ ] Add bounded read-only i915/xe device-query decoding for memory regions and topology. Check returned buffer sizes, counts, reserved/layout requirements and each API return before dereferencing. Device-local memory used/total needs valid permission semantics; integrated system-region totals do not become GPU allocation.
- [ ] Add documented whole-device/engine counter sampling where exposed. Retain previous/current raw counters and query windows, invalidate on failed reads or reset, normalize engine groups by their evidenced capacity and retain exact scope. Avoid duplicate-client accumulation or frequency-as-usage fallbacks. Record inaccessible PMU permissions and unsupported interfaces independently from missing implementation.
- [ ] Add the complete Intel cases from the [acceptance matrix](intel-and-apple-gpu-acceptance.md). Include reordered same-name devices, aliases, multiple GTs/regions, permission errors, malformed responses, failed recovery and nonuniform intervals. Each new behavior gets an observed failing test before its implementation.
- [ ] Run the collector suite, collector formatting and strict Clippy. Commit the implementation and source/capability record with exact paths; retain commands and actual counts.
- [ ] Obtain independent specification review for GPU-001/002/004/006/007 and this task boundary, then independent quality review. Resolve findings through the same implementer before closure. Do not claim Intel hardware acceptance from fixtures or the AMD development host.

## Task 2: Apple Silicon collection

**Own:** New `collectors/src/apple/` modules and native binding boundary, target-specific dependencies, `host/mod.rs` Apple hook, focused tests, and the minimal service-bound correction described below if needed.

- [ ] Before selecting a dependency or copying bindings, record the exact native source/channel/key, ownership rule and unit for every field using the supplied macmon/HardwareVisualizer references and a read-only M1 Pro source probe. Preserve notices for adapted source. Exclude CLI monitoring wrappers and the reference programs' network calls from production collection.
- [ ] Write pure conversion/failure tests on Linux before the native implementation. Required arithmetic examples: 250 inactive + 750 active residency gives 75% activity; equal active residency at 400 MHz and 800 MHz gives 600 MHz active-weighted frequency; 3 joules over 1.5 measured seconds gives 2 watts. A missing channel, unknown state mapping, failed baseline or nonpositive elapsed time yields no measured value.
- [ ] Implement native enumeration and identity association. Join optional accelerator memory to the same physical GPU; do not select the first/last arbitrary registry record. Capture native memory-model facts where available. A device name or a runtime enumeration index is not a persistence identity.
- [ ] Own IOReport sample handles and their raw start/end observations. Validate channel presence, format, unit and performance-state mapping; release Core Foundation/IOKit objects on success and every failure path. Treat SMC and HID as independent optional temperature sources. A missing GPU-attributable fan has an explicit source limitation.
- [ ] Keep native handles on the existing sampling worker. `SamplingService::spawn` currently requires `C: Send` even though `C` is created and consumed inside that worker. If native handles are not `Send`, remove only that unnecessary bound and add a worker-ownership regression using an `Rc` created by the factory; do not invent an unsafe `Send` implementation or another polling thread.
- [ ] Run pure tests locally and compile/run the actual collector on the authorized arm64 MacBook. Transfer only task-owned source into a dedicated validation directory, preserve source/lockfile hashes, and retain command logs. Native compilation failure is unfinished implementation.
- [ ] Obtain independent specification and then quality review; close all findings before moving on.

## Task 3: Memory semantics and integration

**Own:** `examples/system_pulse/src/live.rs`, existing meter/formatter code, model presentation/persistence tests, and additive collector metadata only if the current source/scope fields cannot express a required fact.

- [ ] Add failing tests for shared GPU allocation without a capacity total, dedicated VRAM with a valid total, and rejected system-RAM/process-footprint substitutions. Assert both the physical quantity and visible label; a string-only test is insufficient.
- [ ] Map byte-valued shared allocations through the existing scalar/counter-compatible meters. Capacity rendering requires a valid known total. Keep historical AMD/NVIDIA IDs and saved presentation choices unchanged.
- [ ] Extend discovery/restoration cases with Intel and Apple metadata, mixed vendors, absent/reappearing devices and same-name devices. Inject stale and failed readings to prove that a fresh snapshot cannot refresh an old native value as current.
- [ ] Run collector, model and app tests and affected formatting/Clippy checks. Review specification compliance first, then quality, before committing task closure.

## Task 4: Independent GPU acceptance

**Own:** `scripts/system-pulse/gpu_verify.py`, bounded native/raw capture helpers, verifier tests, and `.cairn/mechanisms/gpu-acceptance`.

- [ ] Write negative verifier tests first: absent hardware report, empty selected test suite, wrong binary/source/device identity, wrong unit, changed interval, incorrect memory scope, missing required field, stale observation and unexplained native mismatch must all prevent pass.
- [ ] Reuse existing runner log/hash/timeout and nonempty-test validation where appropriate. Run the full collector/model/app and existing preservation checks; retain all logs outside the source checkout. Report GPU-001 through GPU-009 independently using Cairn's per-requirement result protocol.
- [ ] Capture raw source operands independently of the production conversion functions. Native reports declare the physical device, supported field set, exact formulas, source precision and comparison windows before measuring. Missing Intel integrated/discrete or Apple evidence yields unverified for the corresponding hardware requirement.
- [ ] Add a bounded task-owned Metal workload for the Mac if needed to exercise activity/power/frequency. Record its process identity and cleanup. Establish actual native desktop observation; SSH launch alone and diagnostic-frame publication alone are insufficient proof of visible labels/interactions.
- [ ] Run verifier tests and independently review the mechanism before trusting its pass outcomes. A missing acceptance entry point is unfinished work, never a passing declaration.

## Task 5: Committed acceptance and closure

- [ ] Commit reviewed implementation and remove its in-progress marker; update the source decision's single `Realized by` entry with the actual resolving commit and exact subject.
- [ ] Run `cairn wake` and the named committed mechanism. Preserve failed attempts. Fix evidence failures at their cause without relaxing coverage or comparison bounds.
- [ ] Obtain actual Intel integrated Linux, Intel discrete Linux and Apple Silicon reports, plus the complete Linux preservation replay. If a required host is unavailable, record that exact external dependency; the commitment stays incomplete.
- [ ] Complete a final independent adversarial review in `.cairn/reviews/intel-and-apple-gpus.md`, recording attacks and findings before any fixes. Complete the production self-audit and documentation checks.
- [ ] Claim completion only after actual `cairn wake` returns Done. Stop the task-owned Mac caffeinate assertion and clean up task-owned workloads. No merge, push or deployment is part of this plan.
