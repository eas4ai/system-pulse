# Windows UAC process actions and GPUI Kit 0.6.1

Contract: [WUAC-001 through WUAC-007](../spec/windows-uac-process-actions.md).
All work stays local unless the developer separately authorizes a push or CI.

- [x] Activate the approved commitment, declare mechanisms and scope, and record the framework upgrade design after inspecting upstream and local patches.
- [x] Upgrade GPUI Kit and reconcile companion/native patches; verify the locked graph, local checks and Linux/macOS/Windows native preservation (Cairn WUAC-007 passed).
- [x] Declare and implement Windows native process identity and graceful/forceful controls with boundary tests; verify committed native tests and ordinary packaged actions.
- [ ] In progress: implement one-action UAC helper launch/result handling and responsive confirmation/error UI; verify ordinary, cancellation, denial and stale-target paths. Implementation, ordinary packaged cases and fresh Mac preservation pass; real UAC evidence remains pending.
- [ ] Collect native Windows approval/credential/cancellation and packaged-layout evidence; run Linux/macOS preservation checks and update support documentation.
- [ ] Record final adversarial review, resolve findings separately, and finish Cairn evidence. No hosted CI or publication is included without separate authorization.

## Native Windows action observations

After committing the implementation, run `windows_build_verify.py` with
`SYSTEM_PULSE_WINDOWS_HOST` set and retain its reported `build.log`. Build the
Windows ZIP with `package_binary.py` from the same committed source on Windows,
then copy its ZIP and `SHA256SUMS` to a local package directory. Run:

```sh
python3 scripts/system-pulse/windows_process_actions_collect.py --build-log /path/to/build.log --package-dir /path/to/package
python3 scripts/system-pulse/windows_process_actions_verify.py --build-log /path/to/build.log --package-dir /path/to/package --evidence /reported/evidence/path
```

The runner validates the shipped ZIP's source, licenses, file inventory and binary
against the native build, then transfers and extracts it on the Windows host. It
runs in a limited interactive desktop, creates disposable GUI and windowless
targets, and places the package under a path containing spaces and non-ASCII text.
The result records full native creation identities, confirmation
and result screenshots, dashboard token observations, helper entry refusals and
cleanup. It covers ordinary cooperative/refusing/unavailable End task, Force quit,
confirmation cancellation, an exited selection and responsiveness during a delayed
close. It refuses uncommitted production or harness edits.

These observations do not establish UAC approval, UAC cancellation or the standard
user credential path. Those cases still need actual human interaction with Windows
and separate native evidence before WUAC-002 through WUAC-006 can pass. A successful
collector run is an observation receipt, not a Cairn acceptance verdict.

## UAC observation harness

`windows_process_uac_collect.py` prepares one isolated packaged run with a limited
dashboard and an elevated observer that owns its disposable target. The observer
uses native process start/stop events to count helpers and consent processes. The
dashboard alone requests UAC. `--case ordinary` requires no operator; consent cases
require the human to be present and `--operator-ready`. The stale case prints a
target-exited cue before the human approves the waiting prompt.

UAC runs never capture screen pixels, including on failure. They retain only the
application's accessibility observations and native process metadata. The native
trace self-test exercises six malformed, short-lived helper invocations without
UAC. Stop-event names are truncated on this Windows host, so lifecycle correlation
uses exact start events and PIDs instead of requiring full stop-event image names.

The initial collector covers ordinary actions, administrator consent, cancellation,
cooperative/refused/delayed closure and exit during consent. Credential-account,
post-elevation denial, helper-failure and resource-lifetime verification remain
unfinished. The full acceptance verifier refuses to pass while those cases or
their observations are missing. A single-run verifier result accepts only that
observation and does not accept WUAC-002 through WUAC-006.
