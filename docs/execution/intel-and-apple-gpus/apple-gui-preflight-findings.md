# Apple GUI preflight findings

Status: Open findings recorded on 2026-09-06 before corrective source work.
This is a failed preparation probe, not native GPU acceptance.

Root launched the committed `4db68c71304d368977265e31ba365b121fcfd9f0` app with
isolated state and diagnostics, then ran the existing bounded read-only AX probe.
Both processes had `OBJC_DEBUG_MISSING_POOLS=YES`. The
[original artifact manifest and observations](apple-gui-preflight-findings.json)
retain exact hashes, process identities and outcomes. Root downloaded every
artifact and verified its size and SHA-256.

## F1: full application missing autorelease pools

The app emitted **551 missing-pool warnings**, all attributed to PID 4374 across
several native threads. The first warnings name `_NSSwiftProcessInfo` and
`Swift.__SwiftDeferredNSArray`; later warnings include Foundation and AppKit
objects. This diagnostic has not yet established the calling stacks or responsible
ownership boundary. No warning is filtered or attributed to the GPU collector
without evidence. The earlier clean collector-only run does not clear warnings
from the full application.

The retained AX probe separately emitted **two warnings from PID 4375**. Its
lifetimes need correction in the planned Task 4 helper. App and helper failures
remain separate. The [native comparison protocol](apple-native-comparison-protocol.md)
requires diagnostic coverage and cannot accept these warnings as a clean result.
Root is investigating calling stacks before choosing a correction. The acceptance
implementer has been told to preserve rejection and continue independent tests.

## F2: generic AX traversal did not observe GPU content

AX trust was true and the window inventory reached one window. However, the
existing generic `AXChildren` traversal returned seventeen `AXApplication` nodes
before its depth bound; the result is explicitly truncated. It contains no GPU
field census, geometry or interaction evidence. Task 4 needs window-rooted,
cycle-aware readiness and bounded observation. No labels are inferred from the
failed tree or from diagnostic publication.

## Cleanup and limits

Probe PID 4375 exited zero and was reaped. Root requested SIGTERM for task-owned
app PID 4374, which exited -15 and was reaped. Neither remains running. No other
process was stopped. This cleanup proves owned process exit, not the normal
application shutdown required by final native replay.

The [Mac build and 63 app tests](memory-mac-build.md) remain passing compilation
and unit-test evidence. They do not establish native resource lifetime, visible
GPU readings or acceptance. Task 3's integration reviews remain limited to their
recorded scope; the broader GPU commitment is unfinished.
