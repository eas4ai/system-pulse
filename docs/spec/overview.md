# System Pulse

Status: Observed

System Pulse's reviewed implementation uses real host collector snapshots in a native GPUI workspace with separate panels, scrolling, independent panel/sensor collapse and persistent recovery. Physical quantities, actual process identities and test-only fixture isolation are implemented. Evidence: [collector](../../crates/collectors/src/host/mod.rs), [live mapping](../../src/live.rs), [workspace](../../src/workspace.rs), [module boundary](../../src/lib.rs).

The [full committed acceptance](../execution/real-system-readings/final-acceptance-pass.md)
passed 745 tests, independent Linux host comparisons and the complete native replay
on 2026-09-06. Cairn records passes for LIVE-001 through LIVE-013. Final adversarial
commitment review passed with no actionable findings, and Cairn returned Done. The record discloses four independently
explained ordinary-process exit gaps and the NVIDIA hardware, other native
platform and physical device-removal limits. The developer rejected simulated
production readings and confirmed real collection; the [handoff](../superpowers/execution/live-collection-handoff.md)
preserves that direction.

The cited [recon report](../recon.md) distinguishes observed behavior, documented intent, contradictions, and unverified claims. The historical fixture acceptance remains valid for its stated scope; it is not evidence of live metric accuracy.

## Reading order

Read [glossary](glossary.md), the relevant domain below, and [the agreed real-collection contract](live-collection.md). The domain partition and source-repository placement are recorded in [this decision](../decisions/adopt-system-pulse-beside-its-source.md).

## Spec map

| Domain | Prefix | Coverage |
| --- | --- | --- |
| [Readings](readings.md) | READ | Historical fixture generation, samples, history, and timer. |
| [Rendering](rendering.md) | VIEW | Historical compact readings, scales, and process table. |
| [Workspace state](workspace-state.md) | STATE | Historical identities, presentation, restore, and storage. |
| [Real collection](live-collection.md) | LIVE | Completed collection contract and preservation constraints. |
| [Intel and Apple GPU collection](gpu-collection.md) | GPU | Current agreed collector, memory-scope and native-evidence requirements. |
| Docking and accessibility | WV, existing contract | Preserved framework behavior; [approved workspace spec](../superpowers/specs/2026-09-04-workspace-visibility-design.md), [verified source record](../../docs/native-fixture-acceptance.md). |
| [Application completion](application.md) | APP | Process controls, complete customization, named presets, appearance, first-launch layout and Linux packaging from the original product scope. |
| Other framework examples, shell, website and reference projects | Outside this work | Workspace membership is defined in [Cargo.toml](../../Cargo.toml:3); this adoption does not redefine those products. |

READ/VIEW/STATE sections record the original fixture baseline; their behavior is not proposed as the target. The glossary and this overview describe the verified live implementation, with final commitment review passed. The developer confirmed LIVE-001 through LIVE-013 on 2026-09-04. The [roadmap](roadmap.md) names the active commitment; historical fixture-specific observations are not promoted into the target contract.
