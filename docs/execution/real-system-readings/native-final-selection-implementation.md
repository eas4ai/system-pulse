# Retain the issued endpoint during final selection proof

The [final-confirmation failure](native-final-selection-failure.md) exposed
an omitted argument in `_navigate`. Its final independent selection check
now receives the same immutable `endpoint_index` retained from the last
issued key batch. This completes the [existing recovery decision](../../decisions/reveal-a-navigation-endpoint-shifted-outside-native-visibility.md)
and [committed plan](../../plans/real-system-readings.md) at `9c216290`.

The production change only passes that argument. Fresh panel discovery,
reconciliation, exact PID/start selection, current membership, coherent
publication, every recovery guard, and the existing deadlines remain in
the shared helper. The inspection callback still exports the successful
final frame and its current positive index.

## Regression evidence

The new regression runs the real `_navigate` and selection/recovery
methods with simulated publication, native nodes, clock, and input. It
issues Home, Down, Down to index 2, acknowledges the exact target, then
moves that target to index 1 as final proof begins. The instantiated span
is indices 2 through 4. Before the correction, both success subcases
raised the expected original-deadline timeout from final selection.

After the correction, final proof starts at simulated time 1.0 and
completes at 1.75 under the unchanged deadline of 9.0. It uses one
nonselecting wheel and no further keys. Recovery records original index
2, current index 1, and span 2 through 4. A second subcase places the
intermediate acknowledgement at index 3, proving that final recovery
uses the issued index rather than that later observation. The exported
acknowledgement has index 1 and the successful final publication.

Additional cases reject an unchanged index, an original slot outside the
visible span, stale frames, detached membership, and duplicate panels
after a rejected scan. A duplicate panel after the wheel also prevents
final acknowledgement. Invalid eligibility emits no wheel, and timeout
cases retain the original deadline. Existing helper tests continue to
cover identity loss/reuse, ambiguous or incomplete scans, selection
transfer, clipping, and late physical input.

## Verification

Commands below ran from the worktree root, except the focused test command
which ran in `scripts/system-pulse`:

- `python3 -m unittest test_native_navigation`: 76 tests passed.
- `python3 -m unittest test_native_navigation test_native_inspection`:
  101 tests passed after formatting.
- `python3 -m unittest discover -s scripts/system-pulse -p 'test_*.py'`:
  308 tests passed.
- `ruff check scripts/system-pulse`: passed.
- `ruff format --check scripts/system-pulse/native_driver.py scripts/system-pulse/test_native_navigation.py`:
  both changed files passed.
- Local Markdown link targets and `git diff --check`: passed.

The broad `ruff format --check scripts/system-pulse` does not pass:
`test_capture_stream.py`, `test_missing_device_specimen.py`, and
`test_requirement_verdicts.py` need formatting. Checking their committed
contents at `9c216290` reproduced all three findings; they are unchanged.

Self-audit against the production rules found no further revision needed
within this bounded correction. No Rust source changed or Rust check ran.
No native capture, Cairn acceptance, build, merge, or push ran for this
implementation. Independent SPEC then QUALITY review and fresh native
and aggregate acceptance remain required. These tests do not establish
the exact timing or cause of every observation in the retained live failure.
