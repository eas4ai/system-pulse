# Selection and exit evidence implementation

Implements the judged decisions
[recover-native-navigation-without-claiming-model-selection-evidence](../../decisions/recover-native-navigation-without-claiming-model-selection-evidence.md)
and [prove-process-exit-in-the-current-native-panel](../../decisions/prove-process-exit-in-the-current-native-panel.md).

## Evidence boundary

The native process table is virtualized. A complete native scan with no
instantiated selected row permits explicit Home/End recovery; it does not prove
that the full model selection cleared automatically. The navigation comment
now states that limit without changing its behavior.

A new GPUI integration regression establishes selection using the existing
table focus and native-key helper, then submits snapshots through production
`WorkspaceView::accept_snapshot`. It verifies both accepted snapshot identities
and rendered process-view identities. It checks the exact `panel.selected`
immediately after reordering, removal with a surviving row, and replacement by
the same PID with different start ticks. No subsequent key can hide stale
selection in these assertions. Existing product behavior passes this test;
no Rust production code changes were needed.

## Current native exit proof

Each exit proof attempt now discovers the unique current Processes panel using
`navigation_panel(deadline)` instead of trusting a live cached panel. The
existing strict cell-pruned scan completes even when it sees the target, so a
foreign selected sibling cannot be hidden by an early return. It records target
presence, verifies current panel/application membership after the scan, and
rejects any other instantiated selected identity before acknowledgement.

The newer child-free snapshot prerequisite, exact PID/start identity, native
node/ancestry bounds, and original five-second absolute deadline remain in
place. Missing or incomplete membership triggers another proof attempt within
that deadline. The application registration fixture uses the actual null-parent,
index-minus-one adapter semantics and current desktop-child enumeration.

## Verification

Initial RED: 29 exit tests ran with six failures and one error. They reproduced
false success from a detached empty cached panel, duplicate panels, replacement
after scanning, incomplete registration, and an undetected foreign selected
row. A foreign selected sibling after the retained target was missed until the
old implementation timed out. All seven new regressions now pass, including
the check that every rediscovery receives the original deadline.

- 29 exit regressions; all 140 focused native Python tests passed in 4.403 s.
- All 244 Python tests passed in 9.965 s using
  `/home/linuxbrew/.linuxbrew/opt/python@3.14/bin/python3.14 -B -m unittest discover -s scripts/system-pulse -p 'test_*.py'`
  with `TMPDIR=/home/shawn/workspace2/task-manager-artifacts/tmp`.
- The focused GPUI test
  `native_tests::accepted_process_snapshots_preserve_identity_and_clear_removed_selection`
  passed. `cargo test -p system-pulse` then passed all 49 app tests; binary and
  doc-test targets contained no tests.
- `cargo clippy -p system-pulse --all-targets -- -D warnings` passed.
- Scoped Ruff lint/format, rustfmt for `native_tests.rs`, and
  `git diff --check` passed.

No live acceptance session or full aggregate was run. Independent SPEC and
QUALITY review precede fresh committed native and aggregate acceptance.
