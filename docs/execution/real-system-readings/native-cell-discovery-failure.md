# Native cell discovery failure

The aggregate at `098d2b2e` passed all 481 automated tests, formatting, strict
Clippy, and both binary builds using the adopted lld configuration. Host
verification passed with 43,004 counter brackets, zero missing brackets or
unverified exit gaps, 468 stable totals, 2,219 exact readings, 17,131 process
field comparisons, and 96 interface comparisons. NVIDIA reported the actual
NVML DriverNotLoaded error; NVIDIA hardware accuracy remains unverified.

Native launch, metrics, collapse, charts, and inner scrolling passed. The
process case stopped at `native_replay.py:753`, searching for a child process
cell through `NativeApp.find`. The full accessibility traversal exceeded its
discovery deadline. This happened before the revised exit synchronization
could be verified. Diagnosis is pending; no product or harness cause is
claimed yet. Original artifacts and receipts remain unchanged.

Cairn recorded LIVE-004, LIVE-012, and LIVE-013 as pass, and the other ten
requirements as unverified. Wake requested `implement LIVE-001`. This is
correct per-requirement reporting, not another Cairn reporting limitation.

See [the artifact record](native-cell-discovery-failure.json). Final native
acceptance, adversarial review, and Cairn Done remain pending.

## Independent diagnosis

The failing column was column 6. After column 5, the next direct cell lookup
fell back to a full application traversal with its own 15-second default.
The caller had created a five-second deadline but did not pass it. The last
column-5 screenshot and failure screenshot are 15.035 seconds apart.

Accepted diagnostic sequence advanced from 146 to 162 and revision from 145
to 161. The controlled child and all eight cells remained in the diagnostic
frame. Three preceding horizontal movements acknowledged in about 0.24
seconds each. These observations rule against a stale diagnostic frame as
the cause; they do not establish general application performance. The exact
AT-SPI invalidation event and traversal costs were not logged.

The retained harness matches the inspected source. The narrow correction
will share the existing metric row-scoped lookup and propagate the original
deadline through process cell discovery and movement. See
[the recorded decision](../../decisions/scope-process-cell-discovery-to-its-native-row.md).
Generic lookup, strict exit verification, and comparison bounds remain intact.
