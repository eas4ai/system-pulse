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
