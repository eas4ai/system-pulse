# Retain supplemental process observation until exit

Level: Judged
Decided by: agent
Rests on: LIVE-013 requires independent counter brackets. Retained host evidence shows a process remained in a post-query census after its fast sampling was retired at the first full sweep.
Would be wrong if: Retained sampling removes ordinary reads, loses PID-start identity or errors, exceeds existing bounds silently, or treats census presence as counter proof.

## Decision

Keep newly discovered processes eligible for the existing prospective 20 ms supplemental schedule after ordinary sweeps begin reading them. Retain direct stat/io attempts and query windows through disappearance, preserving identity checks and actual errors. Keep one thread, every ordinary read, the 4096 supplemental observation cap and existing capture limits. Add focused handoff, disappearance, identity and limit regressions. Preserve the failed evidence; do not infer missing counter values or relax comparisons. Independent reviews and a fresh committed aggregate must still pass.

## Realized by

(none yet: recorded, not built)

## Realized by

- 0458ddee7706913467f59b47fa02aa563ca2c053
