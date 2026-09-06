# Bounded native navigation failure observations

Implemented the [navigation observation decision](../../decisions/retain-bounded-navigation-observation-failures.md)
against base `883724fb9d3761ffb513d19e1192f76dff53853c`.
Initial SPEC review passed. The QUALITY correction below awaits independent
review of the delta.

## Behavior

[`Native.navigate`](../../../scripts/system-pulse/native_driver.py) scopes an
in-memory history to its active operation and clears it on success or failure.
[`native_observations.py`](../../../scripts/system-pulse/native_observations.py)
retains the newest 64 observations, with observed and evicted counts. Each record
contains the existing navigation phase, active observation phase, exact expected
process identity and issued index, batch and total deadlines, monotonic start/end
times, discovery and scan durations, publication brackets, panel checks, outcome,
and rejection or exception reason. Timestamps use Python `time.monotonic_ns`.

Scan records count rows and selection checks actually observed. They retain a
bounded sample of row identities and instantiated selected identities, with the
total selected count. They do not claim model selection. Completed walks are
marked complete before selection uniqueness validation; interrupted walks have
an aborted time and no completion time. Unobserved stages and values stay absent
or null. Existing mapped spans are recorded when calculated. After a scan raises,
a span can be derived from its already-read rows and preceding publication;
that source is labeled and does not claim a verified complete span. Diagnostic
mapping errors are recorded without replacing the original scan error.

Recovery records retain the existing blocked, preparing, started and proof flags.
The first observation and reason that set the blocked flag remain attached to
later observations, even if later scans observe no instantiated selection.

Every retained string is capped at 512 characters. Each observation keeps at most
two scans, two discoveries, six publications and eight panel checks. Each scan
keeps at most eight row samples and eight selected identity samples. Counters
saturate at the unsigned 64-bit maximum. Only bounded scalars and fixed-schema
collections are retained; no accessible objects or full snapshots enter history.
Existing acceptance inputs, including complete row and viewport lists, retain
their original contents.

On failure, the existing navigation failure artifact gains `observations`.
Serialization or storage errors add a bounded note to the original exception.
The original exception remains primary, including its existing 180-second
timeout wrapper and cause when the total deadline has expired. Successful
navigation adds no filesystem output. Instrumentation uses values from existing
calls and adds no accessibility or procfs reads, input, retry, sleep or worker.

## Verification

Tests first reproduced missing observation history, lost partial scans and an
artifact error replacing the original navigation failure. Follow-up failing
tests reproduced missing first-blocking provenance and a diagnostic mapping
error replacing an interrupted-scan error.

The eleven focused tests now pass. They cover partial discovery and selection,
empty versus competing selection, changing publications, first-blocking state,
real failure JSON, serialization failure at the original total deadline, fixed
retention and individual bounds. A successful run with observation enabled has
the same accessibility, procfs, input, publication and save calls as the same
fixture with observation disabled.

Checks ran with temporary files outside the source checkout:

```sh
rtk proxy env TMPDIR=/home/shawn/workspace2/task-manager-artifacts/tmp python3 -m unittest discover -s scripts/system-pulse -p 'test_*.py' -q
rtk proxy ruff check scripts/system-pulse
rtk proxy ruff format --check scripts/system-pulse/native_driver.py scripts/system-pulse/native_observations.py scripts/system-pulse/test_native_exit.py scripts/system-pulse/test_native_observations.py
rtk proxy git diff --check
```

All 355 initial Python tests passed. Ruff lint, changed-file formatting, whitespace and
this note's local Markdown links passed.

## Quality correction

The [initial QUALITY review](native-navigation-observations-review.md) found that
both interrupted-scan handlers extracted `snapshot.processes` before entering
the diagnostic helper's guard. A malformed preceding publication could replace
the original scan exception. Regression tests first reproduced this on both the
initial selection scan and the fresh pending-exit scan: missing `processes`
raised `KeyError`, while a null snapshot became a transient `TypeError` and
retried until timeout.

Both handlers now pass the already-read publication reference into the helper.
The helper extracts `snapshot.processes` inside the same guard as mapping.
Extraction and mapping errors therefore produce a bounded `mapping_error` while
preserving the exact original scan exception. The helper does not copy or retain
the publication, and the fix adds no reads or changes to acceptance policy.

All 13 focused observation tests passed after the correction. The full suite
passed all 357 Python tests using the command above with Python's `-B` option.
All-script Ruff lint, formatting for the three changed Python files, whitespace
and this note's five local Markdown links passed. The production self-audit
found no further known defect; independent delta reviews remain pending.

## Limits and self-audit

No Rust changes, builds or live native replay ran for this implementation.
The [previous traced diagnostic](native-publication-navigation-review.md) remains
FAIL with an unproven cause. This instrumentation supplies future evidence; it
does not explain that failure or authorize a navigation remedy. Timestamp and
memory bookkeeping add work inside the unchanged deadlines. Fresh native
acceptance remains unverified.

Reviewed all 14 production rules. The source change is confined to navigation
diagnostics, a small helper and fixture compatibility. Failure handling,
retention bounds, unchanged call sequences and unchanged acceptance behavior
have automated checks. No known implementation defect remains from the
self-audit. Independent SPEC, then QUALITY review, precede the parent's fresh
focused replay with publication tracing disabled.
