# Scope process cell discovery to its native row

Level: Judged
Decided by: agent
Rests on: LIVE-001 and LIVE-013 require native proof. The retained failure shows an unscoped full-tree cell lookup ignored its existing five-second deadline while the app continued publishing fresh snapshots.
Would be wrong if: The change relaxes deadlines, trusts stale or mismatched process identities, skips cell uniqueness, or substitutes diagnostic presence for native evidence.

## Decision

Extract the existing metric process-row lookup into a shared helper. Use it for process-cell visibility navigation with the original absolute deadline across row reacquisition, cell lookup, and movement. Reacquire defunct cells by PID/start identity within the Processes panel. Preserve generic lookup, full strict exit traversal, all metric comparisons and existing budgets. Add targeted deadline, unrelated-tree, identity, duplicate-cell and replacement regressions. Preserve failed artifacts and require independent spec then quality review before fresh committed acceptance.

## Realized by

(none yet: recorded, not built)
