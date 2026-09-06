# Acknowledged child inspection preparation

Implemented the [inspection reveal decision](../../decisions/reveal-an-acknowledged-process-shifted-during-cell-inspection.md)
on base `78b101b8`. The [observed displacement](native-cell-displacement-failure.md)
remains a failed capture. This change prepares the verifier for another run;
it does not establish native acceptance or change product viewport behavior.

## Evidence and lookup boundaries

`Native.navigate(..., on_acknowledged=...)` keeps its existing selected-row
return value. The optional callback receives the exact target, its index,
and the application/publication identifiers from the existing final coherent
navigation proof. It adds no native read or deadline. The controlled-child
cell-discovery artifact retains that acknowledgement.

`ProcessInspection` owns that original acknowledgement and a separate last
positive observation. Navigation seeds the observation. Only a successful
`app.metric` artifact advances it. The observation records the exact identity,
index, publication metadata, and metric artifact name; full snapshots remain
in the existing metric artifacts. Each metric or horizontal gesture freezes
its own compact evidence, including through retries and reacquisitions.
Inspection cannot start without an acknowledgement.

`process_cell(..., prepare_missing=...)` invokes preparation only when ordinary
panel or row lookup finds no target. That non-strict absence cannot authorize
input. Preparation independently performs the existing strict, coherent native
selection scan with fresh unique Processes-panel discovery and current
membership checks. The exact acknowledged identity must remain in the snapshot,
its index must have changed outside the mapped instantiated span, and the last
positive numeric index must remain inside that span before wheel input is eligible.
A coherent selected competitor or instantiated unselected target fails inspection
immediately, including if a later poll could show the target selected again.
Keyboard acknowledgement keeps its existing polling behavior.

Recovery uses bounded nonselecting vertical wheel steps inside the clipped rows
viewport. Rejected pre-input observations discard provisional permission;
permission can be reused only after successful physical dispatch. Recovery then
requires fresh exact selected identity and unique current membership. Inspection
journal events retain the original acknowledgement, frozen reference, eligibility
publication/index/span, action, and absolute deadline. The proof event also records
the recovered publication, selected identity, current index, and instantiated span.
These events do not label an inspection reference as a keyboard endpoint index.

Preparation returns no cell and does not call `process_cell`. Normal panel, row,
and cell discovery runs again afterward. All eight preliminary comparisons and
all eight visible comparisons remain, with their existing independent labels,
frame coherence, geometry, and clipping checks. Generic callers and held-input
exercises do not receive preparation callbacks. The later generic `sequences()`
and `acknowledge()` calls before controlled-child shutdown are unchanged.

Initial metric discovery retains its original 15-second deadline outside the
comparison bracket. Preparation and lookup share that same deadline. Horizontal
gestures and metric reacquisitions retain their original five-second absolute
deadlines. Preparation creates no replacement budget.

## Verification

TDD runs observed failures for missing acknowledgement/callback/inspection APIs,
the one-row displacement, the missing prior-ACK entry guard, and missing recovered
publication evidence before implementing those behaviors. The final checks passed:

- `test_native_inspection.py`: 18 tests, including actual replay wiring through
  sixteen comparisons, success-only reference advancement, original deadline
  propagation, and callback return-value rejection without recursive lookup.
- `test_native*.py`: 193 tests. Inspection reuses existing behavioral guard tests
  for invalid spans, incomplete/stale observations, duplicate membership,
  pre-dispatch invalidation, and rejected provisional permission. Separate cases
  cover identity loss/PID reuse, wrong or missing ACK, competing selection, and
  journal work consuming the physical dispatch deadline.
- Full Python suite: 297 tests passed in 14.055 seconds with:

```sh
rtk proxy env TMPDIR=/home/shawn/workspace2/task-manager-artifacts/tmp /home/linuxbrew/.linuxbrew/opt/python@3.14/bin/python3.14 -B -m unittest discover -s scripts/system-pulse -p 'test_*.py'
```

Scoped `ruff check` and `ruff format --check` passed for `native_driver.py`,
`native_replay.py`, `test_native_cells.py`, and `test_native_inspection.py`.
`git diff --check` passed. Documentation links were checked locally.

## Limits and self-audit

No native/live capture, Rust build, Cairn mutation/check, or push ran in this work.
The simulated tests verify protocol behavior, not real-host timing or final native
acceptance. Independent SPEC and QUALITY review and a fresh untraced acceptance
run remain separate work.

Reviewed all 14 production rules: the change follows the recorded scope and
existing patterns, keeps APIs opt-in, validates inspection evidence at its boundary,
retains bounded recovery and deadlines, and introduces no dependencies, persistent
schema, secrets, or product changes. Tests and this record report only checks that
ran. No unresolved implementation defect was identified in this self-audit.
