DECISION

Question:   Proceed with the missing-device test specimen correction and reviewed acceptance rerun?
Recommend:  Make the saved dock and collapse preferences consistent; preserve strict assertions, add a regression, and obtain independent reviews before rerunning.
Because:    400 tests and host checks passed; 13 native cases passed. The last case mixed an earlier 280-pixel CPU layout with a later collapsed preference; restore saved 36 pixels. No panel identities changed. Evidence: docs/execution/real-system-readings/aggregate-attempt-2-2026-09-05.md.
If wrong:   A product persistence defect could remain; the regression and independent reviews must distinguish it from specimen inconsistency.
Instead:    Keep acceptance blocked and investigate the retained specimen without rerunning.

Reply: ok | instead | ask

Concerns: LIVE-001, LIVE-002, LIVE-003, LIVE-004, LIVE-005, LIVE-006, LIVE-007, LIVE-008, LIVE-009, LIVE-010, LIVE-011, LIVE-012, LIVE-013
Status: open
Raised: 2026-09-05T06:48:23.276Z
Answer: ok
Answered: 2026-09-05T11:26:01.887Z

## Scope correction, 2026-09-05

The original question concerns the shared live-acceptance rerun, which maps all
thirteen LIVE requirements. Its Concerns field named only the first identifier
selected by the former aggregate verdict. The developer authorized continuation:
"ok you should be good to go now. Let me know if you encounter any more issues
with Cairn". Root recorded that answer at the Answered timestamp above.

This amendment names every requirement already covered by that shared rerun;
it does not change the question, recommendation, developer answer, or original
Raised/Answered timestamps. No new product scope or approval is inferred.
The 2026-09-05T11:59:33Z failure is preserved: a regression expected a decoder's
recursion wording, while this interpreter rejected the same invalid native
result by shape. No host or native run occurred in that attempt.
