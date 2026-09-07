# Task 4 Q1-R1 independent specification re-review

**SPEC PASS** for `a0ff315c54155ddbfa7a618c168bb86d0b65c008`, against previously reviewed `f1e781337d0e32f30c7800795864395dd96e2028`. Q1-R1 is closed for specification review. No new findings. The recorded quality finding at `466458647faf22537eb7c3e8cd13b972063a0ae9` precedes this correction. Separate quality review and hardware acceptance remain outstanding.

## Correction assessment

At `scripts/system-pulse/gpu_capture.py:99`, each stream starts unowned, becomes owned only after its open succeeds, and is closed independently in reverse acquisition order. The execution/start/wait exception is saved before closure can raise. Each later close failure enters the existing secondary-error list; if no earlier error exists, the first close exception becomes primary. The exact original exception object is retained.

Both stream closures finish their guarded attempts before the existing bounded process-group cleanup, direct-child reap and completion/error reporting. Partial acquisition and failed launch correctly close only acquired streams without inventing a child record. Concurrent in-memory cancellation, command/environment/hash fields, lifecycle formats and strict validators remain intact. No native/Rust/capture-caller change, broad reaping or production subreaper policy was added.

## Independent boundary verification

`independent-close-probes.py` wraps real file handles and injects errors from actual `close()`; its `__exit__` delegates to the same method. The identical script was run against a retained copy of the previous production helper and against the unmodified candidate. Eight of ten cases exposed the old error-priority defect; all ten pass on the candidate:

- Normal completion and both-close-failures control.
- Start failure with stdout close failure, and start failure with both closes plus failed completion recording.
- Actual SIGINT with both close failures and failed completion recording.
- Wait failure with both close failures and failed completion recording.
- Failed stdout open; failed stderr open plus failed stdout close; failed launch plus both close failures.
- Concurrent body failure after deleting the start record, followed by both close failures and failed completion, lifecycle and cleanup-error recording.

The checks compare exact original exception identity, retained secondary close errors, closure order, actual handle closure and process cleanup. Candidate calls finished in under 0.13 seconds. Every launched owned child was reaped and its group absent; the unrelated sentinel stayed running and was subsequently cleaned by its own observer. Normal completion retained exit zero without a capture error. Later recording errors remained separately observable, including worker errors during concurrent cancellation.

The frozen quality `combined_faults.py` is copied unchanged as `frozen-combined_faults.py`. That proxy injects only in `__exit__`; it was not replayed as proof of the candidate's actual-close boundary. Baseline and candidate results, commands and original streams are retained separately.

## Checks and source integrity

All 61 GPU unittest methods passed. The development entry point also passed seven groups: 6/5/6/8/15/10/11, totaling the same 61 methods. There are 11 native methods: ten unchanged methods and one new method with 12 close-boundary subcases. Method and subcase counts are distinct.

Affected-file Ruff lint/format, baseline-to-candidate whitespace check and verifier/host-capture/Intel-capture CLI help checks passed. Exact commands, exits, timings and original log hashes are in `checks.json`.

All 2,077 tracked candidate files matched commit blobs; all 60 initially hashed capture/mechanism files remained unchanged during review. The worktree was clean. Extracted source bytes for all ten prior native methods and the existing SIGINT helper matched the baseline. Only the shared helper and its test file changed among scripts/crates; the correction commit adds their two accompanying documents.

The frozen quality manifest and all 55 files matched SHA-256 `b3da56a35e972cf230835b2952512eee308da18aadf79cc4a00d72f1a75ec4af`. The correction post-commit manifest and all 83 files matched `fb1dd4392444c421346aa00e0624f2fd58a13a9b828a8216332e8dd7e3cf7973`. Details are retained in `final-source-integrity.json`.

## Limits and self-audit

The full 444-method Python suite, unaffected Rust/native builds and hardware trials were not independently repeated. Original Linux native 2.0-second freshness failures remain unresolved. Task 5's macOS main/dispatcher pool correction remains queued, and Intel integrated/discrete plus unlocked Apple GUI acceptance reports remain missing.

No source, index, marker, plan/decision or Cairn acceptance changes were made. `cairn wake` still names the unresolved broad build decision; no resolving identifier was supplied. The 14-rule production self-audit in `review.json` passes for this bounded specification review with these broader limits retained.

The [structured source record](gpu-acceptance-q1-r1-spec-review.json) binds this verdict to its external originals. Root independently verified all 95 original file sizes and hashes before committing this specification review.
