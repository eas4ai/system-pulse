# Apple autorelease-pool correction candidate

Status: Implementation and verification in progress; independent re-review pending.
F1 remains owned by the recorded quality review and root orchestration.

## Working state

- In progress: scoped pool and native object-lifetime regression.
- Pending: Linux checks, committed native tests/Clippy/formatting and missing-pool diagnostic.
- Pending: repeated native capture/load, hashed evidence and independent re-review handoff.

## Recorded failure and correction scope

The [quality review](apple-quality-review.md) and [original diagnostic](apple-autorelease-diagnostic.json) record 17 actual missing-pool warnings from the hash-verified collector before this correction. The earlier tiny NSObject diagnostic controls were ineffective and are not treated as positive controls. No leak rate was measured.

Apple's [pool contract](https://developer.apple.com/library/archive/documentation/Cocoa/Conceptual/MemoryMgmt/Articles/mmAutoreleasePools.html) requires pools for Cocoa calls on plain secondary threads and regular draining for long-lived work. The runtime [declarations](https://github.com/apple-oss-distributions/objc4/blob/main/runtime/objc-internal.h#L988-L996) expose objc_autoreleasePoolPush and objc_autoreleasePoolPop with an opaque thread-local token. The correction uses those functions directly through the existing objc link, with no dependency or thread change.

Declare one scoped drop guard before all other locals in AppleCollector::collect. Normal return, early return and Rust unwinding then drain the pool after capture locals cease use. Retained IOReport/CF handles stay owned across captures; only owned Rust descriptors and observations escape a capture. The native lifecycle test uses weak references to actual Objective-C objects, checks their liveness before drainage and deallocation afterward, and checks retained CF/owned Rust data after drainage. It does not infer correct drainage solely from diagnostic silence.
