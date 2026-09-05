# Adopt System Pulse beside its source

Level: Judged
Decided by: agent
Rests on: The product specification places the application inside eas4ai/gpui-component; the existing implementation is in this worktree.
Would be wrong if: Cairn can reliably bind source and tests to commits while running solely in the separate design repository.

## Decision

Keep the design and reference repository intact. Place the formal adoption specifications and eventual execution commitment in this application worktree so declared mechanism inputs belong to its Git history. Keep the cited recon report in the design repository and link it from the keystone. Document readings, rendering, identity and persistence integration to requirement depth for the current work; retain other product areas in the spec map.

## Realized by

822635ff044df53b60258ad645c7dbf01fc0287b
