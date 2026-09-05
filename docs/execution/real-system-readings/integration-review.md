# Live integration review

## Candidate

Implementation commit: `f2f19dd6cf573fcec95c4d96bc62ceea488601c3`. The application now consumes real collector snapshots; runtime fixture controls are test-only. Changes cover physical quantities, device identity and persistence, complete process rows, bounded sampling delivery, and opt-in latest-snapshot diagnostics.

The implementer ran 55 app/model tests (34 app, 21 model), scoped strict all-target Clippy, formatting, whitespace checks and a locked native build; all passed. Its isolated native smoke discovered 151 monitors, 862 sensors and over 1,200 processes. Restart restored 153 panels and a five-second interval from a 540,146-byte workspace. Both smoke application exits returned zero. Artifacts: `/tmp/system-pulse-live-smoke/`. Final native binary SHA256: `4a2941b9ffadca585ee625911e290be4e5395fc3c428c9ac08277bb2cea510be`.

Root inspected the live and CPU-focused screenshots. They show actual physical values, explicit permission-denied fields and separate panels. These are focused smoke results, not full native acceptance.

## Review status

Independent spec review found two P2 issues on `f2f19dd6`; fixes are committed as `59b9b9b8ecb6f97da92deb96a42630acc0357f40` and independent re-review is in progress. The reviewer ran 40 focused model/app/native tests successfully and independently reproduced the formatter behavior without repository edits.

- Elapsed stale transitions update visible/accessible labels but do not republish diagnostic labels. The fix must retain original capture/acceptance age, avoid additional history samples, and publish matching rendered state through the bounded writer.
- Absent-device compact summaries discard known physical units after history eviction. Retained descriptor metadata must supply the unavailable quantity/unit/reason on disappearance and restart.

A tentative Linux process-staleness concern was withdrawn after confirming that the later census timestamp triggers process text refresh. Independent quality review follows a spec pass. Task 2 remains in progress until both reviews pass and findings are verified.

## Native diagnostic boundary

`SYSTEM_PULSE_DIAGNOSTICS_PATH` receives one atomically replaced JSON file. Its schema has `schema_version`, `application_pid`, `accepted_unix_ns`, `render_revision`, `rendered_at_collector_ms`, `snapshot`, and `rendered`. Render revisions order atomic publications; stale transitions preserve original sample acceptance and capture times. Each rendered mapping carries monitor/sensor identity, optional PID/start-time identity, stable element ID, label and optional physical sample. Metric IDs are `<monitor_id>:value:<sensor_id>`; summary IDs are `<monitor_id>:summary`. Process cells use `process:<pid>:<start_ticks>:cell:<column>`.

The pinned AT-SPI adapter obtains Label names from their values. Metric labels therefore set both `aria_label` and `aria_value`, with a separate `accessibility_id`; GPUI `id` alone is internal. Native smoke verified these labels after restart.

## Focused fix verification

The implementer reproduced both regressions before fixing them and ran 57 app/model tests (36 app, 21 model), scoped strict all-target Clippy, formatting, whitespace checks and native build successfully. Controlled delivery tests compare metric, summary and process UI/diagnostic labels after elapsed stale transitions; capture/acceptance identity, sample timestamps and history length remain unchanged, and a repeated unchanged delivery does not republish. The unavailable-summary test covers eviction and serialized metadata restoration with °C retained. Fix binary SHA256: `7c816baa8c72d966216af1f95dadca06be7178f7f6a9eeaeb5ba1caeb9bcd699`. Independent review and full acceptance remain pending.
