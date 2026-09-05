# Native navigation correction review

## Plan review before implementation

Independent SPEC review found no per-batch requirement to advance the
collector sequence. Freshness validation and the existing overall sampling
progress checks must remain intact.

The reviewer identified an important reconciliation boundary: LIVE-003
forbids an exited selection transferring to another process. After an exact
endpoint acknowledgement with no intervening key, accepting an arbitrary
new selected identity would hide that defect. The decision and plan were
corrected before implementation: retry transient old native state, restore
selection only after observing it clear and sending a real Home/End key,
and fail an unexplained transfer. Add a regression for that failure.

Implementation, final SPEC/QUALITY review, and fresh native acceptance
remain pending. This plan check is not a candidate review.

## Navigation proof boundary

Independent SPEC review permits local panel reuse for intermediate input
pacing only. Discover the unique current Processes panel at navigation
start, after invalidation, and before accepting the final selected target.
Intermediate acknowledgements must validate actual parent-child links to
the current application root before and after a strict complete selection
scan, with exact expected identity and coherent fresh frames. Cached
ancestry, name, role, and liveness alone cannot establish membership.
Invalid linkage or incomplete observations require bounded reacquisition.
The final selected-target proof and subsequent cell metrics each perform
fresh membership and uniqueness checks. No new global cache is justified.

## Native API confirmation

Read-only review confirmed installed AT-SPI 2.60.0 and PyGObject 3.56.2.
GObject equality compares underlying object pointers, and libatspi
canonicalizes accessible proxies by application/object path. Relationship
validation uses equality rather than Python object identity.
`clear_cache_single()` refreshes one node; `clear_cache()` recursively
invalidates descendants. Parent/index/child lookups otherwise allow cached
relationships. Missing parents, negative indices, missing children, defunct
nodes, and transport errors cannot establish membership. Bound links by
the existing 40-ancestor limit and shared deadline; reread parentage to
detect reparenting during observation. The calls are not atomic, so before
and after membership/frame validation remains required.

Primary sources examined by the reviewer:
[PyGObject equality](https://raw.githubusercontent.com/GNOME/pygobject/3.56.2/gi/pygobject-object.c),
[AT-SPI proxy identity](https://raw.githubusercontent.com/GNOME/at-spi2-core/2.60.0/atspi/atspi-misc.c),
and [relationship/cache implementation](https://raw.githubusercontent.com/GNOME/at-spi2-core/2.60.0/atspi/atspi-accessible.c).
This API review did not run native sessions or tests.

## Candidate awaiting review

Candidate `0459aa6dc8464f0e378192eb4f4c345afe451127` adds navigation-local
coherent selection observations and current parent-child membership checks.
Full discovery remains at start, invalidation, and final target proof.
The worker reported 29 new navigation regressions, 100 focused native tests,
and 204 full Python tests passing, plus Ruff lint/format and diff checks.

The timing model covers 355 rows and 178 two-key batches, with one-second
full discovery, 0.3-second strict scans, and 0.5-second native delivery. It
finishes within the unchanged 180-second budget at 154.45 simulated seconds.
This is test-fixture evidence, not measured native performance.
Independent SPEC then QUALITY review and fresh live acceptance remain pending.

## Candidate specification review

Independent SPEC PASS on `0459aa6d`. All 100 focused native tests passed.
Additional probes rejected stale frames, application detachment, target
PID reuse, cleared selection, and continuously changing publications
after acknowledgement without sending further keys. AST/source comparison
confirmed separate exit synchronization, newer-snapshot requirements,
held-input replay, frame validation, and metric comparisons are unchanged.
No specification blockers remain; QUALITY and actual native timing are
still pending.

## Candidate quality review

Independent QUALITY PASS on `0459aa6d`. All 100 focused native tests and
five additional probes passed. They covered ancestry failures, identity
mutation, final multiple-selection rejection, and slow membership checks.
No concrete quality findings remain. The worker's exact full suite passed
204 Python tests. Actual native timing and full acceptance remain pending.
