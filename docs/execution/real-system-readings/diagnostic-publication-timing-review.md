# Diagnostic publication timing reviews

## Initial specification review

Reviewed implementation `c69a0598ff4b16b3bd6d77a04ae212ab537bd234`
against base `25674119b52db1b3e48f2baaec0f151a834e47f0`.
Independent reviewer: `review_navigation_spec`. Result: **FAIL**.

The initial review found one P2 issue. The new sidecar error path printed every failed
publication to stderr. A directory at `latest.publication-timing.json` allows
primary publication to continue while each trace attempt appends another log
line. An indefinitely running opt-in application therefore creates an unbounded
new log, contrary to the [decision](../../decisions/trace-diagnostic-publication-stages-without-changing-acceptance.md).
The bounded in-memory ring does not bound this output.

The required correction is to report the first sidecar error once per writer,
continue the bounded error count and latest-error bookkeeping, and retain that
history after a later successful sidecar write. A repeated-failure/recovery test
must prove bounded reporting and unchanged primary error authority. Documentation
must describe the reporting limit without promising every failure is logged.

The reviewer found no other specification gap. Stage ordering, history and field
bounds, disabled behavior, trace retention, aggregate rejection, original
freshness/deadlines, and private accessibility environment ordering satisfy the
inspected contract.

The reviewer actually ran 344 Python tests and 55 Rust app tests successfully,
plus nine independent marker/disabled-mode probes, scoped Ruff lint/format and
`git diff --check`. The coordinator separately built the current application
binary successfully. No native run has been performed for this implementation.

## Specification re-review

Correction `f7c45638ba5367c620eae14bf2ceec00ae75d40e` closes the P2 finding.
The same independent reviewer returned **PASS**, with no new findings. Only the
first sidecar error is logged per writer; all errors still update the saturating
count and bounded latest error, retained after recovery. The implementation note
describes the reporting limit accurately.

The reviewer ran ten Rust diagnostic tests successfully, including repeated real
filesystem failures, recovery and captured stderr, plus `git diff --check`.
The implementer ran all 56 Rust app tests, strict Clippy, Rustfmt, diff and seven
documentation-path checks successfully. Python was unchanged by this correction.
The coordinator rebuilt the corrected application binary successfully.

## Quality review

Independent reviewer `review_publication_quality` reviewed `25674119..f7c45638`
and returned **PASS**, with no findings requiring revision. The review covered
the actual diff, producer/storage/workspace changes, harness, tests and records.
Shared-state locking contains bounded bookkeeping; primary and sidecar file
operations happen after unlocking. History and errors stay bounded, evicted
records cannot return, and submission completion precedes dequeue. Latest-only
delivery, revision ordering, atomic replacement, cleanup and durable configuration
saves remain intact. Primary error authority, trace recovery, disabled behavior
and aggregate rejection also passed inspection.

The quality reviewer independently ran six focused Python tests and nine disabled
opt-in boundary probes successfully. AST comparison found all 45 existing Native
methods outside initialization identical to the review base. No native run or
Rust build/test was repeated during quality review. The coordinator checked all
eight local paths in the implementation and review notes successfully.

## Remaining work

- [x] Correct and verify the bounded-reporting finding; repeat SPEC review.
- [x] Complete independent QUALITY review after SPEC passes.
- [x] Run the separately identified instrumented diagnostic and record its result.

The [instrumented diagnostic](native-publication-diagnostic-failure.md) failed on
an intermediate navigation deadline. Its publication stages do not explain the
earlier stale frame. Navigation diagnosis remains open.

The previous full aggregate remains FAIL. This review does not establish a
publication-delay cause or replace fresh untraced full acceptance.
