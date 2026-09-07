# Drain autoreleased objects at Mac application and dispatcher boundaries

Level: Judged
Decided by: agent
Rests on: GPU-007/008 require native workspace behavior and accurate native evidence; the predeclared lifecycle protocol rejects missing pools. Actual isolated probes of the locked native GPUI artifact reproduce constructor 24-to-0 and executor callback 1-to-0 warnings with proper thread-local scopes.
Would be wrong if: The corrected scopes release values still borrowed across callbacks, leave attributable native warnings unresolved, change dependency identities or scheduling semantics, or require an unrelated framework upgrade.

## Decision

Establish an autorelease pool before the macOS application constructs GPUI and retain it through orderly native shutdown. Establish a separate pool around every pinned Mac dispatcher runnable invocation so callback temporaries drain on that thread after the invocation; a main-thread pool does not cover worker callbacks. Preserve retained native objects and owned Rust results beyond each scope.

Apply the dispatcher correction through a narrowly vendored gpui_macos package from the already locked Zed commit f66ed399cdde86092af8af3dc7b418abf45f37f8, retaining its license and upstream provenance. Normalize only inherited Cargo metadata needed to build that package locally; keep the existing dependency identities, features and lock resolution. Do not update the full GPUI/Zed dependency graph or mutate a shared Cargo checkout. Include any new native implementation inputs in the declared acceptance mechanisms and affected checks.

This is corrective work for the recorded full-application lifetime finding before native GPU acceptance. The current acceptance-helper implementer continues its own task; one subsequent source implementer owns this focused correction and receives independent specification then quality review. Native tests must demonstrate draining across actual dispatcher invocations and survival of explicitly retained/owned values. Rerun the unfiltered full-application diagnostic and native interactions after correction. The isolated constructor and callback probes identify missing scopes but do not prove that these are the only origins of the original 551 warnings; investigate any remaining warning rather than filtering it or widening the acceptance policy.

Evidence is recorded in docs/execution/intel-and-apple-gpus/apple-gui-preflight-findings.md and apple-gui-pool-investigation.md. No source correction was made before this decision.

## Realized by

- c4a6aab106826a5c20c8f48a49e6617a14a2b57b fix: scope macOS application and dispatcher autoreleased objects

This identifies the built source scopes only. Mac F1, the unfiltered full-application replay and independent quality approval remain open in docs/execution/intel-and-apple-gpus/apple-pool-spec-review.md. Binding the source commit does not grant native acceptance.
