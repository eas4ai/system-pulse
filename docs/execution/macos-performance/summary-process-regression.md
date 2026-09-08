# Missing Summary process rows

Status: Summary regression verified at the fix revision; performance commitment remains incomplete.

The developer reported no CPU processes in the release UI and noted seeing the
issue while sysinfo work was underway. The running release was on Summary and
reported 697 readable processes. Saved collector snapshots before and after the
sysinfo guard contain hundreds of processes and nonzero CPU readings; those
snapshots alone do not establish what the developer saw on screen.

The current regression is reproducible without native collection: after accepting
two process rows, Summary has zero formatted rows. The failing test reported
expected 2, actual 0. The presentation optimization cleared that shared vector
and prepared it for the Processes tab and diagnostics, but missed Summary's
Top CPU processes card. The previous new test incorrectly asserted that Summary
should leave the vector empty. Native preservation enabled diagnostics, whose
eager preparation masked the missing normal-render preparation.

The fix prepares process presentation when Summary renders, using the existing
freshness-aware method. Other screens that do not display process rows retain
lazy preparation. Existing visible labels now expose stable native identities,
so verification can inspect the displayed PID, name, CPU and total directly.
The regression test checks populated rows, CPU ordering, return from another
screen, new snapshots and PID reuse. It failed before the fix. All 125 application
tests, strict application Clippy and formatting passed at the fix revision.

The fixed Mac release `05fb36f9c55b142954dba706156818a6127b4453` passed
[native preservation](evidence/summary-regression-05fb36/result.json), including
a separate normal launch with diagnostics disabled: eight Summary rows out
of 704 processes, 22 visible process-table rows, eight Summary rows after
returning from another screen and after reopening, and normal Quit. The
[build receipt](evidence/summary-regression-05fb36/native-build.json) records
the matching binary hash and passing Mac tests, Clippy and release build.

Complete Linux acceptance subsequently passed at `cf534f1f`, after reducing
diagnostic publication work and keeping the private display alive across
recovery sessions. See [the Linux investigation](freshness-investigation.md).
The latest Mac release has passed build checks but still needs fresh native
runtime preservation and paired CPU measurements. Earlier CPU results are
historical observations; no performance-preserving reduction is claimed
from the candidate that omitted required Summary content.
