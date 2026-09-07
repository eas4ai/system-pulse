# Readings as implemented

Status: Observed

Historical baseline inspected at `9f2f3ad0`. These fixture observations are preserved as history; see the [overview](overview.md) and [LIVE contract](live-collection.md) for the current implementation and pending acceptance.
Prefix: READ

These requirements describe current behavior in contract-shaped text. They are not an agreement to retain simulation.

[READ-001] The fixture producer MUST derive sample values and reading status from its deterministic tick formula.
Falsifier: the producer reads host counters or produces a different result for the same monitor, sensor, and tick.
Mechanism: inspect `fixture::sample` and the deterministic fixture tests; this observation is superseded as a production target by LIVE-001.
Evidence: [fixture.rs](../../examples/system_pulse/src/fixture.rs:76).

[READ-002] HistoryStore MUST retain at most its configured sample capacity in each monitor/sensor series.
Falsifier: inserting more than the configured capacity leaves an over-capacity series.
Mechanism: `cargo test --locked -p system-pulse-model --test readings`.
Evidence: [history insertion](../../examples/system_pulse/model/src/readings.rs:60), [reading tests](../../examples/system_pulse/model/tests/readings.rs).

[READ-003] HistoryStore MUST reject a sample with a non-finite scalar or a timestamp that does not increase within its series.
Falsifier: either invalid sample is accepted into a series.
Mechanism: `cargo test --locked -p system-pulse-model --test readings`.
Evidence: [validation](../../examples/system_pulse/model/src/readings.rs:32), [timestamp check](../../examples/system_pulse/model/src/readings.rs:66).

[READ-004] WorkspaceView MUST advance the fixture feed on its one-second runtime timer independently of panel and sensor visibility.
Falsifier: collapse or hiding stops fixture history advancement.
Mechanism: `cargo test --locked -p system-pulse --lib collapse_keeps_a_header_and_continuous_history` plus the recorded native fixture-cycle inspection.
Evidence: [timer](../../examples/system_pulse/src/workspace.rs:322), [advance](../../examples/system_pulse/src/fixture.rs:107), [native evidence](../../examples/system_pulse/NATIVE_ACCEPTANCE.md:12).

There is no bound on the number of distinct history keys in the present type. That matters when replacing its finite catalog with dynamic hardware discovery. Evidence: [series map](../../examples/system_pulse/model/src/readings.rs:44), [key insertion](../../examples/system_pulse/model/src/readings.rs:74).
