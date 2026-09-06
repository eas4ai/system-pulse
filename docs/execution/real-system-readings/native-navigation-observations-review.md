# Bounded navigation observation reviews

Implementation: `125971f244e58fe8020b97fbef0490a96a5ef6d4`.
Review base: `883724fb9d3761ffb513d19e1192f76dff53853c`.
The [decision](../../decisions/retain-bounded-navigation-observation-failures.md)
and [implementation note](native-navigation-observations-implementation.md)
define the observation scope. This is not a navigation remedy or native pass.

## Specification review

Independent reviewer `prepare_child_inspection` returned **PASS**, with no
findings. The reviewer verified bounded retention, partial-observation fidelity,
original-error authority, unchanged acceptance inputs and unchanged deadlines.

Actual checks:

- Eleven observation tests and all 355 Python tests passed.
- Scoped Ruff lint/format and `git diff --check` passed.
- Independent base/head probes matched native/procfs/input/publication/journal/save
  calls, outcomes and deadlines across success, absent selection, competing
  selection, changing publications and partial-scan scenarios. Failure-payload
  comparison excluded only the new observations.
- Independent capacity and unsigned 64-bit counter-saturation checks passed.

This was a read-only review, with no source edits, builds, native capture or
Cairn mutations.

## Initial quality review

Independent reviewer `review_publication_quality` requires one **P2 correction**
against `883724fb..125971f2`. In the interrupted-scan handlers at native driver
lines 1338 and 1439, the preceding publication's `snapshot.processes` lookup runs
before entering the partial-mapping helper's guarded block. A missing field can
therefore replace the original scan exception with `KeyError`.

An independent base/head probe reproduced the difference: the base preserves
the exact `AssertionError("primary strict scan failure")`; the new implementation
raises `KeyError("processes")`. Frame freshness/PID validation does not validate
that snapshot field before the scan. Guard extraction and mapping together,
retain the bounded mapping error and preserve the original exception. Both
interrupted-scan handlers need regression coverage.

The reviewer found no other quality issue. All eleven focused tests passed.
Independent base/head comparisons for pending-exit recovery, terminal permission
failure and reindex reveal preserved native/read/input calls, outcomes, prior
event/save payloads and simulated deadlines. No source edits, builds or live
runs were performed.

## Remaining work

- [ ] Correct and verify the partial-mapping extraction finding.
- [ ] Complete independent QUALITY review.
- [ ] Run the fresh focused native replay with publication tracing disabled.

Native instantiated-selection observations cannot establish hidden application
model selection. The previous failures remain failed. Fresh full aggregate
acceptance, final review and actual Cairn Done remain required.
