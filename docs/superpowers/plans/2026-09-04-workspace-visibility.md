# Workspace Visibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the approved scrollable workspace with separate panels, explicit panel/sensor-row collapse, live compact readings, and recoverable saved presentation state.

**Architecture:** Extend the existing dock's policy and geometry seams, keep presentation/history state in a pure Rust crate, and compose a native GPUI interaction proof using deterministic fixture data. The fixture example verifies the workspace contract before production collectors are integrated. Framework behavior outside the opt-in separate-panel path remains compatible.

**Tech Stack:** Rust 2024, GPUI, gpui-base, gpui-component, serde/serde_json, smol, existing native test facilities.

---

## Approval and scope

The user approved [Workspace Visibility and Collapse](../specs/2026-09-04-workspace-visibility-design.md) on 2026-09-04. That approval authorizes this plan. It does not turn fixture readings into production system metrics or declare the entire product implemented.

The plan follows the original feature spec's stated destination: an application crate inside `eas4ai/gpui-component`. This `task-manager` repository holds the design inputs and plans. Existing `examples/system_monitor` remains a reference; the new example is `examples/system_pulse`.

The implementation proof must visibly identify its fixture data. It covers all twelve WV requirements, including real native docking, scrolling, collapse, keyboard controls, and persistence. Production CPU/GPU/disk/network collection, process termination, full preset CRUD, complete theme/font settings, packaging, and the 120fps release target require their own specs and plans. They are not silently dropped from the product.

## Source baseline

- Framework: `eas4ai/gpui-component` commit `ba3433f0740ee5ba2b1db459af49229caf0c1bcc`.
- Its lockfile resolves GPUI/Zed to `f66ed399cdde86092af8af3dc7b418abf45f37f8`.
- Keep workspace dependency declarations and the checked-in lockfile. New application dependencies inherit workspace entries where available. Do not mix published GPUI versions with the fork's Git dependency graph.
- Planning-host tools observed: rustc 1.95.0 and Cargo 1.95.0. Full native framework compilation has not been established by this documentation work.
- Follow the execution checkout's AGENTS.md and BEST_PRACTICES.md if present. Inspect baseline changes before adapting any patch to a newer revision.

Primary source: [fork workspace manifest](https://github.com/eas4ai/gpui-component/blob/ba3433f0740ee5ba2b1db459af49229caf0c1bcc/Cargo.toml). The [reference review](../research/2026-09-04-reference-review.md) explains why ordinary center drops, insertion, and restoration require explicit separate-panel enforcement.

## Prepare the execution worktree

These commands are instructions for implementation, not commands already run in the user's source checkout.

- [ ] **Step 1: Obtain the framework checkout.** If `/home/shawn/workspace2/gpui-component` does not exist, run:

```sh
rtk git clone --no-checkout https://github.com/eas4ai/gpui-component.git /home/shawn/workspace2/gpui-component
```

If it already exists, inspect its remote and status before reusing it:

```sh
rtk git -C /home/shawn/workspace2/gpui-component remote -v
rtk git -C /home/shawn/workspace2/gpui-component status --short
```

Preserve unrelated work. Do not reset an existing checkout.

- [ ] **Step 2: Create an isolated implementation worktree at the reviewed baseline.** Run once, with a new branch and unused destination:

```sh
rtk git -C /home/shawn/workspace2/gpui-component worktree add -b feat/system-pulse-workspace /home/shawn/workspace2/task-manager-worktrees/workspace-visibility ba3433f0740ee5ba2b1db459af49229caf0c1bcc
```

Set subsequent command working directories to `/home/shawn/workspace2/task-manager-worktrees/workspace-visibility`. If this task's worktree already exists, resume it after inspecting its status; do not recreate or discard it.

- [ ] **Step 3: Check the execution baseline.**

```sh
rtk git rev-parse HEAD
rtk git status --short
rtk cargo metadata --locked --no-deps --format-version 1
```

Expected for a fresh worktree: the reviewed commit, no local changes, and successful metadata. On resume, inspect the task commits instead of requiring the original HEAD. Record native dependency/toolchain failures as environment failures; do not count them as the failing tests required by the tasks.

## Execute the component plans

| Order | Plan | Deliverable |
| --- | --- | --- |
| 1 | [Separate-panel docking](2026-09-04-01-dock-separate-panels.md) | Enforceable policy for moves, insertion, and restored state; invalid operations preserve the source. |
| 2 | [Presentation state](2026-09-04-02-presentation-state.md) | Pure state/history crate, stable identities, snapshot roundtrips, and recovery autosave gate. |
| 3 | [Dock geometry](2026-09-04-03-dock-geometry.md) | Readable minimum extents, released collapsed body size, retained expansion preference, and center canvas measurement. |
| 4 | [Native workspace](2026-09-04-04-native-workspace.md) | Runnable fixture example with real scrolling, docking, controls, persistence, and native acceptance scenarios. |

Plans 1 and 2 are independent in concept. Apply them in this order for reproducibility; serialize shared-file edits. Plan 3 depends on plan 1's policy. Plan 4 depends on all three and is the integration gate. Keep exactly one execution task in progress and do not mark it done before its code and verification are complete.

## Requirement coverage

| Requirement | Implementation ownership | Required evidence |
| --- | --- | --- |
| WV-01 Separate regions | Plans 1 and 4 | Rejected center/header merges leave source unchanged; edge moves work. |
| WV-02 Scrollable overflow | Plans 3 and 4 | Minimum extents survive viewport resizing; all enabled panels remain reachable. |
| WV-03 Explicit hiding | Plans 1, 2, and 4 | Show/hide is independent from collapse; re-enabled monitor receives a separate region. |
| WV-04 Nested scrolling | Plan 4 | Process-table and workspace navigation both work by pointer and keyboard; focus is revealed. |
| WV-05 Initial state | Plans 2 and 4 | First-run and missing saved fields expand panels and rows. |
| WV-06 Panel collapse | Plans 2, 3, and 4 | Header summary remains live; body size request releases; expansion retains preferred dimensions. |
| WV-07 Sensor collapse | Plans 2 and 4 | Label, reading, unit, status, and position remain while the detailed meter folds away. |
| WV-08 Independent state | Plans 2 and 4 | Parent collapse, row collapse, meter choice, and explicit visibility do not overwrite each other. |
| WV-09 Live readings | Plans 2 and 4 | A single fixture feed updates compact readings and bounded history through collapse. |
| WV-10 Controls | Plan 4 | Accessible names/expanded state, Enter/Space activation, focus handoff, and no accidental dragging. |
| WV-11 Restoration | Plans 2, 3, and 4 | Actual dock JSON and presentation state roundtrip; identity reorder and absent sensors preserve choices. |
| WV-12 Invalid state | Plans 1, 2, and 4 | Reject multi-panel groups; preserve original input; prevent autosave overwrite before explicit recovery. |

## Completion gate

- [ ] All companion-plan tasks and targeted tests pass in the real execution worktree.
- [ ] The model and dock suites pass after native integration; shared trait forwarding and exports compile together.
- [ ] The native example is built and the approved interaction scenarios are exercised. Capture actual observations, not only screenshots or a statement that the window opened.
- [ ] Restore mixed panel/row collapse states after restarting the example. Exercise rejected saved state and confirm the original input remains recoverable.
- [ ] Verify keyboard and nested-scroll behavior in the target window system. For macOS accessibility testing, follow the fork's `docs/ACCESSIBILITY-UI-TESTING.md`; its signed-app requirement is not satisfied by a bare `cargo run` process.
- [ ] Record actual commands, native platform, outcomes, and limitations alongside the execution report. Do not claim production collection, cross-platform acceptance, or 120fps performance from this fixture proof.

This is a planning deliverable. Source changes shown in companion documents have not been installed into a production application by writing these plans.

## Planning validation

These checks ran against temporary copies of the embedded code, not an installed application:

- The model's 13 integration tests and Clippy passed in a standalone Rust crate.
- The native plan’s extracted fixture and storage modules passed both tests and Clippy in a temporary crate.
- Six geometry arithmetic tests passed with the original PaneNode source and lightweight GPUI geometry stand-ins.
- All six framework patch stages applied in sequence; the geometry patch applied after them. Changed framework Rust files passed syntax/format checks, and the existing facade export-parity test passed standalone.
- The plan documents were checked for broken local links, unmatched code fences, placeholders, and coverage of WV-01 through WV-12.

The real framework build and native interaction checks remain execution gates. Isolated planning checks do not establish those outcomes.
