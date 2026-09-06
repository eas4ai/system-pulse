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

## Correction and re-review

Correction `2df34d14b6d0e2f2a37b7e4093f5ccee2c6c7a17` passes the already-read
publication to the helper and guards extraction together with mapping. It adds
no read or retained publication. Missing process data and a null snapshot first
reproduced error replacement in both scan handlers, then preserved the exact
original exception, one scan attempt and bounded mapping error after correction.

The implementer passed all 357 Python tests, including thirteen focused tests,
plus all-script Ruff lint, changed-file formatting, whitespace and five note
links. Independent SPEC delta review returned **PASS** after thirteen focused
tests and twelve additional malformed-frame/error probes, scoped Ruff and diff
checks. It found no reads, retries, retained frames or deadline changes.

Independent QUALITY re-review returned **PASS**, closing the P2 finding with no
remaining issue. All thirteen focused tests passed independently. The original
failing probe now preserves the exact exception object; an additional probe
confirmed publication data is not retained. Neither re-review ran builds or
native capture or changed source.

## Remaining work

- [x] Correct and verify the partial-mapping extraction finding.
- [x] Complete independent QUALITY review.
- [x] Run the fresh focused native replay with publication tracing disabled.
  The [capture](native-navigation-observation-stale-failure.md) failed freshness;
  its independent diagnosis authorizes no behavior remedy.

Native instantiated-selection observations cannot establish hidden application
model selection. The previous failures remain failed. Fresh full aggregate
acceptance, final review and actual Cairn Done remain required.
