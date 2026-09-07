# Publish transient diagnostics without a durability flush

Level: Judged
Decided by: agent
Rests on: LIVE-013 depends on timely complete diagnostics. A retained complete newer snapshot was not published while the previous file became stale; source confirms diagnostic publication waits on the durable configuration flush path.
Would be wrong if: Workspace or preset durability changes, readers can observe partial diagnostic JSON, revision ordering or error handling weakens, or an untraced acceptance pass is claimed from tracing.

## Decision

Give diagnostic snapshots atomic replacement after complete writing without requiring a durable disk flush. Preserve durable configuration and preset saves, latest-only worker ownership, revision ordering, failure cleanup, and actual error reporting. Add focused tests for diagnostic publication and durable save separation, atomic replacement failure and stale revisions. The earlier stalled syscall remains unidentified; this removes a verified unnecessary publication dependency, not a proven cause claim. Independent spec then quality review and fresh untraced acceptance are required.

## Realized by

- db08a65ca0462dd1070df82fd17a16f86cd3c28c fix: publish transient diagnostics without a durability flush
