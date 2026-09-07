# Independent SPEC review: Mac application and dispatcher pools

Candidate: `c4a6aab106826a5c20c8f48a49e6617a14a2b57b`  
Base: `4f9bc456d2aeae34776a313e09ee08678a04bee7`  
Worktree: `/home/shawn/workspace2/task-manager-worktrees/workspace-visibility`  
Review date: 2026-09-06

**Verdict: the focused source correction complies with the specified pool boundaries, ownership behavior, narrow vendoring and dependency constraints. Required native verification remains OPEN. This is not an unconditional SPEC pass for the complete decision, F1, Task 5 or the GPU commitment.** No additional actionable source-contract mismatch was found. This review does not perform or replace the subsequent independent quality review.

## Retained finding and required action

**F1 — high severity; native lifetime acceptance remains incomplete.** The decision explicitly requires an unfiltered full-application diagnostic and native interactions after the correction, with investigation of remaining warnings (`docs/decisions/drain-autoreleased-objects-at-mac-application-and-dispatcher-boundaries.md:14`). Task 5 preserves that requirement (`docs/plans/intel-and-apple-gpus.md:116`). The original full-app finding is at `docs/execution/intel-and-apple-gpus/apple-gui-preflight-findings.md:13`.

The final GREEN2 application/background process, PID 10382, prints `PASS application lifetime background` but emits **16 missing-pool warnings** on thread `0x16d253000`. I read the original stderr and independently verified its size/hash against its process record. The warnings have no demonstrated origin. Passing destructor assertions does not make that process clean. No evidence attributes these warnings to a platform-only or test-only source; no such attribution is accepted here.

The ten bounded fatal invocations report no reproduction. Their predeclared protocol changes the missing-pool setting to `fatal` and retains the same executable hash. This does not explain the earlier warnings or establish a clean full application. The Foundation positive control is not a stack trace of the application failure.

**Required action:** retain F1 and the correction's outstanding native verification. Once the authorized desktop observation path is available, rerun the normal linked application with unfiltered missing-pool diagnostics, required native interactions and orderly shutdown. Investigate any remaining warning at its actual origin before acceptance. Do not replace that proof with these isolated regressions, compilation, a killed process, or widened warning policy. The locked desktop is an external dependency for this replay, not a waiver. No new source boundary can be justified solely from the current unattributed warning.

## Source-contract assessment

| Requirement | Independent assessment |
| --- | --- |
| Pool precedes application construction and encloses orderly lifetime | `examples/system_pulse/src/application.rs:3` opens the macOS pool around construction and callback. `examples/system_pulse/src/main.rs:8` runs the native app inside it. Upstream `gpui/src/app.rs:233` keeps its `Application::run` stack through `platform.run`; the caller's pool therefore surrounds that ordinary run/return path. Runtime shutdown verification remains pending. |
| Separate pool for each dispatcher runnable invocation | `vendor/gpui_macos/src/dispatcher.rs:166` encloses reconstruction, metadata access, profiler calls and consuming `runnable.run()`. Global priorities, main-thread and delayed dispatch all pass this trampoline (`:37`, `:55`, `:62`). The separate realtime closure path is unchanged and is not a `RunnableVariant` invocation. Scheduling is unchanged. |
| Callback draining and retained/owned survival, including failures | `vendor/gpui_macos/src/dispatcher_lifetime_tests.rs:13` covers temporary destruction and retained/owned results; `:46`, `:67`, `:111` cover error, pending/resumed polls and cancellation-time future destruction. `:165` uses actual native queues at three priorities and delayed dispatch, checking destruction on the callback thread. `examples/system_pulse/tests/macos_application_lifetime.rs:8` covers application success/error/unwind and `:75` exercises the actual linked background executor. |
| Production integration is exercised | The dispatcher integration crate includes the exact private vendored source (`examples/system_pulse/tests/macos_dispatcher_lifetime.rs:8`), rather than a reimplementation. The linked application/background case additionally goes through `gpui_platform` and its real executor. Native artifact fingerprints bind the normal application to `gpui_platform-d6c94bd1c5e4b7fb`, then local `gpui_macos-307b518d3f66441a`. Source inclusion alone would not have established this. |
| Narrow pinned vendor and provenance | Compared actual upstream checkout files and declarations to the vendor. All 16 inventory hashes match the upstream package. The original license and 13 other Rust files are byte-identical; only `Cargo.toml` and `src/dispatcher.rs` differ. The dispatcher diff adds only the requested scope and private test inclusion. All 39 inherited dependency declarations, package metadata, lints and features normalize exactly to the local manifest. |
| Preserve dependency identities/features/lock resolution | Root patch selects only local `gpui_macos`; the package remains excluded from workspace membership. Parsing both lockfiles found exactly two changed package entries: removal of `gpui_macos`'s git source and addition of already resolved native dependencies to `system-pulse`. Every other selected package entry remains identical, including versions, checksums and dependency lists. No whole-framework upgrade is present. |
| Declare new native inputs and affected checks | Both `.cairn/mechanisms/gpu-acceptance:14` and `.cairn/mechanisms/live-acceptance:13` include the vendor and corrective decision. The existing app directory declaration includes its helper and integration tests. `scripts/system-pulse/acceptance.py:198`, `:522`, `:574` require and execute the vendor formatting step. Existing warning policy and thresholds were not changed. |

The intervening `45ce6418` Linux diagnostic documents are outside this focused source review. No code-quality verdict or whole-GPU source audit is implied.

## Verification performed by this reviewer

All shell commands used `rtk`. Supporting scripts and results are in this report's directory.

- `rtk proxy cairn wake`: exit 1, Resolvable for the pre-existing collector decision's missing `Realized by` entry. Read only; no Cairn marker, decision or receipt was changed.
- `rtk proxy python3 /home/shawn/workspace2/task-manager-artifacts/gpu-macos-pools/spec-review-c4a6aab1/verify-source.py`: exit 0. Parsed lock comparison, exact inherited-manifest normalization and original-file comparison passed. See `source-verification.json` and `dispatcher-upstream.diff`. An initial ad hoc verifier assertion failed because the reviewer assigned normalized entries at the wrong dictionary level; the corrected retained script passed. This was a reviewer-script defect, not a candidate failure.
- `rtk proxy python3 /home/shawn/workspace2/task-manager-artifacts/gpu-macos-pools/spec-review-c4a6aab1/verify-evidence.py`: exit 0. Verified 62 original stdout/stderr bindings across RED5, RED6 and GREEN2; inspected nine expected native lifetime failures and nine corrected passes; all 19 GREEN2 commands exited zero with recorded reaping, absent process groups and no timeout. The 16 warnings remain included. Verified the three copied executable hashes and native fingerprint chain. See `evidence-verification.json`.
- Compared all 2,103 native snapshot manifest paths with the candidate. Only the documented `UPSTREAM.json` purpose text differs; separately compared that archive member to confirm the one descriptive field change. The two final evidence documents were added after the snapshot. The original native app-test stdout reports 63 passed, zero failed.
- `rtk proxy python3 -B -m unittest discover -s scripts/system-pulse -p test_acceptance.py -v`: exit 0; seven tests passed.
- `rtk proxy git diff --check 4f9bc456d2aeae34776a313e09ee08678a04bee7 c4a6aab106826a5c20c8f48a49e6617a14a2b57b`: exit 0.
- `rtk proxy git status --porcelain=v1`: empty; candidate source was clean.

Graph discovery returned no `with_application` node for the indexed app project, so source inspection used the permitted tilth fallback. No shared Cargo checkout was mutated. I did not rerun Cargo builds, native tests, GUI activity, workloads or debugger operations. Native execution results above are independently inspected historical evidence, not new reviewer executions. Root's additional complete archive/source binding checks remain separate supporting evidence; this report does not claim to have independently repeated all of them.

## Limits and self-audit

The focused source scope is reviewable and supported by meaningful native failure-to-pass evidence. Full native application lifetime and interaction acceptance is unperformed; F1, Task 5, Linux preservation, hardware accuracy and the final GPU commitment remain open. No acceptance receipt or realization entry was fabricated to advance the review order.

Reviewed the production rules for scope, boundary behavior, dependencies/provenance, lifetime reliability, verification, truthful reporting and authorization. No source edits or corrections were made during review. This report is complete as a SPEC review; it intentionally does not declare the implementation's remaining acceptance obligations complete.
