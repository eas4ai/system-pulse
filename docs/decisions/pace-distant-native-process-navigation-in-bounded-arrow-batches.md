# Pace distant native process navigation in bounded arrow batches

Level: Judged
Decided by: agent
Rests on: APP-008, LIVE-003, LIVE-010, LIVE-013; final-acceptance-stable-columns-20260907 retained a 180-second timeout while exact two-key acknowledgements advanced toward a child placed mid-table after host PID wrap.
Would be wrong if: A batch can pass without its exact endpoint, input overlaps unacknowledged batches, a prior prefix proves selection, a target disappears unnoticed, any freshness or deadline bound changes, or any held-input, physical-cell or controlled-exit requirement is omitted.
History: Earlier navigation decisions corrected false inferences from virtualized absence and collection-paced input. Preserve their current exact native proofs, independent endpoint-exit evidence, strict membership and uniqueness, prior-prefix expiry and deadline guards. This decision changes only the two-key pacing term for distant targets; all failed captures remain failed.

## Decision

For remaining distances above 32 rows, issue at most eight same-direction physical arrow keys before the existing exact endpoint acknowledgement. Keep one- or two-key batches for the final 32 rows, and preserve Home/End and final-target behavior. Bind optional prior acknowledged-selection evidence to the exact issued direction, count, identity indices, publication and dispatch windows for bounded one-through-eight-key batches. This prefix never acknowledges an endpoint or authorizes more input. Reject mixed, empty and oversized key envelopes. Keep the existing eight-second batch, 180-second navigation, two-second single-read freshness and five-second metric/exit bounds. Keep all sixteen child-cell physical comparisons, target exit, held input and exact 64-key tests. Add deterministic tests using the real navigation method for distant targets with delayed acknowledgements in both directions, dropped or wrong endpoints, and bounded prefix envelopes. Run affected and complete Python tests and fresh native acceptance. No production source change belongs to this pacing correction.

## Realized by

(none yet: recorded, not built)
