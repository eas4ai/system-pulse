# GPUI Kit 0.6 Migration Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development for independent migration and review tasks. Preserve all existing behavioral assertions.

**Goal:** Run System Pulse on the released GPUI Kit 0.6.0 dependency while preserving its current application behavior and native corrections.

**Architecture:** The root application depends on `gpui-kit = "=0.6.0"`. Retain local patches only for the modified base/component libraries and native adapters. Published unmodified macros and icon assets replace their local copies. The application model, collectors, saved-state format, and UI arrangement remain the existing product contract.

**Tech Stack:** Rust, GPUI Kit 0.6.0 at upstream source `94a313a72a2513aee2780240cd322d552b2395f0`, its locked GPUI Pre 0.3.2 family, Linux native AT-SPI/Vulkan verification, Python packaging/replay tools.

## Scope and evidence

The developer authorized this migration on 2026-09-07 after discussion of its native-patch and verification costs. This follows the explicitly requested repository cleanup, Dependabot removal and disabled GitHub CI. Cairn's current scope notice about `.github/dependabot.yml` refers to that authorized earlier removal; it is not an instruction to restore automation. This migration does not claim completion of the outstanding Intel/Apple hardware acceptance.

Baseline: `b7dc6086d8036dccb2687de04d81d31138a02436`; upstream common ancestor: `ba3433f0740ee5ba2b1db459af49229caf0c1bcc`. Work in the application's isolated `migrate/gpui-kit-06` checkout. Keep detailed logs and the single-active-item todo in the external `gpui-kit-06-20260907` evidence directory.

## Tasks

- [x] Run `cargo test --locked -p system-pulse` before migration: 90 tests pass. Inspect the released manifests and compare every locally changed library file against the common ancestor and released source.
- [x] Merge released `crates/base` and `crates/component` source into local `crates/base` and `crates/ui`, preserving local Separate dock policy, minimum/fixed/collapsed extents, focus/navigation/accessibility behavior, fixture ownership, and exact motion deadlines. Keep upstream proportional split sizing for tabbed layouts and bypass it where Separate extents are authoritative. Keep new split caches synchronized. Verify with the existing base/component tests and add focused regressions for newly encountered integration boundaries.
- [x] Update root and retained-library manifests to GPUI Kit 0.6.0 and the matched GPUI Pre graph. Replace local macros/assets with published packages. Use `gpui_kit` exports in application imports and initialization; retain direct GPUI test support only where procedural macros or native harnesses require it. Run `cargo check --all-targets -p system-pulse` and resolve actual API incompatibilities without relaxing assertions.
- [x] Rebase the AccessKit expansion-state adapter patch onto the selected 0.19.1 adapter. Rebase the dispatcher autorelease-pool correction onto GPUI Pre macOS 0.3.2; preserve destruction, pending-poll, cancellation and real-application lifetime tests. Update provenance and patch source identifiers. Verify the actual Cargo graph selects both patched crates. Run adapter tests on Linux and native macOS checks only where a Mac is available; disclose unavailable native evidence.
- [x] Run `cargo fmt --all -- --check`, `cargo test --locked --workspace`, app/model/collector/base Clippy with `--all-targets -- -D warnings`, and the Python verification suite. Adapt package dependency identification to renamed crates where required, with tests for the actual package/source graph.
- [x] Build and exercise the native Linux app using isolated state and a private display: layout restore/reset, collapsed panels and sensor rows, keyboard navigation, process table, live GPU rows, fonts/themes, save/restart, and native expansion states. Build the distributable package, verify notices/source inventory, and run package smoke tests. Do not change the user's saved configuration.
- [x] Review specification compliance and code quality independently; fix findings and rerun affected checks. Record exact verified revisions and platform limits, integrate into the application repository, and install only the verified build. Leave GitHub automation disabled.
