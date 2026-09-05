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
