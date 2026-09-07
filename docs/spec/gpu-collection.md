# Intel and Apple GPU collection

Status: Agreed 2026-09-06
Prefix: GPU

The developer authorized the next GPU-support iteration on 2026-09-06: Intel integrated and discrete GPUs, followed by Apple Silicon system-wide GPU monitoring. The developer confirmed GPU-001 through GPU-009 and their falsifiers on 2026-09-06. Agreement defines the work; it does not claim implementation or hardware acceptance.

## Scope

The first implementation covers Intel GPUs using the Linux `i915` and `xe` drivers and Apple Silicon GPUs on macOS. Intel Windows support is a separate follow-on deliverable, for which the developer has offered a tablet PC. Linux availability on that tablet is being checked. Older Intel-based Macs and per-process GPU utilization are outside this iteration.

Apple's Metal API identifies the graphics device and provides a controlled validation workload where needed. IOReport, IOKit and SMC/HID provide system-wide monitoring observations; theoretical shader throughput is not a utilization measurement.

Existing [LIVE requirements](live-collection.md) remain preservation constraints. The new collectors use the existing background service, descriptors, physical readings, meter compatibility and persistence behavior.

## Field accounting

Every field below appears in the capability report with a source, device/engine/region scope, unit and outcome. An accessible measurement missing its implementation is unfinished work. Unsupported APIs, denied permissions and unavailable hardware are separate outcomes.

| Field | Intel Linux | Apple Silicon |
| --- | --- | --- |
| Identity | PCI device identity, with driver and integrated/discrete classification when evidenced | Physical Apple GPU identity, associated with the actual Metal/IOKit device |
| Activity | Device or engine counters with their documented normalization | GPU active residency divided by total residency |
| Frequency | Actual GT frequency; requested frequency is separately labeled if exposed | Active-state residency-weighted frequency with an evidenced frequency table |
| Temperature | Device/GT sensors where exposed; CPU package temperature retains package scope | GPU SMC/HID sensor readings where exposed |
| Power | GPU/device energy deltas or power readings; package power retains package scope | GPU energy delta divided by measured elapsed time |
| Memory | Dedicated device-local regions where present; shared allocations only at an evidenced scope | Optional accelerator memory counters, with their actual allocation/in-use meaning |
| Fan | Measured RPM or percentage in the source's unit | Only a GPU-attributable fan reading; a system fan is not invented as a GPU fan |

Visible-client fdinfo totals do not establish whole-device GPU utilization or unique resident device memory. Total system RAM and process physical footprint do not establish GPU allocation. A shared allocation without a valid total is a byte-valued reading, not a fabricated capacity bar.

## Requirements and falsifiers

[GPU-001] The collector MUST discover each accessible supported Intel or Apple physical GPU once using an identity independent of display name and enumeration order.
Falsifier: reordering, driver-node renumbering, duplicate render/card nodes, identical names or temporary absence produces duplicate monitors or attaches a saved choice to another physical GPU.
Mechanism: `gpu-discovery` adapter and persistence tests plus independent native device inventory comparison.

[GPU-002] The Intel Linux collector MUST implement each accessible, attributable field in the field-accounting table for the `i915` and `xe` interfaces it supports.
Falsifier: an exposed required counter is omitted, a requested clock is labeled actual, an inaccessible counter becomes a measured zero, or partial client activity is labeled whole-device activity.
Mechanism: `gpu-intel` rooted sysfs and injected DRM/counter tests, source-to-field capability audit, and Intel native accuracy capture.

[GPU-003] The Apple collector MUST obtain supported system-wide GPU readings from native observations associated with the discovered Apple GPU.
Falsifier: the adapter reports a maximum clock as measured current frequency, mistakes a missing channel for idle, assigns a different accelerator's memory to the GPU, or fabricates power/temperature/fan readings.
Mechanism: `gpu-apple` injected IOReport/IOKit/SMC/HID boundary tests, native macOS compilation, and Apple native accuracy capture.

[GPU-004] Each new GPU reading MUST retain sufficient raw source operands, source units, device scope and query timing to independently recompute its physical value.
Falsifier: irregular sampling, counter regression, a failed baseline, overflow, unknown units or an incompatible performance-state layout produces a current but unverifiable value.
Mechanism: `gpu-arithmetic` adversarial tests and independent recomputation of captured observations before display rounding.

[GPU-005] The application MUST distinguish dedicated VRAM, GPU shared-memory allocation, system RAM and process memory in sensor labels and meter semantics.
Falsifier: a shared-memory GPU is assigned dedicated VRAM merely because it uses RAM, system memory is presented as GPU allocation, or an unknown/zero total produces a successful capacity bar.
Mechanism: `gpu-memory` descriptor, formatter, meter and restored-workspace tests plus native label/quantity inspection.

[GPU-006] The new collectors MUST preserve explicit warming-up, unavailable and failed outcomes through recovery without refreshing stale values as current.
Falsifier: an API/channel failure preserves a current-looking cached value, a failed initialization disables every later retry, a reset bridges an invalid counter baseline, or one failed field suppresses valid independent fields.
Mechanism: `gpu-availability` state-sequence tests and native failure/sleep-wake recovery observations where reproducible.

[GPU-007] GPU collection MUST use the existing bounded background sampling pipeline while preserving AMD/NVIDIA readings and workspace behavior.
Falsifier: the new adapters create an overlapping poller, block the UI update path, accumulate device/baseline state, mix device identities, or break collapse, scrolling, history, interval changes or restored sensor choices.
Mechanism: `gpu-integration` mixed-adapter, slow-backend, churn and persistence tests plus the existing Linux acceptance and native workspace replay.

[GPU-008] Native GPU acceptance MUST record actual device discovery and independent accuracy comparisons on Intel integrated, Intel discrete and Apple Silicon hardware before claiming those hardware classes verified.
Falsifier: a fixture, compile-only result, another vendor's host, missing device or unperformed native interaction is accepted as hardware accuracy evidence for a class.
Mechanism: `gpu-native` per-host reports containing hardware/driver/API versions, committed source and binary hashes, predeclared field coverage and comparison bounds, original observations, native labels and cleanup outcomes.

[GPU-009] The GPU acceptance mechanism MUST reject missing mandatory checks and deliberately incorrect source, scope, unit, timing, identity or freshness evidence.
Falsifier: an empty test selection, missing host report, mismatched binary, wrong conversion, stale capture or incorrect memory scope passes the relevant requirement.
Mechanism: `gpu-verifier` negative tests and committed per-requirement Cairn receipts from the aggregate acceptance command.

## Native evidence boundary

The available Apple host is the developer's M1 Pro MacBook, reached by authorized keyed SSH and identified read-only on 2026-09-06. Rust and Xcode are installed. Native GUI evidence still needs a suitable logged-in desktop observation path; SSH success alone does not establish that evidence.

Intel integrated and discrete host evidence remains pending. The tablet's model, GPU, driver and Linux availability are not yet known. Missing hardware remains unverified and cannot satisfy GPU-008. Windows receives its own requirements and native evidence when that follow-on is taken up.

The proposed [commitment](../commitments/intel-and-apple-gpus.md), [acceptance plan](../plans/intel-and-apple-gpu-acceptance.md) and [cited recon](../execution/intel-and-apple-gpus/recon.md) describe the next steps. The roadmap names `intel-and-apple-gpus` as the current commitment. The completed `real-system-readings` evidence remains its preservation baseline.
