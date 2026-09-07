# Real system collection

Status: Agreed 2026-09-04
Prefix: LIVE

The developer has confirmed the direction: the normal app displays real system readings; simulation belongs in tests. The developer confirmed this requirement text and its falsifiers on 2026-09-04. The existing simulation observations remain an accurate record of the defect's starting point.

The baseline evidence links below describe the original fixture implementation at `88343d5e`; they are not claims about the current runtime. Implementation reviews and focused checks are recorded in [execution notes](../execution/real-system-readings/). Final current evidence requires the committed acceptance mechanism.

## Scope and metric contract

This work replaces the fixture producer, discovery, process rows, and demonstration meter scaling in System Pulse. Linux is the first host-verification platform, following the [product specification](../feature-spec-dockable-system-monitor.md:13). Cross-platform system collection uses the pinned sysinfo dependency where supported. Native macOS/Windows acceptance retains separate evidence needs; Linux success is not a claim about them. The developer explicitly added NVIDIA support on 2026-09-04 despite having no NVIDIA GPU installed: an NVML adapter is included in this commitment. Its conversion, discovery, and failure paths require deterministic backend tests; this AMD-only host verifies graceful NVIDIA absence. Live NVIDIA hardware accuracy remains explicitly unverified until tested on such hardware.

The required monitor families and fields come from the [product's monitor definitions](../feature-spec-dockable-system-monitor.md:41):

| Monitor | Field coverage to account for |
| --- | --- |
| CPU | Overall and every logical core's utilization; frequency; temperature; load averages; process/thread counts; uptime. |
| GPU, per actual device | Utilization; VRAM used/total; temperature; power; clocks; fan readings in the units the backend actually supplies. A fan percentage is not RPM. |
| Memory | RAM used/total and composition where defined; swap used/total; page faults. |
| Volume | Capacity used/total; read/write throughput; IOPS; latency where the OS exposes a defensible mapping. Shared device I/O is labeled as device I/O, not invented per-volume attribution. |
| Interface | RX/TX rates and cumulative totals; connection count only at a scope the OS can attribute. System-wide connections are not assigned to every interface. |
| Processes | PID; name; CPU utilization; memory; disk I/O; threads; user. |

A capability report accompanies implementation: each field names its actual source, units, semantic scope, and availability reason. Every listed field with an accessible, attributable OS/device measurement is part of this delivery. Missing collector code blocks completion; it is not an unavailable-hardware result or a deferral. A source that cannot measure a quantity at the requested scope is reported with that specific limit. The implementation cannot define “supported” merely as the subset it happened to implement.

## Requirements and falsifiers

[LIVE-001] The production application MUST obtain displayed metric values from host collector snapshots.
Falsifier: changing host state leaves the app on its deterministic fixture sequence, or any displayed measurement comes from an invented value rather than an OS/backend observation.
Mechanism: `live-runtime-source` check for production fixture dependencies, collector integration tests, and a native host comparison captured by `native-live-readings`.
Baseline evidence: [fixture formula](../../examples/system_pulse/src/fixture.rs:76), [runtime feed](../../examples/system_pulse/src/workspace.rs:404), [missing collector dependency](../../examples/system_pulse/Cargo.toml:8).

[LIVE-002] The collector MUST discover monitors and sensors from the host's actual devices and capabilities.
Falsifier: a fake GPU/volume/interface remains present, a detected supported device is silently omitted, or a capability field is populated without a source.
Mechanism: `collector-discovery` tests with reordered, added, removed, unsupported, and permission-denied devices; native comparison with enumerated host devices and the capability report.
Baseline evidence: [fixed catalog](../../examples/system_pulse/src/fixture.rs:11).

[LIVE-003] The Processes view MUST render the current process snapshot with selection attached to process identity.
Falsifier: a synthetic row remains, rows are silently capped at the old 500/200 limits, or process exit/reordering/PID reuse moves selection to a different process.
Mechanism: `live-process-table` tests for empty snapshots, insertion/removal, sorting, and PID reuse; native launch/exit of a harmless child process with PID/name comparison against the OS.
Baseline evidence: [generated rows and fixed navigation](../../examples/system_pulse/src/panel.rs:247); the reference's truncation is also unsuitable: [system_monitor](../../examples/system_monitor/src/main.rs:128).

[LIVE-004] The collector MUST derive rate and utilization deltas using measured monotonic elapsed time and valid counter baselines.
Falsifier: warm-up produces a fabricated measured value, an irregular interval gives the wrong rate, or a reset/wrap/nonpositive elapsed time creates a spike, negative rate, or non-finite value.
Mechanism: `collector-deltas` tests with known byte/CPU counters at unequal intervals, first samples, resets, and failed reads; native rate comparison using independently sampled counters.
Baseline evidence: [synthetic timestamps](../../examples/system_pulse/src/fixture.rs:91); the existing sample model rejects [non-finite values](../../examples/system_pulse/model/src/readings.rs:32).

[LIVE-005] The meter layer MUST render readings according to their physical kind, unit, and scale.
Falsifier: a byte rate above 100 is clipped as a percentage, a capacity bar disagrees with used/total, a chart labels a quantity with the wrong unit, or an incompatible meter option becomes selectable.
Mechanism: `physical-meter-scales` tests covering percentage, capacity, rate, temperature, counter, and compound summaries, followed by native numeric/chart comparisons.
Baseline evidence: [percentage clamping](../../examples/system_pulse/src/meters.rs:29), [untyped meter choices](../../examples/system_pulse/model/src/presentation.rs:7); intended kinds: [product matrix](../feature-spec-dockable-system-monitor.md:97).

[LIVE-006] The application MUST label unavailable, warming-up, stale, and failed readings without presenting them as successful measurements.
Falsifier: a failed read becomes an unqualified zero, stale data appears current, an unavailable value loses its unit/reason, or backend failure is hidden behind a synthetic replacement.
Mechanism: `collector-availability` tests for individual sensor failure, whole-backend failure, recovery, and delayed snapshots; native permission/unsupported-backend inspection where reproducible.
Baseline evidence: [existing three-state reading model](../../examples/system_pulse/model/src/readings.rs:6), [compact formatter](../../examples/system_pulse/src/meters.rs:5). The implementation may model warm-up through explicit unavailable metadata rather than adding a redundant state.

[LIVE-007] Workspace persistence MUST keep presentation choices associated with stable real monitor and sensor identities.
Falsifier: discovery order, temporary absence, restart, or fixture-state migration attaches a choice to another device, destroys recoverable old input, or rejects a structurally valid saved device solely because it is temporarily absent.
Mechanism: `live-identity-persistence` tests and native mixed-state restart with device absence/reappearance; migration tests retain the original fixture file and prove that fixture IDs are never assigned to physical devices by position.
Baseline evidence: [fixture-only validator](../../examples/system_pulse/src/workspace.rs:94), [fixture storage path](../../examples/system_pulse/src/storage.rs:12), [existing invalid-input retention](../../examples/system_pulse/model/src/persistence.rs:18).

[LIVE-008] The sampling service MUST perform blocking host collection outside the UI update path.
Falsifier: a deliberately slow backend prevents scrolling, collapse, or keyboard navigation while its refresh is pending.
Mechanism: `collector-scheduling` test with a controlled slow backend and native responsiveness replay while collection runs.
Baseline evidence: the reference performs refresh in [the UI update](../../examples/system_monitor/src/main.rs:300); current app feed ownership is [WorkspaceView](../../examples/system_pulse/src/workspace.rs:322).

[LIVE-009] The sampling service MUST maintain one bounded collection-and-delivery pipeline at the selected global interval.
Falsifier: changing the interval creates overlapping polling loops, a slow UI accumulates unbounded snapshots, disappearing device identities accumulate unbounded history, or shutdown leaves collection running.
Mechanism: `collector-lifecycle` tests for interval changes, backpressure, device churn, and shutdown; support the product's 0.5/1/2/5-second values with a one-second default.
Baseline evidence: [one existing timer](../../examples/system_pulse/src/workspace.rs:322), [per-series history without key eviction](../../examples/system_pulse/model/src/readings.rs:44); intended intervals: [product spec](../feature-spec-dockable-system-monitor.md:205).

[LIVE-010] The workspace MUST preserve its existing separate-panel, scroll, collapse, focus, and recovery behavior during real sampling.
Falsifier: collection or discovery creates a tab group, hides/collapses content without the user's action, stops history because a panel is collapsed, traps focus/scrolling, or breaks saved-state recovery.
Mechanism: existing model/dock/native regression suites adapted to inject fixtures only in tests, plus `native-live-readings` repeating collapse, overflow, focus, and restart while actual samples advance.
Baseline evidence: [approved workspace contract](../superpowers/specs/2026-09-04-workspace-visibility-design.md), [verified baseline](../../examples/system_pulse/NATIVE_ACCEPTANCE.md).

[LIVE-011] The normal application MUST exclude fixture-generation controls and fixture-only device identities from its runtime interface.
Falsifier: normal launch exposes Advance fixture, fake GPU connect/disconnect, synthetic discovery reversal, or a fake device; a demonstration value is labeled as a live reading.
Mechanism: `live-runtime-source` check and native accessibility-tree inspection; tests retain deterministic injection through a test-only construction path.
Baseline evidence: [runtime toolbar](../../examples/system_pulse/src/workspace.rs:672), [entry title](../../examples/system_pulse/src/main.rs:21), [fixture module](../../examples/system_pulse/src/lib.rs:2).

[LIVE-012] The collector MUST implement each listed field for which the target OS and device provide an accessible, attributable measurement.
Falsifier: the capability report omits such a field or marks it unimplemented while the commitment is considered complete.
Mechanism: `collector-capability-coverage` check joins the required metric matrix to source/permission probes and adapter tests; an unimplemented accessible field fails the check. Unsupported attribution and denied permissions require recorded source evidence, not an adapter's absence.
Baseline evidence: the broader [product field list](../feature-spec-dockable-system-monitor.md:41) exceeds the [fixture catalog](../../examples/system_pulse/src/fixture.rs:11).

[LIVE-013] The host verifier MUST reject unexplained differences or missing mandatory comparisons under the predeclared quantity definitions, comparison bounds, and process-exit observation policy.
Falsifier: a wrong unit, normalization, counter interval, out-of-bound value, or unexplained missing comparison passes; an exited-process gap counts as a verified comparison; controlled-process brackets are missing; or the verifier chooses its bounds or mandatory coverage after seeing the app's result.
Mechanism: `native-live-readings` verifier records the source, formula, units, monotonic sample window, raw counters, and comparison bound before capture; verifier regression cases intentionally inject each mismatch and require failure.
Baseline evidence: [existing acceptance](../../examples/system_pulse/NATIVE_ACCEPTANCE.md) proves fixture interactions and supplies no host-accuracy comparison.

Comparison rules: identical captured inputs require exact numeric agreement before documented display rounding. Independent live readings use recorded bracketing sample windows and bounds derived from source precision and measured variation; unbounded percentage tolerances are not acceptable. Rate checks recompute counter deltas over their recorded elapsed time. CPU/process checks state the CPU denominator explicitly, including whether process usage may exceed 100%; memory checks name the exact used/available definition. GPU and disk comparisons name the device and attribution scope. A mismatch fails acceptance unless its explanation fits those predeclared bounds.


## Process-exit observation policy

Agreed 2026-09-05: the developer approved the process-exit observation proposal and the related escalation. The earlier universal after-counter condition is replaced only for independently proven exits.

Every available process reading retains exact source, PID/start identity, unit, normalization and counter arithmetic checks. Independent brackets remain mandatory for non-process counters and the predeclared controlled child whose lifetime covers capture. Other real processes receive the same attempted comparisons. Only independently documented exit of the observed identity may explain a missing after-counter bracket; its raw readings, query windows and terminal stat evidence remain recorded, and the missing comparison is labeled unverified, never passed or assigned an inferred value. Available comparison bounds still apply.

Census absence alone does not prove exit. Permission errors, ambiguous identities or PID reuse, missing before observations, and unexplained gaps remain failures. Acceptance may complete with these disclosed exited-process gaps only when the controlled workload and every other mandatory comparison pass. Coverage and the controlled workload are declared before capture. Previous failed captures retain their original outcomes.

## Execution commitment

Current commitment: [real-system-readings](../commitments/real-system-readings.md), covering LIVE-001 through LIVE-013. The observed READ/VIEW/STATE requirements describe the starting point; fixture-specific observations will not be promoted into the target contract.

The mechanism declarations in `.cairn/mechanisms/` bind the acceptance groups to executable checks and declared inputs. Missing checks and failing checks are implementation work, never passing evidence. Collector units, snapshot delivery, typed rendering, dynamic identity/state integration, and native host verification are the implementation boundaries. Existing model and native tests remain preservation constraints.

Done requires actual host evidence: discovered devices; real CPU/RAM values compared with OS sources using documented definitions; network/disk deltas over recorded intervals; real process appearance/disappearance; supported GPU readings; truthful unavailable cases; and all preserved workspace interactions. A simulated run or an app window opening does not satisfy that gate.

Process termination, full preset CRUD, final visual styling, and packaging are retained in the broader product map. They are not quietly reclassified as completed by this collection work.
