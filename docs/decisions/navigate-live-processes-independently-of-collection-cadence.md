# Navigate live processes independently of collection cadence

Level: Judged
Decided by: agent
Rests on: LIVE-003 and LIVE-010 require real process navigation during collection. The retained diagnostic performed 176 two-key batches; newer-snapshot waits consumed 116.612 seconds, and an exited selected identity caused an unchecked list.index failure with the controlled target still present.
Would be wrong if: The correction weakens native endpoint acknowledgement, accepts multiple selected identities, aliases PID reuse, navigates from stale frames, hides target disappearance, overlaps input batches, or extends any original deadline.

## Decision

Retain two-key batches, exact native endpoint acknowledgements, and the original 180-second total and eight-second batch deadlines. Read and validate the current diagnostic frame between batches without requiring its sequence to increase after every two keys. If the previous selected identity disappears, reconcile its native state against a fresh snapshot under the same deadline. Retry transient retention of the exited identity; once selection is actually clear, reestablish Home or End through actual keyboard input and acknowledge it. If a different identity becomes selected without an intervening key, fail: accepting it would hide a forbidden selection transfer under LIVE-003. Require the exact controlled target to remain present, never reuse an obsolete index or substitute a reused PID, and preserve multiple-selection rejection. Add focused lifecycle, unchanged-sequence, freshness, acknowledgement-ordering, identity, and deadline regressions. Preserve failures, complete independent SPEC then QUALITY review, then run fresh untraced native and aggregate acceptance.

## Realized by

- 0459aa6dc8464f0e378192eb4f4c345afe451127 fix(system-pulse): navigate across live process collection
- c2396a49ce04068bfc05f8f97a77843d168dde92 fix(system-pulse): validate native application registration
- ef36088be360347e3f58f8c367860a906055ce1e fix(system-pulse): retain validated navigation pacing paths
