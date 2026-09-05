# Live integration review

## Candidate

Implementation commit: `f2f19dd6cf573fcec95c4d96bc62ceea488601c3`. The application now consumes real collector snapshots; runtime fixture controls are test-only. Changes cover physical quantities, device identity and persistence, complete process rows, bounded sampling delivery, and opt-in latest-snapshot diagnostics.

The implementer ran 55 app/model tests (34 app, 21 model), scoped strict all-target Clippy, formatting, whitespace checks and a locked native build; all passed. Its isolated native smoke discovered 151 monitors, 862 sensors and over 1,200 processes. Restart restored 153 panels and a five-second interval from a 540,146-byte workspace. Both smoke application exits returned zero. Artifacts: `/tmp/system-pulse-live-smoke/`. Final native binary SHA256: `4a2941b9ffadca585ee625911e290be4e5395fc3c428c9ac08277bb2cea510be`.

Root inspected the live and CPU-focused screenshots. They show actual physical values, explicit permission-denied fields and separate panels. These are focused smoke results, not full native acceptance.

## Review status

Independent spec review is in progress. Independent quality review follows a spec pass. Task 2 remains in progress until both reviews pass and findings are verified.

## Native diagnostic boundary

`SYSTEM_PULSE_DIAGNOSTICS_PATH` receives one atomically replaced JSON file. Its schema has `schema_version`, `application_pid`, `accepted_unix_ns`, `snapshot`, and `rendered`. Each rendered mapping carries monitor/sensor identity, optional PID/start-time identity, stable element ID, label and optional physical sample. Metric IDs are `<monitor_id>:value:<sensor_id>`; summary IDs are `<monitor_id>:summary`. Process cells use `process:<pid>:<start_ticks>:cell:<column>`.

The pinned AT-SPI adapter obtains Label names from their values. Metric labels therefore set both `aria_label` and `aria_value`, with a separate `accessibility_id`; GPUI `id` alone is internal. Native smoke verified these labels after restart.
