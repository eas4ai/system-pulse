# Recover native navigation without claiming model selection evidence

Level: Judged
Decided by: agent
Supersedes: navigate-live-processes-independently-of-collection-cadence
Cause: the premise was false
Rests on: LIVE-003 forbids selection transfer on exit, reorder or PID reuse. Independent SPEC review confirms native virtualization omits offscreen selected rows, while existing pure reconciliation tests do not exercise production accept_snapshot selection clearing before another key.
Would be wrong if: The evidence split weakens LIVE-003, accepts observed selection transfer, treats virtualized native absence as model absence, extends existing budgets, or changes product behavior merely to help the verifier.

## Decision

Retain navigation independent of per-batch collector advancement, two-key batches, exact native endpoint acknowledgements, original 180-second total and eight-second batch deadlines, and current membership and frame validation. The previous decision assumed a complete native scan could prove model selection clear; this was false because the process table instantiates only visible rows. When a fresh snapshot omits the previous PID/start identity and a complete native scan finds no instantiated selected row, send Home/End and acknowledge its exact endpoint as explicit navigation recovery. Do not claim this observes automatic model clearing. Continue rejecting any observed different or multiple selected identities without an intervening key, stale frames, target loss, PID reuse, incomplete observations, and deadline overruns. Prove actual clearing separately with a GPUI integration regression through production accept_snapshot: retain selection through reordering, then remove the selected identity while another survives, and assert panel.selected is None before further input; also cover same-PID/different-start replacement. During the existing actual selected-child exit check, reject another instantiated selected identity before further input within the same five-second deadline. Native evidence describes visible selection only; direct integration tests cover the full model state. No new product diagnostic channel or relaxed requirement is needed. Preserve earlier decisions and failures and complete focused verification, independent SPEC then QUALITY reviews, and fresh committed native and aggregate acceptance.

## Realized by

- 1790fe53506439b8c897421aa91be15598586162 test(system-pulse): prove selection clearing and current native exit
