# Task 4 Q1 independent quality re-review

**CHANGES REQUIRED** at candidate `f1e781337d0e32f30c7800795864395dd96e2028`, against the complete Task 4 quality baseline `50ea29d6653d42ceafc8b3f246b9a18ae721b612`. The original process leaks are corrected. Q1 remains open for one Important error-preservation defect in the correction. There are no other Critical, Important or Minor actionable findings in this focused review.

Source and index remained frozen at documentation HEAD `c01f33f53b4d6518952cf7e1e3b20eb0ab2017f4`. Only `gpu_capture.py` and `test_gpu_native.py` changed among the reviewed source files since the baseline. This verdict concerns the acceptance helper implementation, not hardware acceptance, Task 5 or commitment completion.

## Q1-R1 — Important: stream-close failure replaces the triggering exception

**Location:** `scripts/system-pulse/gpu_capture.py:104` and `:131` in `owned_process`; error recording at `:169` and re-raise at `:182` then use the replacement exception.

The outer `except` captures the error only after both stream context managers have exited. If start-record publication or the wait raises and closing stdout/stderr also raises, Python propagates the close error to that handler. It becomes `primary`. The triggering exception survives only in `__context__`; it is not the object re-raised by `owned_process`, and the stream failure is not retained as a separate `capture_errors` entry. The normal caller's compact failure record consequently names the close error instead of the original launch failure or cancellation.

The Q1 correction contract explicitly requires preserving the original exception object while retaining secondary cleanup/reporting errors separately. Protecting cleanup with a finalizer fixed process survival, but it did not preserve error priority across the stream-exit boundary.

### Independent reproduction

`combined_faults.py` invokes the unmodified `owned_process` with real bounded Python children. A small file proxy delegates actual opening, file descriptors and closing to real files, then raises a specific `EIO` exception on stdout context exit. Only filesystem failure boundaries are injected; process launch, waiting and termination execute normally. For cancellation, a helper thread waits for the real child's readiness and sends an actual SIGINT to the reviewer process. Its signal handler raises the original sentinel `KeyboardInterrupt` object so identity can be checked precisely.

| Case | Expected | Actual |
| --- | --- | --- |
| Close failure alone | Close error is primary | Correct; original object preserved, PID 4042154 reaped and group absent |
| Start-record `ENOSPC`, then close `EIO` | Original `ENOSPC` object; close error retained separately | Close `EIO` object replaces original; `capture_errors` empty; PID 4042155 reaped and group absent |
| Actual SIGINT, then close `EIO` | Original `KeyboardInterrupt` object; close error retained separately | Close `EIO` object replaces interruption; `capture_errors` empty and completion says `capture_error: OSError`; PID 4042157 reaped and group absent |

All three calls finished in less than 0.13 seconds. An unrelated sentinel remained alive throughout, then its own reviewer killed/reaped it and verified group absence. These are not new process leaks, native GPU observations or false-acceptance demonstrations. They are two concrete failures of the required primary/secondary exception contract, with one passing control.

The exact command, exit 0 meaning the defect was reproduced, original stdout/stderr hashes and timings are in `combined-fault-command.json`. `combined-fault-results.json` retains identities, context chains, completion records, PIDs and cleanup outcomes. The original Q1 review and its frozen reproductions remain untouched.

**Remedy:** Capture the execution/start/wait exception before stream context exit can replace it. Close each owned stream through a guarded cleanup path, preserving the first failure as primary and appending later close failures to the existing secondary-error list. Keep group termination and direct-child reaping unconditional and bounded. Add focused combined-failure regressions for both cases above; retain the single-close-error control and existing successful lifecycle behavior. No production child-subreaper policy or broad `waitpid` is needed. Record this finding before assigning a correction.

## What the correction improves

- The guard now surrounds process start, record publication, waits and stream lifetime. Start-record failures no longer escape cleanup with an executing child.
- Cleanup polls/reaps only the owned direct child and signals only its process group. TERM/KILL/reap stages are bounded. No production subreaper or unrelated-child reaping was added.
- Concurrent jobs have in-memory stop events; removing start artifacts no longer loses cancellation ownership. Existing command, binary, environment and lifecycle interfaces remain intact.
- Hashing, completion, lifecycle and cleanup-error publication generally retain secondary failures separately. The remaining problem is the earlier stream-exit boundary, not a reason for a broad redesign.
- The new native tests exercise real bounded child processes. The confined observer reaps only its adopted descendant during SIGINT cleanup. The original observer's deferred-reaping zombie is correctly distinguished from an executing descendant; this review does not reopen that corrected leak on the basis of `killpg(..., 0)` alone.

## Checks actually run

| Check | Result |
| --- | --- |
| GPU unittest suite | 60 methods passed |
| Actual development CLI | Seven groups passed: 6/5/6/8/15/10/10, 60 total; no Cairn acceptance output |
| Native lifecycle coverage within those runs | 10 methods: seven existing plus three new methods covering seven fault cases; these are not additional methods |
| Independent combined-error probes | One control passes; two contract violations reproduced; all owned children reaped and groups absent |
| Ruff lint/format | All 23 GPU Python files passed |
| Native format | Three unchanged native helper files passed `clang-format --dry-run --Werror` |
| CLI help | Verifier, host capture and Intel capture passed |
| Diff whitespace | Baseline-to-candidate diff passed |
| Source/integrity | 60 reviewed files match initial hashes and candidate blobs; 711 committed inputs validated; clean source/index, no marker; frozen review, correction and SPEC manifests verified |

`checks.json` retains exact commands, exit codes, timeouts, durations and original log hashes. This re-review did not independently repeat the full 443-method Python suite, Rust checks, native compilation, GPU workload, desktop interaction, remote Mac work or full Linux preservation. The 60-method GPU suite and development gate execute the same methods through different entry points; counts are not summed into 120 distinct tests.

The original Linux native 2.0-second freshness failures remain unresolved. Task 5's Mac application pool correction and complete Intel integrated/discrete/Apple GUI reports remain pending. No BIOS change, reboot, GUI attempt or Cairn acceptance was performed. `cairn wake` still names the broad unresolved build decision; no `Realized by` or marker was changed.

## Fourteen-rule self-audit

| Rule | Review-scope result |
| --- | --- |
| 1. Understand before editing | Read the actual correction, Q1 contract, committed correction/SPEC records and preserved original quality baseline. No source edited. |
| 2. Smallest coherent change | Focused review and external artifacts only; the proposed repair is local to stream/error ownership. |
| 3. Maintainability | Assessed the single owner guard, bounded cleanup and stop-event interfaces. No unrelated redesign requested. |
| 4. Boundary contracts | Verified normal interfaces and tested original/secondary error priority; Q1-R1 requires correction. |
| 5. Deliberate errors/secrets | Identified the replaced primary error with exact exception identity and context evidence. No secrets used. |
| 6. Security | Probes target only task-owned children; unrelated sentinel remained running. |
| 7. Survivable state changes | Tested simultaneous execution/publication and close failures. Cleanup succeeds; original error preservation remains incomplete. |
| 8. Reliability | Reviewed bounded escalation, direct-child reaping, concurrency and zombie ownership. All reviewer children cleaned up. |
| 9. Track work | External todo records review, focused checks and immutable reporting with one active item during execution. |
| 10. Verify what matters | Ran 60 GPU methods, actual CLI gate, lint/format/help and three independent real-process cases. Unrun checks are explicit. |
| 11. Report honestly | CHANGES REQUIRED; original leaks are corrected, but Q1 is not fully closed. No hardware approval. |
| 12. Technical partnership | Provided a bounded repair and regression cases, preserving review-before-fix order. |
| 13. Release audit | Review delivery is complete; implementation approval is withheld until Q1-R1 is corrected and independently checked. |
| 14. Plain English | Trigger, expected/actual behavior, impact and remedy are stated directly. |

The [structured source record](gpu-acceptance-q1-quality-review.json) binds this review to its external originals. Root independently verified all 55 original file sizes and hashes before committing Q1-R1; this record precedes its correction.
