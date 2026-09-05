# Reading presentation as implemented

Status: Observed
Prefix: VIEW

[VIEW-001] The compact value formatter MUST distinguish unavailable and stale samples from measured zero.
Falsifier: an unavailable sample renders as zero or a stale sample loses its stale label.
Mechanism: `cargo test --locked -p system-pulse --lib compact_status_does_not_turn_unavailable_into_zero`.
Evidence: [formatter and test](../../examples/system_pulse/src/meters.rs:5).

[VIEW-002] The current graph renderer MUST clamp scalar values to its fixed 0–100 range.
Falsifier: a scalar above 100 produces a plot height above the fixed ceiling.
Mechanism: inspect `meters::meter`; LIVE-005 proposes replacing this behavior for non-percentage quantities.
Evidence: [meter paths](../../examples/system_pulse/src/meters.rs:29).

[VIEW-003] The current Processes view MUST render 500 generated rows with synthetic PID, name, and CPU columns.
Falsifier: its row count or values depend on actual process enumeration.
Mechanism: inspect `MonitorPanel::process_table`; LIVE-003 proposes the opposite production behavior.
Evidence: [table](../../examples/system_pulse/src/panel.rs:247).

[VIEW-004] The workspace MUST retain independent routes for process-table navigation and outer scrolling.
Falsifier: keyboard or pointer interaction traps the user in the table so another panel cannot be reached.
Mechanism: the app's `workspace_and_long_table_are_independently_reachable`, `wheel_routes_to_table_and_outer_canvas_independently`, and `tab_enters_and_leaves_the_retained_process_table` tests, plus native replay.
Evidence: [native tests](../../examples/system_pulse/src/native_tests.rs), [native acceptance](../../examples/system_pulse/NATIVE_ACCEPTANCE.md:9).
