# Process-action verification

The implementation is committed in `ca7273de`; the
[decision](../../decisions/authenticate-one-identity-bound-process-action-through-the-operating-system.md)
records the OS authentication and identity boundaries. Native password-dialog
verification is still pending. PROC-004 and the final commitment are not done.

## Completed checks

- Linux: 113 collector library tests, 129 application tests and strict clippy pass.
  The complete preservation suite runs 1,046 tests and validates host readings
  and native product behavior. Thirty-one additional base compatibility tests pass.
- Mac: 129 application tests, 63 collector tests and seven vendored refresh tests
  pass. Nine collector tests cover process-control boundaries, including actual
  AppleScript parsing and quoting without requesting authentication.
- Both direct executable helpers reject a changed birth identity, deliver the
  requested SIGTERM/SIGKILL to owned children, and create no application state.
- Committed native Mac and Linux table observations pass. Mac confirmation
  cancellation leaves owned children alive; ordinary End and Force Quit then
  deliver the expected signals and show success notices.
- The [Linux package acceptance](linux-package-acceptance.json) passes packaged
  application replay, tray behavior, installation and removal. Its source is
  `8fc99332`; later verification-only changes do not alter the application.

The full acceptance first rejected uncommitted Cairn receipts. A later debug
replay failed a freshness check during disk-menu navigation: 2.549 seconds
against the unchanged two-second limit. The original failures remain under
`task-manager-artifacts/process-table/`. A bounded continuation checked the
unchanged commit and binary, revalidated every retained automated/host log hash,
and executed the native and subsequent application-gate statements unchanged.
That native replay and all package stages passed. No freshness fix or broader
performance improvement is claimed.

The continuation script and complete raw evidence are in
`/home/shawn/workspace2/task-manager-artifacts/process-table/continue-auth-acceptance.py`
and `auth-acceptance-resumed/` beside it. The retained manifests link each log
and artifact by its digest. The pinned notice generator is cargo-about 0.9.2 at
`task-manager-artifacts/finish-application/tools/bin/cargo-about`.

## Pending interactive verification

[process_auth_native.py](../../../scripts/system-pulse/process_auth_native.py)
prepares the remaining native observations. Its four boundary tests pass on
Linux and Mac without opening authentication dialogs. It requires the explicit
`--interactive-auth` flag and a developer at the desktop.

The verifier starts its own unprivileged application and asks the OS to create
short-lived root sleep processes. Each fixture exits by itself within 180
seconds. It independently reads the PID, birth identity and owner, verifies
ordinary permission denial, and limits selection to that exact fixture row.
It then checks system-dialog cancellation, authenticated End, authenticated
Force Quit and a target that expires while authentication is pending. The
application's UID must remain unchanged. Only the application tree is read;
password dialogs are neither inspected nor captured.

Run Linux observations through the existing private X11/DBus replay wrapper.
The desktop's polkit agent handles authentication. Mac observations use the
existing `performance_tree.swift` native application helper. Passwords are
entered only into OS dialogs; no password is entered into the agent, command
arguments, application, diagnostic files or test results.

## Review boundaries

The helper accepts only a fixed mode, PID, birth identity and Terminate/Kill
choice before GUI initialization. It never authenticates recursively. A typed
permission-denied result is the sole authentication trigger. Linux signals an
owned pidfd; Mac binds BSD birth time to the kernel PID version and rejects a
missing native interface. Existing seconds-based sysinfo callers remain intact;
the Mac collector retains the precision already present in its BSD observation.

Mac ABI references are Apple's [process identity declarations](https://github.com/apple/darwin-xnu/blob/main/bsd/sys/proc_info.h)
and [libproc interface](https://github.com/apple-oss-distributions/xnu/blob/main/libsyscall/wrappers/libproc/libproc.h).
The Mac signal interface is private; unsupported versions fail with an error.
A final Cairn review of all five requirements still follows interactive proof.

## Interactive attempt on 2026-09-09

The developer answered the readiness escalation. The SSH-launched Mac verifier
failed during root-fixture setup; an isolated 20-second setup probe returned
OS error -60007 immediately. No privileged application action was verified.
The SSH launchctl manager is Background. An owned Aqua LaunchAgent reached the
desktop session but failed before fixture creation because its native helper
lacked Accessibility trust. A separate helper-only check confirmed
`PID and accessibility trust required`. The owned LaunchAgent was unloaded.
The requested caffeinate process remains running. No credentials were used in
commands, scripts, application inputs or artifacts.

Raw failed observations remain on the Mac under the performance directory in
`auth-interactive-20260909T1318/`, `auth-interactive-gui-20260909T1320/`,
and `auth-gui-access-check.log`. These are setup failures, not passing evidence
and not proof of an application authentication defect. Native privileged
actions and Linux interactive verification remain incomplete.

After Accessibility was enabled, the desktop verifier passed its UI setup and
the developer authenticated fixture creation. The verifier then failed reading
PROC_PIDTBSDINFO for root sleep PID 16983. Independent read-only probes returned
EPERM for both that process and PID 1, while SHORTBSDINFO and KERN_PROC_PID
were readable. KERN_PROC_PID returned a complete 648-byte record and a nonzero
microsecond birth time. A compiled SDK layout probe confirmed the record size
and offsets. The collector also depends on the denied full BSD record and its
existing fallback leaves birth identity zero. This requires an implementation
fix before another interactive attempt. The owned GUI job was unloaded; the
180-second fixture expires itself. No application signal was attempted.

The rebuilt `040f5240` candidate passed both native table replays and ordinary
Mac actions. Cairn again passes PROC-001 through PROC-003. During the first
privileged retry, setup authentication created root sleep PID 17888 and the
verifier successfully read and selected its precise identity. The developer
submitted the next dialog, which closed without a visible error. The application
reported authentication failure and the fixture remained alive. The cancellation
observer timed out, retained a failing record, and closed its owned UI; the
LaunchAgent was unloaded. The OS error number is currently collapsed into the
generic authentication message and needs diagnostic context before retrying.
No privileged success or cancellation is claimed.

The diagnostic build verified real OS cancellation on an owned root process.
A subsequent End dialog was also cancelled, so that run correctly remained
incomplete and timed out. The fixture expired without a verified successful
End. A new optional `--step-gates` mode pauses before each dialog, publishing
`operator-step.json` and requiring its `continue-STEP` file after the operator
announces the instruction. This coordinates entry without collecting credentials.
Eight verifier boundary tests pass on Mac (Linux skips the native root case).
The application now preserves a numeric AppleScript authentication error in its
visible failure message while discarding the error text. Nine Linux and eleven
Mac process-control tests pass, including actual AppleScript error-number tests
that do not request authentication. The single-instance observation is captured
as a separate backlog item; no instance-lock implementation is included here.

The committed release `7c203bc9` passed native OS cancellation and returned a
successful End request, but the root sleep did not exit. A native SDK signal
inspection of PID 20007 showed ignored mask `0x848c006`, blocked mask zero and
SIGTERM bit `0x4000`: setup had passed an ignored SIGTERM disposition to the
background sleep. This is a fixture defect, not evidence that the application
failed to send the request. The failed run is retained.

Fixture setup now uses `/usr/bin/python3 -I -S` to reset SIGTERM disposition
and unblock it before exec of the same bounded sleep. Isolated mode prevents
user environment, site or current-directory imports in the privileged setup.
A regression reproduces inherited ignored and blocked SIGTERM without elevation;
it failed before the fix. The application binary is unchanged.

The observer dependency list now lives in `process_table_harnesses.py`.
Authentication records hash that runtime dependency instead of the Cairn gate,
so adding receipt validation cannot invalidate an unchanged native observation.
All 46 process-verifier tests pass on Linux (one Mac-only skip), and the changed
Python modules pass Ruff. Native authentication remains pending.

The corrected Mac run reached root fixture selection and paused before the
cancellation dialog. The developer noted they are working across projects and
may not see prompts immediately. The verifier was interrupted at that safe
checkpoint and its Aqua job unloaded; the owned UI closed and the bounded root
sleep is allowed to expire. No application authentication case ran in this
attempt. The interrupted result remains in `auth-7c203bc9-gated-run2/` on Mac.

The PROC-004 gate now validates all four native cases, unprivileged UI ownership,
root target identities, ordinary denial, cancellation survival, success notices,
expired-target rejection, cleanup, matching builds and observer hashes. Missing
native receipts still leave PROC-004 unverified. All 522 Python checks pass on
Linux (one Mac-only skip), as do collector tests and changed-module Ruff checks.

The current full Linux acceptance stopped after the Python suite: its parser
requires no skipped tests. Root PID 1 identity observation is applicable on
Linux as well as Mac, so that test now runs on both hosts; all 16 authentication
verifier tests pass without skips on each host. The acceptance parser is
unchanged. The interrupted Mac fixture has now independently been observed
exited. No verifier, owned UI or authentication dialog remains active.

## Current Linux acceptance

Full [application/package acceptance](evidence/linux/application-manifest.json)
passes against `c87880f33a426d8c2b98fee75487bfed6a8b6aa7`. Its release
binary matches the existing `7c203bc9` Linux native build by SHA-256. The run
passes 1,063 preservation tests, formatting, strict clippy, debug build,
independent live readings and native replay; ten input-focus tests, packaging,
packaged application replay, tray behavior and installation/removal also pass.
All manifest log and artifact hashes were revalidated before retaining it here.

Earlier attempts remain outside the checkout in `auth-current-acceptance-20260909*`.
The first rejected the now-removed platform skip. The second found stale debug
collector metadata missing the authentication export (retained SHA-256
`7e4302d59e093d18da1ea2faa0978782cfdc9d1daac2878b488ecb3f989e54ae`).
Cleaning only that package and rebuilding without the compiler wrapper produced
metadata containing the export and a successful debug build. The third passed
automated checks but lacked an earlier independent counter observation for one
process, leaving four brackets unverified. The fourth complete run passed with
compiler caching disabled; no source or acceptance criteria changed between
those last two runs. No broader performance correction is claimed.

Ripwire quality delta still exits 2 with 648 gating findings, including existing
reference findings; it is not a clean result. Its test gate exits 0 on the
committed tree. Changed verification code has passing focused tests and lint;
native OS authentication on both hosts and the final commitment review remain
pending. No privileged-action completion claim is made.

The developer clarified that delayed attention to dialogs is not a request to
pause. The scheduling escalation is answered and native verification resumes.
Ordinary fixtures and authentication-result waits now allow 1,800 seconds,
while the deliberate expired-target fixture remains 20 seconds. This changes
only verification timing; identity, cancellation, signal and cleanup assertions
remain unchanged. All 16 authentication verifier tests pass on both hosts and
the changed Python modules pass Ruff.
