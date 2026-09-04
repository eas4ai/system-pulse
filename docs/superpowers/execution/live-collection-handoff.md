# Resume: real system collection

The user requested a harness restart during initial discovery. Resume the real-collection task; do not repeat the completed workspace implementation.

## User direction

The user rejected simulated readings as the delivered system monitor. The assistant acknowledged that the fixture proof was too narrow, proposed real collectors feeding the existing panels with simulation confined to tests, and the user replied **“ok”**. This authorizes moving that work forward. Earlier authorization to use subagents remains applicable. Do not ask again whether real readings or subagents are wanted.

User layout requirements remain: **no UI tabs**, scroll to panels, explicit independent panel/row collapse, retained useful compact readings, and persistent layout choices. Unsupported metrics must be labeled unavailable, never replaced with invented readings.

## Existing verified implementation

- Design repository: `/home/shawn/workspace2/task-manager`.
- Implementation worktree: `/home/shawn/workspace2/task-manager-worktrees/workspace-visibility`.
- Implementation branch: `feat/system-pulse-workspace`.
- Implementation HEAD: `9f2f3ad0382ce4c7ce0aadfc0c4ed88588ad95af` (acceptance documentation).
- Latest source change: `88343d5ed3be72865e52fc3d51a860649d8def83`.
- Backing framework clone: `/home/shawn/workspace2/gpui-component`.
- Application: `examples/system_pulse`; pure model: `examples/system_pulse/model`.
- The existing `examples/system_monitor` is unchanged and may contain reusable real collector patterns.
- Verified fixture baseline: **275 tests**, affected-package formatting, strict all-target Clippy, native build, and independent reviews passed. Linux native interaction checks passed. This does **not** establish real collection.
- Full evidence: [workspace execution report](2026-09-04-workspace-visibility.md), including committed artifacts and interactive native driver.

## Current task state

1. **In progress:** inspect collector requirements, existing code, references, and host capabilities.
2. Pending: write the real-collection spec and implementation plan, consistent with the user's correction.
3. Pending: implement and independently review live collection integration.
4. Pending: verify native readings against the host and document actual results.

**No collector source code or real-collection spec/plan has been written yet.** No dependencies have changed. A read-only research agent (`dock_quality_review`) was started and interrupted for this restart before returning findings. Do not assume it completed discovery. Other agents from the fixture work are finished.

The root agent read the existing root `AGENTS.md`, prior workspace plan, and Superpowers brainstorming/writing-plans skills. The full feature-spec output was truncated; read the missing collector/sensor sections before designing. The project is Rust/GPUI with Linux-primary development and cross-platform product intent. Do not invent another fixture-only completion boundary.

## Next discovery work

- Read `docs/feature-spec-dockable-system-monitor.md` for required metrics and collector architecture, plus the workspace visibility spec for preserved UI contracts.
- Inspect the current app's fixture, meter, panel, process-table, shared-state, and timer seams. Find where real snapshots can replace synthetic data without changing docking behavior.
- Inspect pinned dependencies and existing `examples/system_monitor`; consult local `reference/` source snapshots for collection techniques and license constraints.
- Inspect actual host GPU/backend availability. Prefer existing pinned collector libraries. Clearly separate unsupported hardware metrics from missing implementation.
- Define stable real monitor/sensor identities, cumulative counter deltas, sampling intervals, error/stale states, dynamic devices/processes, bounded histories, off-UI-thread work, and safe migration from fixture identities.
- Keep simulation only in tests. Remove runtime fixture controls and labels when actual collectors are installed; report real source/availability where useful.

## Working rules

Follow root user instructions and imported files: `/home/shawn/.codex/{RTK,TILTH,PARTNERSHIP}.md` and `/home/shawn/.claude/BEST_PRACTICES.md`; any repository-specific production standard overrides the global copy. Keep one todo in progress, and verify before marking complete.

Prefix shell commands with `rtk`; use `rtk proxy` for unsupported commands. Prefer codebase-memory-mcp for code discovery and index first if stale/missing; use `tilth` when graph results are insufficient. The framework graph project is `home-shawn-workspace2-task-manager-worktrees-workspace-visibility`.

Use the Superpowers workflow already requested, with source ownership and independent spec/quality reviews. User authorization persists; avoid redundant permission requests. Do not merge, push, or remove the existing worktree merely to resume.

The design repository's existing `AGENTS.md`, `docs/System Pulse.html`, `docs/files.zip`, and `reference/` are intentional untracked inputs. Preserve them. The original instruction explicitly prohibited modifying an existing `AGENTS.md`.

## Run and verify baseline

Run from the implementation worktree:

```sh
rtk cargo run -p system-pulse
rtk cargo test --locked -p system-pulse --lib
```

The current binary still uses simulated readings. That is the deficiency to fix, not the desired final behavior. The prior verification report contains the complete affected-package commands and Linux native harness setup. Do not rerun all baseline checks without a reason; inspect status first and use focused checks as changes are made.
