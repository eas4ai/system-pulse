# Glossary

Status: Observed

These definitions describe the reviewed live implementation through `5d38680e`, not final acceptance. Historical fixture observations remain in the earlier READ/VIEW/STATE records; the current LIVE commitment still requires independent host/native acceptance.

| Term | Meaning and evidence |
| --- | --- |
| Monitor | A panel identity and summary. The collector describes an actual monitor's kind and summary sensor; the presentation descriptor also retains sensor metadata for restoration. [Collector types](../../examples/system_pulse/collectors/src/types.rs:34), [presentation](../../examples/system_pulse/model/src/presentation.rs:203). |
| Sensor | A separately identified quantity with physical kind/unit, actual source and semantic scope. [SensorDescriptor](../../examples/system_pulse/collectors/src/types.rs:69). |
| Reading | Optional physical value/total, availability/reason and raw source observations, before presentation formatting. [Reading](../../examples/system_pulse/collectors/src/types.rs:97). |
| Sample | Monotonic timestamp, optional physical scalar/total, quantity, formatted text/unit, status and reason used by presentation/history. [Sample](../../examples/system_pulse/model/src/readings.rs:15). |
| Availability / ReadingStatus | Collector states are Available, WarmingUp, Unavailable and Failed. Presentation uses Current plus those latter states and elapsed Stale; only Current values form chart segments. [Collector availability](../../examples/system_pulse/collectors/src/types.rs:80), [presentation status](../../examples/system_pulse/model/src/readings.rs:6). |
| HistoryStore | Bounded deques keyed by monitor/sensor identity; absent keys are evicted. Marking the latest observation stale does not add a sample. [HistoryStore](../../examples/system_pulse/model/src/readings.rs:60). |
| Meter | Number, Sparkline, Line, Bar or Radial, selected only when compatible with the physical quantity. [Presentation](../../examples/system_pulse/model/src/presentation.rs), [meters](../../examples/system_pulse/src/meters.rs). |
| Workspace | Serializable dock JSON, panel/sensor preferences, sampling interval and retained monitor metadata. [Workspace](../../examples/system_pulse/model/src/presentation.rs:133). |
| WorkspaceView | GPUI owner of docking, snapshot delivery, presentation, persistence and commands. Blocking collection lives in the background service. [WorkspaceView](../../examples/system_pulse/src/workspace.rs). |
| PanelState / SensorState | Independent visibility/collapse and retained sizing, ordering or meter choice; distinct from measurement availability. [Presentation](../../examples/system_pulse/model/src/presentation.rs). |
| Session | Workspace and optional rejected original input retained during recovery. [Persistence](../../examples/system_pulse/model/src/persistence.rs). |
| Separate | Dock policy preventing multi-panel tab groups while permitting split movement. Keyboard Tab remains ordinary focus navigation. [Workspace](../../examples/system_pulse/src/workspace.rs). |
| Fixture | Deterministic test-only input. The normal library excludes fixture generation and the app consumes real snapshots. [Module boundary](../../examples/system_pulse/src/lib.rs), [test fixture](../../examples/system_pulse/src/fixture.rs). |
| Collector snapshot | Owned descriptors, readings, process identities, diagnostics, capture times and shared network-attribution observations. [Snapshot](../../examples/system_pulse/collectors/src/types.rs:6). |
| Raw observation / clock anchor | Original integer/decimal source operands and query windows; an anchor relates the collector's monotonic origin to wall time with bounded read uncertainty. [Types](../../examples/system_pulse/collectors/src/types.rs:20). |
| SamplingService | One background collector, interruptible interval wait and latest-only delivery slot. [Service](../../examples/system_pulse/collectors/src/service.rs). |
| LiveState | Converts accepted host descriptors/readings into presentation and history while preserving stable choices and process selection. [LiveState](../../examples/system_pulse/src/live.rs). |
| Stable identity | A device/sensor key independent of display label or discovery ordinal. A process combines PID with start ticks to distinguish PID reuse. [ProcessIdentity](../../examples/system_pulse/collectors/src/types.rs:106), [live mapping](../../examples/system_pulse/src/live.rs). |
| Accepted diagnostic frame | Opt-in bounded publication of the actual consumed snapshot and labels derived from presentation data. Sequence and render revision support native comparisons; they do not acknowledge a painted or accessibility frame. Stale rendering preserves original acceptance time. [Diagnostics](../../examples/system_pulse/src/diagnostics.rs). |
