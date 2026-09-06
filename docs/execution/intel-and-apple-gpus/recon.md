# GPU iteration recon and draft review

Status: Observed 2026-09-06

The developer supplied qmassa, macmon, hw-smi, HardwareVisualizer and gptop snapshots to inform Intel integrated/discrete and Apple GPU support, then approved preparing the next iteration. This recon covers that change's collector, reading, persistence and verification boundaries.

## Existing implementation

| Finding | Evidence | Implication |
| --- | --- | --- |
| The previous collection commitment is complete | [Completion and actual Cairn verdict](../real-system-readings/completion.md); `cairn wake` returned Done again during this recon | Preserve its evidence; activate a new contract rather than reopening historical failures |
| Linux device dispatch collects AMD GPUs; NVML runs through a separate adapter | [Device dispatch](../../../examples/system_pulse/collectors/src/host/devices.rs:3), [host capture](../../../examples/system_pulse/collectors/src/host/mod.rs:56) | Intel and Apple production adapters do not yet exist |
| Readings already carry physical kinds/units, source/scope and raw query observations | [Types](../../../examples/system_pulse/collectors/src/types.rs:69) | Reuse this boundary; add schema only for a demonstrated missing fact |
| Background collection has one latest-only delivery slot and an interruptible wait | [Collector public API](../../../examples/system_pulse/collectors/README.md:14), [service](../../../examples/system_pulse/collectors/src/service.rs) | New vendor libraries belong to that worker; no second sampler loop |
| Stable identities preserve choices for absent hardware | [Restoration regression](../../../examples/system_pulse/src/live.rs:433) | Extend mixed-vendor cases without changing established AMD/NVIDIA IDs |

## Reference findings

| Reference | Concrete value | Limits to avoid copying |
| --- | --- | --- |
| [qmassa i915](../../../../../task-manager/reference/qmassa-main/qmlib/src/drm_drivers/i915.rs:144) and [xe](../../../../../task-manager/reference/qmassa-main/qmlib/src/drm_drivers/xe.rs:114) | DRM query layouts, GT frequency paths, PMU and memory-region examples | First-sample zero, unconditional clamping and partial-client aggregation do not satisfy the existing reading contract |
| [macmon](../../../../../task-manager/reference/macmon-0.8.2/src_lib/metrics.rs:206) | Apple native sources and actual residency-weighted frequency calculation | Layout assertions and missing-channel/default zero values need explicit failure handling |
| [HardwareVisualizer IOKit memory](../../../../../task-manager/reference/HardwareVisualizer-1.10.1/core/src/infrastructure/providers/macos/io_kit/iokit_info.rs:327) | Optional `In use system memory` and `Alloc system memory` observations | [Selecting the last accelerator](../../../../../task-manager/reference/HardwareVisualizer-1.10.1/core/src/infrastructure/providers/macos/io_kit/iokit_info.rs:110) does not establish physical GPU identity; shared memory is not dedicated VRAM |
| [hw-smi Intel initialization](../../../../../task-manager/reference/hw-smi-1.6/src/main.cpp:993) | Level Zero Sysman integrated-device detection and telemetry APIs | Unchecked returns, retained old readings and estimated limits need independent treatment; [custom license](../../../../../task-manager/reference/hw-smi-1.6/LICENSE.md:3) has use restrictions |
| [gptop Apple clients](../../../../../task-manager/reference/gptop-0.2.0/src/backend/apple/mod.rs:566) | Native IOKit GPU-client discovery | [Maximum frequency estimate](../../../../../task-manager/reference/gptop-0.2.0/src/backend/apple/mod.rs:141), [zero process GPU percent and full process footprint](../../../../../task-manager/reference/gptop-0.2.0/src/backend/apple/mod.rs:931) are not measured equivalents |

The reference snapshots are evidence leads, not dependencies selected for wholesale inclusion. Preserve applicable notices for any reused source.

## Primary source checks

The kernel documents [Xe GT frequency](https://www.kernel.org/doc/html/latest/gpu/xe/xe_gt_freq.html) under each device's tile/GT frequency directory and distinguishes actual frequency from the current requested frequency. These require separate semantics in the collector.

The kernel's [DRM client statistics contract](https://www.kernel.org/doc/html/latest/gpu/drm-usage-stats.html) describes client/device deduplication, engine capacity and memory-region accounting. Client busy time has client scope; summing visible clients is not automatically complete device coverage, and shared buffers need separate accounting. These definitions will constrain the source decision rather than allowing a generic percentage or memory total to stand in for the requested quantity.

## Host access verified

The developer authorized keyed SSH to the MacBook. Read-only commands on 2026-09-06 returned Darwin arm64, Apple M1 Pro, macOS 26.6.1 build 25G76, 17179869184 bytes RAM, Xcode selected at `/Applications/Xcode.app/Contents/Developer`, Cargo/Rust 1.97.1 and approximately 7.8 GB free. `system_profiler SPDisplaysDataType -json` reported the Apple M1 Pro GPU. The report deliberately excluded serial numbers and other unrelated host details.

No remote files were changed, and no remote builds, workloads or GUI checks were run. SSH access establishes a collector validation path; native desktop observation is still to be established. The developer has an Intel Windows tablet and is checking whether Linux dual boot is practical. Its exact hardware and an Intel discrete target remain unknown.

## Draft review attacks

The draft contract was checked for these failure paths before presentation:

- A class called supported could hide absent implementation behind an unavailable result: the field-accounting rule requires source/API/permission evidence.
- A shared-memory device could receive a plausible but false VRAM bar: GPU-005 and dedicated negative cases reject the substitution.
- An IOReport cache could survive failures as a current value: GPU-006 requires freshness and baseline recovery checks.
- Correct arithmetic could still describe the wrong device or only visible clients: GPU-001/004 and source-scope checks address attribution separately.
- A Mac build or AMD Linux replay could be used to claim Intel hardware accuracy: GPU-008 explicitly requires the corresponding native classes.
- A GPU verifier could pass vacuously or accept its own producer's formula: GPU-009 requires missing-evidence and corrupted-evidence rejection with independent expectations.

The unresolved operational constraint is hardware access, particularly Intel discrete Linux and a Mac native desktop observation path. This is exposed in the draft rather than treated as passing evidence. Detailed specification/falsifier confirmation and executable source planning are still pending; no production code was modified by this recon.

## Preparation checks

The new GPU specification passed the installed Cairn spec lint in isolation. All 24 local links in the four draft documents resolved, including cited line numbers. `git diff --check` passed for tracked changes; the draft files were still untracked at that check.

Running the same lint over the complete existing `docs/spec` directory returned ten existing absolute-path citation findings in `live-collection.md` and `overview.md`. It reported no finding in `gpu-collection.md`. Those historical documents were not edited during this preparation. The full-directory lint is therefore not reported as passing; relative-link cleanup can accompany activation without changing the agreed behavior.

## Activation

The developer confirmed GPU-001 through GPU-009 and their falsifiers after reading the proposed contract on 2026-09-06. The specification and commitment are now Agreed and the roadmap names `intel-and-apple-gpus`. Activation converts the ten historical absolute citations to equivalent relative links; it does not change the LIVE behavior or falsifiers. The [implementation plan](../../plans/intel-and-apple-gpus.md) and [source decision](../../decisions/add-intel-and-apple-collectors-within-the-existing-physical-reading-pipeline.md) define the next action.

At the developer's request, stale Cargo outputs on the MacBook were subsequently cleaned. Twenty-three verified build trees were cleaned, three source archives preserved, and source manifests remained unchanged. A separate path check verified 21 removed target directories and only the three archives remaining in the other two. Free space increased by 129593520128 bytes during cleanup, to approximately 169.6 GB. No active Rust process or open file inside the targets was observed before deletion.

Activation verification: full `docs/spec` lint passed after the equivalent relative-link corrections. All 89 local links and cited line numbers across the eight affected contract/plan/recon documents resolved. The actual Cairn verdict is Resolvable: build the recorded source decision; no GPU mechanism evidence exists yet.
