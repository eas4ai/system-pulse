# Windows UAC process actions

Status: Agreed 2026-09-10
Prefix: WUAC

The developer requested a specification for a Windows UAC helper after publishing
0.3.0. The agreed direction is a normally privileged monitor with a separate,
short-lived elevated helper for a specific process action. Windows currently
supports neither ordinary process actions nor the authenticated retry; both are
in scope. Linux and macOS authentication already have native verification.

## Action semantics

This single commitment includes both Windows actions:

- **End task** requests graceful closure of the selected applications own verified
  windows. The application may show a save dialog or decline to exit. Report
  closure requested separately from confirmed process exit. For a background
  process with no safely addressable window, report graceful close unavailable
  and offer the separately confirmed Force Quit action.
- **Force Quit** terminates only the selected process through its verified process
  handle. Confirmation explicitly warns that unsaved work can be lost.

Never silently turn graceful closure into forceful termination, broadcast close
messages or console events to unrelated processes, or terminate a process tree.
Graceful window targeting must preserve the same process-identity guarantee as
termination: validate ownership and handle/window lifetime races, and fail closed
where safe targeting cannot be established. Linux/macOS retain existing behavior.

## Requirements

[WUAC-001] Windows process actions MUST bind the confirmation and execution to the selected PID and its full native creation identity, and retain the verified process handle throughout execution. Force Quit MUST act through that same handle; graceful closure MUST target only windows safely bound to that process.
Falsifier: collection or request serialization truncates the creation time; a changed/exited identity is accepted; the backend reopens by PID after validation or sends a close request to a reused/foreign window; missing identity is treated as valid; or a different process receives the action.
Mechanism: native creation-time comparison against an independent Windows API observation; boundary tests for missing/mismatched identities and exit/reuse interleavings; controlled-child native tests that prove the wrong identity leaves the child alive. PID reuse need not be forced nondeterministically to prove rejection.

[WUAC-002] A confirmed Windows action MUST first try with the current user's permissions and request Windows UAC only for a genuine access-denied result that elevation can address.
Falsifier: ordinary actions prompt; validation failures, unsupported actions or exited targets trigger elevation; the normal launch requires administrator privileges; the dashboard is relaunched elevated; or permission still denied after elevation causes repeated prompts or a bypass attempt.
Mechanism: dispatch/error mapping tests plus native ordinary and administrator-owned disposable targets, with dashboard token inspection before and after. Protected/critical OS targets and the dashboard/helper itself are refused; do not enable debug privileges or attempt protected-process bypasses.

[WUAC-003] The elevated helper MUST execute at most one strictly validated action from the confirmed request, then exit without initializing the dashboard, collection, persistence or a reusable privileged service.
Falsifier: changed selection alters a pending request; arbitrary commands, executable paths or extra arguments are accepted; executable lookup uses PATH/current-directory search; shell interpretation is involved; credentials cross into application code/logs; malformed/direct unelevated helper invocation bypasses checks; or a helper can apply subsequent requests without new authorization.
Mechanism: parser/entry-point tests, executable-path and argument-boundary tests including spaces/non-ASCII paths, source review of the elevated entry, and native helper lifetime/token observations. Use the installed executable's fixed helper mode or an equivalently bound packaged helper; launch its absolute path through the OS elevation interface. Revalidate identity inside the helper after approval. The process-wide launch manifest remains asInvoker.

[WUAC-004] The dashboard MUST remain responsive while UAC and the helper run, prevent duplicate submission of the pending action, and report cancellation, refusal, target exit, failure, pending termination and verified completion honestly.
Falsifier: UAC cancellation changes the target or automatically retries; the UI freezes; duplicate activation creates extra helpers/prompts; requesting termination is reported as confirmed exit without observing it; a timeout/crash with unknown outcome claims the process was untouched; or helper/process handles leak after a finished operation.
Mechanism: state-transition and result-mapping tests plus native cancellation, delayed approval, duplicate activation, target exit while awaiting approval, helper failure and completion observations. Bound post-launch waits and cleanup; do not infer consent from a timeout. Outcome uncertainty instructs the user to refresh/check the process list, without resubmitting automatically.

[WUAC-005] Windows UI and documentation MUST describe the settled action semantics and current signing status accurately, preserve PID/start identity in confirmation, and keep Linux/macOS behavior intact.
Falsifier: a forceful action is presented as graceful; confirmation refers to another row after sorting/filtering; graceful close silently becomes Force Quit or offers no honest unavailable state; unsigned UAC prompts are described as having a verified publisher; or Linux/macOS controls, table navigation, filtering, selection or tray behavior regress.
Mechanism: focused model/UI tests and native Windows table/confirmation/error observations, Linux/macOS preservation checks, and review of README, user guide and binary instructions. Signing is not a prerequisite or deliverable of this commitment; describe actual packaged signing status.

[WUAC-006] The Windows implementation MUST have committed-source native evidence for permitted ordinary and UAC-assisted actions, real UAC cancellation, and stale-target rejection, with a clean final review before completion.
Falsifier: mocks or hosted compilation substitute for real UAC interaction; a required case is skipped without remaining pending; evidence lacks source/binary identity; tests affect unrelated processes; or a packaged helper cannot run from the shipped layout.
Mechanism: controlled disposable targets on an interactive Windows desktop; record source commit, binary hash, OS/toolchain, token elevation, requested PID/creation identity, exact action and observed outcome. Cover cooperative and refusing GUI targets, a windowless target, and ordinary/elevated Force Quit. Cover an administrator's consent prompt and a standard user's administrator-credential path; the human enters secrets only into Windows. Keep every harness-owned target under cleanup and do not target system-critical processes. Run native Windows tests/build and local package verification, plus applicable Linux/macOS preservation checks, before any separately authorized hosted build.

[WUAC-007] System Pulse MUST use the latest stable GPUI Kit release verified at commitment activation, with compatible companion crates and retained application-specific/native fixes.
Falsifier: Cargo still resolves the prior kit release; duplicate incompatible GPUI generations enter the application graph; a retained patch is lost without demonstrated upstream equivalence; notices or version documentation disagree; or the upgrade regresses supported desktop behavior.
Mechanism: crates.io reports GPUI Kit 0.6.1 as the latest non-yanked stable release on 2026-09-10. Reconcile upstream 0.6.0-to-0.6.1 changes with the local base/UI and native patches, inspect locked dependency metadata, run workspace formatting/tests/Clippy without warning-to-error flags, and verify affected Linux/macOS/Windows native and packaging paths locally. Record retained and superseded patches. This requirement pins the observed release rather than chasing moving upstream commits.

## Boundaries and execution policy

No process trees, service management, persistent administrator agent, general
command execution, credential storage, automatic action retries, new GPU/thread
collectors, signing-service integration or unrelated dependency upgrades. The developer explicitly added the GPUI Kit 0.6.1 upgrade and its required compatible dependencies to this commitment.

Local checks first: rustfmt and full workspace Clippy without warning-to-error
flags, appropriate tests, and native Windows verification. Existing Windows
hosts may be used when available. Required interactive evidence remains pending
until someone can respond to the actual UAC prompt. Working branches stay local;
pushes, hosted CI and release publication need separate developer authorization.

Before implementation, record a judged design decision for the native identity
representation, exact action mapping, helper invocation/result protocol, caller
protection and handle ownership. Declare Cairn mechanisms and inputs against the
requirements. After all evidence passes, review the elevated boundary without
changing code during the review; resolve findings as separate work.

## Platform references

- [Microsoft: administrator privileges and elevated helper processes](https://learn.microsoft.com/en-us/windows/win32/secbp/running-with-administrator-privileges).
- [GetProcessTimes: native creation time as 100-nanosecond FILETIME units](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocesstimes).
- [Process handles and identifiers](https://learn.microsoft.com/en-us/windows/win32/procthread/process-handles-and-identifiers).
- [Process termination behavior](https://learn.microsoft.com/en-us/windows/win32/procthread/terminating-a-process).
- [Window-close requests](https://learn.microsoft.com/en-us/windows/win32/learnwin32/closing-the-window).
