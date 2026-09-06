# Task 4 Q1 independent specification re-review

**SPEC PASS** for candidate `f1e781337d0e32f30c7800795864395dd96e2028`, against baseline `50ea29d6653d42ceafc8b3f246b9a18ae721b612`. Q1 is closed for specification review. No new findings. Prior F1–F10 SPEC PASS remains the baseline. This review does not establish hardware acceptance or replace the separate quality review.

## Ownership and error handling

The guard at `scripts/system-pulse/gpu_capture.py:84` surrounds successful process creation, start-record publication, waiting and stream closure. Its finalizer cleans the owned group and reaps the direct child before hashing logs and attempting completion publication. The bounded cleanup at line 35 escalates TERM to KILL and retains secondary cleanup errors. It does not add broad child reaping or a production subreaper policy.

Log hashing and completion publication are separately guarded at line 164. The original exception object remains primary; additional cleanup or recording failures are retained separately. Concurrent ownership at line 225 uses one in-memory stop event per job. Cleanup therefore continues when start artifacts are absent or recording fails. Body exceptions remain primary even when lifecycle and cleanup-error publication also fail.

Only `gpu_capture.py` and `test_gpu_native.py` changed among scripts/crates since the prior SPEC baseline. The correction commit itself changes those two files and two correction documents. Native/Rust helpers, role commands, environment/native provenance fields and the strict lifecycle verifiers remain intact.

## Verification actually run

- All 60 GPU unittest methods passed.
- Development verification passed all seven groups: aggregate 6, Apple capture 5, arithmetic 6, desktop 8, evidence 15, Intel 10, native 10. These are the same 60 methods, executed through the development entry point.
- The 10 native methods include seven existing methods and three new methods covering seven fault cases. They are not 14 methods.
- Affected-file Ruff lint and format checks, baseline-to-candidate whitespace check, and help invocations for `gpu_verify.py`, `gpu_host_capture.py` and `gpu_intel_capture.py` passed.
- Six independent real-process probes passed: stream-close exception; wait exception; log-hash plus completion error; completion error; two concurrent children with deleted start files; and two concurrent children with deleted starts plus completion/lifecycle/cleanup-error recording failures. Each preserved the original exception object and left all owned direct children reaped with absent groups in under 0.14 seconds. An unrelated child remained running throughout and was then cleaned up by its own observer.

Exact commands, exits and log digests are in `checks.json`. Extra probe code and observed results are retained in `independent-extra-faults.py` and `extra-fault-results.json`.

## Original reproductions

Both original quality reproductions were copied unchanged into separate review directories. Their original files were not modified.

The ENOSPC reproducer now records a terminated/reaped child, absent group and existing completion record. Its old defect assertion exits 1 because the leak is fixed.

The original SIGINT reproducer defers reaping its adopted descendant until after `owned_process` returns. Its process-existence assertions still exit 0. A separate instrumented copy observes `/proc` state `Z` and waitable SIGKILL exit status 9 before the observer reaps: the descendant is dead, not executing. The owner preserves `KeyboardInterrupt`, attempts completion, and truthfully records the residual group as a secondary cleanup error. The committed corrected-observer regression reaps during cleanup and verifies group absence. These original and diagnostic runs are retained separately.

## Integrity and remaining limits

All 2,072 tracked candidate files matched their commit blobs, including the 60 initially hashed capture/mechanism files. The worktree was clean. The frozen quality manifest and all 51 listed originals matched SHA-256 `48e5439f0ce77cbb67cb9caa384aa8f8feff8eee1d223fa29cfd0a079caea42b`; the correction post-commit manifest and all 93 listed files matched `595f6e821505b2e6cc5a9d11be40e817d96fac309c662dacec4bb5289d0a959c`. Full per-file verification is retained in `final-source-integrity.json`.

The full 443-test Python suite and unaffected native/Rust builds were not independently repeated for this correction. No hardware trials were run. Intel integrated/discrete and unlocked Apple GUI acceptance evidence remains missing; the original Linux native two-second freshness failures remain unresolved; Task 5's macOS main/dispatcher autorelease-pool correction remains unimplemented. No Cairn acceptance, marker, source, index or plan/decision changes were made by this reviewer.

The 14-rule production self-audit is recorded in `review.json`; it passes for this bounded Q1 specification review with the broader limits above retained.

The [structured source record](gpu-acceptance-q1-spec-review.json) binds this verdict to its external originals. Root verified all 87 original file sizes and hashes before committing this specification review.
