# Fresh missing-row inspection eligibility

Implemented the [bounded consolidation decision](../../decisions/consolidate-fresh-missing-row-inspection-eligibility.md)
against base `c5326f3c8539e7705ccdb95d824e25d3af40095e`.
Independent SPEC and QUALITY review remain pending.

## Behavior

[`ProcessInspection.preparation`](../../../scripts/system-pulse/native_replay.py)
accepts an explicit `missing_row=True` option. Only the controlled child's metric
and horizontal visibility callbacks supply it. Pre-exit preparation retains its
default call, and generic navigation, pending-exit recovery and held input keep
their existing calls and behavior.

The callback passes `inspection_missing_row=True` to
[`Native.navigation_selection`](../../../scripts/system-pulse/native_driver.py).
That option requires inspection evidence. Existing inspection validation still
checks the exact prior acknowledgement, reference, index and publication, and
forces fresh global strict panel discovery before the selection observation.

When that first complete, unique and coherent observation satisfies every
existing reveal guard, missing-row preparation can establish eligibility and
dispatch its first nonselecting wheel without the inherited extra preparation
pass. The target must have changed index, be outside the complete instantiated
span, and retain a reference inside that span. Selected competitors and an
instantiated unselected target still reject the observation. All existing
membership, clipped-viewport and publication checks remain before dispatch.
The original journal and physical dispatch deadline checks remain in place.

The existing cleanup still discards provisional eligibility and its panel path
after any rejection before the first dispatch. The next observation must qualify
again from fresh evidence. No evidence or native object is newly cached across
operations. Established gesture evidence is retained only after actual input.

After the wheel, the existing strict scan may request final proof; it cannot
finish proof from the retained panel. Final proof still performs a separate
fresh global discovery of a unique current panel and a complete strict scan
showing the exact selected child. Ordinary unique cell lookup and all original
metric, identity and clipping comparisons then run. The change keeps all sixteen
controlled-child comparisons and controlled exit, all original 15/5/8/180-second
deadlines and the single-read freshness/PID contract.

## Verification

The new [eligibility tests](../../../scripts/system-pulse/test_native_inspection_eligibility.py)
first reproduced duplicate discovery through the actual metric preparation
callback. With synthetic 0.7-second discovery costs, the original code performed
two strict eligibility observations before the first wheel, at 2.35 seconds
instead of the expected 1.4 seconds. With 0.9-second costs, it exhausted the
original five-second gesture before cell reacquisition. The actual replay wiring
test also failed because its callbacks did not yet carry the explicit opt-in.

After implementation, both cost cases pass within five seconds. The regression
requires one complete strict observation before the wheel, another global panel
discovery after it, and the separate final strict selected-child proof. It also
requires ordinary cell reacquisition after preparation. The wiring test executes
the actual replay statements and checks all sixteen metric callbacks and eight
visibility callbacks opt in; default pre-exit and generic paths retain two
pre-wheel observations and the original arguments and deadlines.

Negative fixtures exercise duplicate/detached panels, partial scans, stale or
changing publications, wrong PID, invalid spans, missing/reused identity,
competing selection and instantiated unselected targets. Rejected geometry or
membership cannot preserve earlier permission. Both journal-expiry paths block
physical input. Stale, clipped, wrong, ambiguous or detached post-wheel evidence
cannot produce successful proof. Existing inspection guards run through the new
opt-in path as well as their original path.

Checks used the external artifact temporary directory:

```sh
rtk proxy env TMPDIR=/home/shawn/workspace2/task-manager-artifacts/tmp python3 -B -m unittest discover -s scripts/system-pulse -p 'test_*.py' -q
rtk proxy ruff check scripts/system-pulse
rtk proxy ruff format --check scripts/system-pulse/native_driver.py scripts/system-pulse/native_replay.py scripts/system-pulse/test_native_cells.py scripts/system-pulse/test_native_inspection.py scripts/system-pulse/test_native_inspection_eligibility.py
rtk proxy git diff --check
```

All 31 focused inspection tests and all 363 Python tests passed. Ruff lint,
changed-file formatting, whitespace and this note's five local links passed.

## Limits and self-audit

The traversal costs are synthetic. They prove removed work and bounded behavior,
not a measured contribution to the [combined diagnostic failure](native-combined-inspection-review.md).
That capture remains FAIL. It does not establish the timeout's cause or explain
earlier stale-frame failures. No Rust/product changes, builds or native runs
were performed. Fresh focused untraced replay and full acceptance remain pending.

Reviewed all 14 production rules. The source delta adds a narrow opt-in and skips
one inherited preparation branch; it does not introduce a retry, input policy,
cache, thread or trace mode. Negative fixtures and full verification preserve
the acceptance guards and default paths. No known defect remains from this
self-audit. Independent SPEC, then QUALITY review, precede the next live replay.
