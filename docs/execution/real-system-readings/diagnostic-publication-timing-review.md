# Diagnostic publication timing reviews

## Initial specification review

Reviewed implementation `c69a0598ff4b16b3bd6d77a04ae212ab537bd234`
against base `25674119b52db1b3e48f2baaec0f151a834e47f0`.
Independent reviewer: `review_navigation_spec`. Result: **FAIL**.

One P2 finding remains open. The new sidecar error path prints every failed
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

## Remaining work

- [ ] Correct and verify the bounded-reporting finding; repeat SPEC review.
- [ ] Complete independent QUALITY review after SPEC passes.
- [ ] Run the separately identified instrumented diagnostic and record its result.

The previous full aggregate remains FAIL. This review does not establish a
publication-delay cause or replace fresh untraced full acceptance.
