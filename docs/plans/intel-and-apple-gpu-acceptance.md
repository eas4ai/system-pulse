# Intel and Apple GPU acceptance plan

Status: Agreed acceptance contract 2026-09-06. The [implementation plan](intel-and-apple-gpus.md) assigns executable source tasks.

**Goal:** Prove the [GPU contract](../spec/gpu-collection.md) while preserving completed real-collection behavior.

**Architecture:** Each platform adapter supplies the existing owned descriptors/readings to `HostCollector`. OS handles and sampling baselines remain on its current background worker. Raw values and explicit failure states cross the adapter boundary; UI formatting never infers missing hardware facts.

**Tech stack:** Rust collector/model/app crates, Linux DRM/sysfs and supported counter APIs, native macOS IOReport/IOKit/SMC/HID, existing GPUI workspace, Python acceptance harness and Cairn receipts.

## Preparation and activation

- [x] Inspect existing collector boundaries and supplied reference implementations; verify findings against source.
- [x] Reach the authorized MacBook and inspect hardware/build-tool availability without modifying it.
- [x] Confirm GPU-001 through GPU-009 and their falsifiers.
- [x] Record the reviewed backend/source decisions, write the executable implementation plan and mechanism declarations, then move the roadmap's Current line to `intel-and-apple-gpus`.

Preparation and activation were completed on 2026-09-06 in commit `66ea860f`. Intel Linux implementation and focused tests are in progress. Read-only [Apple source probes](../execution/intel-and-apple-gpus/apple-source-probe.md) establish source availability; they do not establish production collector accuracy or native acceptance.

## Implementation sequence and owners

| Stage | Files/responsibility | Required proof before closure |
| --- | --- | --- |
| Contract and sources | `docs/spec/gpu-collection.md`, cited source matrix and decision records | Every required field has a source or an explicit attribution question; no unsupported approximation is specified as measurement |
| Intel adapter | Proposed `collectors/src/intel/` modules, `host/mod.rs`, Linux device dispatch and focused tests | Failing regression first; integrated/discrete and i915/xe inputs; independent spec and quality reviews |
| Apple adapter | Proposed `collectors/src/apple/` modules, target-specific dependencies, native binding boundary and focused tests | Pure arithmetic/failure tests on Linux; actual arm64 macOS compilation and collector execution; independent reviews |
| UI and persistence | `collectors/src/types.rs` only if metadata cannot be represented already; existing `src/live.rs`, model/formatters and tests | Shared-memory labels, unknown capacity totals, stable restoration, current/stale semantics and mixed-vendor snapshots |
| Acceptance | Proposed `scripts/system-pulse/gpu_verify.py`, host probes and negative tests | Each GPU requirement receives its own evidence outcome; every absent mandatory comparison is rejected |
| Completion | Execution reports, `.cairn/reviews/intel-and-apple-gpus.md`, roadmap | Native hardware matrix, preserved Linux acceptance, closed reviews and actual Cairn Done |

The executable implementation plan assigns the module owners and review order. Its working-state list tracks code and verification progress; this table defines the acceptance boundaries.

## Deterministic falsifier cases

| Group | Required cases | Requirements |
| --- | --- | --- |
| Discovery | Reordered devices; same-name devices; duplicate card/render nodes; driver-node changes; missing stable identity; absent/reappearing device; mixed AMD/NVIDIA/Intel | GPU-001, GPU-007 |
| Intel source boundary | i915 and xe; integrated and local-memory devices; multiple GTs/regions; actual versus requested clock; permission denial; unsupported ioctl/API; malformed/truncated response; changed topology | GPU-002, GPU-004 |
| Apple source boundary | Missing/renamed IOReport channel; unknown state/table pairing; optional SMC failure with valid HID result; absent accelerator memory dictionary; multiple registry candidates; retry after initialization failure | GPU-003, GPU-006 |
| Arithmetic | Unequal intervals; real elapsed versus requested delay; first observation; zero elapsed; decreased counters; failed intermediate sample; integer overflow; non-finite values; source-unit mismatch | GPU-004 |
| Memory | Dedicated VRAM used/total; shared allocation with no total; system RAM rejected as GPU allocation; process footprint rejected as GPU-only bytes; used greater than total; missing total | GPU-005 |
| Service/presentation | Slow capture; interval changes; shutdown; device churn; one-slot backpressure; independent field failure; stale input; restored hidden/collapsed sensors | GPU-006, GPU-007 |
| Verifier | Wrong physical device; wrong source/binary hash; changed unit/denominator; altered elapsed time; stale observation; missing field/host; absent test selection; unsupported result presented as pass | GPU-008, GPU-009 |

The new verifier must include independent arithmetic expectations and intentionally corrupted evidence. Calling the production conversion function from an expected-value assertion is not independent verification.

## Native hardware matrix

| Target | Access now | Planned observations |
| --- | --- | --- |
| Apple Silicon | Keyed SSH to developer's M1 Pro MacBook; macOS 26.6.1, Rust 1.97.1, Xcode present; 16 GiB RAM | Inventory, independent raw observations, controlled Metal load, recovery, actual app labels/interactions and cleanup |
| Intel integrated Linux | Pending tablet model and Linux availability | PCI/driver inventory, source permissions, idle/load intervals, memory scope, actual app labels and recovery |
| Intel discrete Linux | No target identified yet | Device-local memory, GT/engine attribution, idle/load intervals, actual app labels and recovery |
| Intel Windows follow-on | Developer has offered a tablet PC | Separate Windows contract and evidence after hardware details/access are available |

The Mac had approximately 7.8 GB free during preflight. After the developer freed space and authorized stale Cargo-target cleanup, 23 verified build trees were cleaned, with three source archives preserved and approximately 169.6 GB free. Source manifests were unchanged and an independent path check verified the result. Start with a collector-only build in a dedicated validation directory and recheck space before a full GPUI build. Do not remove unrelated files or build caches to make room. Build/test sources and artifacts retain exact hashes. Remote commands need bounded execution and cleanup of only task-owned workloads.

Before each native capture, declare device/field coverage, formulas, sampling windows, source precision and comparison bounds. Compare the native view against the consumed collector snapshot and independent source readings. Record permission/API limits and failed attempts rather than weakening bounds after capture.

## Commands and evidence status

Existing focused commands to run during implementation:

```sh
rtk cargo test --locked -p system-pulse-collectors
rtk cargo test --locked -p system-pulse-model
rtk cargo test --locked -p system-pulse --lib
rtk cargo clippy --locked -p system-pulse-collectors --all-targets -- -D warnings
rtk cargo fmt -p system-pulse-collectors -p system-pulse-model -p system-pulse -- --check
```

Existing complete Linux preservation command:

```sh
rtk proxy python3 scripts/system-pulse/verify.py
```

The GPU mechanism declaration names the planned aggregate entry point. That declaration is not executable proof: its implementation and successful committed execution are still required. Missing GPU checks are unfinished work. No command above was run as part of specification preparation; implementation reports record subsequent test runs. The previous LIVE pass is historical preservation evidence, not proof of these new adapters.
