# Prior selection in intermediate arrow observations

Implemented the [prior-selection decision](../../decisions/recognize-prior-selection-during-intermediate-arrow-observation.md)
against base `8e392b350682a226d1e622326bbb495c3ba3a28d`.
Independent SPEC and QUALITY reviews passed; see the
[review record](native-prior-selection-review.md).

## Evidence and scope

[`Native._navigate`](../../../scripts/system-pulse/native_driver.py) captures a
bounded identity, current index and publication from an already returned positive
native acknowledgement. The summary reads existing frame values and retains no
native object, process vector or full frame. It does not inspect diagnostic model
selection, journal records or the navigation observation history.

Only intermediate pending arrow batches can carry the optional
`prior_acknowledgement` proof. The existing issue-frame identities must uniquely
contain the prior selection, expected endpoint and controlled target. The prior
and endpoint indices must match that frame and the issued key direction/count;
the target must lie beyond the intermediate endpoint in that issue frame. The prior ACK and issue
publication must match completely. If these construction conditions do not
qualify, including an ACK-to-issue publication change, the optional proof is
omitted and the existing navigation behavior continues.

The pending envelope binds the proof to its issued selection, expected identity,
target, endpoint index, publication, keys, batch/total deadlines and completed
dispatch timestamps. The existing actual-key and independent-stat validation
remain authoritative. Supplied malformed or mismatched proof fails closed before
the pending observation. A later publication is not required to match the old
issue frame; it expires the optional prefix instead.

Interrupted pending results are not positive acknowledgements. After an
interruption, later proof comes from the separately successful native boundary
acknowledgement. Home/End can supply that prior positive proof, but their own
observations receive no exception. Reconciliation, final-target arrows,
inspection, pre-exit and held-input behavior remain unchanged.

## Prefix behavior and bounds

The state in [`native_pending.py`](../../../scripts/system-pulse/native_pending.py)
starts active only with valid bound proof. It recognizes the exact prior identity
only in the initial prefix of the same issued publication. Each existing
publication read can expire it, including a read in an observation whose bracket
later rejects coherence. Coherent absence or another selected identity also
expires it. Returning to the old identity or publication cannot reopen it.

An exempt observation only avoids setting a new competing-selection block. It
acknowledges nothing, cannot authorize input and never clears an existing block.
A distinct competitor or an instantiated unselected expected row still blocks
recovery permanently, including when the prior identity remains selected.

After the prefix, every existing strict coherent absence/reindex guard, fresh
global uniqueness check, viewport clip, final membership/publication check and
post-journal input deadline remains in place. Reveal still needs separate fresh
strict exact expected-selection proof afterward. Hidden selection remaining on
the prior identity cannot manufacture an expected ACK after revealing an
unselected expected row. All original 8/180/5-second bounds, fail-fast single-read
freshness/PID checks, sixteen child metric comparisons and controlled exit remain.

The ACK summary has three fields; the bound proof adds eight fixed envelope
fields. Identity strings are limited to 64 characters with unsigned 64-bit PID
and start values. Publications contain four unsigned 64-bit integers, keys contain
one or two identical arrow names, and indices/timestamps use unsigned 64-bit
bounds. Deadlines must be finite nonnegative numbers within that bound. State is
scoped to the pending operation. No new helper module, read, input policy, retry,
cache, queue, thread, polling loop or tracing mode was introduced.

## Verification

Two tests first failed against the original source: the actual pending envelope
lacked the returned native ACK, and two prior-selection observations followed by
coherent absence/reindexing exhausted the original absolute batch deadline.

All 18 [focused tests](../../../scripts/system-pulse/test_native_prior_selection.py)
now pass. They cover actual ACK-to-envelope wiring, Up and
Down bindings, absence of optional proof, persistent/returning prior selection,
publication advance and rejected brackets, hard blocks, malformed fields and
dispatch bindings, hidden-prior post-wheel rejection, and both journal-expiry
barriers. Additional checks show that changed issue data omits optional proof,
only bounded values are retained, interrupted frames never become ACK evidence,
and the successful conditional scenario works without a journal or observation
history. Default navigation preserves native, procfs, frame, input, artifact and
deadline observations with capture enabled or disabled.

Final verification ran after the last source change:

```sh
rtk proxy env TMPDIR=/home/shawn/workspace2/task-manager-artifacts/tmp python3 -B -m unittest discover -s scripts/system-pulse -p 'test_*.py' -q
rtk proxy ruff check scripts/system-pulse
rtk proxy ruff format --check scripts/system-pulse/native_driver.py scripts/system-pulse/native_pending.py scripts/system-pulse/test_native_prior_selection.py
rtk proxy git diff --check
```

All 381 Python tests passed in 20.860 seconds. The final focused run passed all
18 tests in 0.872 seconds. Ruff lint, changed-file formatting, whitespace and
this note's five local links passed.

## Limits and self-audit

The [captured replay](native-prior-acknowledgement-review.md) remains FAIL. The
fixture supplies a recoverable native tree and exact post-wheel selection; it
does not prove the live run would have passed the previously unreached input
guards. No Rust/product changes, builds or live runs were performed. Fresh
[focused untraced replay](native-prior-selection-focused-pass.md) passed; full
acceptance remains pending.

Reviewed all 14 production rules. The implementation is confined to the pending
arrow evidence and blocking decision, with bounded state, explicit failure
handling and existing acceptance guards. No known defect remains from this
self-audit. Independent SPEC and QUALITY reviews subsequently passed. The fresh
[untraced focused replay](native-prior-selection-focused-pass.md) subsequently
passed all sixteen comparisons and controlled exit. Full acceptance remains open.
