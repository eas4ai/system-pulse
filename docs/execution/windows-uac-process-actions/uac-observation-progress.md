# Windows UAC observation progress

Historical approval and cancellation observations are retained under `uac-native`
and `uac-native-attempts`; see `human-observations.md` for the operator responses.
These receipts predate the live-dashboard handle checkpoint and must be rerun
before the complete acceptance verifier can accept them.

The native trace and fault self-tests passed. The new handle self-test also passed
real synchronization, query and termination handle positive controls, snapshot
release and owned-child cleanup. The source-bound result is in
`native-handle-selftest.json`. The Python suite passed 566 tests.

The current harness keeps the dashboard alive after the action settles while an
independent observer checks the actual owned target and helper handles. The full
verifier requires all ten current-harness cases, matching packaged binary identity,
platform preservation and a source-bound resource ownership review. Delayed consent
must also demonstrate sampling progress during the actual prompt lifetime.

Current-harness native cases and final review remain pending. The developer has
returned to the Windows desktop. Begin with ordinary actions, which require no
UAC response, then announce each interactive case before running it. The agreed
scope is administrator consent; standard-user credential entry is excluded.

All work remains local. No push, hosted CI or release was performed for this work.
