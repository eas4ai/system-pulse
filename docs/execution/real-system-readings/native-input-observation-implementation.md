# Held input observation implementation

Implements the judged decision
[observe-held-input-movement-before-waiting-for-collection](../../decisions/observe-held-input-movement-before-waiting-for-collection.md).

The input exercise now measures native movement after release and before
waiting for subsequent collector sequences. The existing publication watcher
runs across both checks and is stopped and joined in the existing `finally`
block. The three-second hold, five-second movement limit, three fresh sequences,
publication age checks, signed movement check, exact 64-key burst, and exact
expected-identity acknowledgement remain in place.

An optional `observe(deadline)` callback returns the numeric movement value and
the exact observed identity together. The two process exercises use one native
selection read for both PID and PID/start identity; the before/after identities
are saved alongside the numeric values actually compared. Ordinary geometry
callbacks remain unchanged. Native absence returns no observation and triggers
a bounded retry; it never becomes PID zero or evidence of cleared model
selection. Baseline and post-input observation each receive one absolute
five-second deadline, passed through to `selected()` on every retry. The real
`Native.wait()` rejects a result completed after that deadline.

The retained failed diagnostic did not capture release-time selection. This
change corrects the known observation ordering and adds evidence; it does not
establish that exit, focus loss, transfer, or missing input caused that failure.
The separate selection/exit evidence work is not part of this change.

## Verification

Initial RED ran 11 focused tests with two failures and four errors: movement
was observed after sequence waiting, the failed-movement check started two
seconds later, and the identity/deadline callback was absent. The corrected
tests pass. Two further tests cover absent baseline selection and the real
replay call sites; an AST fixture line-metadata error was corrected before the
final verification.

The tests exercise real input-exercise logic, `Native.wait`, `Native.sequences`,
the publication watcher, and the replay callback/call boundaries without a
native session. They cover wrong signed movement, stale/missing publication,
exact burst count and endpoint failure, absent selection, shared deadlines,
numeric/identity correspondence, and observer cleanup.

- 13 input regressions; all 133 focused native Python tests passed in 4.281 s.
- All 237 Python tests passed in 9.935 s using
  `/home/linuxbrew/.linuxbrew/opt/python@3.14/bin/python3.14 -B -m unittest discover -s scripts/system-pulse -p 'test_*.py'`.
- Tests used `TMPDIR=/home/shawn/workspace2/task-manager-artifacts/tmp`.
- Scoped Ruff lint/format and `git diff --check` passed.

No native runs, builds, Rust edits, or Cairn mutations were performed. Independent
SPEC and QUALITY review precede the parent's next untraced native verification.

## Retain the main reader's sequence evidence

The subsequent untraced run observed held movement and the exact 64-key
endpoint, but the independent watcher retained only two sequences before
shutdown. The main `Native.sequences()` call had observed three and returned
their records; the input exercise discarded that list.

`Native.sequences()` now captures age immediately after each existing frame
read and retains it beside the existing sequence and accepted timestamp.
The input exercise appends the returned actual sequence/age records to the
watcher observations before stopping the watcher. Every watcher record and
error remains intact. No additional frame reads, sequence waits, callback
mechanisms, or deadline changes were introduced. Ages are neither fabricated
nor recomputed when the sequence wait returns.

Four regressions cover a third main-reader observation missed by the watcher,
watcher errors surviving the merge, read-time age versus later return-time
age, and compatibility of existing sequence fields/count options. RED
reproduced the three-sequence evidence failure and missing age field; all
17 input tests now pass. Final verification: all 144 focused native tests
passed in 4.562 s and all 248 Python tests passed in 10.161 s using the exact
Python 3.14 and TMPDIR commands above. Scoped Ruff lint/format and
`git diff --check` passed. No live runs, builds, or Cairn mutations were made.
