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

Correction verification: the new mutation tests ran before the correction and
reported 20 rejected-expectation failures across stale/future EMI windows in all
six stages, stale/future/mismatched-frequency helper QPC windows, the frame before
helper exit, and a fresh EMI result paired with a 98-second-old baseline. After
the correction, all 21 verifier tests pass, including the corrected complete
lifecycle fixture; Ruff also passes. These are local mechanism tests, not native
acceptance evidence.

The validator now uses `capture_finished_ns`, which HostCollector records after
collection, as the EMI upper bound. Current observations must be at most three
seconds old, each source read at most one second, and the baseline interval at
most six seconds (the supported five-second sampling interval plus margin).
Helper queries must finish no later than the observer QPC and within three
seconds, with matching frequencies; collector receipt freshness remains a
separate check. The successful frame before helper exit receives these same
checks and the snapshot clock-anchor/ordering validation.

## Live capture finding — 2026-09-11, run 401c59f7

The signed native application failed the first interactive capture. The temperature
helper connected to the dashboard pipe, then the dashboard reported Windows error
109 (pipe ended). The expected denial state never appeared and the harness failed
after its deadline. The user reported a problem with Energy; clarification remains
pending. The captured Energy screen contains real package watts and history.
No conclusion about the user's UAC response is inferred. The mechanism correctly
rejected this run. Retained raw evidence is in
`docs/execution/windows-thermal-energy/failed-live-401c59f7/`.

Read-only source inspection shows existing native pipe tests exercise one process
and one token, and do not execute the real driver-backed helper lifecycle.
Investigate the connected-helper exit before changing production code. This is an
open finding; prior test passes do not establish successful native temperatures.

### Root cause reproduced without interactive elevation

The test-only real-helper reproduction at `a5070611` failed on the tablet with
`driver.rs:145`: `copy_from_slice: source slice length (15) does not match
destination slice length (14)`. The fixed `ioctl_read_msr` command plus its NUL
occupies 15 bytes, but the request encoder selected 14 bytes. The helper panics
before producing its first hardware reading and closes the pipe. The native
red log and exact command are retained beside the live failure artifacts.
This explains the pipe-ended symptom without attributing a UAC response to the
user. Correct the fixed request encoding, then repeat actual-helper native tests
and package acceptance.

### Request encoding correction review

Correction `8dfe7c33` derives the destination slice length from the fixed command
bytes. Independent review confirmed that the request remains 40 bytes and the
only permitted registers remain `0x1A2` and `0x1B1`. The native opt-in actual-helper
regression returned an authenticated 64-byte frame and 41 C after the correction.
Its ordinary non-opt-in suite result is not evidence of real driver execution.
The attempted Limited-parent diagnostic failed in its test-only OpenProcess call;
production retains the ShellExecuteEx process handle instead. No cross-token
success is claimed from that diagnostic. Signed interactive replay remains due.

### Remove the unsuccessful experimental cross-token test

Read-only follow-up review found that `native_real_driver_limited_parent` in
`8dfe7c33` should not remain in the final source. Its opt-in execution fails in
OpenProcess before testing the thermal protocol, and production does not use
that handle-acquisition path. Preserve the failed diagnostic log as investigation
evidence, remove that experimental function, and retain the working real-driver
regression. The signed application replay must establish the real cross-token
launch. This correction changes test code only.

### 1.0.0 release preparation

The unsuccessful `native_real_driver_limited_parent` experiment has been removed.
The working `native_real_driver_helper_session`, its child entry and shared
`read_test_temperature` remain. The removed OpenProcess imports were local to the
experimental function. Formatting and all 609 Python verification/packaging tests
passed during release preparation. Final native Windows compilation and tests
will run against the committed 1.0.0 source. This closes the source-cleanup item;
it does not claim completion of the signed interactive thermal lifecycle or Cairn.
