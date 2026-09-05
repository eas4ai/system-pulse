# Report validated LIVE evidence per requirement

Level: Judged
Decided by: agent
Rests on: LIVE-001 through LIVE-013 have independent falsifiers; Cairn now supports explicit results and the prior aggregate erased unrelated passing evidence.
Would be wrong if: The evidence groups omit a required assertion or publish before relevant artifacts and cleanup validate.

## Decision

Use the conservative three-group mapping in docs/execution/real-system-readings/cairn-verdict-mapping.md. Reuse existing checks and preserve the complete aggregate gate. Emit only validated requirement passes; interrupted proof remains unverified under the new protocol. Preserve original failure exits and disclose the legacy fallback when no known verdict lines exist. No product requirements or comparison bounds change.

## Realized by

(none yet: recorded, not built)

## Realized by

- 5da24b21ddc6a9e8da69e39c9f22b6cc76de6bdd
