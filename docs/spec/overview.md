# System Pulse

Status: Observed

System Pulse currently provides a native GPUI workspace with separate panels, scrolling, independent panel/sensor collapse, and persistent layout recovery. Its runtime readings and process rows are simulated. Evidence: [entry point](../../examples/system_pulse/src/main.rs:5), [fixture](../../examples/system_pulse/src/fixture.rs:11), [workspace](../../examples/system_pulse/src/workspace.rs:232).

The developer's intended product monitors the actual machine. The immediate work replaces runtime simulation with real collection while preserving the workspace behavior already verified. The developer rejected simulation as the delivered application and confirmed real collection; see the [restart handoff](/home/shawn/workspace2/task-manager/docs/superpowers/execution/live-collection-handoff.md:5).

The cited [recon report](/home/shawn/workspace2/task-manager/docs/recon.md) distinguishes observed behavior, documented intent, contradictions, and unverified claims. The historical fixture acceptance remains valid for its stated scope; it is not evidence of live metric accuracy.

## Reading order

Read [glossary](glossary.md), the relevant domain below, and [the proposed real-collection contract](live-collection.md). The domain partition and source-repository placement are recorded in [this decision](../decisions/adopt-system-pulse-beside-its-source.md).

## Spec map

| Domain | Prefix | Coverage |
| --- | --- | --- |
| [Readings](readings.md) | READ | Observed fixture generation, samples, history, and timer. |
| [Rendering](rendering.md) | VIEW | Observed compact readings, scales, and process table. |
| [Workspace state](workspace-state.md) | STATE | Observed identities, presentation, restore, and storage. |
| [Real collection](live-collection.md) | LIVE | Draft intended behavior and proposed falsifiers for this session. |
| Docking and accessibility | WV, existing contract | Preserved framework behavior; [approved workspace spec](/home/shawn/workspace2/task-manager/docs/superpowers/specs/2026-09-04-workspace-visibility-design.md), [verified source record](../../examples/system_pulse/NATIVE_ACCEPTANCE.md). |
| Process actions, full presets, styling, settings and packaging | Product scope | Retained in the [product specification](/home/shawn/workspace2/task-manager/docs/feature-spec-dockable-system-monitor.md:164); no claim that collection completes these areas. |
| Other framework examples, shell, website and reference projects | Outside this work | Workspace membership is defined in [Cargo.toml](../../Cargo.toml:3); this adoption does not redefine those products. |

Observed sections record what exists; their fixture behavior is not proposed as the target. The live-collection requirements remain Draft until their text and falsifiers are confirmed. No active Cairn commitment is created before that confirmation.
