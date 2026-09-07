# Discover panels without traversing monitor bodies

Level: Judged
Decided by: agent
Rests on: LIVE-001 and LIVE-013 require native cell proof. The current membership-safe panel lookup exhausts its original15-second discovery deadline traversing151 monitors and1350 process rows. Monitor body viewports are explicit native structural boundaries.
Would be wrong if: A legitimate monitor panel can live inside a pruned monitor body, an unmatched viewport hides a panel, current membership or uniqueness is bypassed, or bounds and strict exit behavior weaken.

## Decision

During panel discovery, continue through the current application layout and all monitor-panel siblings but prune content beneath a validated monitor body viewport. Match its viewport identity to the named parent monitor panel; keep workspace/layout viewports traversable. Preserve current panel, row and cell membership and uniqueness checks, exact PID/start identity, existing absolute deadlines and node bounds. Default generic traversal and strict exit semantics stay unchanged. Add structural pruning, malformed-boundary, duplicate-sibling and deadline regressions. Independent spec then quality review and fresh untraced acceptance remain required.

## Realized by

- 18a7c978c07a3424244ddbd2e16dd62f7d636631 fix: prune monitor bodies during native panel discovery
