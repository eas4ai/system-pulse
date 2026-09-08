# Prepare application presentation when it is displayed

Level: Judged
Decided by: developer
Rests on: PERF-001 PERF-002 PERF-003 PERF-005
Would be wrong if: Deferred rows or panel refreshes expose old process identities, stale current labels, lost history, or no measured improvement.

## Decision

Developer approved the bounded presentation-work proposal on 2026-09-08. Extend source scope to application snapshot acceptance, derived presentation and notification in src with directly affected tests. Retain every accepted snapshot and monitored history, reconcile selection from raw identities, prepare process cells on display or diagnostics using the current collector clock, and refresh only the active screen presentation. Keep the fixed native CPU targets and full preservation gates; this does not authorize a service, dependency or framework redesign.

## Realized by

(none yet: recorded, not built)
