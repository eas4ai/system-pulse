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
requires fresh exact selected identity and unique current membership. Initial
eligibility and final proof force fresh discovery on every retry. After physical
dispatch succeeds, intermediate observations may reuse validated local membership
links, including after a publication or selected-node rejection. An incomplete
scan or broken membership still requires rediscovery. Inspection
journal events retain the original acknowledgement, frozen reference, eligibility
publication/index/span, action, and absolute deadline. The proof event also records
the recovered publication, selected identity, current index, and instantiated span.
These events do not label an inspection reference as a keyboard endpoint index.

Preparation returns no cell and does not call `process_cell`. Normal panel, row,
and cell discovery runs again afterward. All eight preliminary comparisons and
all eight visible comparisons remain, with their existing independent labels,
frame coherence, geometry, and clipping checks. Generic callers and held-input
exercises do not receive preparation callbacks. After the existing `sequences()`
wait, the controlled-child pre-exit check uses that same strict inspection proof
with a frozen last successful metric reference and the existing five-second
deadline. Generic acknowledgement, `stop_child`, and strict exit verification
remain unchanged.

Initial metric discovery retains its original 15-second deadline outside the
comparison bracket. Preparation and lookup share that same deadline. Horizontal
gestures and metric reacquisitions retain their original five-second absolute
deadlines. Preparation creates no replacement budget.

## Verification

TDD runs observed failures for missing acknowledgement/callback/inspection APIs,
the one-row displacement, the missing prior-ACK entry guard, and missing recovered
publication evidence before implementing those behaviors. The final checks passed:

- `test_native_inspection.py`: 25 tests, including actual replay wiring through
  sixteen comparisons, success-only reference advancement, original deadline
  propagation, and callback return-value rejection without recursive lookup.
- `test_native*.py`: 200 tests. Inspection reuses existing behavioral guard tests
  for invalid spans, incomplete/stale observations, duplicate membership,
  pre-dispatch invalidation, and rejected provisional permission. Separate cases
  cover identity loss/PID reuse, wrong or missing ACK, competing selection, and
  journal work consuming the physical dispatch deadline.
- Full Python suite: 304 tests passed in 14.347 seconds with:

```sh
rtk proxy env TMPDIR=/home/shawn/workspace2/task-manager-artifacts/tmp /home/linuxbrew/.linuxbrew/opt/python@3.14/bin/python3.14 -B -m unittest discover -s scripts/system-pulse -p 'test_*.py'
```

Scoped `ruff check` and `ruff format --check` passed for `native_driver.py`,
`native_replay.py`, `test_native_cells.py`, and `test_native_inspection.py`.
`git diff --check` passed. Documentation links were checked locally.

## Connected pre-exit correction

After candidate `b7dd5553`, the separately authorized SPEC finding extended this
same inspection proof to the controlled-child pre-exit boundary. RED tests
executed the actual replay statements and reproduced both reported failures:
a detached cached selected target incorrectly overrode a current selected
competitor, and a legitimate one-row displacement exhausted the original deadline.

The correction replaces only that generic acknowledgement call with a deadline
assignment followed by the existing frozen inspection preparation. It adds no
metadata loop or new selection mechanism. GREEN tests prove both failures are
fixed, the five-second deadline begins after the existing sequence wait, an invalid
reference slot still fails, and neither acknowledgement nor the last successful
metric reference advances during this proof.

## Established-recovery discovery correction

The recorded QUALITY finding at `55b6a12c` identified avoidable full panel discovery
during an intermediate observation after successful wheel dispatch. The correction
uses one fresh-discovery predicate for initial discovery and both retry branches:
pre-dispatch observations, recovery preparation, and final proof remain fresh;
established intermediate observations may retain validated membership links.
Missing paths, incomplete scans, and broken links still require discovery.

A regression runs the actual horizontal helper, strict recovery, and subsequent
ordinary cell lookup under explicit synthetic costs. With 1.0 second per ordinary
scan and 0.6 seconds per strict discovery, RED used two ordinary scans and four
strict discoveries, failing at 5.4 seconds. GREEN uses two ordinary scans and three
strict discoveries and finishes at 4.8 seconds within the same five-second deadline.
These are illustrative costs, not measured native timings.

Two further cases reject the first post-wheel observation because its publication
changed or its selected node was replaced. With synthetic costs of 0.95 second per
ordinary scan and 0.55 seconds per strict discovery, RED used five strict discoveries
and failed at 5.9 seconds. GREEN retains validated intermediate links, uses three
strict discoveries, and finishes at 4.8 seconds. Neither retry advances the metric
reference. Separate tests preserve fresh uniqueness after initial/final coherence
retries, force rediscovery after a real incomplete native scan, and reacquire a
replacement panel after post-wheel membership breaks.

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
