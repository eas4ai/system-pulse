DECISION

Question:   Proceed with the missing-device test specimen correction and reviewed acceptance rerun?
Recommend:  Make the saved dock and collapse preferences consistent; preserve strict assertions, add a regression, and obtain independent reviews before rerunning.
Because:    400 tests and host checks passed; 13 native cases passed. The last case mixed an earlier 280-pixel CPU layout with a later collapsed preference; restore saved 36 pixels. No panel identities changed. Evidence: docs/execution/real-system-readings/aggregate-attempt-2-2026-09-05.md.
If wrong:   A product persistence defect could remain; the regression and independent reviews must distinguish it from specimen inconsistency.
Instead:    Keep acceptance blocked and investigate the retained specimen without rerunning.

Reply: ok | instead | ask

Concerns: LIVE-001
Status: open
Raised: 2026-09-05T06:48:23.276Z
Answer: ok
Answered: 2026-09-05T11:26:01.887Z
