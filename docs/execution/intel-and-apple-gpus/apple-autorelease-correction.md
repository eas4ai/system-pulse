# Apple autorelease-pool correction candidate

Status: Correction candidate implemented and verified; independent re-review pending.
F1 remains owned by the recorded quality review and root orchestration.

## Working state

- Complete: scoped pool and native object-lifetime regression, verified by 46 native tests.
- Complete: Linux checks, native Clippy/formatting/build and corrected missing-pool diagnostic.
- Complete: repeated native capture/load, artifact transfer and SHA-256 verification.
- In progress: independent SPEC impact and QUALITY re-review handoff; root owns closure.

## Recorded failure and correction scope

The [quality review](apple-quality-review.md) and [original diagnostic](apple-autorelease-diagnostic.json) record 17 actual missing-pool warnings from the hash-verified collector before this correction. The earlier tiny NSObject diagnostic controls were ineffective and are not treated as positive controls. No leak rate was measured.

Apple's [pool contract](https://developer.apple.com/library/archive/documentation/Cocoa/Conceptual/MemoryMgmt/Articles/mmAutoreleasePools.html) requires pools for Cocoa calls on plain secondary threads and regular draining for long-lived work. The runtime [declarations](https://github.com/apple-oss-distributions/objc4/blob/main/runtime/objc-internal.h#L988-L996) expose objc_autoreleasePoolPush and objc_autoreleasePoolPop with an opaque thread-local token. The correction uses those functions directly through the existing objc link, with no dependency or thread change.

The correction declares one scoped drop guard before all other locals in AppleCollector::collect. Normal return, early return and Rust unwinding then drain the pool after capture locals cease use. Retained IOReport/CF handles stay owned across captures; only owned Rust descriptors and observations escape a capture. The native lifecycle test uses weak references to actual Objective-C objects, checks their liveness before drainage and deallocation afterward, and checks retained CF/owned Rust data after drainage. It does not infer correct drainage solely from diagnostic silence.
## Verified correction

Source commit: `2a40f069ef3b98856fa7a5ff32e004d48c383fa4`.
Collector Git tree: `5c8fafda1192ea27f153f12a20bee8befaa65b7c`.
The [evidence manifest](apple-autorelease-correction-evidence.json) records source archive, lockfile, executable and every retained artifact's SHA-256 and size. All 21 transferred native artifacts matched their remote hashes. The [selected snapshots](apple-autorelease-correction-snapshots.json) preserve Apple descriptors and readings from captures 1, 3, 16 and 40; the complete JSONL remains in the manifest's local and remote artifact directories.

| Check | Result |
| --- | --- |
| Linux collector tests | 96 passed |
| Linux strict Clippy and formatting | Passed |
| Native Apple collector tests | 46 passed, including weak-object lifetime and retained-value tests |
| Native strict Clippy, formatting and pulse-snapshot build | Passed |
| Same 3-capture diagnostic, 500 ms interval | Exit 0, 3 snapshots, unfiltered stderr 0 bytes, 0 missing-pool warnings |
| Repeated capture during 15-second Metal workload | Exit 0, 40 snapshots, unfiltered collector stderr 0 bytes, 0 missing-pool warnings |

Both diagnostics set `OBJC_DEBUG_MISSING_POOLS=YES`; no warnings were filtered or suppressed. The earlier source attempt `286c668f` passed 46 native tests but failed strict Clippy on `err().expect()` in the new test. Commit `2a40f069` uses `expect_err()` and passed all final native checks. Both attempts' logs are retained.

The corrected 3-capture diagnostic ran as PID 3654. The repeated collector ran as PID 3664 and the workload as PID 3666. Every process exited 0 and was waited for and reaped. The load run preserved stable sensor identities through all 40 captures. Usage and power returned 39 post-warmup values; frequency returned 31 active-residency values. Both shared-memory byte sensors remained available in all 40 captures. This exercises the retained IOReport handles across pool drainage and the owned snapshot data after each capture returns.

The existing Swift load helper inherited the diagnostic environment and emitted 57 missing-pool warnings from PID 3666. Its 10,324-byte stderr is retained separately and unchanged. This helper is distinct from collector PID 3664, whose stderr is empty. Task 4 owns the helper lifecycle correction; this candidate does not claim the helper is warning-free.

The existing SMC below-15-Celsius software guard remains unchanged. Under this load, Tg05 and Tg0D each supplied 32 accepted temperature values. Missing Tg0L/Tg0T keys, unattributable HID temperature and system fans retained their explicit unavailable reasons. These observations do not establish measurement accuracy or quantify a leak rate. Independent re-review, broader GPU acceptance and UI validation remain outside this correction's completion claim.

## Production self-audit

Rules 1–4: the change follows the recorded F1 evidence, adds one capture-scoped guard and native lifecycle tests, and preserves sensor contracts. Rules 5–8: the guard drains on normal return, early return and Rust unwinding; retained values remain owned, and native subprocesses have bounded waits and cleanup. No dependency, worker or persistence change was needed. Rules 9–12: the working list records completed verification, including the intermediate Clippy failure and the helper limitation, with root-owned review still pending. Rule 13: source, evidence and documentation were checked together before handoff. Rule 14: comments and documentation describe the concrete lifetime rule and observable results. No further implementation revision is identified by this self-audit; independent reviewers decide F1 and Task 2 closure.
