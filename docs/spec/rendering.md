# Reading presentation as implemented

Status: Observed

Historical baseline inspected at `9f2f3ad0`. These fixture observations are preserved as history; see the [overview](overview.md) and [LIVE contract](live-collection.md) for the current implementation and pending acceptance.
Prefix: VIEW

[VIEW-001] The compact value formatter MUST distinguish unavailable and stale samples from measured zero.
Falsifier: an unavailable sample renders as zero or a stale sample loses its stale label.
Mechanism: `cargo test --locked -p system-pulse --lib compact_status_does_not_turn_unavailable_into_zero`.
Evidence: [formatter and test](../../src/meters.rs:5).

[VIEW-002] The current graph renderer MUST clamp scalar values to its fixed 0–100 range.
Falsifier: a scalar above 100 produces a plot height above the fixed ceiling.
Mechanism: inspect `meters::meter`; LIVE-005 proposes replacing this behavior for non-percentage quantities.
Evidence: [meter paths](../../src/meters.rs:29).

[VIEW-003] The current Processes view MUST render 500 generated rows with synthetic PID, name, and CPU columns.
Falsifier: its row count or values depend on actual process enumeration.
Mechanism: inspect `MonitorPanel::process_table`; LIVE-003 proposes the opposite production behavior.
Evidence: [table](../../src/panel.rs:247).

[VIEW-004] The workspace MUST retain independent routes for process-table navigation and outer scrolling.
Falsifier: keyboard or pointer interaction traps the user in the table so another panel cannot be reached.
Mechanism: the app's `workspace_and_long_table_are_independently_reachable`, `wheel_routes_to_table_and_outer_canvas_independently`, and `tab_enters_and_leaves_the_retained_process_table` tests, plus native replay.
Evidence: [native tests](../../src/native_tests.rs), [native acceptance](../../docs/native-fixture-acceptance.md:9).
