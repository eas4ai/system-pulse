# Application completion review record

## Mechanism review: LIVE-005

Reviewed the current physical-kind/unit/scale requirement and falsifier against `examples/system_pulse/model/tests/readings.rs:121`, the compatibility assertions at line 160, `src/meters.rs:35`, and native replay physical-value/capacity comparisons in `scripts/system-pulse/native_replay.py:715`. Model tests explicitly reject negative rates and non-finite percentages, verify 4096 bytes/s remains 4 KiB/s with a scale above 100, check 16/64 GiB produces 0.25, and reject incompatible temperature bars. Native replay requires the actual CPU chart and RAM capacity labels, with artifacts required by `acceptance.validate_primary_native`. These cover the current falsifier; no mechanism mismatch found.

The actual safe negative and positive cases above ran in the retained 870-test full pass documented in `docs/execution/intel-and-apple-gpus/linux-preservation-pass.md`. The source has not changed since that run. This review audited existing executed evidence rather than rerunning it. The forthcoming product UI changes will require a new final replay. This is a focused mechanism review, not final application approval.

## Mechanism review: LIVE-009

Compared the bounded pipeline and lifecycle falsifier with `collectors/src/service.rs` and its six actual worker/lifecycle tests, plus history key eviction in `src/live.rs`. The slow-backend test tracks maximum concurrent calls and requires one latest snapshot; interval-change and in-flight-drop tests prove interruptible waits and joined shutdown; unsupported 42ms intervals are rejected. The retained collectors log in the 870-test Linux pass contains all six passing cases. Native acceptance also requires successful application and transport cleanup. No mismatch found. This review audited the existing unchanged source and executed positive/negative evidence; no tests were rerun and no final application approval is implied.

## Mechanism review: LIVE-010

The current workspace preservation falsifier matches the existing separate-panel model/dock suites, `native_tests.rs` collapse/focus/discovery/recovery tests and all fourteen native replay cases. `acceptance.validate_primary_native` requires the original no-tab, physical-value, held-input and scrolling artifacts; `validate_remaining_native` requires both recovery cases and the missing-device specimen. Existing `test_requirement_verdicts.py` negative cases reject false/missing cases, failed shutdown, missing artifacts and incomplete transport. The unchanged complete command actually passed all those tests and the full native replay in the retained 870-test pass. No mismatch found; this is an audit of that executed evidence, not a rerun or final application review. Upcoming layout/context changes must preserve these checks and receive a fresh replay.

## Mechanism review: LIVE-012

Compared the accessible-field coverage falsifier with the independent `host_capture.Observer` inventory and `verify_inventory` at line 703. The latter requires exact independent sensor/readings/monitor sets and source/unit/monitor/raw-source attribution; omitted accessible fields cannot pass. `test_host_inventory.py` supplies safe missing/extra/misattributed inventory specimens, and the actual independent host capture passed in the retained full Linux run. GPU hardware classes retain their separate native requirements; this AMD-host result does not verify Intel or Apple. No mismatch found for the inherited Linux capability check. Existing executed evidence was audited without rerunning or changing source.
