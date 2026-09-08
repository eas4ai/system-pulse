# Stop Mac optimization after the final paired comparison

Level: Consequential
Decided by: developer
Rests on: PERF-001 PERF-002 PERF-003 PERF-004 PERF-005 PERF-006
Would be wrong if: This record is used to claim the unmet CPU targets passed or to authorize further optimization.

## Decision

On 2026-09-08 the developer agreed to finish the running comparison, stop further optimization and move to the requested process-table improvements. The final committed-source comparison measured Summary 12.7801 to 10.0064 percent of one CPU and tray-only 11.0807 to 7.3179 percent. Both 50 percent targets remain unmet. PERF-003 through PERF-006 passed the committed gate. Retain the verified implementation and all receipts; leave the performance commitment incomplete and suspended. The next work is the requested expanding process table, compact search, hidden macOS Threads column and action-scoped password authentication for privileged process controls.

## Realized by

- 7263b6d495579314f178267d1a56f75e905e751c Suspend Mac optimization with the CPU targets unmet
