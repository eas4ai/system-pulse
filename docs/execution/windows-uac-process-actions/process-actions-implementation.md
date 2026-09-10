# Windows process-action implementation

Status: implementation verification in progress; not commitment acceptance.

Windows collection retains the full FILETIME creation identity. Actions validate
that identity through an owned process handle. Force quit uses that same handle;
End task registers only the selected GUI process with a private Restart Manager
session and never requests forced shutdown. Missing windows, refusal and observed
exit remain distinct outcomes.

A denied Force quit handle now receives a read-only identity and protection check
before authorization is offered. Failure to verify safety does not trigger UAC.
The helper accepts one fixed request, checks elevation and the caller's executable
identity, revalidates the target, and exits with a bounded result vocabulary.
The normal executable retains its asInvoker manifest. Real UAC verification is
still pending.

Confirmation retains its original identity. Busy state survives recreation of the
Processes screen, blocks duplicate submission and publishes native disabled button
state. Windows confirmation and result text distinguish graceful closure from
Force quit and describe the unsigned executable accurately.

Editing checks passed on Linux: 1,714 workspace Rust tests, workspace Clippy without
warning promotion, formatting, and 553 Python tests. Windows passed five application
UI tests, 17 component button tests, 13 process-control tests, Clippy and a release
build. The process-control tests include full creation-time comparisons, wrong
identity refusal, protected/exited targets, executable aliases, unrelated-window
protection and denial classification.

The editing release executable has SHA-256
`f00bfa63cf45585d6d5bae923e6cae2ef2fe3cfa18030ad8fdee4a3a6fef08c4`.
Seven ordinary desktop cases exercised confirmation cancellation, cooperative and
refusing GUI applications, unavailable windowless closure, Force quit, an exited
selection and a slow-response application. Navigation and sampling continued while
the slow request was pending. The dashboard remained unelevated and unrelated
control processes were unaffected. Harness-owned processes were cleaned up.

Inspection exposed two harness issues: Windows PowerShell provider metadata caused
recursive JSON serialization, and diagnostic readers could briefly block atomic
snapshot replacement. The reader now returns plain text with read/write/delete
sharing; nonempty application stderr fails the run. The slow-response fixture is
expected to remain alive when Restart Manager refuses shutdown; successful graceful
exit is established separately by the cooperative case.

These editing observations are not committed-source Cairn evidence. The committed
runner requires a validated native Windows ZIP, verifies its source and file hashes,
and exercises the extracted package under a directory containing spaces and
non-ASCII text. It cannot accept UAC requirements on ordinary observations alone.

Remaining work includes fresh committed-source Windows/package and Linux/macOS
preservation evidence, actual administrator consent and standard-user credential
paths, UAC cancellation and stale-target observations, helper lifetime/failure and
handle cleanup evidence, and the final adversarial commitment review.
