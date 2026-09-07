# Task 4 Q1-R1 independent quality re-review

**QUALITY PASS / APPROVED** for candidate `a0ff315c54155ddbfa7a618c168bb86d0b65c008`, against previously reviewed `f1e781337d0e32f30c7800795864395dd96e2028`. **Q1 and Q1-R1 are closed.** No Critical, Important or Minor actionable findings remain from this review. The original complete Task 4 quality audit at `50ea29d6` remains the baseline for unchanged code.

This approves the scoped Task 4 acceptance helper implementation. It does not establish native GPU hardware acceptance, resolve Task 5 or complete the GPU commitment. The code stayed frozen throughout this read-only review; current documentation HEAD is `882c5e877cfcb1d30ae0e2e661385f7bbbf2ac39`.

## Why Q1-R1 is closed

`scripts/system-pulse/gpu_capture.py:99` initializes both stream owners explicitly. Successful opens assign ownership one at a time. The execution/start/wait exception is captured at line 133 before either stream closes. The finalizer at line 135 attempts stderr then stdout independently; each exception is retained without preventing the other close. A prior exception remains the exact primary object. With no prior exception, the first close error becomes primary and later errors are secondary.

The existing process-group cleanup, direct-child reap, log hashing and completion reporting still run after the guarded close attempts. Partial acquisition and failed launch close acquired streams without inventing a child or completion record. In-memory concurrent cancellation and the bounded group cleanup are unchanged. No new production abstraction, dependency, unrelated reaping or subreaper policy was introduced. Commands, environment, binary/hash fields and normal lifecycle records remain compatible with the unchanged capture callers and strict validators.

The correction is local and easy to follow: explicit resource acquisition, saved execution error, separately guarded closures, then existing process cleanup and reporting. It addresses the recorded boundary without broadening the architecture.

## Independent actual-close probes

`actual_close_probes.py` retains real file handles and real bounded child processes. Its proxy injects from actual `close()` and delegates `__exit__` to the same method, so either cleanup style encounters the same fault. The identical probe script ran against an exact retained copy of the previous helper and the unmodified candidate.

| Case | Candidate result |
| --- | --- |
| Normal completion | Exit-zero record, no capture error; both handles closed |
| Both close errors after successful work | First close error stays primary; second stays secondary |
| Start-record failure plus both close errors | Exact start error preserved; both close errors retained separately |
| Actual SIGINT plus both close errors and failed completion write | Exact `KeyboardInterrupt` preserved; all three later errors retained |
| Failed stderr acquisition plus stdout close error | Acquisition error preserved; only acquired stdout closed; no child invented |
| Both close errors plus log-hash failure | First close error preserved; later close and hashing failures remain secondary |

The previous helper violates the contract in five of these six cases. The candidate passes all six. The same assertions check exception identity, secondary-message order, actual handle closure, reverse acquisition order, normal records, direct-child reaping and group absence. Candidate calls finished in less than 0.13 seconds. An unrelated sentinel remained alive during each run, then its own reviewer cleaned and reaped it; both sentinel groups are absent.

Original scripts, commands, stdout/stderr and structured results are retained in `actual-close-commands.json`, `previous-probe-results.json` and `candidate-probe-results.json`. The commands exit zero because their assertions require the previous violations and the candidate's complete pass. The original frozen `combined_faults.py` was not modified or treated as proof of actual-close behavior.

## Checks actually run

| Check | Result |
| --- | --- |
| GPU unittest suite | 61 methods passed |
| Actual development entry point | Seven groups passed: 6/5/6/8/15/10/11, the same 61 methods; no Cairn acceptance lines |
| Native lifecycle coverage in those runs | 11 methods: ten prior methods plus one new method with 12 close-boundary subcases |
| Independent actual-close probes | Six previous/candidate comparisons; five previous violations, zero candidate violations |
| Ruff lint/format | All 23 GPU Python files passed |
| Native format | Three unchanged native helper sources passed `clang-format --dry-run --Werror` |
| CLI help | Verifier, host capture and Intel capture entry points passed |
| Diff whitespace | Previous-to-candidate diff passed |
| Final integrity | All 60 reviewed source/mechanism files match initial hashes and candidate blobs; 711 committed inputs validated; clean source/index and no marker |

`checks.json` records exact commands, exit codes, timeouts, durations and original log sizes/hashes. `source-after.json` also records exact preservation of all ten previous native test methods, the existing SIGINT helper, `CaptureChildren`, `clean_group` and `retain_errors`, plus verification of the original quality, Q1-R1 quality, correction and SPEC manifests. The reviewed source change is confined to `gpu_capture.py` and `test_gpu_native.py`.

This re-review did not independently repeat the full 444-method Python suite, unaffected Rust checks, native compilation, desktop operations, remote Mac commands, native GPU work, full Linux preservation or Cairn acceptance. The focused GPU suite includes the prior Q1 real-process regressions. The confined test observer's adopted-zombie distinction remains settled; no production broad-reaping change is required.

## Remaining completion boundaries

The original Linux native 2.0-second freshness failures remain failed and unresolved. Task 5's Mac application pool correction is still queued. Actual Intel integrated/discrete and unlocked Apple GUI reports are missing. No BIOS/reboot/unlock action or hardware claim was made. `cairn wake` still names the unresolved broad build decision; no resolving identifier or acceptance evidence was written.

## Fourteen-rule production self-audit

| Rule | Review-scope result |
| --- | --- |
| 1. Understand before editing | Read actual correction, prior finding and committed correction/SPEC records. No source edited. |
| 2. Smallest coherent change | Assessed the local stream/error ownership repair; review artifacts are external only. |
| 3. Maintainability | Explicit stream ownership and reverse closure reuse the existing error list and cleanup path. No unnecessary abstraction or caller redesign. |
| 4. Boundary contracts | Verified exact first-error priority, independent close attempts, partial acquisition and normal records. |
| 5. Deliberate errors/secrets | Actual-close/SIGINT/reporting probes preserve primary objects and retain secondary failures. No secrets used. |
| 6. Security | Only task-owned groups were affected; unrelated sentinels survived and were later cleaned by their own reviewer. |
| 7. Survivable state | Simultaneous start/close, cancellation/close/reporting and acquisition/close faults pass with ownership retained. |
| 8. Reliability | Process cleanup remains bounded and unchanged; all probe children were reaped and groups absent. |
| 9. Track work | External todo tracked review, checks and immutable reporting with one active step during execution. |
| 10. Verify what matters | Ran 61 GPU methods, the actual seven-group CLI, lint/format/help and six independent paired probes. Unrun checks are explicit. |
| 11. Honest reporting | Task 4 QUALITY PASS only; native hardware and Task 5 limits remain. Method/subcase/repeated-run counts stay distinct. |
| 12. Technical partnership | Closed the recorded local defects on evidence; no unnecessary scope expansion or approval request. |
| 13. Release self-audit | All 14 rules assessed. No known actionable Task 4 quality finding remains after these corrections; broader commitment approval is not claimed. |
| 14. Plain English | The record states the correction, proof and remaining boundaries directly. |

The [structured source record](gpu-acceptance-quality-pass.json) binds this verdict to its external originals. Root independently verified all 87 original file sizes and hashes before closing Task 4. The implementation plan now tracks Task 5 as the single active task.
