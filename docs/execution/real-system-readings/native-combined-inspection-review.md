# Combined inspection failure: independent diagnosis

The [combined diagnostic](native-combined-inspection-failure.md) remains FAIL.
Independent reviewer `review_publication_quality` inspected its frozen source,
artifacts and implementation history without code changes, builds or live runs.

## Findings

Before the first recovery wheel, the failed missing-row path requires ordinary
cell lookup's global application discovery and panel-row walk, inspection's fresh
strict global discovery and strict selection walk, and another fresh strict
discovery/selection walk after setting `recovery_preparing`. Rejections can add
more work. This is at least three global discoveries (two strict) and three
panel walks before first input. The first reveal occurred 3.337287358 seconds
into the original five-second budget. The artifacts do not time each traversal,
so they cannot assign a measured share of the failure to that repetition.

Commit `485c5129` introduced `recovery_preparing` to require fresh uniqueness
following a candidate from a potentially retained panel. Commit `b7dd5553` added
inspection with unconditional fresh panel discovery while inheriting the extra
pass. The inspection contract requires a fresh coherent strict unique eligibility
observation and fresh exact proof after the wheel. It requires neither two
pre-wheel observations nor a minimum interval between them.

The first complete inspection observation can therefore satisfy that historical
uniqueness purpose. Any consolidation must preserve `d4452f8f`'s requirement to
discard provisional eligibility following rejection before first dispatch.
The pre-exit path also uses inspection preparation; a blanket inspection shortcut
would affect it. Limit the change explicitly to missing-row cell preparation.
Keep pre-exit, generic navigation and held-input behavior unchanged.

## Proposed bounded correction

Use the first already fresh, complete, strict, unique and coherent observation
both to establish missing-row inspection eligibility and to dispatch the first
nonselecting reveal. Keep every existing identity, prior acknowledgement,
reference-index, membership, selection-competitor, instantiated-target, mapped-span,
clipped-viewport and publication guard. Rejected/partial/changing evidence cannot
carry permission into a later observation. A non-strict lookup absence only
triggers this proof and cannot itself authorize input.

After the wheel, fresh strict unique exact selected-child proof remains mandatory,
followed by ordinary unique cell lookup and all independent metric and clipping
comparisons. Keep original absolute deadlines and dispatch checks, including
after journal work. Retain established gesture evidence only after actual input.
Do not cache native objects across operations or infer hidden model selection.

This is a source-supported removal of redundant work, not a proven explanation
of this timeout or the earlier stale-frame failures. Record a separate Judged
decision before implementation; use failing guard/call-count/deadline tests and
independent SPEC then QUALITY review. Fresh untraced full aggregate acceptance
and final review remain required.
