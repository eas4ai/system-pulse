# Full preservation: Python suite budget mismatch

Status: F1 closed by correction `61e8ceef` and independent [SPEC and QUALITY passes](linux-python-budget-reviews.md). Full preservation remains pending; original failures are retained.

The first full uninstrumented Linux preservation attempt after the reviewed
process-reveal correction stopped in its mandatory Python stage. It ran from
clean HEAD `7ddd3a5722b43d92dc526cb01e916ce47ff60c3a`, with all 734 GPU mechanism
inputs recorded. Source guard passed; the Python stage reached its unchanged
30-second execution deadline before completing. Rust, host and native stages
were not reached. This attempt adds no native freshness reproduction.

## Demonstrated cause

`scripts/system-pulse/acceptance.py` gives the full Python discovery invocation
30 seconds. The suite expanded to 444 tests during GPU acceptance work. The
retained final Task 4 passing invocation already took **34.043 seconds**, as
verified against its lifecycle and stream hashes. A new bounded diagnostic ran
the exact unchanged 444-test command successfully in **34.240 seconds**.
The current deadline is shorter than both observed successful full runs.

The new diagnostic used a separate 120-second outer limit to measure the complete
suite; it did not modify the aggregate runner or establish a preservation pass.
All 444 tests passed, its child exited zero and was reaped, and its PID and
process group were absent. The original 30-second aggregate failure is retained.

## Correction boundary

Increase only the full Python suite's aggregate execution deadline from 30 to
60 seconds, retaining a finite bound above the two measured 34-second passes.
Keep the exact complete discovery command, nonempty test-count validation,
failure propagation and child cleanup. All individual test and native operation
deadlines remain unchanged. In particular, the two-second native freshness limit,
navigation deadlines, hardware comparison bounds and mandatory coverage must
not change.

The actual timed-out aggregate is the pre-change failure evidence. Verify the
complete Python stage through the real runner after correction; do not add a
test that merely repeats the new numeric constant. Obtain independent source
specification and quality review before the next full preservation attempt.

## Retained evidence

Original failure: `gpu-task5/linux-preservation-3ab14ff0-20260906`, with adjacent
`-owner` and `-setup` directories. Root's
`linux-preservation-3ab14ff0-20260906-root-failure-verification.json` binds 11
originals and confirms all four recorded process IDs and groups absent. The
owner reaped both adopted descendants and recorded no remaining children.

Earlier pass: `gpu-task4/q1-r1-correction-20260906/final-python-finished.json`.
New timing diagnostic: `gpu-task5/linux-python-budget-20260906`, including its
`root-verification.json`. The [preservation evidence record](gpu-linux-preservation-failure.json)
binds these verification records. This runner correction does not resolve or
attribute the original Linux freshness failures, Mac F1 or missing hardware.
