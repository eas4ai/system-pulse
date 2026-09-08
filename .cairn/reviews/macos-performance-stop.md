# Mac performance stop review

Scope: review the final receipts and stop disposition. This is not a passing
final review of the performance commitment. No code was changed during review.

Attacked measurement integrity: the gate recomputed all twelve observations,
checked current production source, native harness and binary hashes, matched
the native build and preservation receipts, and checked Linux preservation.
All eleven negative verifier tests passed. The gate correctly withheld both
CPU passes: Summary ratio 0.782968 and tray ratio 0.660418 exceed 0.5.

Attacked preservation and cleanup: the native receipt includes ordinary UI
without diagnostics, close/reopen, background history, one-second settings,
current filesystem capacity comparisons and normal Quit. The coordinator
records restoration of the original smoke app (PID 9969) and removal of its
owned wake assertions. Earlier evidence remains archived rather than replaced
as history.

Finding: the required CPU reduction was not achieved. Resolution is the
developer's explicit decision to stop optimization and suspend this commitment,
not a waiver, lowered threshold or passing review. Missing Intel/GPU evidence
and unrelated application work remain outside this result.
