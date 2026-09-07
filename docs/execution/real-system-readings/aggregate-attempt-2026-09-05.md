# Committed aggregate attempt — 2026-09-05

Result: FAIL at independent host counter bracketing. Native replay did not run.
Candidate: `7e7a678af68d68e793c9057e88dff51125b5efaf` (reviewed source `322b05d9`).
Cairn recorded all 13 shared-mechanism receipts as fail at `20260905T061208`.

The run passed 396 tests: Python 45, base dock 205, base resizable 13, component
dock 19, model 24, app 45, collectors 43, and AT-SPI 2. Scoped formatting (including
vendored AT-SPI), strict combined Clippy on all targets, both locked binary builds,
source guard, and diff check passed.

The fresh host capture retained four snapshots, initial/final independent device
inventories, and controlled child appearance/exit. It passed 41,986 counter
brackets, 468 independent stable totals, 2,218 sensor comparisons, 16,386 process
field comparisons, and 96 interface comparisons. These counts do not override
the failure: two mandatory CPU counter brackets were absent for process
`2835657:67295702`, name `imgproxy`, in sequence 1. Its observed collector query
window was `[672957070834055, 672957070845719]` monotonic nanoseconds; no
independent matching windows were retained. Ownership/cause requires diagnosis.

Full evidence: `/tmp/system-pulse-cairn-check-g5vrhjsx/system-pulse-acceptance-ijo2cidw/`.
The root observer only polled its existing execution session during capture;
implementation and review agents were idle. No population exclusion, tolerance
change, or retry-to-green is authorized by this failed attempt. Investigate the
retained observations before any further aggregate run.
