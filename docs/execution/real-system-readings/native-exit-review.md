# Native exit synchronization review

## First candidate

Candidate: `b3f0160facab6b110d2e3a7b49a1c48478fdd4bf` against `bc5237d1f8e24074a5eb4d75d1e409ef9e944847`.

Independent SPEC review ran all 14 focused tests successfully but found one important gap. The shared permissive traversal skips missing children and defunct descendants. A live panel root therefore did not prove a complete subtree scan. Two independent probes retained the target while returning either a missing child or a defunct intermediate container; both incorrectly acknowledged exit at 0.5 seconds.

The deadline boundary, exact PID/start identity, newer child-free snapshot, cache clearing, and unchanged application behavior otherwise matched the contract. The requested correction is strict traversal for this exit check, rejecting incomplete trees and negative child counts within the same deadline. Existing callers keep their behavior. Permanent and transient incompleteness need regression coverage.

## Correction candidate

Correction: `d912b5066f80fb73cc4412a6df0e9f2665217e12`.

The worker added strict traversal only for the exit check. A dedicated incomplete-tree error joins the existing bounded wait's transient errors and preserves the timeout reason. Missing children, defunct descendants, and negative child counts prevent success. Existing traversal callers remain permissive; node and time limits still fail immediately. The worker reports 22 focused and 108 total Python tests passing on the exact gate interpreter, plus Ruff lint/format and diff checks.

## SPEC re-review

Independent SPEC re-review passed the cumulative candidate. All 22 focused tests passed under the exact gate Python. Both original false-acknowledgement probes rejected at exactly five seconds. A transient missing-child probe acknowledged only after complete removal at two seconds. No scoped specification gap remained.

## QUALITY review

Independent QUALITY review passed with no actionable findings. The reviewer ran all 22 focused tests using the exact gate interpreter, confirmed the reviewed Python files matched the candidate, and checked the cumulative implementation, error handling, identity, deadline, cache and test boundaries. The tests exercise actual driver and replay code with substituted transport and clock.

Cumulative SPEC and QUALITY status is PASS for `d912b5066f80fb73cc4412a6df0e9f2665217e12`. Fresh native acceptance and final commitment review remain pending; the old capture remains FAIL.

## Subsequent current-membership finding

Status: open. Independent QUALITY review reproduced exit success at
0.5 seconds from a live detached empty cached panel. The application's
current replacement panel retained the exact child; root() was never read.
The earlier strict traversal review did not challenge current membership.

Use the reviewed navigation_panel and navigation_panel_current helpers
for fresh unique discovery and post-scan membership under the original
five-second deadline. Preserve strict complete traversal and the newer
child-free snapshot prerequisite. Add detached-cache, replacement during
scan, and duplicate-panel regressions. This correction is separate from
the no-visible-selection-transfer evidence repair; both need re-review.
