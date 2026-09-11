# Package Windows with Inno Setup and an optional pinned PawnIO prerequisite

Level: Judged
Decided by: Codex
Rests on: WTE-001
Would be wrong if: The installer cannot preserve signed artifact provenance, avoid downgrading a shared driver, or leave the dashboard unelevated.

## Decision

Use Inno Setup 6.4.3 to build a signed System Pulse installer from the verified native package. Offer CPU temperature support as an explicit optional task using the official pinned PawnIO 2.2.0 setup. Preserve an existing newer driver and never remove the shared driver during System Pulse uninstall. Sign application, setup and uninstaller with the existing Winboat signing command, then verify the results and regenerate artifact hashes. The app still asks for elevation only when the user enables CPU temperatures. Installer launch remains optional and uses original user credentials; launching setup from an already elevated session cannot establish an unelevated original token.

## Realized by

(none yet: recorded, not built)
