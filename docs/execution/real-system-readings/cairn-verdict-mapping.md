# Cairn requirement verdict mapping

This is the predeclared evidence mapping for the existing LIVE acceptance gate,
following Cairn commitment 10. It changes reporting, not the agreed falsifiers.

All automated steps remain prerequisites: source guard, nonempty Python and Rust
suites, scoped formatting, strict Clippy, locked builds and diff validation.

| Requirements | Additional evidence required before reporting pass |
| --- | --- |
| LIVE-004, LIVE-012, LIVE-013 | Successful independent host process plus every mandatory host artifact, capability/source comparisons, stable totals, counter brackets and cleanup. Automated tests include backend and verifier mutations. |
| LIVE-001, LIVE-002, LIVE-003, LIVE-005, LIVE-008, LIVE-009, LIVE-011 | Host proof above; all primary native cases through restart; their metric/chart/process/interaction artifacts; normal shutdown evidence for session-01 and session-02; successful shared transport cleanup. |
| LIVE-006, LIVE-007, LIVE-010 | Both recovery cases and missing-device; their required artifacts and normal shutdowns; the complete native and aggregate gate. |

The lifecycle requirement LIVE-009 combines its existing service tests with
primary native interval changes, restart and normal shutdown. The verifier
requirement LIVE-013 combines mutation tests with actual host comparison evidence;
native display correctness remains separately required by LIVE-001 and LIVE-005.
Unavailable presentation, identity persistence and complete workspace preservation
remain pending until the recovery and missing-device proof finishes.

A native case's progress flag is provisional. Read final retained results only
after the native subprocess terminates, and validate artifacts and applicable
shutdown/cleanup before using completed cases. Reuse existing checks for both
full and partial results. A missing artifact invalidates its evidence group;
a focused preparation cannot earn aggregate evidence. No test or session is
repeated to generate a separate requirement receipt.

Emit each earned result once as `cairn: LIVE-001: pass`. Incomplete or interrupted
proof is omitted, which Cairn records as unverified when at least one known
result line exists. Free-text harness exceptions do not identify a falsified
requirement and must not be guessed into individual failures. Retain the original
aggregate failure and nonzero exit even when some requirement passes survive.

Cairn's compatibility rule uses the exit code for every mapped requirement if no
known result lines exist. Consequently the protocol cannot yet represent an
entirely unverified early harness failure. This limit is disclosed; do not invent
a sentinel verdict, alter Cairn, or claim such a run yielded independent failures.
