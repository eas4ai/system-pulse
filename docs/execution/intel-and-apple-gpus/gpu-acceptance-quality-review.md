# Task 4 independent code quality review

**CHANGES REQUIRED** for implementation `50ea29d6653d42ceafc8b3f246b9a18ae721b612`, reviewed against `fa28a5b34bb5732d910e642aefe3f18fcd6bc455`. One Important finding remains. There are no Critical or Minor actionable findings from this review.

This review covers the complete Task 4 GPU acceptance mechanism, Python capture/replay helpers, native Intel and Apple helpers, fixtures and verifier tests. Documentation HEAD `f4bfdf3b440e2805195e3bc855515d2d97a40106` contains the same reviewed code. Source, index, marker, decisions and Cairn evidence remained unchanged. This is a code quality verdict, not native hardware acceptance or commitment completion.

## Q1 — Important: cleanup does not cover the complete owned-process lifetime

**Location:** `scripts/system-pulse/gpu_capture.py:70`, `:86` and `:96`, in `owned_process`; caller consequences include `CaptureChildren.start`/`finish` and the synchronous build/metadata/action calls in `gpu_host_capture.py`.

The function starts a new process group, then writes the start record before entering its `try/finally`. If that write raises, no timeout or cleanup runs for the child that has already started. Later, its `finally` protects only the direct child's wait. `clean_group` runs after the `try/finally`, so an exception such as `KeyboardInterrupt` escapes before descendant cleanup and completion recording.

Two independent reproductions demonstrate the defect in the unchanged implementation:

1. `reproduce_cleanup.py` launches a real three-second Python child through `owned_process`, with a 50 ms deadline. Only `Path.write_text` for the start record is fault-injected to raise `ENOSPC`; process creation and ownership logic are real. The call raises immediately, but PID **3770832** and its process group are still alive 200 ms later, four times the requested timeout. No completion record exists. The reviewer explicitly killed and reaped it; the group is absent. Original result: `cleanup-reproduction.json`.
2. `reproduce_interrupt.py` uses no mocked process or wait functions. A real child starts a three-second descendant that ignores SIGTERM. After that descendant publishes readiness, the reviewer sends an actual SIGINT to its own Python test process while `owned_process` waits. The direct child **3795426** is terminated/reaped, but descendant **3795427** and its process group survive the propagated `KeyboardInterrupt`; no completion record exists. A Linux subreaper confined to this short-lived reviewer process lets the reviewer kill and reap that orphan explicitly. Final group absence is verified. Original result and command/logs: `interrupt-reproduction.json`, `interrupt-command.json`, `interrupt.stdout`, `interrupt.stderr`.

**Why it matters:** Native capture and build work can survive a failed capture or cancellation after its only owner has returned. The first path also loses the published PID used by `CaptureChildren` to stop work. This violates Task 4's bounded process ownership and cleanup requirement and undermines GPU-008 cleanup evidence. The verifier does not falsely accept these incomplete records; the defect is the capture runner leaving work alive on failure. The existing normal-timeout, normal-descendant-exit and concurrent-capture tests all pass because they do not exercise these exceptional ownership paths.

**Remedy:** Establish an exception-safe ownership guard immediately after successful `Popen`. Put start-record publication, waiting, direct-child termination/reaping and process-group cleanup under that guard. Cleanup must run on every exceptional exit, including recording failures and interruption, with bounded escalation and process-exit races handled. Preserve the original failure while reporting any cleanup/recording failure separately; a writable start artifact must not be required to recover the owned PID. Add focused regressions with real bounded children for both reproduced cases. Keep the source frozen until this finding is committed and corrective ownership is assigned.

## Strengths and reviewed boundaries

- The aggregate reuses the existing command runner and preservation validators. Each of seven mandatory verifier groups must exist and run nonempty tests. Development mode emits no Cairn acceptance result.
- Report ingestion separates source/artifact binding, original process/command/lifecycle reconciliation, arithmetic, native display actions and OS/provider provenance. Full-ingestion Intel/Apple fixtures reach the unmodified verifier and explicitly state that they are synthetic.
- Independent raw replay compares contributing memory operands, monotonic counter brackets, actual elapsed time and physical identity before checking displayed values. Native action checks bind selected controls and saved state to original helper commands and PIDs.
- Native helper code generally keeps resources local: fixed Vulkan allocation and serial completed fences; serial Metal work with inner autorelease pools; explicit Objective-C/Core Foundation release paths; bounded DRM buffers, sysfs reads and native enumerations. The cross-platform subprocess guard is the exception identified in Q1.
- The implementation and review records disclose unsupported hardware, failed preservation and locked-desktop limits. This review found no concrete reason for a broad architectural rewrite or unrelated production Rust change.

## Checks actually run

`checks.json` retains exact commands, exit codes, timeouts, durations, original stdout/stderr sizes and SHA-256 values. Commands ran from the application worktree through the external `run_checks.py` runner, invoked with `rtk proxy`; logs and caches are outside the checkout.

| Check | Result |
| --- | --- |
| All Python acceptance tests (`test_*.py`) | 440 passed; exit 0 |
| Actual GPU development CLI | Seven groups passed: 6/5/6/8/15/10/7, 57 total; exit 0; no Cairn acceptance output |
| Ruff lint and format | All 23 GPU Python files passed |
| Native format | Both Objective-C sources and Vulkan C helper passed `clang-format --dry-run --Werror` |
| CLI help | Verifier, host capture and Intel capture entry points passed |
| Diff whitespace | Complete implementation range passed `git diff --check` |
| Start-record failure injection | Reproduced surviving owned child beyond deadline; reviewer cleanup verified |
| Actual SIGINT during child wait | Reproduced surviving descendant after interruption; reviewer cleanup verified |
| Final source integrity | All 60 reviewed files match initial hashes and candidate commit; 711 committed input bindings validated; clean worktree and no marker |

`candidate-before.json` and `candidate-after.json` retain source hashes and final committed bindings. `artifact-manifest.json` binds the external review artifacts; `artifact-manifest.sha256` binds that manifest. The manifest intentionally excludes itself and its checksum file.

I did not run native GPU work, desktop interaction, remote Mac commands, native compilation, Rust tests, full Linux preservation or Cairn acceptance. Native helper compilation/readiness in prior records was reviewed as context, not reported as a new execution. The retained Linux freshness failures and separate Task 5 Mac application pool correction remain unresolved. Intel integrated/discrete and Apple GUI hardware evidence remains incomplete. The possible local UHD770 requires actual enumeration after any separately authorized BIOS change; no such evidence is inferred here.

## Fourteen-rule production self-audit

| Rule | Review-scope result |
| --- | --- |
| 1. Understand before editing | Read the repository agreement, imports, glossary, overview, roadmap, commitment, GPU contract/acceptance matrix, decisions, implementation and prior reviews; mapped the complete Task 4 path. No source edited. |
| 2. Smallest coherent change | Review-only artifacts outside the checkout. No refactor or unrelated correction proposed. |
| 3. Next maintainer | Assessed responsibility boundaries, replay contracts and native ownership. Q1 identifies a concrete ownership gap and a local remedy. |
| 4. Boundary contracts | Reviewed paths, JSON/size bounds, inputs, formulas, identities, commands and error transitions. No compatibility change made. |
| 5. Deliberate errors/secrets | Q1 demonstrates a real error-propagation/cleanup defect. Evidence contains only task-owned local PIDs, paths and synthetic data; no credentials. |
| 6. Security | Reviewed artifact traversal/hash checks, command construction and owned process groups. Fault tests use only bounded local children. |
| 7. Survivable state changes | Tested partial failure during start-record publication and actual interruption. Both expose Q1; this implementation needs revision. |
| 8. Performance/reliability | Reviewed allocation, enumeration, stream, thread and process bounds. Q1 prevents approval of process cleanup. Reviewer-created processes were reaped and absent. |
| 9. Multi-step tracking | External `todo.json` tracked contract/mapping, verification, and final recording with exactly one item in progress during the work. Completion refers to this review only. |
| 10. Meaningful verification | Ran the complete Python suite, actual CLI group gate, lint/format/help checks, and real process fault tests. Unrun native/Rust checks are stated explicitly. |
| 11. Honest reporting | CHANGES REQUIRED. Passing standard tests do not clear Q1 or any existing hardware/preservation boundary. |
| 12. Technical partnership | Recorded a concrete local repair and required regressions for the orchestrator to assign after committing the finding. No unnecessary permission request or scope expansion. |
| 13. Release self-audit | The review is complete and evidenced; the implementation is not approved. Source remains frozen so the finding can be recorded before correction. |
| 14. Simple technical English | Findings state the trigger, observed behavior, consequence and repair directly. |

The [structured source record](gpu-acceptance-quality-review.json) binds this review to its external originals. Root independently verified all 51 file sizes and hashes before committing Q1; no correction precedes this record.
