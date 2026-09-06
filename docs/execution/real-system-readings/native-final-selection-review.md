# Final navigation endpoint review

## Independent diagnosis

Source assessed: `0cf236c2fedb7cd0895c6089f2b237465d2b58af`.
Status: open final-call endpoint omission; implementation is separate work.

SPEC confirmed the retained endpoint_index comes from the actual Home/End
or arrow key-issue snapshot and survives reconciliation without recomputing
it. Passing it to final navigation proof completes the existing decision.
Fresh unique/current exact-selection proof, reconciliation, deadlines,
eligibility guards, and final-frame inspection acknowledgement must remain
unchanged. No tests or live execution ran during this contract assessment.

QUALITY independently reproduced displacement at entry to the real
_navigate final call. The acknowledged target moved from issued index 2
to index 1, with instantiated span 2–4. Current code exhausted the original
eight-second proof budget, sent no wheel, and did not acknowledge success.
An in-memory one-argument correction completed the proof in 0.75 seconds
with one nonselecting wheel, no further keys, and a fresh final acknowledgement.
Four adversarial variants still rejected unchanged indices, invalid
reference spans, competing selection, and duplicate panels after scrolling.

The reviewer passed 72 current navigation tests; the in-memory correction
passed 97 navigation/inspection tests. Neither reviewer edited source or
ran a live app or build. The offline timing is a reproduction under fixture
costs, not a native performance measurement. The [retained capture](native-final-selection-failure.md)
supports the displacement scenario but does not expose every failed retry.

## Implementation reviews

Candidate: `4cb9981a32cdb0412c9a37df716a46306892d4d0`. Independent SPEC
then QUALITY review passed. The final-call endpoint omission is closed.
Only the retained endpoint_index argument was added to the final call.
Final discovery, reconciliation, eligibility, current membership/coherence,
selection, deadlines, and final-frame callback data remain unchanged.

The worker passed 76 navigation, 101 navigation/inspection, and 308 full
Python tests, Ruff lint, changed-file formatting, document links, and diff
checks. Broad formatting identified three unchanged baseline files, listed
in the [implementation note](native-final-selection-implementation.md).

SPEC independently passed 76 navigation and 25 inspection tests, scoped
Ruff, and diff checks. Four additional probes checked Home/End issue-index
provenance, total-deadline exhaustion preventing final acknowledgement,
and journal exhaustion preventing input and acknowledgement.

QUALITY independently passed 204 native tests, scoped Ruff, and diff checks.
Four additional probes covered the original final-entry displacement,
Home/End provenance, and post-scroll selection-transfer rejection. The
original reproduction passed on actual committed source with one
nonselecting wheel, no extra keys, and fresh final acknowledgement within
the unchanged proof deadline. Both reviewers examined the exact candidate
above and performed no edits, live runs, builds, or Cairn mutations.

No findings remain for this correction. Fresh native and aggregate
acceptance and final commitment review remain pending.
