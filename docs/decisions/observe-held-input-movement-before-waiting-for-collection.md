# Observe held input movement before waiting for collection

Level: Judged
Decided by: agent
Rests on: LIVE-003, LIVE-008 and LIVE-010 require actual native movement while fresh samples advance. The retained diagnostic waited 1.283 seconds after key release before inspecting selection; no release-time identity was retained, and virtualized native absence cannot establish model selection state.
Would be wrong if: The correction hides missing movement or stale publication, weakens the three-sequence requirement or exact 64-key endpoint proof, extends deadlines, or counts diagnostic runs as acceptance.

## Decision

Observe signed native movement immediately after the held input is released, before waiting for subsequent collector sequences. Keep the publication observer running across both observations, retain the three fresh sequence requirement, and preserve the existing movement and freshness limits. Keep the exact 64-key burst and exact expected-identity acknowledgement unchanged. Retain the observed process identity alongside its PID movement measurement, without claiming that an absent instantiated row proves model selection is clear. The latest failed diagnostic remains failed; it did not retain the release-time selection and does not identify exit, transfer, focus loss, or key loss. Add regressions proving measurement precedes sequence waiting, publication or movement failures still fail, and burst count and endpoint acknowledgement are preserved. Complete independent SPEC then QUALITY review before fresh live acceptance.

## Realized by

- caa06d742df2739149e46547ad1bc8b83b7030a6 fix(system-pulse): observe input movement before collection wait
- 25fdc7025e216640f0627f3a5593eb3e1f007918 fix(system-pulse): retain main input sequence observations
