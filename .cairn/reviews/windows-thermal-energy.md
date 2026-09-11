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
