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

No host capture or native session ran for this implementation. Independent review
and fresh committed native and aggregate acceptance remain required before
claiming live acceptance.

## Specification review correction

Independent specification review found that a live cached row bypassed current
Processes-panel membership and row uniqueness. Three regressions reproduced the
finding before correction: a detached cached row supplied a cell, duplicate rows
passed with a live cache match, and panel discovery cached a same-ID row from an
unrelated panel and returned its cell.

Every lookup now scans the current Processes panel for the unique exact row,
skipping all process-cell descendants until that row is selected. It does not
use the global row cache as evidence. The same deadline and node budget apply.
This requires a row scan even when the cache contains a live match; native timing
remains subject to the original acceptance budget.

After correction, all 50 native harness tests passed, including 24 cell tests.
The exact full Python command above passed 154 tests. Ruff lint, format checks,
and `git diff --check` passed. Self-audit covered the three review cases and found
no remaining known implementation issue. Independent re-review remains pending.

## Quality review correction

After specification re-review passed, quality review found the equivalent cache
boundary at the panel level. Four regressions failed before correction: a live
cached panel supplied cells after detachment, after renaming, with a wrong role,
and despite duplicate current Processes panels.

Every lookup now discovers the unique Processes panel with the expected name and
role under the current application root. It uses the existing traversal with
process-cell descendants skipped. The panel cache cannot bypass this check.
Two old assertions forbidding root discovery were removed because they conflict
with verifying current application membership; unrelated-cell pruning remains
covered. Generic lookup, strict exit traversal, and all budgets are unchanged.

All 54 focused native tests passed, including 28 cell tests. The exact full
Python command above passed 158 tests. Ruff lint, formatting, and diff checks
passed. No live run was performed. Self-audit found no remaining known defect;
independent re-review remains required. Each lookup now traverses the application
tree with process-cell descendants skipped, so the fresh native run must establish
whether it meets the unchanged five-second deadline.
