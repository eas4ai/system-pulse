# Process table improvements

Status: Agreed 2026-09-08
Slug: process-table-improvements
Requirements: PROC-001, PROC-002, PROC-003, PROC-004, PROC-005

The developer named responsive process-table width, compact search, hidden Mac
Threads and sudo-style password authentication for privileged process actions.
They agreed to proceed after the final Mac CPU comparison. The
[contract](../spec/process-table.md) records these requests without authorizing
further performance optimization or unrelated visual redesign.

Source scope: process table and toolbar presentation, process-control dispatch
and platform authentication, directly affected model/collector code and tests,
necessary package support, native verification helpers and evidence. Keep normal
application execution unprivileged. Record the authentication design before
implementation; never solicit or retain passwords in agent or application data.

Done requires all five requirements passing against committed source, applicable
Linux and Mac native verification, package checks for affected packaging, and a
review of identity handling, authentication cancellation/failure and resize
behavior. The earlier performance and GPU commitments remain incomplete.
