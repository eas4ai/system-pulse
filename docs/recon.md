# System Pulse reconnaissance

Status: Observed. Inspected 2026-09-04 at implementation commit `9f2f3ad0382ce4c7ce0aadfc0c4ed88588ad95af`.

This is a historical inspection of the fixture baseline. Source links identify what was inspected at that revision; current files have since changed. Reviewed live collectors, snapshot integration, attribution evidence and native repaint fixes now exist. The [current source overview](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/docs/spec/overview.md) and [handoff](superpowers/execution/live-collection-handoff.md) track them. Full independent host/native acceptance and final Cairn evidence remain pending; the original findings below are preserved rather than rewritten as a new inspection.

The session's work is already known: replace runtime simulation with readings from the user's machine. That direction was confirmed before the harness restart; it is recorded in the [handoff](superpowers/execution/live-collection-handoff.md:5). This report describes existing behavior, not approval to preserve every observed behavior.

## Repository boundary

`S` below means `/home/shawn/workspace2/task-manager-worktrees/workspace-visibility`. The application is `S/examples/system_pulse`; this repository retains design inputs and third-party snapshots. The source placement follows the [product specification](feature-spec-dockable-system-monitor.md:15) and [implementation manifest](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/Cargo.toml:20).

The formal adoption spec lives at [S/docs/spec/overview.md](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/docs/spec/overview.md), beside the source whose committed inputs Cairn will verify. The [decision record](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/docs/decisions/adopt-system-pulse-beside-its-source.md) records that choice. Root `AGENTS.md` is preserved under the user's explicit instruction.

## Exists

| Finding | Evidence |
| --- | --- |
| The app is a Rust 2024 GPL-3.0-or-later workspace package using GPUI, gpui-base, gpui-component, smol, and a pure model crate. Its manifest has no host-collector dependency. | [App manifest](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_pulse/Cargo.toml:1), [model manifest](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_pulse/model/Cargo.toml:1). |
| Cargo.lock pins GPUI to Zed `f66ed39`; the existing monitor uses sysinfo 0.37.2. A separate sysinfo 0.31.4 entry also exists. | [GPUI lock entry](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/Cargo.lock:3383), [sysinfo entries](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/Cargo.lock:9290). |
| The native entry point opens a minimum 960×640 window titled Fixture mode and calls `WorkspaceView::new(true, ...)`. Here `true` enables the timer and persistence, not host collection. | [Entry point](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_pulse/src/main.rs:5), [constructor](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_pulse/src/workspace.rs:232). |
| A fixed catalog defines CPU, two fake GPUs, memory, one fake volume/interface, processes, and settings. A tick formula creates values and deliberately cycles unavailable/stale status. | [Catalog](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_pulse/src/fixture.rs:11), [sample generator](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_pulse/src/fixture.rs:76). |
| A one-second timer calls `advance`; `advance` inserts generated samples and notifies panels. There is no host snapshot boundary in this path. | [Timer](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_pulse/src/workspace.rs:322), [advance](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_pulse/src/workspace.rs:404). |
| Samples carry timestamp, optional scalar, formatted text, unit, and status. History keys use monitor/sensor strings; each series has a capped deque, finite-value checks, and increasing timestamps. The number of series itself is not capped. | [Reading model](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_pulse/model/src/readings.rs:13), [history insertion](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_pulse/model/src/readings.rs:60). |
| Separate panel policy, scrollable overflow, explicit independent collapse, retained dimensions, and keyboard focus behavior exist. | [Dock setup](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_pulse/src/workspace.rs:287), [panel implementation](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_pulse/src/panel.rs), [native acceptance record](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_pulse/NATIVE_ACCEPTANCE.md:7). |
| Process rows are generated from indices, with `1000 + index` PIDs, synthetic names, and index-based CPU percentages; navigation and row count are fixed at 500. | [Process table](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_pulse/src/panel.rs:247). |
| Graphs clamp all scalar kinds to 0–100. Unavailable and stale text is explicit, and unavailable rows retain units. | [Meter rendering](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_pulse/src/meters.rs:5). |
| Presentation state is independent of history; restore retains invalid raw input and blocks ordinary autosave until recovery. Storage defaults to `system-pulse-fixture` with an environment override. | [Presentation](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_pulse/model/src/presentation.rs:34), [restore](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_pulse/model/src/persistence.rs:18), [storage](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_pulse/src/storage.rs:12). |
| Layout validation rejects monitor IDs outside the fixture catalog, coupling restored layouts to synthetic identities. | [validate_dock](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_pulse/src/workspace.rs:72). |

## Documented

| Coverage | Evidence |
| --- | --- |
| The product spec describes real CPU, GPU, memory, disk, network, and process data, with auto-discovery and sysinfo/platform GPU backends. | [Monitor definitions](feature-spec-dockable-system-monitor.md:41), [data layer](feature-spec-dockable-system-monitor.md:236). |
| The narrower approved workspace plan deliberately specified a fixture proof and deferred production collection. Its completion evidence accurately describes that limited result. | [Plan scope](superpowers/plans/2026-09-04-workspace-visibility.md:15), [execution evidence](superpowers/execution/2026-09-04-workspace-visibility.md:1). |
| The app README documents fixture behavior, persistence, minimum geometry, and native repeat scenarios. | [README](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_pulse/README.md:1). |
| Retained results record 275 affected-package tests, formatting, Clippy, and a native build; Linux native evidence covers docking, collapse, scrolling, focus, persistence, and recovery. These were prior checks, not rerun for this recon. | [Command results](superpowers/execution/artifacts/2026-09-04/checks/results.json), [native report](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_pulse/NATIVE_ACCEPTANCE.md:7). |
| Framework CI declares Linux/macOS/Windows workspace tests. Its explicit Clippy job lists framework packages, not a dedicated System Pulse all-target check. | [CI workflow](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/.github/workflows/ci.yml:15). |
| Recent source history contains the fixture, model, policy, geometry, focus, and accessibility changes; the runnable worktree is on `feat/system-pulse-workspace`, separate from `main`. | [Commit anchors](superpowers/execution/2026-09-04-workspace-visibility.md:72); recon commands: `rtk git log -30 --oneline`, `rtk git branch --list`, and `rtk git status --short` in `S`. |

## Contradicted or incomplete

These findings compare product intent with current code. They do not accuse the fixture implementation of violating its narrower workspace plan, and they do not silently revise that historical plan.

| Intended behavior | Current behavior | Consequence |
| --- | --- | --- |
| Real metrics from auto-discovered hardware: [spec](feature-spec-dockable-system-monitor.md:217). | Hard-coded catalog and formula: [fixture.rs](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_pulse/src/fixture.rs:11). | The app cannot yet monitor the user's machine. |
| Real process columns and CPU sorting: [spec](feature-spec-dockable-system-monitor.md:75). | Three fabricated columns and 500 rows: [panel.rs](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_pulse/src/panel.rs:247). | Collection must replace row data, identity, selection bounds, and summaries together. |
| Meter compatibility varies by SensorKind: [spec](feature-spec-dockable-system-monitor.md:97). | Five meter variants have no sensor-kind metadata; graph paths clamp values to percentages: [model](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_pulse/model/src/presentation.rs:7), [meters](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_pulse/src/meters.rs:29). | Passing byte rates or capacities directly into current graphs would misrepresent real values. |
| Stable identities survive missing hardware: [workspace spec](superpowers/specs/2026-09-04-workspace-visibility-design.md:79). | Layout validation accepts only known fixture IDs: [validator](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_pulse/src/workspace.rs:94). | Dynamic discovery and restore validation need a shared identity contract. |
| Configurable 0.5/1/2/5-second sampling: [spec](feature-spec-dockable-system-monitor.md:205). | A fixed one-second timer generates synthetic timestamps: [timer](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_pulse/src/workspace.rs:327), [sample](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_pulse/src/fixture.rs:91). | Rate computation needs measured monotonic elapsed time, independently of display cadence. |
| Product styling, full presets, process actions, and packaging are in the broader product direction: [spec](feature-spec-dockable-system-monitor.md:164). | Fixture scope expressly excludes them: [acceptance record](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_pulse/NATIVE_ACCEPTANCE.md:29). | Keep these visible in the spec map; real collection alone will not complete the whole product. |

## Existing real collector reference

`S/examples/system_monitor` is useful source evidence, not a ready backend to transplant.

| Finding | Evidence |
| --- | --- |
| It retains sysinfo `System`/`Disks` and reads real CPU, RAM, process, and volume-capacity fields. | [Manifest](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_monitor/Cargo.toml:14), [refresh](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_monitor/src/main.rs:319), [process mapping](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_monitor/src/main.rs:113). |
| It refreshes synchronously inside the GPUI update, truncates process data to 200 rows, and uses 500-ms samples with an integer increment formatted as seconds. | [Timer/refresh](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_monitor/src/main.rs:300), [sorting](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_monitor/src/main.rs:128), [time axis](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_monitor/src/main.rs:338). |
| It implements neither network nor GPU collection; graphics manifest dependencies alone do not supply a GPU backend. | [Example source](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_monitor/src/main.rs), [platform dependencies](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_monitor/Cargo.toml:18). |
| Pinned sysinfo exposes CPU/process warm-up and refresh controls, byte counters, and process start times. Its Linux network backend can substitute zero on failed counter reads; that needs an explicit availability strategy. | [CPU refresh docs](/home/shawn/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/sysinfo-0.37.2/src/common/system.rs:172), [network API](/home/shawn/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/sysinfo-0.37.2/src/common/network.rs:128), [Linux read helper](/home/shawn/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/sysinfo-0.37.2/src/unix/linux/network.rs:24). |

## Blast radius

| Area | Files and preserved behavior |
| --- | --- |
| Entry and collection | `S/examples/system_pulse/src/{main,lib,fixture,workspace}.rs`: replace runtime generation, timer ownership, catalog discovery, and fixture controls. [Current path](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_pulse/src/workspace.rs:232). |
| Readings and rendering | `S/examples/system_pulse/model/src/readings.rs`, `src/meters.rs`, `src/panel.rs`: real units, status, scale, process rows, and bounded history. [Sample boundary](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_pulse/model/src/readings.rs:13). |
| Identity and state | `model/src/{presentation,persistence}.rs`, `src/{workspace,storage,panel}.rs`: retain choices while real devices appear/disappear; preserve invalid-input recovery. [State types](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_pulse/model/src/presentation.rs:54). |
| Tests and manifests | App/model manifests, Cargo.lock, `src/native_tests.rs`, `model/tests/{readings,presentation,persistence}.rs`; add collector tests and host verification rather than treating fixture tests as host evidence. [Current test entry](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_pulse/src/lib.rs:4). |
| Framework preservation | Dock policy, geometry, resizable behavior, and AT-SPI remain regression constraints; no new framework redesign is assumed. [Prior evidence](superpowers/execution/2026-09-04-workspace-visibility.md:72). |

## Unverified

| Limit or question | Evidence / required next check |
| --- | --- |
| Actual host GPU devices, driver APIs, permissions, and supported sensors were not probed in this recon. | No host-collection results exist in the [fixture evidence](superpowers/execution/2026-09-04-workspace-visibility.md:17); inspect the host during collector design. |
| Native metric accuracy, process churn, counter resets, and collection under permission failures have no app acceptance evidence yet. | Current [native tests](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_pulse/src/native_tests.rs) use the fixture; proposed mechanisms are in the [live-collection draft](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/docs/spec/live-collection.md). |
| Reference snapshot contents and licenses were not re-audited this pass. | Preserve the earlier [reference review](superpowers/research/2026-09-04-reference-review.md); inspect any source before borrowing implementation. |
| CI declarations are not proof of a current remote CI run or native acceptance on macOS/Windows. | [Workflow](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/.github/workflows/ci.yml:15), [Linux-only acceptance limit](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_pulse/NATIVE_ACCEPTANCE.md:29). |
| Cairn adoption has not reached an agreed commitment. | Initial `rtk proxy cairn wake` returned exit 3: no `docs/spec/roadmap.md`. The confirmation stage comes before creating an executable commitment; new Observed/Draft text is not contract. |

## Recon validation

The installed Cairn lint ran as `rtk proxy node /home/shawn/workspace2/cairn/scripts/spec-lint.mjs docs/spec` from `S` and passed. The root validated all eight new report/spec/review documents for local link targets, cited line bounds, and balanced code fences; those checks passed. No application tests were rerun because this pass changes documentation only.

`rtk proxy cairn wake` and `rtk proxy cairn check` ran in `S`; both returned exit 3 because there is no roadmap yet. No passing evidence or Done verdict is claimed. The invoked adoption skill's confirmation stage precedes the active roadmap/commitment. Its Stage 3 will install the working-agreement template in `S/AGENTS.md`, which is currently absent; the existing design-repository `AGENTS.md` stays untouched.
