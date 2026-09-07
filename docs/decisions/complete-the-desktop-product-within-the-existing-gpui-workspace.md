# Complete the desktop product within the existing GPUI workspace

Level: Judged
Decided by: agent
Rests on: The developer asked to finish the original application; APP-001 through APP-008 describe its remaining process controls, customization, appearance, presets, layout and Linux package while retaining LIVE and GPU obligations.
Would be wrong if: The implementation bypasses process identity, loses existing saved state, introduces a second collection pipeline, fabricates readings or treats unavailable native hardware as verified.

## Decision

Implement the feature-sized work in docs/plans/finish-application.md directly in the existing application. Keep process projection and identity-bound native actions separate from sampling, with Linux pidfd signaling and explicit unsupported outcomes elsewhere. Extend the model with backward-compatible appearance and named preset state; preserve corrupted originals and the legacy preset. Use existing GPUI component inputs, menus, semantic theme tokens and separate dock panels. Bundle licensed fonts and application assets, build hardware-aware layout templates only for first launch or explicit preset recall, and produce a rootless Linux package. Use targeted behavior tests and native product flows, then run the required committed aggregate once after the meaningful source changes. The recent full Linux pass remains a starting checkpoint, not final evidence for the changed app. Keep the outstanding Intel/Apple native evidence and Mac F1 review visible and required; no public release or deployment is included.

## Realized by

- 6a46f15a204ca31e4258cb408912877e17ba450d Complete product source, native flow replay and composed Linux/package acceptance; final committed execution remains required.
