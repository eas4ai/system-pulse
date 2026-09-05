# Host counter coverage after process handoff

The full aggregate at `204780f2` passed all 430 automated tests, formatting,
Clippy and locked builds. Host verification retained 42,542 valid brackets and
four missing endpoints for PID/start `1322913:69430231`. No native run followed.
The machine-readable evidence and artifact hashes are in
[resumed-host-exit-gap.json](resumed-host-exit-gap.json).

Independent diagnosis found an avoidable handoff gap. The sampler cleared its
supplemental PID set on each full sweep, after which ordinary reads alone covered
that PID roughly every 90–140 ms. Its last collector query ended at monotonic
`694302723635237`. Supplemental census 153 still contained the PID during
`694302761921839..694302766398810`, but did not read its counters. Census 154
omitted it. The next direct ordinary stat attempt returned ENOENT.

The post-query census is evidence of an observation opportunity, not a counter
value. The failed run stays failed. Retain supplemental candidates across full
sweeps and preserve a direct terminal stat observation before retiring them.
Keep the prospective 20 ms schedule, every ordinary read, actual PID/start
identity, errors, query windows and all existing bounds. This addresses the
observed gap without guaranteeing that every uncontrolled process lifetime can
be bracketed.

A fixed-timeline census estimate suggests 359 supplemental attempts rather than
101, with at most 16 active candidates; these are illustrative costs, not a
prediction of live timing or proof of a recovered bracket. Candidate reads may
still race exit, and unchanged capture limits must fail on exhaustion.

The judged decision is
[retain-supplemental-process-observation-until-exit](../../decisions/retain-supplemental-process-observation-until-exit.md).
The worker is adding regressions before the correction. Independent SPEC then
QUALITY review and a new committed aggregate remain required.

## Reviewed correction

Candidate `0458ddee7706913467f59b47fa02aa563ca2c053` changes two sampler
methods, adding nine source lines. The worker ran 11 focused and all 86 Python
tests under the exact aggregate Python 3.14.7 interpreter; both passed.
Independent SPEC passed those eleven focused cases and ordinary-read ordering.
Independent QUALITY passed eleven focused cases and three further probes for
store-before-retirement, multi-candidate mutation, attempt 4096, and exact-deadline
partial evidence. Both report PASS with no remaining scoped findings.

Old failed evidence is unchanged. Fresh full acceptance remains pending.
