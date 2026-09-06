# Interrupted pending navigation implementation

Implemented the [pending-endpoint decision](../../decisions/recover-a-pending-navigation-batch-after-proven-endpoint-exit.md)
on base `17d39770`. The [b9safeex failure](native-pending-endpoint-failure.md)
remains failed. It lacks the independent before/terminal evidence; this change
cannot reconstruct its missing acknowledgement.

## Protocol and evidence

Only a pending intermediate arrow endpoint different from the controlled target
receives an independent pre-dispatch stat observation. The focused
[native_pending.py](../../../scripts/system-pulse/native_pending.py) helper reuses
`host_capture.observe(source, reader)` and `host_accuracy.parse_process_stat`.
It reads `/proc/<pid>/stat` directly and retains literal raw text, source, parsed
PID/start identity, errno or parse error, and the independent monotonic read window.
It does not call the generic process collector or read process status or I/O files.

The helper freezes the `/proc` device/inode and observer/application PID namespace
lookup context before and after each read. It requires the application and
observer to use the same PID namespace. It never compares the endpoint's own
namespace: a process in a nested namespace can still have a valid host PID.
Terminal observations must match the baseline lookup context. Driver timestamps
also retain the full helper query window, including namespace checks and parsing.
No collector-relative clock is compared directly with the driver's clock.

An eligible arrow batch retains its original expected identity/index, issue
publication, planned and actually dispatched keys, independent baseline, dispatch
window, and original eight-second and 180-second absolute deadlines. A terminal
ENOENT/ESRCH before dispatch sends no keys and replans with the same remaining
batch budget. Replanning preserves the previous acknowledged endpoint's issued
index. Permission errors, malformed evidence, wrong identity/PID reuse, or invalid
query windows fail.

After dispatch, snapshot absence only triggers fresh eligibility discovery.
A complete strict native scan must establish a unique current Processes panel,
current application/panel links, no instantiated selected identity, a snapshot
without the expected identity, and the exact surviving controlled target. Native
row identities must be unique and belong to that snapshot. An observed selected
competitor or reused PID fails before the fresh retry can discard it.

Only independent terminal stat ENOENT/ESRCH can authorize interruption. A live
matching endpoint omitted by the application fails. Terminal read and full-query
windows follow completed dispatch. After the terminal read, fresh global discovery,
strict selection scanning, current links, and publication checks repeat; a changed
publication or replacement requires fresh eligibility under the same deadline.

`InterruptedNavigation` is an explicit unverified outcome. The
`navigation-batch-interrupted` journal retains the frozen issue, independent
observations, current publication/snapshot identities, and instantiated native
identities. It claims neither selected-endpoint acknowledgement, processed keys,
nor model selection clearing. Existing post-ack absence reconciliation records
`navigation-absence` rather than a selected acknowledgement. Other wait callers
keep their acknowledgement behavior.

Recovery journals and physically sends Home/End, freezes its newly chosen endpoint,
and requires that exact selected identity within the same remaining batch and total
deadlines. Recovery does not receive the interruption option. Journaling cannot
extend a deadline; both the navigation caller and the physical key method check
before dispatch after their journal writes. Key release and generic/held-input
calls retain their behavior. Ordinary navigation receives a new batch budget only
after a real exact endpoint acknowledgement.

The final controlled-target proof and callback, all sixteen independent cell
comparisons, selected-child exit verification, held input, and exact-64-key
exercise are unchanged. Only the driver, focused helper, navigation fixtures,
new pending tests, and this record changed.

## Verification

Tests were written and run before driver changes. The original driver reproduced
the two-Up endpoint disappearing before acknowledgement, and both misleading
selected acknowledgements from absence (including the flag-only pending shortcut).
Further failing tests exposed duplicate native rows, snapshot PID reuse, a key
journal crossing the deadline, and invalid frozen publication/deadline evidence.
The corrected protocol passes these regressions.

Final commands and results:

- `rtk proxy env PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/system-pulse -p test_native_pending_endpoint.py`: 23 tests passed.
- `rtk proxy env PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/system-pulse -p 'test_native*.py'`: 227 tests passed in 10.525 seconds.
- `rtk proxy env PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/system-pulse -p 'test_*.py'`: 331 tests passed in 16.061 seconds.
- `rtk proxy ruff check scripts/system-pulse`: passed.
- `rtk proxy ruff format --check scripts/system-pulse/native_driver.py scripts/system-pulse/native_pending.py scripts/system-pulse/test_native_navigation.py scripts/system-pulse/test_native_pending_endpoint.py`: all four files formatted.
- `rtk proxy git diff --check`: passed. Relative links in this record were checked locally.

The broad `ruff format --check scripts/system-pulse` remains unsuccessful only for
three untouched baseline files: `test_capture_stream.py`,
`test_missing_device_specimen.py`, and `test_requirement_verdicts.py`. They were
not reformatted.

Adversarial cases cover baseline absence/wrong identity, live omission, both
terminal disappearance errnos, permissions/other errors, malformed raw text,
missing/reversed/future windows, wrong source or namespace, controlled-target loss,
competing/multiple selection, stale/incomplete/detached/duplicate native evidence,
publication/membership replacement during terminal observation, pre-dispatch
replanning, original issued-index provenance, journal expiry, exhausted shared
budgets, failed recovery acknowledgement, and successful final callback evidence.
The previous navigation and inspection tests retain their assertions.

## Observation costs and limits

A local helper microprobe ran 20 reads of its own Python PID and 20 reads of absent
PID `2147483647`, with the probe itself as the application namespace reference.
It used `read_stat` and independent `time.monotonic_ns()` brackets around the full
helper. No System Pulse application or native session ran.

| Local probe | Stat read min / median / max, ns | Full helper min / median / max, ns |
| --- | --- | --- |
| Self PID, matching stat | 7,452 / 7,926 / 17,605 | 19,276 / 19,806 / 54,941 |
| Absent PID, ENOENT | 3,782 / 4,011.5 / 9,029 | 13,731 / 13,951 / 22,284 |

These measurements are local helper costs, not native acceptance timings or an
exit bracket for one process. The protocol tests' artificial query delays and
existing large-population discovery costs are synthetic. Fresh captures will
retain actual stat and full-helper windows for every observation.

Reviewed all 14 production rules against the final change. Scope, explicit
outcomes, error handling, evidence provenance, fixed deadlines, fixture contracts,
and unchanged mandatory proofs were checked; no unresolved implementation defect
was found in this self-audit. No live capture, Rust build, Cairn check/mutation,
merge, or push ran. Independent SPEC then QUALITY review and fresh native/aggregate
acceptance remain separate work.


## SPEC correction: start the final bracket after discovery

The [independent SPEC review](native-pending-endpoint-review.md) of `69ac6897`
found that post-terminal validation incorrectly required a publication captured
before global discovery to remain current through that discovery. A test-first
reproduction uses one-second collector publications and a 1.1-second discovery
cost after endpoint loss. RED performs three valid terminal ENOENT reads and seven
discoveries after loss (eight including initial discovery), then fails at 9.2
seconds against the original 8.5-second batch deadline. The zero-cost and
0.3-second controls succeed.

The correction retains fresh global discovery and current application/panel links,
then captures a new before/after publication bracket around the complete strict
selection scan. It recomputes target survival, expected absence, PID reuse,
snapshot uniqueness, and native row/selection membership from that current
bracket. The interruption artifact records that snapshot's identities. The
independent terminal observation remains prior evidence; a publication change
during discovery does not invalidate it. Publication changes during the strict
scan still reject the observation and require a new complete proof. Existing
coherently observed competitors or PID reuse still fail before any retry.

With the same synthetic 1.1-second discovery cost, GREEN uses one terminal read,
records interruption and dispatches recovery at 2.95 seconds under the same
8.5-second deadline, and completes final target proof at 6.05 seconds. No budget,
freshness, uniqueness, final target, inspection, metric, exit, or held-input
requirement changed. These times are synthetic protocol costs, not native timing
measurements.

New cases mutate the post-terminal scan to lose the target, restore the expected
identity, reuse its PID, introduce a competing or multiple selection, duplicate
snapshot/native identities, expose a foreign row, become stale, detach the panel,
or produce an incomplete tree. Further cases reject a publication change within
the new bracket and verify that a replacement publication's membership is what
the interruption artifact retains. The existing publication-change case now
requires one terminal read plus the fresh native bracket, instead of requiring a
redundant terminal read solely because the earlier publication changed.

Correction verification uses the same commands listed above: pending tests passed
27 cases; 231 native tests passed in 10.980 seconds and 335 full Python tests
passed in 16.543 seconds. Broad
Ruff lint and the four-file format check passed. Documentation links and
`git diff --check` were checked again. Only `native_driver.py`,
`test_native_pending_endpoint.py`, and this implementation record changed in the
correction. No native capture, build, Cairn check/mutation, merge, or push ran.
The production self-audit was repeated with the SPEC finding resolved; fresh
independent SPEC then QUALITY review remain required.
