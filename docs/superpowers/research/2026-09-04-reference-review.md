# Dockable System Monitor: Reference Review

## Status and purpose

Research for the Superpowers spec and planning workflow. Findings below come from source inspection and a browser preview; reference applications were not built or tested. The user approved the focused workspace spec. Broader product boundaries below remain proposals.

The repository contains product/design documents and five source snapshots, plus TMOG screenshots. It has no application crate; the commits added during this work contain documentation. The initial documents inside `docs/files.zip` matched their extracted copies before the correction below; the archive remains historical input.

## Confirmed correction: no tabs

The user clarified on 2026-09-04 that tabbed panels were a model drafting mistake. All visible monitors occupy separate regions. Users split, stack, resize, move, show, and hide panels; they do not group them into tabs. Settings follows the same rule.

The user further clarified that scrolling is preferable to hiding panels behind a click. Every enabled panel stays in the workspace at a readable size; panels outside the viewport are reached by scrolling. Window resizing must not automatically change panel visibility. The feature spec now includes workspace overflow behavior and an acceptance scenario that also covers nested process-table scrolling.

The user then approved explicit collapse at both levels: panel headers retain compact current summaries, and sensor rows retain labels and current values while detailed meters fold away. Content starts expanded, expands in place, and remembers choices with the layout. The user reviewed and approved the resulting [workspace spec](../specs/2026-09-04-workspace-visibility-design.md) on 2026-09-04.

The default arrangement is CPU above GPU on the left, Memory above Processes on the right. When no GPU is available, CPU fills the left region. This correction is applied to the [feature spec](../../feature-spec-dockable-system-monitor.md) and [design prompt](../../claude-design-prompt.md).

The framework integration must prevent tab merging, not merely hide the tab strip. The acceptance condition is one panel per visible region, with no action or restored state introducing a group of mutually hidden panels. Tabs are not an optional mode. A framework limitation does not relax this requirement.

## Reference findings

Paths below identify the supplied snapshots; they do not imply current upstream behavior.

| Reference | Useful evidence | Implication for our specs |
| --- | --- | --- |
| TuxManager 1.0.7 | `src/os/processrefreshservice.cpp:135` uses a worker thread. `src/processeswidget.cpp:357` bounds refresh requests and preserves interaction state. `src/historybuffer.h:114` provides O(1) bounded history. | Separate collection from panels; bound pending refresh work; retain selection by identity; use real ring buffers. Hardware sampling in `src/metrics.cpp:132` is still synchronous, so do not assume every reference collector is isolated. |
| neohtop 1.2.0 | `src-tauri/src/monitoring/system_monitor.rs:56` computes cached memory with an expression that is identically zero; line 86 subtracts aggregate unsigned network counters without reset guards. `process_monitor.rs:98` caches metadata by PID without pruning or checking start time. | Define formulas and counter lifecycle before UI formatting. Test reset, removal, PID reuse, and memory reconciliation with deterministic fixtures. Its sysinfo 0.29 API is historical reference, not the new app's dependency choice. |
| TaskExplorer 1.8.0 | `TaskExplorer/API/SystemAPI.cpp:50` separates collection onto a thread. `API/Windows/WindowsAPI.cpp:847` uses PID plus creation time. `API/MiscStats.h:111` handles initial and decreasing counters. | Adopt sampling separation, process incarnation identity, and explicit warmup/reset behavior. Its privileged service fallback and critical-process bypass conflict with our ordinary-user contract. |
| TaskManager 1.0.3 | `Sources/TaskManager/Model/SamplingEngine.swift:20` uses an actor and snapshots. `Views/Components/ProcessTable.swift:142` reuses visible cells. `System/GPUSampler.swift:29` distinguishes unified memory metadata but samples the busiest accelerator. | Preserve responsive table updates; do not confuse one sampled accelerator with complete per-device enumeration or unified memory with dedicated VRAM. |
| task-manager-for-mac 1.0.1 | `Sources/TaskManager/System/SystemMonitor.swift:176` drops overlapping ticks. `System/GPUSampler.swift:19` keys accelerators by display name and substitutes values when readings are absent. `docs/limitations.md:151` describes APFS attribution limits. | Bound sampling work; define stable device identity and unavailable readings. Do not copy privileged helper installation or treat physical-device traffic as per-volume traffic. |
| TMOG screenshots | `reference/tmog.org/` shows dense numeric tables, per-core charts, explicit unavailable values, and subsystem colors. | Useful visual references. Services, startup apps, NPU monitoring, and other visible features do not expand iteration 001. Screenshots cannot establish backend accuracy or performance. |

Reference roots: [TuxManager](../../../reference/TuxManager-1.0.7/), [neohtop](../../../reference/neohtop-1.2.0/), [TaskExplorer](../../../reference/TaskExplorer-1.8.0/), [TaskManager](../../../reference/TaskManager-1.0.3/), [task-manager-for-mac](../../../reference/task-manager-for-mac-1.0.1/), [TMOG](../../../reference/tmog.org/).

## Framework evidence

The `eas4ai/gpui-component` fork was inspected at commit `ba3433f0740ee5ba2b1db459af49229caf0c1bcc`. The workspace plans use this source baseline; it is not a production dependency lock.

- The [workspace manifest](https://github.com/eas4ai/gpui-component/blob/ba3433f0740ee5ba2b1db459af49229caf0c1bcc/Cargo.toml) contains `gpui-base`, `gpui-component`, and `examples/system_monitor`. The existing example is a useful integration reference, not the requested product.
- The [dock presentation module](https://github.com/eas4ai/gpui-component/blob/ba3433f0740ee5ba2b1db459af49229caf0c1bcc/crates/ui/src/dock/mod.rs) supplies `DockSkin::dock_area`, re-exports behavior types, and exposes the presentation layer. Styled panels also implement the base behavior trait and use `panel_handle` at the presentation boundary.
- The [panel registry](https://github.com/eas4ai/gpui-component/blob/ba3433f0740ee5ba2b1db459af49229caf0c1bcc/crates/base/src/dock/registry.rs) reconstructs panels from `PanelBuildContext`. Unknown panel state is retained through a placeholder. Application hardware identity and missing-device presentation still need their own contract.
- The [system-monitor example](https://github.com/eas4ai/gpui-component/blob/ba3433f0740ee5ba2b1db459af49229caf0c1bcc/examples/system_monitor/src/main.rs) calls collection inside an entity update and uses a point counter for history labels. Borrow its initialization and component integration, not its polling architecture or time-axis semantics.
- The [dock example](https://github.com/eas4ai/gpui-component/blob/ba3433f0740ee5ba2b1db459af49229caf0c1bcc/crates/story/examples/dock.rs) demonstrates serialization and debouncing, but writes directly to a file. Product persistence needs an explicit failure and recovery contract.

The fork's lockfile resolves GPUI to Zed revision `f66ed399cdde86092af8af3dc7b418abf45f37f8` and the system-monitor example's sysinfo dependency to 0.37.2. Validate the complete compatible dependency set before choosing versions. The [sysinfo documentation](https://docs.rs/sysinfo/latest/sysinfo/) confirms that differential metrics need retained collection state and repeated refreshes; indiscriminately refreshing everything costs more than selecting required fields.

## Mockup assessment

### Dock integration finding

At the inspected framework revision, ordinary center drops merge panels, `add_panel` inserts into an existing group, and loading state accepts multi-panel groups. The public lock also disables the required edge dragging, so it is not a suitable solution. See [drop handling](https://github.com/eas4ai/gpui-component/blob/ba3433f0740ee5ba2b1db459af49229caf0c1bcc/crates/base/src/dock/tab_group.rs#L625-L673) and [programmatic insertion](https://github.com/eas4ai/gpui-component/blob/ba3433f0740ee5ba2b1db459af49229caf0c1bcc/crates/base/src/dock/dock_area.rs#L393-L412).

The implementation plan must include an enforceable policy that allows splits and rejects merging. Reject invalid moves before removing the source panel; provide insertion into a new split; validate restored layouts before applying them. Acceptance tests must prove that center/header drops cannot merge panels, rejected moves preserve the source, re-enabled panels get separate regions, and restored state cannot introduce tabs. This is a source-derived integration finding, not a runtime-verified patch.

### Existing visual artifact

`docs/System Pulse.html` was opened in a browser and its bundled template inspected. It contains one dark first-launch screen with generated example data. Its 1360-pixel-wide app window shows CPU above GPU, and Memory above Processes. This supports the corrected split layout but does not demonstrate docking, settings, process controls, or minimum-window behavior.

Use its density, hierarchy, numeric typography, and panel separation as visual input. The example data mixes Apple/unified-memory labels with a discrete Radeon and Linux process names; those labels are not a platform contract. The requested light theme and additional screens still need acceptance coverage.

## Contracts for the remaining product specs

1. **Repository placement.** The workspace implementation plan follows the source spec: a new application crate in `eas4ai/gpui-component`. This separate repository retains the design inputs and plans.
2. **Platform delivery.** Distinguish cross-platform architecture from which platforms and hardware must pass acceptance in the first implementation cycle. Linux-first is a proposal, not an approved scope reduction.
3. **Metric semantics.** Specify canonical units, process CPU normalization, memory composition, first samples, actual elapsed-time rate calculation, and counter reset rules. The Mac references disagree about CPU time conversion; validate against native API documentation and controlled measurements.
4. **Capability and freshness.** Distinguish measured zero from warming up, unsupported, permission denied, stale, disconnected, and failed. History should show gaps rather than fabricated measurements.
5. **Stable identity.** Separate display names and enumeration ordinals from hardware identity. Use PID plus process start identity for rows, caches, histories, and actions. Define reconnect and device replacement behavior.
6. **Disk attribution.** Separate mounted-volume capacity from block-device I/O. Specify how shared backing devices, APFS, LVM/RAID, virtual filesystems, and removable media appear without double counting.
7. **GPU coverage.** Define support per device and sensor. DXGI enumeration does not itself establish all promised sensors; the Windows reference uses additional mechanisms. The examined DRM fallback is not universal. Decide Intel Linux coverage and fallback precedence explicitly.
8. **Polling and delivery.** One owner per collector, bounded pending work, coherent snapshots, slow-backend isolation, cancellation, and shutdown. Panel visibility must not create duplicate collectors.
9. **History.** Choose duration, memory ceiling, timestamps, gap handling, interval-change behavior, suspend/resume behavior, and limits on retained disconnected-device histories. Changing a meter must not reset collected history.
10. **Meter model.** Reconcile the compatibility table with the promised memory composition bar and per-core bar grid. A capacity sensor currently allows only number/bar, but the spec also promises memory history charts. Define compound meters or additional sensor types explicitly.
11. **Panel interaction.** Enforce separate split regions without tab merging, including restored layouts. Preserve readable sizes and scroll to overflow panels. Choose sensor ordering controls; the source spec leaves menu dragging versus in-panel dragging undecided. Provide a recovery action when all monitors are explicitly hidden.
12. **Process actions.** Preserve the selected process incarnation during sorting and refresh. Define stale selection, permission denial, exit races, and pending outcomes. A successful signal is not proof of exit. Windows graceful/force terminology needs platform-specific behavior.
13. **Configuration and presets.** Define schema versions, atomic replacement, validation, malformed/future-state recovery, failed writes, absent hardware, and dirty preset semantics. Decide whether polling interval belongs to a preset; the current descriptions are inconsistent.
14. **Performance and usability.** Turn 120fps into a measurable target with named hardware, workload, window size, refresh rate, and percentile criteria. Separate render cadence from polling cadence. Specify keyboard operation, minimum size, and overflow behavior.
15. **Verification.** Map each requirement to a falsifier and evidence method. Fixture tests should cover rates, resets, identity, history, configuration, and per-device GPU isolation. Native smoke tests and rendering measurements need named target environments.

## Approaches for discussion

| Approach | Benefit | Cost |
| --- | --- | --- |
| **Working slices with shared contracts — recommended** | Prove live data, separate docking, and restoration together early; add monitors against stable data contracts. | Requires agreement on the first acceptance platform and a few foundational semantics. |
| All platform backends first | Exposes capability differences before UI work. | Delays usable software and risks designing interfaces without panel integration feedback. |
| Complete UI prototype first | Quickly explores density, resizing, and customization. | Leaves the hardest metric, identity, and persistence problems unresolved; the existing mockup already supplies visual direction. |

## Proposed spec and plan sequence

The approved workspace spec now has a [four-part implementation plan](../plans/2026-09-04-workspace-visibility.md). It first proves separate docking, scrolling, collapse, and restoration with fixtures. The following boundaries address the remaining product work; each approved spec should receive its own plan under `docs/superpowers/plans/`.

1. **Foundation and first working slice:** repository/dependency setup, metric types, clock/fixture seams, live CPU and Memory, separate split panels, basic history, minimal versioned restoration, and integration proof that tab merging is disabled.
2. **Process table and actions:** stable row identity, sorting/filtering, virtual rendering, selection continuity, safe process commands, and observable outcomes.
3. **Device monitors:** Network, storage, and GPU in separately testable increments; each delivers discovery, capability states, sampling, panel rendering, and restoration together.
4. **Customization and presets:** sensor visibility/order, compatible meter choices, docked settings, complete themes/fonts, built-in presets, and robust persistence recovery.
5. **Platform completion and release evidence:** remaining backends, native packaging, hardware acceptance, performance measurements, and requirement evidence closure.

The first slice is not a redefinition of iteration 001. The full feature set remains the product target unless the user approves a narrower release boundary.

## Workflow checklist

- [x] Inspect product/design documents, reference source, framework examples, and mockup.
- [x] Record and verify the user's no-tabs correction and preference for scrolling to overflow panels.
- [x] Assess visual companion: current questions concern architecture and scope; use text for this stage.
- [x] Write and audit the focused workspace visibility/collapse spec after the user confirmed that interaction direction.
- [x] Obtain user approval of the written workspace spec.
- [x] Map the approved workspace requirements to four executable plans and verified framework APIs.
- [x] Audit the plans for requirement coverage, API consistency, patch composition, and documentation checks.
- [ ] Confirm the first release's platform acceptance scope during the remaining product-spec discussions. Planning follows the original feature spec's application-crate placement in the gpui-component workspace unless the user corrects it.
- [ ] Review approaches and the proposed design boundaries with the user.
- [ ] Write the agreed design specs and audit consistency, scope, and acceptance criteria.
- [ ] Obtain review of written specs, then write and verify executable implementation plans.


## User baseline and collection cross-check, 2026-09-06

The user identifies neohtop as their current daily task manager and its lack
of GPU statistics as a gap. Keep it as a usability reference alongside the
other supplied examples. This is context for the agreed System Pulse work;
it does not change the LIVE commitment or request a port of neohtop.

A focused source reread of the supplied neohtop 1.2.0 snapshot confirms that
`src-tauri/src/commands.rs:30` returns processes and system statistics together,
and `src/lib/stores/processes.ts:54` applies them in one store update while
reattaching selection by PID. `src/routes/+page.svelte:56` handles filtering,
sorting and pagination; lines 101–109 schedule collection separately from
those presentation choices. The one-second setting is mapped to 1.5 seconds
in this snapshot, so that timing is not System Pulse's sampling contract.
System Pulse retains the agreed PID/start identity and physical GPU coverage.

TuxManager 1.0.7 supplies a complementary scheduling example:
`src/os/processrefreshservice.cpp:135` puts collection on a worker thread,
and `src/processeswidget.cpp:357` coalesces requests when one is already in
flight. These references support coherent snapshots, bounded work and
interaction-state preservation. They do not establish the cause of System
Pulse's current diagnostic publication delay. That separate investigation
retains its failed capture and opt-in stage-tracing plan.

This reread used local snapshots only. No reference application was modified,
built or runtime-tested, and no upstream-current claim is made.
