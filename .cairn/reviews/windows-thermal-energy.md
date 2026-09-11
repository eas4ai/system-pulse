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

## Installer review findings before correction

Reviewed installer candidate: 3100aa1b. The read-only review found that the
optional PawnIO setup redistributes a driver whose corresponding source/notices
were not yet retained. The module source is separate. Retain the exact PawnIO
2.2.0 tree and pinned PawnPP submodule with their licenses before packaging.

The input validator accepted only an executable and build.json as a complete
package. Require source, license and notice files, and validate the source archive
hash and source revision before signing. Demonstrate failure after removing source
and rebuilding the manifest, so the test does not merely detect an old hash.
The unsafe-path test must keep required entries so it reaches path validation.
These findings remain open until their corrections and checks complete.

## Mechanism review: stale sensor operands accepted

Reviewed mechanism candidate: `50bc40fe`.

The independent mechanism review demonstrated two accepted violations. A fresh
snapshot could contain EMI read/capture windows 98 seconds old. The power
validator checked ordering and arithmetic, but never compared those windows with
the snapshot's collector clock. It also accepted helper QPC timestamps 1..2
against observer QPC 100000000000 at 10000000 ticks/second when the collector
receipt timestamp was fresh. The captured observer QPC and frequency were unused.

Correct the mechanism before using it as acceptance evidence. All lifecycle
frames, including the successful frame before forced helper exit, must bind EMI
windows to collector-relative snapshot time and helper query windows to the
observer's QPC/frequency. Keep those clocks separate. Demonstrate rejection of
both mutations, future timestamps and mismatched QPC frequencies, then retain a
passing corrected example. No code correction or new check is claimed in this
finding entry yet.
