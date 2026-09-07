# Native process exit check failure

The aggregate against `bc5237d1f8e24074a5eb4d75d1e409ef9e944847` passed 437 automated tests, formatting, strict Clippy, both binary builds, and independent host verification. Native acceptance failed with `exited identity remains in native tree`. This is not complete acceptance.

The host verifier checked 42,258 counter brackets with zero missing endpoints, 468 stable totals, 2,218 exact readings, 16,654 process fields, and 96 interface comparisons. Cairn retained passes for LIVE-004, LIVE-012, and LIVE-013; the ten remaining requirements are unverified.

The native replay reached the real child process case after launch, metrics, collapse, charts, and inner scrolling. Its child was `process:1524059:69556521`. The diagnostic frame at failure had sequence 217 and render revision 216, with the child absent from both the accepted snapshot and diagnostic rendered entries. The prior child-right frame had sequence 214, revision 213, and eight child entries. The failure screenshot was byte-identical to the prior child-right screenshot.

The harness waited for a newer snapshot without the child, then immediately asserted that the accessibility tree no longer contained its identity. Independent source diagnosis confirms the synchronization race. `workspace.rs` replaces process data and submits diagnostics before panel refresh and redraw scheduling. `diagnostics.rs` derives its rendered entries from that data; the entries do not acknowledge native rendering. GPUI constructs accessibility updates during frame prepaint. These facts do not prove that the native tree would have updated within the five-second budget. The failure must remain recorded. A repair must still observe actual native disappearance within that existing budget.

[The compact artifact record](native-exit-failure.json) preserves paths and SHA-256 hashes. Native cleanup terminated the application with exit -15 and confirmed its PID no longer existed; normal shutdown and later native cases were not reached. NVIDIA hardware accuracy remains unverified on this host.
