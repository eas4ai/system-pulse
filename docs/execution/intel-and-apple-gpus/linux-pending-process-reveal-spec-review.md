# Pending process reveal: specification review

**PASS** for source candidate `3ab14ff0bcd9a612a60477b397252bee48b2a48d`,
reviewed against base `a1421f5d8beac7012f1aba8b54e4d1de7c686b04`.
The independent reviewer found no actionable specification mismatch.
Fresh quality review remains required.

The review inspected the actual four-file diff against GPU-007, preserved
LIVE-003/LIVE-010, the [recorded finding](linux-pending-process-reveal-finding.md)
and the [source decision](../../decisions/resolve-pending-process-reveals-by-identity-at-list-layout.md).
It confirmed the pre-fix failing viewport regression and unchanged-order control,
resolution by full process identity immediately before list layout, one-time
intent consumption, and preservation of passive updates, manual scrolling,
horizontal navigation and PID-reuse behavior. Shared list APIs, native guards,
freshness limits, persistence and collector behavior are unchanged.

The reviewer independently ran the full application tests: **67 passed, zero
failed**, including all four pending-reveal cases. Candidate diff checking also
passed. It recomputed all 26 retained artifact hashes, 12 check-log hashes,
both candidate source hashes and the original production-file hash. The retained
RED was inspected and hashed, not independently rerun. Formatting, strict Clippy
and build results were audited from the implementer's original logs.

The [structured review](linux-pending-process-reveal-spec-review.json) retains the
complete assessment, commands, stream hashes and limitations. Originals remain
at `gpu-task5/linux-pending-reveal-spec-20260906`; root verified all 12 files in
its artifact manifest before recording this pass. Working HEAD `744a97bd` contained
only documentation changes after the reviewed candidate; source bytes matched
before and after independent testing. The reviewer made no source or index edits.

This pass covers the focused source correction. No native workload, full
uninstrumented Linux replay, Mac test or GPU hardware capture ran in this review.
Original Linux freshness failures remain unresolved and the historical navigation
run remains unattributed. The Mac F1/native proof and Intel hardware evidence
remain open. Task 5 and the GPU commitment are incomplete.
