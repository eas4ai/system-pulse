# Apple collector quality review

Status: CHANGES REQUIRED on 2026-09-06. F1 is open.
This review is recorded before corrective source work.

## Scope and strengths

Reviewer: independent `apple_gpu_quality`, read-only after
[specification review passed](apple-spec-review.md).

Base `2eebd6a2e77509279606605bbf9ae30e0b2df62b`; candidate
`a7518cbe077aa390e960926dd616dba4e386ae2a`; native-tested source
`df2300f2a6af5a9e6bf0ebe60d725379096c2b46`.

The reviewer found cohesive native/arithmetic modules, checked operands and
bounded enumeration, independent field outcomes and baseline invalidation,
careful partial-output/subscription ownership and library destruction order.
Integration preserves the public schema and uses a meaningful Rc worker
lifecycle regression. Capability records state the native evidence limits.

## F1 — Important: drain autoreleased objects per Apple capture

Location: `examples/system_pulse/collectors/src/apple/native/mod.rs:19`.
The production path reaches it from the plain Rust sampling worker at
`collectors/src/service.rs:84` through `host/mod.rs`. The direct snapshot
collector also calls it without an autorelease pool.

Explicit Create/Copy ownership does not drain autoreleased objects from Metal
and Objective-C calls. Apple's [autorelease-pool contract](https://developer.apple.com/library/archive/documentation/Cocoa/Conceptual/MemoryMgmt/Articles/mmAutoreleasePools.html)
requires a pool on secondary threads using Cocoa and periodic drains for
long-lived threads.

Root's bounded native diagnostic used the hash-verified committed collector,
three snapshots and `OBJC_DEBUG_MISSING_POOLS=YES`. The independent reviewer
inspected the originals. They contain 17 missing-pool warnings for Foundation
objects, explicitly identifying autoreleased objects without a pool. Collector
PID 3155 exited zero and was reaped; no root diagnostic process remains.
The [retained diagnostic](apple-autorelease-diagnostic.json) contains commands,
hashes, original stderr and transfer verification. Full artifacts remain in
`/home/shawn/workspace2/task-manager-artifacts/apple-collector/root-autorelease-1thyc5x8/`.

The initial tiny NSObject controls emitted no warnings in either mode and were
ineffective positive controls. The collector itself emitted the runtime
diagnostic. Neither this short run nor the review measured a long-term leak
rate; no such rate is claimed.

Required correction: establish a scoped autorelease pool around each Apple
capture, including early returns, and drain after borrowed native references
cease use. Retained handles and owned Rust snapshot data must remain valid.
Verify lifecycle behavior and repeat the native diagnostic on the committed
correction. Resolve through the original implementer, then obtain independent
re-review before closing F1 or Task 2.

## Verification and boundaries

The reviewer independently ran 96 Linux collector tests, strict Clippy and
formatting checks; all passed. All 12 changed collector/notice/manifest/lock
files matched the immutable native-tested and candidate commits. All 42 retained
artifact hashes and sizes matched; original native logs showed 44 passing tests.
These checks did not detect the pool omission; code inspection and the native
diagnostic did.

No Critical or Minor findings were recorded. The review performed no source
edits, commits, SSH or native actions; root performed the diagnostic and retained
its original results. External hardware accuracy, other Apple platforms,
sleep/wake, UI/persistence and aggregate acceptance remain pending.
