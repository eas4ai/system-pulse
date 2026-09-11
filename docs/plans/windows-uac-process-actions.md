# Windows UAC process actions and GPUI Kit 0.6.1

Contract: [WUAC-001 through WUAC-007](../spec/windows-uac-process-actions.md).
All work stays local unless the developer separately authorizes a push or CI.

- [x] Activate the approved commitment, declare mechanisms and scope, and record the framework upgrade design after inspecting upstream and local patches.
- [x] Upgrade GPUI Kit and reconcile companion/native patches; verify the locked graph, local checks and Linux/macOS/Windows native preservation (Cairn WUAC-007 passed).
- [x] Declare and implement Windows native process identity and graceful/forceful controls with boundary tests; verify committed native tests and ordinary packaged actions.
- [ ] In progress: implement one-action UAC helper launch/result handling and responsive confirmation/error UI; verify ordinary, cancellation, denial and stale-target paths. Implementation and all ten native observations pass; committed full acceptance is in progress.
- [ ] Collect native Windows administrator approval/cancellation and packaged-layout evidence; run Linux/macOS preservation checks and update support documentation.
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

These observations do not establish UAC approval or UAC cancellation.
Those cases still need actual human interaction with Windows
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
cooperative/refused/delayed closure and exit during consent. Post-elevation denial,
helper-failure and resource-lifetime verification remain
unfinished. The full acceptance verifier refuses to pass while those cases or
their observations are missing. A single-run verifier result accepts only that
observation and does not accept WUAC-002 through WUAC-006.

The denial/crash/timeout collectors are now implemented, with native fault
self-tests passing on disposable processes. The observer removes its own debug
privilege before creating targets; the initial SSH token otherwise bypassed the
test DACL. Owned fault targets enter a job that terminates them when its handle
closes, including when the observer exits. These self-tests do not replace the
still-pending real application UAC cases. The Python suite passed 562 tests after
these harness changes. Ripwire's test gate named three tests, all included in that
suite; its quality-delta command could not establish a Git baseline in this
checkout, through either CLI or MCP, so no quality-delta pass is claimed.

The first real consent preflight found that the medium-integrity account could
open a termination handle to its same-user high-integrity fixture without debug
privilege. No UAC prompt occurred in that failed run. The owned UAC fixtures now
use an explicit administrator termination DACL, with independent elevated and
limited access probes before the application action. Native elevated access,
denial, retained-handle cleanup and all 16 process-evidence tests passed after
this correction. The older ordinary receipt predates these harness hashes and
must be recollected; no real UAC acceptance is claimed by the fixture self-test.

The corrected `consent-force` run passed independent single-run verification with
one real consent prompt and one elevated helper, the selected fixture exiting,
the unrelated control unchanged and the dashboard remaining limited. The human
confirmed approving the prompt and observing Unknown publisher. The next run,
intended as `consent-cancel`, observed an approved helper and target exit; it is
retained as a failed attempt and requires clarification and a valid cancellation
observation. These observations do not complete the full UAC commitment.

The developer clarified on 2026-09-10 that elevation acceptance is for the
administrator-account workflow. Standard-user credential entry is excluded from
this release commitment. No account creation or sandbox-account reuse is needed.

A graceful-close attempt completed the application action successfully but its
supervisor read a stale `SCHED_S_TASK_RUNNING` result immediately before reading
the task's completed state. Both polling loops now wait for a terminal result as
well as a non-running state, under their existing deadlines. The attempt remains
failed evidence and will be rerun; its successful application result alone does
not replace a complete receipt.

The live-dashboard handle checkpoint and full receipt aggregation are implemented.
A native Windows positive-control run detected opened and closed synchronization,
query and termination handles, released its snapshots and cleaned its owned child;
its source-bound record is `native-handle-selftest.json`. The Python suite passed
566 tests. Delayed approval now requires sampling progress during at least eight
seconds of actual consent-process lifetime. Current-harness native cases and the
resource ownership review remain pending. Ripwire named three tests included in
the passing suite; quality-delta also reported reference-tree findings and verifier
length growth, so no quality-delta pass is claimed.

On 2026-09-11 all nine ordinary and non-timeout UAC observations passed from the
packaged executable. The timeout run reported uncertainty correctly and cleaned
its owned targets, but the resource assertion counted sysinfo's normal query-only
handle to the still-live helper. The corrected native counter distinguishes
SYNCHRONIZE handles from exact collector query masks; four positive controls pass.
A pinned compatibility check retains the stronger zero-helper-handle proof in
the nine earlier receipts. The corrected real timeout run passed independent verification. Its live dashboard retained only one QUERY_LIMITED_INFORMATION handle (0x1000) to the suspended helper, with zero synchronization or termination handles. Full committed acceptance remains pending.
Windows GPU detection parity is the developer-named next commitment.
