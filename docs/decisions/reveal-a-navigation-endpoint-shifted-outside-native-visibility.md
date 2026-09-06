# Reveal a navigation endpoint shifted outside native visibility

Level: Judged
Decided by: agent
Rests on: LIVE-003 and LIVE-010 require exact process identity and preserved reachability. Source retains pixel scroll offset across process churn; the untraced expected index shifted from 1221 to 1216 while the viewport began at 1221. Diagnostic complete scans also observed expected identities outside instantiated spans, without proving sustained drift.
Would be wrong if: Scrolling changes selection, hides incorrect keyboard endpoints, accepts stale/incomplete or ambiguous observations, contaminates held-input movement evidence, changes product behavior, or extends the original deadlines.
History: The prior navigation decision was reversed for overstating virtualized native absence as model-clear proof. This decision responds by requiring explicit current visible-range evidence, retaining an immutable endpoint, and never inferring selection from scrolling. Its level remains Judged: it repairs bounded verifier observability within agreed reachability/identity requirements and leaves product behavior and all bounds unchanged. Independent plan review added the original-slot-inside-span guard to avoid broadly substituting scrolling for keyboard reveal.

## Decision

Support a narrowly identified observation recovery during navigation acknowledgement. Retain the immutable expected PID/start identity and original endpoint index from the snapshot used to issue the current key batch. Recovery may begin only after a fresh coherent snapshot, complete current native scan, and valid panel membership establish: no instantiated selected row; the expected and controlled target identities still exist; the expected identity is absent outside the mapped instantiated span; its index changed; and its original numeric endpoint index lies inside that current span. Index change alone is insufficient. Use only bounded nonselecting vertical scrolling inside the current clipped Processes viewport to reveal the immutable endpoint, then require fresh exact selected-identity and current membership/uniqueness proof. Do not select a row, change or recompute the endpoint, substitute another PID/start, or accept an instantiated unselected endpoint or another selected identity. Charge discovery, scrolling, and proof to the existing eight-second batch and 180-second navigation deadlines. Keep the recovery out of held-input movement measurement and leave production behavior unchanged. Record original/current indices, observed span and nonselecting recovery explicitly; do not claim keyboard-only visibility through churn. Add regressions for index-shift recovery and rejection of unchanged indices, original slot outside the span, visible unselected rows, foreign selection, stale/incomplete/ambiguous membership, PID reuse, target loss, and time exhaustion. Reuse existing physical scrolling/clipping helpers and retain final independent metric proof. This supports a valid recovery case; it is not a demonstrated causal fix for the prior eight-second timeout. The instrumented 2.020-second freshness failure remains separate and unchanged. Complete focused/full checks and independent SPEC then QUALITY review before fresh actual acceptance.

## Final navigation proof

The [retained final-confirmation failure](../execution/real-system-readings/native-final-selection-failure.md)
reached an intermediate exact target acknowledgement, then retained the
same target one row above the viewport at failure. The final independent
navigation_selection call omits endpoint_index while batch/reconciliation
calls retain it. Independent SPEC assessment at `0cf236c2` confirms that
passing the existing immutable key-issued endpoint index to this final call
completes the decision above. Do not recompute the index from a later frame
or substitute inspection evidence. Preserve fresh_panel, reconciliation,
the original deadline, all eligibility/retry guards, and final current
unique exact-selection proof. The exported inspection acknowledgement must
still use the successful final frame and its current positive index.

## Realized by

- 485c5129c2e95ddff27b2ec78fcdbcc8ff65a7cc fix: reveal displaced native navigation endpoints
- d4452f8f38c7734ec70567e47a6f2ca56305c7ed fix: discard rejected navigation reveal eligibility
- bb733beb7c45a1cfc7e1a49d976098e89bc5a44d fix: enforce navigation deadline at wheel dispatch
