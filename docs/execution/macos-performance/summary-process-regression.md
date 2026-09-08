# Missing Summary process rows

Status: Fix implemented; native release verification in progress.

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
tests, strict application Clippy and formatting now pass.

The native release must be checked with diagnostics disabled, both on Summary
and on Processes, including switching away and returning. Earlier CPU results
are retained as historical observations; no performance-preserving reduction
is claimed from a candidate missing required UI content.
