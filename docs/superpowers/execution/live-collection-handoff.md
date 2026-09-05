# Resume: real system collection

The user restarted the harness and invoked `/existing-project`. Resume the real-collection task through the adoption drafts; do not repeat the completed workspace implementation.

## User direction

The user rejected simulated readings as the delivered system monitor. The assistant acknowledged that the fixture proof was too narrow, proposed real collectors feeding the existing panels with simulation confined to tests, and the user replied **“ok”**. This authorizes moving that work forward. Earlier authorization to use subagents remains applicable. Do not ask again whether real readings or subagents are wanted.

User layout requirements remain: **no UI tabs**, scroll to panels, explicit independent panel/row collapse, retained useful compact readings, and persistent layout choices. Unsupported metrics must be labeled unavailable, never replaced with invented readings.

## Existing verified implementation

- Design repository: `/home/shawn/workspace2/task-manager`.
- Implementation worktree: `/home/shawn/workspace2/task-manager-worktrees/workspace-visibility`.
- Implementation branch: `feat/system-pulse-workspace`.
- Verified fixture acceptance documentation: `9f2f3ad0382ce4c7ce0aadfc0c4ed88588ad95af`.
- Adoption drafts begin at `822635ff044df53b60258ad645c7dbf01fc0287b`; inspect Git history for later documentation commits.
- Latest source change: `88343d5ed3be72865e52fc3d51a860649d8def83`.
- Backing framework clone: `/home/shawn/workspace2/gpui-component`.
- Application: `examples/system_pulse`; pure model: `examples/system_pulse/model`.
- The existing `examples/system_monitor` is unchanged and may contain reusable real collector patterns.
- Verified fixture baseline: **275 tests**, affected-package formatting, strict all-target Clippy, native build, and independent reviews passed. Linux native interaction checks passed. This does **not** establish real collection.
- Full evidence: [workspace execution report](2026-09-04-workspace-visibility.md), including committed artifacts and interactive native driver.

## Current task state

1. Complete: inspect current application code, existing collector reference, documentation, and tooling. Host GPU capability probing remains part of collector design.
2. **In progress:** confirm the adoption draft's real-collection requirements and falsifiers, then write the implementation plan.
3. Pending: implement and independently review live collection integration.
4. Pending: verify native readings against the host and document actual results.

**No collector source code or implementation plan has been written yet.** No dependencies have changed. The cited [recon](../../recon.md) is now written. Formal adoption documents live beside the source at `/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/docs/spec/`; start with `overview.md` and `live-collection.md`. READ/VIEW/STATE sections are Observed; LIVE requirements are Draft pending confirmation of text and falsifiers. They are not yet a Cairn contract.

The read-only collector agent completed a cited audit of `examples/system_monitor` and pinned sysinfo 0.37.2. It found reusable CPU/memory/process/disk APIs, but no network/GPU implementation in that example, and UI-thread collection, time-axis, warm-up, truncation, and zero-on-error weaknesses to avoid. The recon records its findings. The full relevant product sensor/data-layer sections have now been read. The project is Rust/GPUI with Linux-primary development and cross-platform product intent. Do not invent another fixture-only completion boundary.

The user-invoked existing-project skill requires confirmation of the proposed requirement text and falsifiers before marking new sections Agreed. Their high-level approval of real readings and subagents already stands. Ask only for corrections/confirmation of the newly concrete acceptance bar, not whether to pursue real readings again. No active roadmap/commitment is created before this confirmation. `cairn wake` and `cairn check` currently return exit 3 because `docs/spec/roadmap.md` does not exist; this is not a passing or Done verdict.

## Next discovery work

- Read the recon and adoption drafts before doing further discovery; they cite the inspected app, reference collector, tests, pinned dependencies, and preservation contracts.
- Confirm the LIVE text/falsifiers through the existing-project workflow, then create the roadmap/current commitment and executable mechanisms in the implementation worktree.
- Consult local `reference/` source snapshots for any collection technique used and preserve its license constraints.
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
