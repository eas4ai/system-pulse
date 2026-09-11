# Preserve System Pulse patches while upgrading to GPUI Kit 0.6.1

Level: Judged
Decided by: Codex
Rests on: WUAC-007
Would be wrong if: The locked graph retains GPUI Kit 0.6.0, selects incompatible GPUI versions, or drops a local fix without equivalent upstream behavior and passing preservation checks.

## Decision

The developer explicitly requested the latest GPUI Kit alongside the approved Windows UAC commitment. The crates.io registry reports 0.6.1 as the latest stable non-yanked release on 2026-09-10. Compare checksum-verified 0.6.0 and 0.6.1 package sources, merge upstream deltas into local base/UI libraries while preserving application patches, and pin the facade, retained libraries, macros and assets to 0.6.1. Retain the existing GPUI Pre 0.3.2 family and native adapter patches where compatible with the released requirements; update only dependencies needed for the upgrade. Verify source patch inventory, locked dependency graph, formatting, workspace tests/Clippy without warning promotion and affected native/package behavior locally. Keep this branch local and do not start hosted CI without separate authorization.

## Realized by

- 46880b959c894620d5c39728d820b81a8ded7978 feat: upgrade GPUI Kit to 0.6.1 with local behavior patches
