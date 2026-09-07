# GPUI Kit 0.6 migration

The application uses the released `gpui-kit` 0.6.0 facade and the matching
GPUI Pre 0.3.2 package family. The retained base/component libraries are
rebased onto release source `94a313a72a2513aee2780240cd322d552b2395f0` with
System Pulse's behavior patches. Unmodified macros and icon assets now come
from registry dependencies. No framework website, examples or automation
are imported.

All 35 existing local library regressions are preserved. Upstream's new
proportional split reconciliation remains active for ordinary tabbed layouts;
Separate layouts retain absolute sizes and keep the new cache synchronized.
The new sizing regression fails before that correction and passes afterward.
Sensor collection, persistent workspace format, presets and the product layout
remain unchanged by this dependency migration.

The Linux adapter is rebased to AccessKit AT-SPI 0.19.1. Both unchanged
expansion-state regressions fail without the mapping and pass with it; all nine
adapter tests pass. The macOS dispatcher pool boundary and lifetime tests are
retained on GPUI Pre macOS 0.3.2. Each adapter records package/archive provenance.
The build-input verifier now follows resolved dependencies through the facade
to include local patches in source evidence.

Before native acceptance, local checks passed: 1,479 Rust workspace tests,
465 Python tests, application all-target compilation, app/model/collector/base
Clippy with warnings denied, workspace and adapter formatting, and dependency
license generation. Independent library preservation review found no lost
contract behavior. These checks do not yet constitute native or package
acceptance of the migrated build.

The first full host run exposed an older verifier assumption: it joined socket
attribution by the monitor's display title, which no longer equals the raw
interface name after the readable-name change. The verifier now uses the
stable network identity's name suffix. Four new regressions cover aliases,
identity forms, zero/unavailable/failed readings and rejection of wrong values
or malformed identity. The original failed capture remains retained; its 96
interface comparisons pass the corrected join, and a fresh full acceptance
run is required. No collector arithmetic or availability rule was changed.

A fresh full host run passed after that verifier correction: 2,218 exact readings,
96 network interface comparisons, 20,958 process fields and 49,046 counter
brackets. Native replay then exposed malformed cache signals introduced by
`accesskit_unix` 0.22.1. Its original run failed the five-second held-input
acknowledgement and logged 20,166 rejected cache events. The original failure
remains retained; timing causality is not inferred from the protocol defect.

The Unix adapter is now vendored with one structured-argument wrapper at the
cache emitter. Two wire-level regressions fail against the original framing and
pass with the correction. All seven Unix and nine common adapter tests pass.
The acceptance command includes the new adapter's tests, formatting and lint;
the build-source guard binds its files. The standalone native replay passed all 14 cases with zero malformed cache
warnings after this correction. A final native/package run is required.

Native macOS checks passed on the migrated application: build, 90 application
tests, five dispatcher tests and fresh-process application success, error,
unwind and background cases. Direct test binaries emitted no missing-pool
diagnostics. The Mac desktop session was locked, so GUI replay was not run.
The checks were repeated successfully on cache-patch revision `f6fcffc`; all
551 runtime input hashes remained unchanged and owned processes were cleaned up.

The final native run then found a separate replay bookkeeping defect during
real-child navigation. A positive native acknowledgement observed a selected
identity at index 1275, while the driver retained the earlier issued index 1273.
After passive process exits moved that identity offscreen, this old index no
longer supplied the historical viewport proof required by the recovery guard.
Passive reconciliation now uses the index already captured with the positive
acknowledgement. First pending-input acknowledgement and the final target proof
retain their issued index; selection, recovery and deadline checks remain unchanged.
A regression reproduces the same timeout before the correction and passes
afterward, requiring no arrows for the disappeared proposed endpoint, a guarded
nonselecting wheel and a fresh exact target acknowledgement. Application code
is unchanged; the original failed run remains recorded.

A later complete-tree inventory exceeded its unchanged 15-second deadline
following preset recall. Profiling the retained saved layout found redundant
identity reads and recursive descendant-cache invalidation before geometry
queries. Removing those redundant operations produced 3.293- and 3.980-second
complete inventories, bracketed by original traversals that both timed out at
15 seconds. Changing all cache clears to single-node clears did not reliably
improve the result and was not adopted.

The walker now optionally returns the identity it already read. Inventory still
checks every node, forbidden role/fixture identity, bounds, and complete child
membership. Geometry calls use AT-SPI's live GetExtents RPC without first clearing
descendant caches; liveness and pre/post traversal refreshes remain unchanged.
Two new regressions fail before the correction and pass afterward, including
fresh successive geometry and propagation of a disappearing-node error. Existing
partial-tree rejection and exact deadline tests remain unchanged.

The plan is [GPUI Kit migration](../superpowers/plans/2026-09-07-gpui-kit-migration.md).
Detailed logs are retained outside the checkout in
`/home/shawn/workspace2/task-manager-artifacts/gpui-kit-06-20260907/`.
Earlier hardware evidence remains bound to its original source and dependencies;
this work does not claim the outstanding Intel/Apple GPU acceptance complete.
