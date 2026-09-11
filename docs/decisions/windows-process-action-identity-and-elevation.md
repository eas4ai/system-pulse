# Windows process action identity and elevation

Level: Judged
Decided by: Codex
Rests on: WUAC-001 WUAC-002 WUAC-003 WUAC-004 WUAC-005 WUAC-006
Would be wrong if: Full creation identity is lost; Restart Manager affects another process or forces graceful shutdown; caller/protected-target checks can be bypassed; ordinary success prompts; or outcome and handle lifetime claims exceed native evidence.

## Decision

Use Windows FILETIME creation ticks without division or epoch conversion as the process start identity, retaining the value already queried by the patched sysinfo collector. Open a non-inheritable process handle with the minimum action rights, validate full creation time, live state and critical/protected-process status through that handle, and retain it until the action and bounded completion observation finish. Force Quit calls TerminateProcess through the same handle and distinguishes observed exit from pending termination.

For End task, use a private Restart Manager session registered with exactly one RM_UNIQUE_PROCESS and zero files/services. Require the affected list to contain only that identity as a GUI application; reject unknown, console, service, shell, critical or additional targets. Call RmShutdown with flags zero, never RmForceShutdown or RmRestart. This asks the selected application to end its session and permits refusal. Retain the verified process handle throughout. Do not send to cached HWND values: Microsoft documents their destruction/reuse race. Native cooperative/refusing GUI, unrelated-control and stale-identity experiments must establish the proposed Restart Manager behavior before production use. Fail closed and revisit this decision if those experiments contradict the single-target or non-forcing assumptions.

Preserve the existing Unix helper mode and outcomes. Add a Windows-only fixed helper mode with strictly bounded decimal target PID/creation ticks, the two action tokens, and caller PID/creation ticks. Reject extra arguments, missing identity, direct unelevated invocation, the helper/caller and the application executable itself. Revalidate caller and target after UAC approval. Invoke the canonical absolute current executable through ShellExecuteExW with the runas verb on a background worker, require its returned process handle, and never enable debug privileges or accept commands or executable paths from the request. The normal application manifest remains asInvoker.

Use fixed Windows result codes for observed exit, graceful request sent/refused/unavailable, pending termination, stale identity, protected/denied/invalid request and unknown outcome. Keep Unix result strings unchanged. Elevate only an ordinary native permission-denied result, once. A missing/crashed/timed-out helper reports uncertainty and asks the user to check the process list; do not claim the target was untouched or retry automatically. Bound post-launch waits, retain/close owned handles, and keep confirmation identity immutable and duplicate submission disabled. Record native consent and credential-path evidence only after actual human interaction with Windows; credentials never enter the application.

References: https://learn.microsoft.com/en-us/windows/win32/api/restartmanager/ns-restartmanager-rm_unique_process ; https://learn.microsoft.com/en-us/windows/win32/api/restartmanager/nf-restartmanager-rmregisterresources ; https://learn.microsoft.com/en-us/windows/win32/api/restartmanager/nf-restartmanager-rmshutdown ; https://learn.microsoft.com/en-us/windows/win32/rstmgr/guidelines-for-applications ; https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-iswindow .

## Realized by

- 47617b85e9f0b86ad0440f60dead49ad4cd561f8 Implement Windows process identity, safe actions and one-shot UAC helper
