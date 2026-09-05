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
- Historical fixture source baseline: `88343d5ed3be72865e52fc3d51a860649d8def83`. Inspect current source HEAD and worktree status before resuming.
- Backing framework clone: `/home/shawn/workspace2/gpui-component`.
- Application: `examples/system_pulse`; pure model: `examples/system_pulse/model`.
- The existing `examples/system_monitor` is unchanged and may contain reusable real collector patterns.
- Verified fixture baseline: **275 tests**, affected-package formatting, strict all-target Clippy, native build, and independent reviews passed. Linux native interaction checks passed. This does **not** establish real collection.
- Full evidence: [workspace execution report](2026-09-04-workspace-visibility.md), including committed artifacts and interactive native driver.

## Current task state

The developer explicitly **confirmed** LIVE-001–013 and their falsifiers, then added NVIDIA support despite having no NVIDIA GPU installed. No further scope approval is needed for these collectors or subagents.

1. Complete: cited recon, agreed LIVE contract, implementation plan, roadmap/current commitment and executable baseline mechanism.
2. Complete: host collector crate and bounded sampling service, with independent spec and quality review.
3. Complete: real devices/readings/process rows, physical meters, stable state and test-only fixtures, with independent spec and quality review.
4. **In progress:** close the independent connection-attribution evidence gap in the collector.
5. Pending: full independent host/native acceptance and final review.

Activation is committed as `55087aa6` in the source worktree. Read `docs/spec/live-collection.md`, `docs/plans/real-system-readings.md`, and `docs/commitments/real-system-readings.md` there. Historical READ/VIEW/STATE specs remain Observed. The new source-root AGENTS working agreement was created from the existing-project skill's template; the design repository's existing AGENTS remains untouched.

Cairn's first committed baseline check failed on the actual production fixture dependency and retained receipts for all LIVE requirements. `cairn wake` reports **Resolvable: implement LIVE-001**. `.cairn/in-progress` records that source action. Do not rerun the aggregate repeatedly while implementation is incomplete; use focused tests and retain failing receipts.

The active collector follow-up worker owns only `examples/system_pulse/collectors/`. App/model integration passed both reviews; do not reopen source work there without a concrete new defect. One source implementer at a time; independent spec then quality review follows each coherent task. Root owns execution documentation and independent acceptance preparation.

Host preflight found 32 logical CPUs and two Radeon AI PRO R9700 GPUs, with readable utilization, VRAM, temperatures, average SoC power, graphics/memory clocks and fan RPM. Stable AMD IDs and exact sources are in source `docs/execution/real-system-readings/host-preflight.md`. NVIDIA backend API research and the verification design are adjacent documents. NVIDIA deterministic adapter tests and graceful-absence tests are required; actual NVIDIA hardware accuracy remains explicitly unverified until run on such hardware.

The collector is committed through `c217818d`; independent spec and quality reviews passed after fixing shared-MAC interface identity collisions, public counter-helper retention, and common-backend query timestamps. All 35 collector tests, scoped strict Clippy and formatting passed. Source `docs/execution/real-system-readings/collector-review.md` records the review results. Root independently checked 2,509 external counter brackets and 754 derived values in a real-host probe; this is supporting evidence, not final acceptance.

Live integration is committed through `9c6034b456a0a50d6a8b7a708d36dddd8d6cbd4b`, with independent spec and quality PASS. All 65 app/model tests and scoped strict Clippy passed independently. Review fixes preserve stale diagnostic timing/labels, absent summary units, stable exported process accessibility IDs, and coherent 16 MiB configuration read/write bounds. The original valid 451-panel oversized-state failure now round-trips, and rejected saves preserve previous state. See source `docs/execution/real-system-readings/integration-review.md`.

Real native smoke discovered 151 monitors, 862 sensors and over 1,200 processes. Root separately verified CPU keyboard focus/collapse at 960×640, expanded accessibility events, continuing real sample sequences, and clean app exit. Root also launched a real child named `pulse ) probe`, confirmed its PID/start/name and RSS conversion in collector snapshots, then confirmed exit. These are supporting checks; full native replay and exact unchanged-revision numeric matching remain pending.

Task 2a closes an acceptance evidence gap: connection readings currently retain only the derived count. The collector follow-up will preserve shared raw interface address ownership and TCP4/TCP6 local-address/state tokens with query windows/errors, excluding remote endpoints/ports/owners, so Python can independently recompute attribution. See the tracked plan and `acceptance-inventory.md`. No final acceptance or completion is claimed. Missing implementation must never be labeled unavailable hardware.

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

The old baseline used simulated readings. Committed integration uses real collection and has passed both reviews. Collector attribution evidence repair and full acceptance remain; inspect current state before judging completion. The prior verification report contains the complete affected-package commands and Linux native harness setup. Do not rerun all baseline checks without a reason; inspect status first and use focused checks as changes are made.
