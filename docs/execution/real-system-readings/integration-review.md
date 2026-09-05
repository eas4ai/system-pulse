# Live integration review

## Candidate

Implementation commit: `f2f19dd6cf573fcec95c4d96bc62ceea488601c3`. The application now consumes real collector snapshots; runtime fixture controls are test-only. Changes cover physical quantities, device identity and persistence, complete process rows, bounded sampling delivery, and opt-in latest-snapshot diagnostics.

The implementer ran 55 app/model tests (34 app, 21 model), scoped strict all-target Clippy, formatting, whitespace checks and a locked native build; all passed. Its isolated native smoke discovered 151 monitors, 862 sensors and over 1,200 processes. Restart restored 153 panels and a five-second interval from a 540,146-byte workspace. Both smoke application exits returned zero. Artifacts: `/tmp/system-pulse-live-smoke/`. Final native binary SHA256: `4a2941b9ffadca585ee625911e290be4e5395fc3c428c9ac08277bb2cea510be`.

Root inspected the live and CPU-focused screenshots. They show actual physical values, explicit permission-denied fields and separate panels. These are focused smoke results, not full native acceptance.

## Review status

Independent spec review found two P2 issues on `f2f19dd6`; fixes are committed as `59b9b9b8ecb6f97da92deb96a42630acc0357f40` and independent re-review passed. The reviewer ran 40 focused model/app/native tests successfully and independently reproduced the formatter behavior without repository edits.

- Elapsed stale transitions update visible/accessible labels but do not republish diagnostic labels. The fix must retain original capture/acceptance age, avoid additional history samples, and publish matching rendered state through the bounded writer.
- Absent-device compact summaries discard known physical units after history eviction. Retained descriptor metadata must supply the unavailable quantity/unit/reason on disappearance and restart.

A tentative Linux process-staleness concern was withdrawn after confirming that the later census timestamp triggers process text refresh. Independent quality review follows a spec pass. Task 2 remains in progress until both reviews pass and findings are verified.

## Native diagnostic boundary

`SYSTEM_PULSE_DIAGNOSTICS_PATH` receives one atomically replaced JSON file. Its schema has `schema_version`, `application_pid`, `accepted_unix_ns`, `render_revision`, `rendered_at_collector_ms`, `snapshot`, and `rendered`. Render revisions order atomic publications; stale transitions preserve original sample acceptance and capture times. Each rendered mapping carries monitor/sensor identity, optional PID/start-time identity, stable element ID, label and optional physical sample. Metric IDs are `<monitor_id>:value:<sensor_id>`; summary IDs are `<monitor_id>:summary`. Process cells use `process:<pid>:<start_ticks>:cell:<column>`.

The pinned AT-SPI adapter obtains Label names from their values. Metric labels therefore set both `aria_label` and `aria_value`, with a separate `accessibility_id`; GPUI `id` alone is internal. Native smoke verified these labels after restart.

## Focused fix verification

The implementer reproduced both regressions before fixing them and ran 57 app/model tests (36 app, 21 model), scoped strict all-target Clippy, formatting, whitespace checks and native build successfully. Controlled delivery tests compare metric, summary and process UI/diagnostic labels after elapsed stale transitions; capture/acceptance identity, sample timestamps and history length remain unchanged, and a repeated unchanged delivery does not republish. The unavailable-summary test covers eviction and serialized metadata restoration with °C retained. Fix binary SHA256: `7c816baa8c72d966216af1f95dadca06be7178f7f6a9eeaeb5ba1caeb9bcd699`. Independent review and full acceptance remain pending.

Independent spec re-review passed on `59b9b9b8`. The reviewer independently ran both new regressions and both diagnostic-writer tests: four passed. A separate code quality review is now in progress.

## Quality finding

Independent quality review requested one P2 fix. Dynamic retained metadata could produce a valid 451-panel, 1,473,216-byte workspace. Existing save accepted it, but read rejected it under the 1 MiB bound, causing fallback on restart. The reviewer reproduced this through actual model validation, serialization and Storage methods in `/tmp/pulse-quality-size-74x3c8cr`. A coherent bounded read/write policy and rejection before replacing prior valid state are required; diagnostics remain separate.

The quality reviewer independently ran all 57 app/model tests and scoped strict all-target Clippy successfully. No other finding remains; the Linux census timing cleared the tentative stale-process concern. The persistence fix is in progress.

## Independent native smoke

Root launched binary `7c816baa8c72d966216af1f95dadca06be7178f7f6a9eeaeb5ba1caeb9bcd699` in a private Xvfb/DBus session with isolated configuration and diagnostics. Artifacts: `/tmp/pulse-root-native-live-4dulvflb/`. The actual PID was 755663. A visible filesystem metric was exposed with its exact physical text through AT-SPI; screenshots were inspected. At 960×640, focusing `Collapse CPU` revealed the control. Space collapsed it, emitted an expanded-state event with value zero, and retained the compact percentage. Accepted sequences advanced from 110 to 201 during the session, with observed acceptance ages below one second. The application exited zero; a subsequent Ctrl-C cleaned up the remaining display/session wrapper. This is a focused smoke, not unchanged-revision numeric matching or the full native replay.

The final harness should cache AT-SPI nodes by `get_accessible_id()` after discovery. A whole-tree query traverses many panels and can exceed a sample interval; it is unsuitable inside the exact label/sequence comparison window. The installed Python AT-SPI binding exposes `get_accessible_id`.

## Configuration and process identity fix

Commit `9c6034b456a0a50d6a8b7a708d36dddd8d6cbd4b` defines a shared `MAX_CONFIGURATION_BYTES = 16 * 1024 * 1024` boundary in the model and adapter. Workspace/preset serialization, restoration and disk IO enforce the same bound. Over-limit saves preserve prior valid files and in-memory preset state; diagnostic atomic writes use a separate path. Regression coverage includes a valid 451-panel workspace and preset above the former 1 MiB limit.

Root also found that process row/cell constructors used only internal GPUI IDs. They now export PID/start-based `accessibility_id` values matching diagnostic mappings. The new native regression first failed on missing author ID, then passed through reorder and PID reuse.

The implementer ran 65 app/model tests (41 app, 24 model), scoped strict all-target Clippy, formatting, whitespace checks and native build successfully. Focused spec boundary re-review is in progress; quality re-review follows.

Focused spec boundary re-review passed on `9c6034b4` with 16 independent tests covering model persistence, storage, preset preservation, native process identity, and diagnostic size independence. Quality re-review of the original failure is in progress.
