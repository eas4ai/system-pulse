# Native process cell lookup repair

The [recorded decision](../../decisions/scope-process-cell-discovery-to-its-native-row.md)
repairs the harness lookup that stopped the retained native replay at column 6.
The [failed capture](native-cell-discovery-failure.json) remains unchanged.

`Native.process_cell` shares the metric lookup with the replay visibility loop.
It reacquires the Processes panel and exact PID/start row while skipping other
rows' cells. It scans the target row for a unique cell, rechecks identity and
liveness, and retries transient replacement under the caller's absolute deadline.
A cached cell cannot bypass row membership or uniqueness checks.

The replay passes its original five-second deadline through discovery,
replacement lookup, visibility, and movement acknowledgement. It checks the
deadline before sending a movement key after reading geometry. Each column still
requires the existing independent native metric comparison. Initial metric
discovery retains its separate fifteen-second allowance; its five-second metric
bracket and comparisons remain unchanged. Generic lookup and strict process-exit
traversal are unchanged.

## Verification on 2026-09-05

Twenty new tests failed before production changes. They exercise the real Native
class and replay visibility loop with a deterministic clock and native node
doubles. A twenty-first failing test exposed a movement key sent after a slow
bounds read exhausted the deadline; the repair now rejects that keypress.

- Focused native harness suite: 47 tests passed, including 21 new cell regressions.
- `/home/linuxbrew/.linuxbrew/opt/python@3.14/bin/python3.14 -B -m unittest discover -s scripts/system-pulse -p 'test_*.py'`: 151 tests passed.
- Ruff lint and format checks on the three changed Python files passed.
- `git diff --check` passed.

Coverage includes unrelated-cell pruning, defunct panel/row/cell replacement,
wrong cached identity, PID reuse, missing rows/cells/panels, duplicate cells,
node limits, slow and expired deadlines, replacement during movement, all eight
visible metric calls, and metric reacquisition using the same shared helper.

Self-audit against the production rules found no remaining implementation issue.
No host capture or native session ran for this implementation. Independent spec
and quality review, followed by fresh committed native and aggregate acceptance,
remain required before claiming live acceptance.
