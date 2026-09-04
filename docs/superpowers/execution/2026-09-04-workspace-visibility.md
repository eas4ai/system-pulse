# Workspace Implementation Evidence

Status: In progress. The user authorized execution with subagents on 2026-09-04.

## Source and scope

- Plan: [Workspace Visibility](../plans/2026-09-04-workspace-visibility.md).
- Source repository: `eas4ai/gpui-component`.
- Baseline: `ba3433f0740ee5ba2b1db459af49229caf0c1bcc`.
- Branch: `feat/system-pulse-workspace`.
- Execution worktree: `/home/shawn/workspace2/task-manager-worktrees/workspace-visibility`.
- Deliverable: native fixture workspace proving separate panels, scrolling, explicit panel/row collapse, and recoverable presentation state. Live OS collection remains outside this slice.

## Task state

- [x] Prepare worktree and verify baseline dock tests.
- [x] Implement separate-panel docking; spec review; code-quality review.
- [x] Implement presentation state; spec review; code-quality review.
- [ ] **In progress:** implement collapse geometry; spec review; code-quality review.
- [ ] Implement native fixture workspace; spec review; code-quality review.
- [ ] Complete integrated native acceptance and final review.

## Environment evidence

The pinned worktree was created successfully. `cargo metadata --locked --no-deps --format-version 1` passed. Graph indexing succeeded. Host inspection found Rust/Cargo 1.95, Linux graphics/development libraries, Xvfb, XTEST, Pillow, and AT-SPI bindings. An isolated Xvfb and D-Bus smoke check also passed: a 1440×1000 screenshot, XTEST extension, and AT-SPI desktop were available. Application-level native acceptance remains pending.

## Verification record

The initial baseline command `cargo test --locked -p gpui-base -p gpui-component --lib dock::` failed: an accidental `centred` token in `crates/base/src/styled.rs:148` prevented parsing and caused cascading imports to fail. The one-token prerequisite fix is committed as `385bc28665ac571730776860ce3b0a570f38e695`. The baseline command then passed all 197 dock tests, and touched-file rustfmt passed. Independent spec and code-quality reviews passed. The docking agent subsequently verified policy/mutation/drop test failures before implementing them. Current feature checks: 196 base dock tests and 18 UI dock tests pass; package formatting passes. Policy commits: `3eac4c5d`, `cfe12c90`, `ed45f48c`, and review fixes `43813bb4` and `3e1075e3`. Strict Clippy exposed a pre-existing calendar boolean-expression lint; the equivalent correction is isolated in `d16ff11a`, with 8 calendar tests passing before and after. Strict Clippy now passes. The independent policy spec review identified an unguarded infinite side-dock size in policy transition and direct resize; both regressions failed before the fix and passed afterward. Spec re-review passed. Code-quality review found a minor stale center-drop preview during a live policy change; its regression failed before correction and passed afterward. The quality re-review passed with no remaining findings. Native acceptance remains pending.

## Presentation and geometry review notes

The pure model implementation (`700b747f`, `7489aecb`) passes 15 integration tests, formatting, and strict Clippy after review fix `afa1cfa3`. The exhausted u32 sensor-order case now compacts existing order values while retaining relative order and all other settings; its regression failed before the correction. Independent spec and code-quality reviews passed with no remaining findings. The 16,384 dimension limit comes from the approved plan's implementation and is retained as a documented layout bound.

Geometry source preflight found that hidden-slot divider indexing, shrink redistribution, and container growth in the existing Resizable state violate the proposed fixed/hidden constraints. Commit `a352bb16` adds an opt-in correction for Separate layouts, plus the geometry interface and renderer. The implementer verified the failures before correction: a hidden slot retained 220 pixels, a fixed 36-pixel header expanded to 76, and two saved 420-pixel panes became 600 each in a 1200-pixel container. Corrected allocations preserve hidden zero slots, fixed headers, and the first fixed/last flexible rule. Reported final checks pass: 8 geometry tests (included in 205 Base dock tests), 10 Base resizable tests, 19 UI dock tests, formatting, strict Clippy, and diff checks. Independent review reran all 205 Base dock, 10 resizable, and 19 UI dock tests successfully, then found a stale active resize index after hiding its source. The hidden guard prevents movement while hidden, but re-showing before release resumes the old drag. Three regressions reproduced the defect, including zero-slot adoption when an entire split is omitted. Correction `b4de4d18` passes those cancellation checks, including preservation of an unrelated visible active source. Independent spec re-review passed and reran 205 Base dock, 13 resizable, and 19 UI dock tests successfully. Independent quality review is in progress; implementer formatting and strict Clippy also passed. This focused resize adjustment implements the approved interaction without changing default consumers.

Model test-process note: all three supplied test suites were installed before implementation and failed together against missing exports. The implementer did not run three separate tranche-specific red commands. The ordering regression received its own meaningful red/green check.

## Native acceptance checklist

All scenarios below remain pending until the fixture application runs. The prepared Xvfb driver supports semantic inspection, pointer/keyboard input, resize, screenshots, and graceful shutdown; its Python syntax check passed.

| Contract | Native evidence to collect |
| --- | --- |
| WV-01, WV-03 | Edge/header/center drops, source preservation, divider dragging, hide/re-enable. |
| WV-02, WV-04 | Minimum window, both overflow axes, nested wheel routes, keyboard table entry/exit, focus reveal. |
| WV-05–WV-08 | Default expansion, mixed panel/row state, meter changes, retained dimensions after dragging. |
| WV-06, WV-09 | Full fixture cycle while collapsed, truthful status, continued history. |
| WV-10 | Enter/Space, accessible names and expanded state, focus recovery, no control-induced drag. |
| WV-11 | Preset recall, quit/restart immediately after resize, stable device/sensor identities. |
| WV-12 | Invalid saved group retained byte-for-byte, preset gate, explicit recovery archive. |
