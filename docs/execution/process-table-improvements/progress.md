# Process table improvements

- [x] Complete: implement and verify responsive table width (PROC-001).
- [x] Complete: implement and verify compact search (PROC-002).
- [x] Complete: implement and verify platform column visibility (PROC-003).
- [ ] In progress: record authentication design, implement and verify privileged actions (PROC-004).
- [ ] Pending: run committed acceptance and review all five requirements.

The previous performance pass is suspended, with its CPU targets unmet and
its verified preservation evidence retained. No further optimization is planned.

## PROC-001 work in progress

The original table left unused width at 1280 pixels. A new rendered-layout
regression reproduced this before the fix. The table now uses available width
with the content width as its minimum; the Name heading and cells receive excess
space, and virtualized rows fill their root allocation. The test checks header
and row alignment across 1280, 1800, 2560, 960 and 1280 pixel window sizes.
The targeted regression and all 127 application tests pass. Linux development
replay also passes: 1280 and 1800 pixel windows fill their width; minimum-width
horizontal scrolling exposes User with aligned headers and cells. Five receipt
validation tests pass, and the extended Swift accessibility helper compiles.
The committed Linux replay passes with build/source and harness provenance in
`evidence/linux/`. Mac application tests and its release build pass;
Mac resize observations also pass at 1280, 1440 and 960 pixels, including
horizontal access to User. The Mac verifier supports the host Python 3.9;
explicit length checks precede paired-column comparisons. Cairn validation
against the committed evidence is next.

The process-table mechanism is declared. Its initial run records missing verifier
implementation as unverified; no PROC requirement has a passing Cairn receipt.

Ripwire `process_row` edit-check found no signature change or incompatible caller.
The whole-repository quality delta exited 2 with broad existing/reference-symbol
findings; it is not a passing quality claim. The post-commit test gate reported
zero uncommitted changed symbols. Application and native checks provide the
behavioral verification above.

PROC-001 now has passing committed Cairn evidence at `20260908T223936355Z`.
The Mac was unlocked and the access escalation was answered. The developer
requested a 24-hour caffeinate session; PID 10516 has verified 86400-second
system/display sleep-prevention assertions and is left running as requested.

## PROC-002 work in progress

A rendered regression reproduced the stretched input at 1039 pixels before the
fix. The search wrapper now has a fixed 280-pixel width. All 128 application
tests and ten receipt-validation tests pass. Linux native resize, compact
search, PID filtering and clear observations pass in development replay.
Committed-source native Linux and Mac observations now pass, including PID
filtering and clearing at minimum width. The Mac harness clicks the text editor
before typing because semantic focus alone did not route text entry. Rust clippy
and Python lint checks pass. Cairn evidence validation is next.

PROC-001 and PROC-002 have passing committed Cairn receipts at
`20260908T225018604Z`.

## PROC-003 work in progress

One platform column list now drives table widths, headers, cells, details and
sort choices. Mac omits canonical column 6 (Threads); User keeps canonical
column 7 while its accessible position becomes the seventh visible column.
Linux retains all eight columns. All 129 Linux application tests, thirteen
receipt checks and Rust/Python lint pass. Linux native User sorting and Home/End
navigation also pass. All 129 Mac application tests and its release build pass. Native Mac and Linux
column, sort, navigation, resize and search observations pass against source
`8c32f787`. The Mac observer reads selected PID from the visible details panel
and requires its matching stable row visible; its bridge omits AXSelected.
Committed Cairn validation is next.

PROC-001 through PROC-003 have passing committed Cairn receipts at
`20260908T230939573Z`. Authentication design is being grounded in the existing
Linux pidfd boundary and native Mac identity-safe signaling support.


## PROC-004 work in progress

The recorded authentication design uses a one-action helper mode before GUI
initialization. Ordinary actions run first; only typed permission denial opens
an OS authentication dialog. The helper parses one PID, birth identity and
Terminate/Kill choice, rechecks identity after authentication, and never retries
or requests a password. Linux retains pidfd signaling. Mac now retains BSD
birth-time microseconds and signals by kernel PID version through libproc.
Missing native support and unknown identities fail closed.

Development verification: 113 Linux collector tests, 129 application tests,
13 geometry-receipt tests and strict Rust/Python lint pass. Nine native Mac
process-control tests pass, including real AppleScript parsing/quoting without
authentication, same-process signals and rejected stale PID versions. Seven
vendored Mac refresh tests pass, including subsecond identity replacement.
The Mac application release build and native table replay pass. Native Mac
confirmation cancellation leaves each owned child alive; End and Force Quit
then deliver SIGTERM and SIGKILL respectively and show success notices.
The direct Linux executable-helper probe rejects changed birth identity and
sends both correct signals without creating application state or output.

Actual system-password cancellation, successful privileged actions and delayed
authentication remain unverified. The developer has been asked which desktop
they can use for native password entry. No authentication dialog has been
launched and no password has been requested outside an OS dialog. Full committed
Linux/package acceptance and refreshed committed native receipts are pending.


Committed source `41acec06` now has refreshed passing native Linux and Mac
resize/search/column/navigation records. The Mac record also includes ordinary
End/Force Quit and confirmation cancellation, with its matching release build,
129 application tests, 63 collector tests and seven vendor tests. Thirty-one
base compatibility tests pass on Linux. The broader Linux preservation gate
passes 1,046 tests, host comparisons and native product replay; ten input-focus
tests also pass. Package acceptance rejected the uncommitted Cairn receipts.
Those receipts are retained and committed before the next full invocation.
An earlier invocation was deliberately interrupted after the decision-link
commit changed HEAD; it is not a passing acceptance run.

The process-table mechanism now declares its native evidence directory as an
input, so changes to those observations invalidate its receipts. Ripwire's
whole-repository quality delta reports 652 preexisting/reference findings
(exit 2), and its test gate reports broad untested name-based reachability
(exit 4). Neither is claimed as a clean result. The named Python and base
compatibility test obligations passed; native tests cover the real action path.

PROC-001 through PROC-003 again have passing committed Cairn receipts at
`20260908T234056179Z`/`20260908T234056180Z`. PROC-004 remains active.


The Linux acceptance continuation now passes native preservation and all package,
tray, installation and removal stages. Its manifests and the retained freshness
failure are described in `authentication-verification.md`; no performance fix
is claimed. The interactive verifier is prepared and its four boundary tests
pass on both hosts without opening any authentication dialog. Actual OS password
entry, cancellation and privileged outcomes remain pending developer presence.

All 510 Python verifier tests pass after adding the interactive harness. Its
four boundary tests also pass on the Mac. No OS authentication dialog has been
opened; the readiness question is still unanswered.
