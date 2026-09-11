# Partial review: Windows thermal and energy collection

This records an independent review finding. It is not the final commitment review.

## WTE-001: blocked driver calls bypass helper lifetime checks

Reviewed candidate: `110756ef`.

The independent specification review examined the elevated helper's synchronous
`DeviceIoControl` calls and its caller/session lifetime checks. Those checks run
before or after driver calls. A stalled module load or register read can prevent
the helper from reaching the next caller-exit or session-deadline check. Closing
the parent's pipe does not stop that blocked call.

Required correction: start an independent watchdog before opening the driver.
It must retain the verified caller and terminate its own helper if the caller
exits, a fixed driver-operation deadline expires, or the session deadline expires.
It must not depend on termination rights in the parent's ShellExecute handle.

Demonstration required: a test child deliberately stalls inside a watched operation;
the watchdog must terminate that child within the bound. Also exercise caller exit,
session expiry, and a corrected operation that completes before its deadline.
The stalled-read case was identified by source inspection; no native demonstration
has run at the time this finding was recorded.

### Correction prepared for native verification

The helper now starts a separate watchdog before driver opening. It retains the
verified caller, checks every 25 ms, and terminates only its own process after
caller exit, a five-second driver opening/read deadline, or the 24-hour session
deadline. A completed operation clears its own deadline. No watchdog mutex is
held across driver work. Normal helper exit cancels and joins the watchdog.

The initial four watchdog tests failed against the missing implementation
(`~/.local/share/rtk/tee/1789134206_cargo_test.log`). The stalled-child test also
failed with exit 101 instead of the required timeout exit 82
(`~/.local/share/rtk/tee/1789134256_cargo_test.log`). After implementation, all six
portable watchdog tests passed, including operation/session termination of real
test children whose worker thread deliberately sleeps inside the watched call.
This simulates a blocked read; it does not deliberately hang the kernel driver.

The Linux collector suite passed 155 tests. Linux and Windows GNU all-targets
Clippy, formatting and diff checks passed. Windows-only coverage additionally
starts a stalled helper test child, pins a separate caller process with the
production identity code, exits that caller, and requires helper exit 81.
That native test and the Windows `TerminateProcess` branches of the stalled-child
test still require execution on the tablet. This finding is not marked closed
and this document is still not a final commitment review.
