# Native process exit synchronization repair

Status: implemented with deterministic checks; fresh native acceptance pending.
Base: `bc5237d1f8e24074a5eb4d75d1e409ef9e944847`.

## Cause and change

The [failed capture](native-exit-failure.md) observed a newer child-free diagnostic
snapshot while the native Processes tree still contained that PID/start identity.
`WorkspaceView` publishes diagnostics before refreshing panels and notifying the
UI. Snapshot publication therefore cannot acknowledge native row removal.

`Native.wait_for_process_exit` now requires both observations in one poll: a
strictly newer snapshot without the identity, and its absence from a live native
Processes subtree. The replay starts the same five-second absolute deadline
immediately after `stop_child`. The helper passes that deadline through native
lookup, traversal, and the existing wait; it adds no second wait budget or sleep.

The helper clears accessibility caches through the existing liveness/traversal
methods. A missing or defunct cached panel uses an explicit bounded lookup,
without calling the panel helper that could start a fifteen-second discovery.
The scan must yield the panel itself and confirm it remains alive afterward.
It skips process cells while checking exact PID/start row identities. Traversal
errors and late completion still fail. Existing app-liveness and diagnostic
freshness checks remain active. No application source or comparison bound changed.

## Verification

The regression harness compiles the real driver class and replay exit statements
from their ASTs. Only the native transport, diagnostic input, and clock are faked;
the actual wait, liveness checks, traversal, panel lookup, identity conversion, and
replay deadline boundary execute without GI, DBus, or a native app.

The first run on the original source ran ten tests and failed five as expected:
the diagnostic-before-native race, premature retained-row failure, missing and
defunct panel discovery reaching 15.5 seconds, and successful completion of a
slow tree scan after the original deadline. The remaining five controls passed.

After the repair, all fourteen focused tests passed. They cover delayed removal,
permanent retention, old sequences, snapshots still containing the child, missing
and defunct panels, replacement of a defunct cached panel, panel disappearance
before/during traversal, slow traversal, PID reuse, app exit, stale diagnostics,
and the deadline starting after child cleanup. Full discovery passed all 100
Python tests, including the 86 existing tests. Ruff lint and formatting checks
also passed for all three changed Python files; the focused suite passed again
after formatting the test file.

Commands run from the worktree root:

```sh
rtk proxy /home/linuxbrew/.linuxbrew/opt/python@3.14/bin/python3.14 -m unittest discover -s scripts/system-pulse -p test_native_exit.py -v
rtk proxy /home/linuxbrew/.linuxbrew/opt/python@3.14/bin/python3.14 -m unittest discover -s scripts/system-pulse -p 'test_*.py' -v
rtk proxy ruff check scripts/system-pulse/native_driver.py scripts/system-pulse/native_replay.py scripts/system-pulse/test_native_exit.py
rtk proxy ruff format --check scripts/system-pulse/native_driver.py scripts/system-pulse/native_replay.py scripts/system-pulse/test_native_exit.py
rtk proxy git diff --check
```

These checks are implementation verification, not Cairn acceptance evidence.
No native replay, host acceptance, build, or Cairn check ran for this repair.
The original captured run remains FAIL. Independent SPEC then QUALITY review
and a fresh committed shared acceptance run are still required.

## Self-audit

The change is limited to the native driver, the replay exit call, its focused
regressions, and this record. It preserves process identity semantics, existing
error handling, and all time limits. Review against the production coding rules
found no known implementation defect. Actual AT-SPI timing and transport behavior
remain subject to the fresh native acceptance run.
