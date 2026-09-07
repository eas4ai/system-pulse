# Tabbed Screens Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development for bounded implementation and independent review. The developer has authorized the reference-based UI replacement.

**Goal:** Replace the visible dock canvas with working tabbed screens matching the eight TMOG reference images.

**Architecture:** Keep the existing live WorkspaceView controller and persistence contracts. Add a production screen view using shared data and reusable process/settings components. Draw native segmented meters and timestamped charts through one focused graphics module.

**Tech Stack:** Rust, GPUI Kit 0.6.0, existing bounded sensor history and Linux/macOS adapters, native GPUI and AT-SPI verification.

## Baseline and authority

Base: `a9f77ad55f13ae1d4ed71a540a1d0a167a0da1d4`. The previous migration is installed and pushed with passing source-bound Linux acceptance. Work in `design/tabbed-ui` in the isolated application worktree. The new developer instruction supersedes the former no-tabs product requirement. Cairn's stale README scope notice is retained as bookkeeping, not a request to undo authorized work or restore automation.

## Tasks

- [x] **Native chart primitives.** Create `src/screen_charts.rs` with `ChartSeries { label, color, samples }`, `history_chart(id, series, height, range, cx)`, and `segmented_meter(id, ratio, color, vertical, cx)`. Add focused tests for timestamp mapping, disjoint gap paths, finite zero domains and clamped fill. Use real monotonic sample timestamps and expose text equivalents; draw grids, area/trace and last-value marker natively. Run `cargo test --locked -p system-pulse screen_charts` after the parent wires the module. A worker owns only this file; the parent owns module wiring.
- [x] **Tab state and production root.** Add defaulted `ScreenState` and `Screen` to `crates/model/src/presentation.rs`, preserving old JSON documents and validating persisted IDs. Test old-state restoration, all tab round trips and invalid selections. Create `src/screens.rs` as the new root, change `src/main.rs` and `src/lib.rs` exports, and add the narrow notification/command connection to `src/workspace.rs`. Reuse live collection, storage, presets and recovery. Verify native tab roles/selection, keyboard reachability and active-tab persistence with new tests in `src/screen_tests.rs`.
- [x] **Reference layouts and data projection.** Create `src/screen_data.rs` for pure monitor/sensor selection, valid-value projections and metric formatting; create `src/screen_pages.rs` and `src/screen_summary.rs` for the fixed compositions. Use named physical devices, preserve statuses, expose all valid cores/sensors and use bounded history. Add tests showing current zero survives, absent/stale data is not made current, wrong units cannot enter an aggregate, and device IDs survive discovery reordering. Run targeted app/model tests.
- [x] **Process and settings screens.** Adapt `src/panel.rs` and `src/process_panel.rs` for standalone rendering and retain identity-based selection, virtual scrolling, search, sort and guarded actions. Add usage shading and a selected-process details region using current snapshot fields. Keep `src/settings.rs` and preset controls functional in the new screen. Test tab switching across an open process selection and settings/preset refresh.
- [x] **Native acceptance and visual review.** Add `scripts/system-pulse/tabbed_replay.py` and its focused driver tests; update `verify.py`, `application_acceptance.py` and packaging smoke navigation for the new root. Retain historical dock mechanisms without treating their no-tabs assertions as the new product requirement. Run Python tests, Rust app/model/collector tests, formatting, Clippy, live source comparison, every tab/device/keyboard/restart replay, and screenshot review at 1280x880 and 960x640. Fix observed defects without relaxing assertions.
- [x] **Review and deliver.** Obtain independent specification and code-quality reviews, correct findings, build/package the committed source and run product/package smoke checks. Update feature/design/current-execution documentation. Record exact revisions and platform limits, integrate and push to application main with automation disabled, and install only the verified binary.

Detailed evidence and the single-active-item todo are in `/home/shawn/workspace2/task-manager-artifacts/tabbed-ui-20260907/`.
