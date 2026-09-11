# Use native EMI energy and an opt-in PawnIO temperature helper

Level: Consequential
Decided by: Shawn and Codex
Rests on: WTE-001
Would be wrong if: Native readings are mislabeled, helper access can perform arbitrary hardware operations, or the dashboard requires elevation.

## Decision

The developer approved native Windows energy collection plus the signed PawnIO driver and restricted Rust temperature helper. EMI observations on the tablet work unelevated. Preserve separate package/component domains and raw counters; validate metadata, resets and unavailable values. Use the official signed driver and pinned module only for fixed temperature reads, keep the dashboard unelevated, authenticate and bound helper lifetime and output, and do not weaken driver permissions. Offer the prerequisite through Windows installation and inspect the existing Winboat signing workflow without exposing signing secrets. No hosted CI or release publication is authorized. Design: docs/plans/windows-thermal-energy-source-design.md; native investigation: docs/execution/windows-thermal-energy/status.md.

## Realized by

(none yet: recorded, not built)
