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

The developer explicitly **confirmed** LIVE-001–013 and their falsifiers, then added NVIDIA support despite having no NVIDIA GPU installed. No further scope approval is needed for these collectors or subagents.

1. Complete: cited recon, agreed LIVE contract, implementation plan, roadmap/current commitment and executable baseline mechanism.
2. **In progress:** implement and review the host collector crate and bounded sampling service.
3. Pending: integrate real devices/readings/process rows, physical meters, stable state and test-only fixtures into the workspace.
4. Pending: independent host/native acceptance and final review.

Activation is committed as `55087aa6` in the source worktree. Read `docs/spec/live-collection.md`, `docs/plans/real-system-readings.md`, and `docs/commitments/real-system-readings.md` there. Historical READ/VIEW/STATE specs remain Observed. The new source-root AGENTS working agreement was created from the existing-project skill's template; the design repository's existing AGENTS remains untouched.

Cairn's first committed baseline check failed on the actual production fixture dependency and retained receipts for all LIVE requirements. `cairn wake` reports **Resolvable: implement LIVE-001**. `.cairn/in-progress` records that source action. Do not rerun the aggregate repeatedly while implementation is incomplete; use focused tests and retain failing receipts.

A fresh implementer owns only `examples/system_pulse/collectors/`, workspace membership and Cargo.lock. Its task includes full Linux field coverage, AMD sysfs, optional-runtime NVIDIA NVML, serializable source/counter observations, real process identities, and a single latest-only sampling worker. Check current subagent/worktree state before editing. One source implementer at a time; independent spec review then quality review follows each coherent task.

Host preflight found 32 logical CPUs and two Radeon AI PRO R9700 GPUs, with readable utilization, VRAM, temperatures, average SoC power, graphics/memory clocks and fan RPM. Stable AMD IDs and exact sources are in source `docs/execution/real-system-readings/host-preflight.md`. NVIDIA backend API research and the verification design are adjacent documents. NVIDIA deterministic adapter tests and graceful-absence tests are required; actual NVIDIA hardware accuracy remains explicitly unverified until run on such hardware.

The collector is committed in `8b7c35b9`, `9c9d059c`, and `19099472`; independent spec review passed after fixing shared-MAC interface identity collisions. A separate quality review requested fixes for public counter-helper retention and common-backend query timestamps; the implementer is addressing them. See source `docs/execution/real-system-readings/collector-review.md` for the current review record. App/model integration has not started. The app still uses fixtures until that task lands; no native live acceptance or completion is claimed. Preserve all accessible-field requirements: missing collector code is not an unavailable hardware result.

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
