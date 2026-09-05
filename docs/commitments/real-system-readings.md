# Real system readings

Slug: real-system-readings
Requirements: LIVE-001, LIVE-002, LIVE-003, LIVE-004, LIVE-005, LIVE-006, LIVE-007, LIVE-008, LIVE-009, LIVE-010, LIVE-011, LIVE-012, LIVE-013

## Goal

Normal System Pulse launch displays measurements from this machine, with no runtime fixture data. The source contract is [live-collection.md](../spec/live-collection.md), confirmed by the developer on 2026-09-04.

## Deliverables and ownership

1. `examples/system_pulse/collectors/`: typed descriptors, physical readings, process identities, capability/source records, counter arithmetic, real OS adapters including AMD sysfs and optional-runtime NVIDIA NVML, and a diagnostic snapshot command. NVIDIA tests cover the backend boundary without asserting hardware verification.
2. `examples/system_pulse/src/` and `model/`: background snapshot delivery, dynamic discovery/state restoration, real process rows, physical meters, test-only fixture injection, and preserved workspace behavior.
3. `scripts/system-pulse/`: source guard, automated acceptance runner, and independently checked host/native evidence. All host comparisons state source semantics, sampling windows, and bounds before measuring.
4. `docs/execution/real-system-readings/`: capability matrix, native observations, command logs/results, source commit/binary hashes, and independent reviews.

The [implementation plan](../plans/real-system-readings.md) sets task order. One source implementer works at a time, followed by independent spec and quality review. Root orchestration and read-only investigation may run alongside it.

## Formats and preservation

Snapshots use serde JSON for diagnostic capture, with monotonic timestamps, raw quantities, units, availability reasons, device identity and source metadata. Normal UI state remains JSON and retains structural validation, invalid-original recovery, panel/sensor choices, and preferred expanded geometry. Fixture state is never silently mapped to physical devices by enumeration position.

## Mechanisms

`live-acceptance` maps the complete LIVE set to one aggregate command because Cairn assigns one mechanism per requirement. It runs the source guard, collector/model/app tests, affected dock regressions, formatting, strict Clippy, native build, capability coverage, and host/native verification. No missing mechanism, empty test selection, absent hardware adapter, or absent native evidence counts as pass.

Command: `rtk proxy python3 scripts/system-pulse/verify.py`

The baseline command fails on the known runtime fixture path before collectors exist. Intermediate implementers run focused checks directly; aggregate Cairn checks run after meaningful changes, preserving failures rather than accumulating repeated identical attempts.

## Done when

- LIVE-001 through LIVE-013 have current passing evidence against committed source.
- Every accessible, attributable required host field is implemented; permission/attribution limits carry actual evidence.
- Native UI readings agree with independent host observations under predeclared comparisons, and the full workspace interaction preservation replay passes.
- Independent spec/quality review and final review have no open findings.
- `cairn wake` reports Done.
