# Diagnostic publication timing implementation

This implements the [publication timing decision](../../decisions/trace-diagnostic-publication-stages-without-changing-acceptance.md)
and its [plan section](../../plans/real-system-readings.md#trace-diagnostic-publication-stages-without-changing-acceptance).
The [full stale-frame failure](native-full-stale-frame-failure.md) remains FAIL.
No performance cause, remedy, native pass or final acceptance is claimed.

## Opt-in and retained artifacts

Run the existing replay with `--trace-publication`. For example, after the
independent reviews and a current build, the coordinator can run:

```sh
rtk proxy env TMPDIR=/home/shawn/workspace2/task-manager-artifacts/tmp python3 -B scripts/system-pulse/native_replay.py --binary target/debug/system-pulse --output /home/shawn/workspace2/task-manager-artifacts/tmp/publication-timing-diagnostic --focus process --trace-publication
```

The output directory must be fresh. This command is documented, **not run**
by the implementer. The flag propagates into the private session. Direct
application use requires both `SYSTEM_PULSE_DIAGNOSTICS_PATH` and
`SYSTEM_PULSE_DIAGNOSTICS_TRACE=1`; the trace flag alone starts no writer.
Only the exact value `1` enables timing.

Each traced session writes `latest.publication-timing.json` beside its
existing `latest.json`. The harness retains that worker-produced file in
place, including failure cleanup. It writes `publication-timing-metadata.json`
before launching the application; the outer replay writes its own opt-in
marker before launching the private session. Session metadata and the final
result carry `publication_timing_instrumented`. Aggregate validation rejects
instrumented results, session metadata and retained trace markers/sidecars.
An uninstrumented legacy metadata record keeps its existing validation path.

No trace file, timing clock or history is created when tracing is disabled.
The diagnostic writer remains optional and the primary diagnostic JSON schema
remains unchanged. The harness obtains the application environment after its
existing private accessibility transport clears the old bus address.

## Stage and clock meaning

[Workspace instrumentation](../../../examples/system_pulse/src/workspace.rs)
records acceptance entry and the end of model/catalog/process preparation
before constructing the rendered diagnostic record. These are observations
of that preparation, not acknowledgements of painted or accessible content.
Same-snapshot stale publications retain the original `accepted_unix_ns`,
acceptance entry and model completion. Each publication has a new revision
and new record-construction/submission observations.

[The writer](../../../examples/system_pulse/src/diagnostics.rs) records
construction completion, submission start, slot installation before unlock,
worker dequeue, JSON conversion and serialization. Construction completion
is observed on entry to the timed submission method. Submission completion
is stamped after installing the latest slot while holding the existing lock,
so dequeue cannot precede it. [Storage](../../../examples/system_pulse/src/storage.rs)
records temporary-write start/completion and rename start/completion. The
temporary-write interval includes parent preparation, file creation and the
optional metadata observation. The writer also records serialized byte count
and, on Unix, the open temporary file's device/inode before rename.

[The timing clock](../../../examples/system_pulse/src/diagnostic_timing.rs)
is `std::time::Instant`, with nanosecond offsets from one writer-local origin.
The file identifies the application PID and a session identifier derived
from PID and the origin's wall-clock bracket. `origin_wall_before_unix_ns`
and `origin_wall_after_unix_ns` bracket that origin. Within a stable wall-clock
interval, offset `t` corresponds to the wall interval `[before + t, after + t]`.
Use that bracket and the harness's separate monotonic/wall bracket to correlate
observations. Do not directly subtract writer offsets, collector milliseconds
or Python `monotonic_ns`. Wall-clock steps or drift limit cross-clock inference;
within-writer durations use only its monotonic offsets.

## Bounds, partial evidence and errors

The existing latest-only slot and single diagnostic worker remain. UI work
adds bounded timestamps and memory bookkeeping only. The history retains at
most 64 fixed-field records in submission order. Counters distinguish submitted,
dequeued, overwritten-before-dequeue and evicted records. A completion for an
evicted revision cannot restore it to the history. Error fields retain at most
512 UTF-8 bytes, including an explicit truncation marker when needed.

The worker snapshots the history after each completed or failed primary
publication attempt and atomically replaces the optional sidecar. That history
can include later submitted entries that have not been dequeued. A missing,
null or pending stage is unobserved; it is never assigned an invented completion.
A stuck or terminated current attempt may be absent from the last sidecar.
If the worker never finishes its first attempt, no sidecar is promised.
The older sidecar and application log remain available to the harness.

The original primary error remains in the writer's existing error channel.
Timing metadata/cleanup errors are distinct record fields. Only the first
sidecar error per writer is reported to stderr. Every sidecar failure updates
the saturating counter and bounded latest-error field; a later successful
sidecar includes both. A final sidecar failure cannot publish its own failure,
and later failures are not individually logged. The retained application log
can establish the first failure, but does not enumerate all failures.
Tracing adds no thread, polling loop, filesystem work on the UI path or fsync.
The same storage implementation retains revision checks, atomic rename and
temporary cleanup on handled errors. Workspace/preset writes retain their
durable flush policy. Abrupt process termination does not promise cleanup of
an interrupted temporary write.

## Verification

Tests were added before the corresponding implementation. RED observations
included traced results/session metadata being accepted, the missing Rust
opt-in API, missing opt-in workspace timing output, unmarked error truncation
and an inherited stale accessibility bus address during final self-review.
The corrected focused timing tests pass.

- `cargo test --locked -p system-pulse --lib`: 56 passed. Covers ordered stages,
  inode/byte identity, fixed history and overwrite counts, disabled mode,
  temporary-write/rename failure, revision skipping, cleanup, bounded errors,
  primary/sidecar error precedence and retained original stale acceptance.
  The SPEC correction added a real repeated-sidecar-failure/recovery test:
  captured stderr first reproduced three reports, then passed with one report,
  all three failures retained after recovery, and unchanged primary authority.
- Full Python unittest discovery: 344 passed. Includes six new timing tests;
  existing single-read freshness, process metrics/navigation/exit and held-input
  regressions remain in that suite.
- `cargo clippy --locked -p system-pulse --all-targets -- -D warnings`: passed.
- `cargo fmt -p system-pulse -- --check`: passed.
- `ruff check scripts/system-pulse`: passed.
- Ruff format check for the four changed Python files: passed. The three
  previously identified unrelated format flags were not changed or claimed
  to pass a broad formatting check.
- `git diff --check` and this document's local links: passed.

Commands above ran through `rtk proxy` with the external artifact `TMPDIR`.
The SPEC correction reran the focused regression, full Rust app suite, strict
Clippy, Rustfmt, diff and local-link checks. Python source did not change;
its previously passing suite and lint/format checks were not repeated.
The production-rules self-audit found no remaining implementation revision
needed. Independent SPEC then QUALITY review and the coordinator's single
instrumented diagnostic remain pending. Fresh untraced full acceptance is
still required.
