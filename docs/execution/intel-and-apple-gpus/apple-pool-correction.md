# macOS application and dispatcher pool correction

This source checkpoint implements the [recorded pool decision](../../decisions/drain-autoreleased-objects-at-mac-application-and-dispatcher-boundaries.md). It does not close the full-application lifetime finding F1 or satisfy native GPU acceptance. The final native tests pass, but one constructor/background test process still emitted 16 missing-pool warnings from an unresolved thread. Full native interaction and unfiltered application replay remain outstanding while the desktop is locked.

## Change and ownership

`examples/system_pulse/src/application.rs` creates the macOS autorelease pool before `gpui_platform::application()`. The production entry point calls `app.run` inside that same scope, including orderly return and destruction. Non-macOS construction follows the existing path. A separate pool wraps each actual Mac dispatcher trampoline invocation, including runnable recovery, profiler update, runnable execution and profiler restoration. High, medium, low, main-thread and delayed dispatch already share that trampoline; their scheduling is unchanged. The separate real-time closure entry point is unchanged.

An autorelease pool drains native temporary references on its own thread. It does not own explicitly retained references or owned Rust results. Native tests verify this distinction through weak native references and destruction notifications, including pending polls and canceled future destruction. No borrowed native object crosses a thread or callback boundary in the new code. The linked executor smoke test keeps its native string on the worker and returns owned Rust strings; Objective-C objects are not given an unsafe `Send` implementation.

Only the already locked `gpui_macos` package is vendored from Zed commit `f66ed399cdde86092af8af3dc7b418abf45f37f8`. Its 13 other original Rust files and original Apache license match the inventory hashes. `UPSTREAM.json` records all 16 original package files and 39 inherited dependency declarations. The local manifest expands inheritance, preserves package features and dev-dependencies, and replaces upstream workspace paths with the existing git source identity. Cargo.lock changes only gpui_macos to a local package and adds already resolved native dependencies to System Pulse. It changes no other selected package, version, checksum or dependency list.

The package is excluded from workspace membership to avoid resolving unrelated upstream benchmark features. The macOS dispatcher integration test includes the exact private vendored dispatcher source. A separate test constructs the real linked GPUI application and exercises its actual background executor. Neither test adds a product API. Both acceptance mechanisms now declare the vendor directory and corrective decision as inputs; their native package formatting check is required. Warning policies and acceptance thresholds are unchanged.

## Native red and green evidence

Tests ran on the existing Apple Silicon validation host in task-owned processes. Every test and build had a recorded deadline, PID and process group. All recorded final processes were reaped, their groups were absent afterward, and none timed out. The test application constructs the native platform without starting the AppKit run loop or opening a window.

| Check | Before correction | Final corrected source |
| --- | --- | --- |
| Ready callback: native temporary, retained object and owned result | Native temporary survives invocation; fails | Pass |
| Callback error result | Native temporary survives invocation; fails | Pass |
| Pending and resumed polls | First poll fails to drain | Pass for both invocations |
| Canceled future destruction | Drop-created native temporary survives; fails | Pass |
| Actual high/medium/low/delayed queues | Native destruction deadline fails | Pass; native deallocation occurs on the callback thread |
| Actual application construction: success, error and unwind | All three fail to drain scope temporary | All three pass; retained object survives pool |
| Actual linked background executor | Native destruction deadline fails | Pass; owned results survive and deallocation occurs on worker |

The five dispatcher regressions failed in RED5. The four application cases failed in RED6, after fixing test compilation errors. Earlier build preparation failures and intermediate GREEN1 Clippy failure remain in the original evidence; they are not reported as successful checks. GREEN2 contains the final `let _ =` handling for native autorelease helper return values and passed all 19 commands:

```sh
cargo test --locked -p system-pulse --test macos_dispatcher_lifetime --no-run --message-format=json
cargo test --locked -p system-pulse --test macos_application_lifetime --no-run --message-format=json
cargo build --locked -p system-pulse --bin system-pulse --message-format=json
cargo build --locked -p gpui_macos --lib --message-format=json
cargo clippy --locked -p system-pulse --all-targets --no-deps -- -D warnings
cargo clippy --locked -p gpui_macos --lib --no-deps -- -D warnings
cargo test --locked -p system-pulse --lib --bin system-pulse
cargo fmt -p system-pulse -- --check
cargo fmt --manifest-path vendor/gpui_macos/Cargo.toml -- --check
cargo metadata --locked --format-version 1 --filter-platform aarch64-apple-darwin
```

The remaining nine commands invoke the compiled test executables directly: five dispatcher methods with `--exact`, and application cases `success`, `error`, `unwind`, `background`, each in a fresh process with `OBJC_DEBUG_MISSING_POOLS=YES`. Exact executable paths, arguments and all 19 process results are in [the machine-readable record](apple-pool-correction.json). The application library tests passed 63 tests on native macOS and Linux. Local Clippy, both formatting checks and Apple-target metadata resolution passed. The acceptance script suite passed all 444 tests. Local checks predate only the macOS test return-value cleanup; native GREEN2 checks include that cleanup.

## Remaining warning and diagnostic limits

GREEN2 application background PID 10382 emitted 16 warnings on thread `0x16d253000`: six `__NSSetI`, four `__NSArrayM`, three `__NSCFString`, two `__NSSingleObjectSetI`, one `NSConcreteData`. All five dispatcher methods and the other three application cases emitted no missing-pool warnings. GREEN1 also had intermittent application warnings. Passing lifetime assertions does not dismiss those warnings or establish their origin.

A separately recorded Foundation positive control confirmed that `OBJC_DEBUG_MISSING_POOLS=fatal` aborts the task process and produces a matching native crash report. That positive-control stack is not the application's warning stack. Additional constructor and background diagnostics did not reproduce the actual warning, and one attempt refused execution because the shared target artifact hash had changed. Those outcomes are preserved.

One predeclared final diagnostic batch used the exact GREEN2 background executable pathname and working directory, checked its SHA-256 before and after every invocation, and changed only the missing-pool setting to `fatal`. The batch was capped at ten invocations and 60 seconds total, with a stop on the first matching crash. All ten processes exited zero in 1.823 seconds with no matching warning or crash. No additional source boundary is justified by that nonreproduction. F1 remains open; no full GUI replay, shutdown interaction or native GPU receipt is claimed. No debugger attachment, screen capture, input automation or privacy/security setting change occurred.

## Artifact binding

Evidence root: `/home/shawn/workspace2/task-manager-artifacts/gpu-macos-pools/correction-20260906`.
Native root: `/Users/shawnmcallister/system-pulse-gpu-validation-03rjwxl7`.

- Final native source archive `pool-green2-source.tar.gz`: SHA-256 `737011493389d04c9f16f72342787c3c26e48d4901ade91f49839f7561bc17b4`.
- Final native application: SHA-256 `18954fbde83a6596965268b7b7ed4561ce49ecb8ddc14c27e8c9a7f0134562a5`.
- Original evidence archive 1: SHA-256 `2db520ca93ba2af2fff36504e4d70f6c91cd921a22f5034acb3e4104f0cc49e3`; 126 files verified after transfer.
- Original evidence archive 2: SHA-256 `08017d5084a4b125f1ce0ed0a02d6b6d67d9164a174556999534e3602add92bf`; 83 files verified after transfer.
- External `artifact-manifest.json`: SHA-256 `e34dedc312539965c518b1a5647f58b97ea2d59e4c0bc6fb28482b321e35b93a`; 287 files with byte counts and hashes. Later review outputs are separate.

Archive 2 preserves final binaries, original stdout/stderr, process records and Cargo fingerprints. The application binary's content identifies its hashed Cargo artifact; fingerprint dependency values bind that artifact to `gpui_platform-d6c94bd1c5e4b7fb`, then `gpui_macos-307b518d3f66441a`. Cargo's corresponding compiler artifact names the GREEN2 local vendor manifest. This proves the final application links the corrected package; a standalone dispatcher test alone would not prove that. `linkage.json` also records library and test executable hashes.

All files in the tested source snapshot still match except the descriptive `purpose` text in `UPSTREAM.json`, corrected after testing to describe the completed inventory. This evidence document and its JSON companion were then added. These documentation-only changes do not change the tested executable. The commit identifies the final reviewable source; committed acceptance input enumeration is checked after that commit and retained externally. The decision's Realized by section remains for independent specification and quality review.

## Production rules self-audit

1. Mapped the actual application, dispatcher and ownership paths before changing them.
2. Limited production behavior to two native pool boundaries; preserved the locked framework revision.
3. Used one private application helper and the existing dispatcher trampoline.
4. Preserved scheduling and public APIs; retained and owned result tests cover the lifetime boundary.
5. Kept failures visible in original process logs; no credentials or private content were added.
6. Recorded upstream provenance and license; changed no shared checkout or host permission.
7. No persistent state or migration changes; process cleanup was checked after every final trial.
8. Scoped one pool per invocation; native test waits and diagnostic batches are bounded.
9. Tracked implementation, verification and evidence work separately; the broader finding stays open.
10. Observed native regression failures and final passes, built both native packages, and ran relevant lint and acceptance tests.
11. Reported intermediate failures, remaining warnings and the missing full native replay explicitly.
12. Followed the recorded decision and the coordinator's bounded diagnostic protocol.
13. Satisfied with this focused source checkpoint for independent review. The unresolved warning and required native replay prevent production acceptance or closure of F1.
14. Reviewed the new implementation comments and evidence for plain technical language.
