# Glossary

Status: Observed

These terms follow existing identifiers and the product's vocabulary. Correct differences in meaning by exception.

| Term | Meaning and evidence |
| --- | --- |
| Monitor | One panel's identity, title, summary sensor, and sensor list; currently the `fixture::Monitor` descriptor. [fixture.rs](../../examples/system_pulse/src/fixture.rs:3). |
| Sensor | A reading within a monitor, identified separately from its displayed label. Current descriptor pairs appear in [fixture.rs](../../examples/system_pulse/src/fixture.rs:17). |
| Sample | Timestamp, optional numeric scalar, formatted text, unit, and `ReadingStatus`. [readings.rs](../../examples/system_pulse/model/src/readings.rs:13). |
| ReadingStatus | `Current`, `Stale`, or `Unavailable`; current samples alone participate in chart segments. [readings.rs](../../examples/system_pulse/model/src/readings.rs:6). |
| HistoryStore | Per-monitor/per-sensor deques with a configured sample-count bound. [readings.rs](../../examples/system_pulse/model/src/readings.rs:44). |
| Meter | `Number`, `Sparkline`, `Line`, `Bar`, or `Radial`, stored as sensor presentation. [presentation.rs](../../examples/system_pulse/model/src/presentation.rs:7). |
| Workspace | Serializable presentation state containing dock JSON and panel/sensor choices. [presentation.rs](../../examples/system_pulse/model/src/presentation.rs). |
| WorkspaceView | GPUI owner of docking, timer, persistence, commands, and shared view data. [workspace.rs](../../examples/system_pulse/src/workspace.rs:199). |
| PanelState / SensorState | Independent visibility/collapse state and retained sizing or ordering/meter selection; distinct from a sample's availability. [presentation.rs](../../examples/system_pulse/model/src/presentation.rs:34). |
| Session | A workspace plus optional rejected original input retained during recovery. [persistence.rs](../../examples/system_pulse/model/src/persistence.rs:10). |
| Separate | Opt-in dock policy preventing multi-panel groups while permitting split movement. [workspace.rs](../../examples/system_pulse/src/workspace.rs:295). |
| Fixture | Deterministic generated test/proof data; currently also the runtime producer, which the developer wants replaced. [fixture.rs](../../examples/system_pulse/src/fixture.rs:76). |
| Collector snapshot | Proposed immutable result from a host collector delivered to the UI. This seam does not exist yet; it is a proposed term in [LIVE-001](live-collection.md). |
| Stable identity | A key that keeps presentation attached to the same monitor or sensor across discovery changes; it is not merely a display label or enumeration index. Existing string keys: [readings.rs](../../examples/system_pulse/model/src/readings.rs:65); intended guarantee: [workspace spec](/home/shawn/workspace2/task-manager/docs/superpowers/specs/2026-09-04-workspace-visibility-design.md:79). |
