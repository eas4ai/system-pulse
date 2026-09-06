# Trace diagnostic publication stages without changing acceptance

Level: Judged
Decided by: agent
Rests on: LIVE-013 requires retained explanations for verification differences. Full capture 78w90voc retained a 2.197-second old-inode frame read, with short read/parse and normally spaced acceptance samples; stage timings downstream of acceptance are absent.
Would be wrong if: Tracing changes freshness or deadlines, unbounded state or UI filesystem work is introduced, primary errors are hidden, traced runs count as final acceptance, or an unmeasured cause is asserted.
History: The prior read-identity instrumentation now distinguishes atomic replacement from parser pause. Transient diagnostics already omit fsync. This extends observation to publication stages without changing acceptance or choosing an unsupported remedy.

## Decision

Extend the existing optional diagnostic writer with an explicitly enabled, fixed-capacity publication timing history (maximum 64 bounded records). The full 78w90voc capture proves atomic replacement during a short old-file read; it does not identify downstream publication latency. Preserve that FAIL and every freshness/identity/deadline requirement. Measure acceptance/model processing, rendered record construction, submission, worker dequeue, JSON conversion/serialization, temporary write and rename start/completion. Correlate original acceptance time, application/session identity, sequence/revision, byte count, temporary device/inode and documented monotonic clock anchors. Retain overwritten counts and partial stage failures without inferring an unobserved completion.

UI instrumentation adds only bounded timestamp and memory bookkeeping. Use the existing worker for optional sidecar publication; add no UI filesystem I/O, new worker, flush, polling loop or unbounded log. Preserve latest-only delivery, revision ordering, atomic diagnostic replacement, durable configuration saves and cleanup. Trace errors remain distinct from primary errors and cannot replace or hide them. Disabled instrumentation preserves existing behavior and adds no trace file. Bound individual fields as well as record count.

Retain opt-in trace artifacts and instrumented metadata in the existing native harness. Traced runs are diagnostic and must not count as final aggregate acceptance. Preserve Native.frame single-read fail-fast freshness/PID behavior and all mandatory metric/navigation/exit proofs. Test timing order, bounded retention and overwrite accounting, disabled mode, error precedence/partial failures, cleanup and rejection of instrumented acceptance. Run focused/full relevant checks and independent SPEC then QUALITY reviews. Then run one traced diagnostic; record any evidence-supported performance remedy as separate work before implementation. Fresh untraced full acceptance remains required. Existing syscall tracing is available only if timing leaves a syscall ambiguity; do not claim a cause from an unobserved stage.

## Realized by

Implemented in `c69a0598ff4b16b3bd6d77a04ae212ab537bd234`, with bounded
sidecar reporting corrected in `f7c45638ba5367c620eae14bf2ceec00ae75d40e`.
Independent SPEC and QUALITY reviews passed; see the
[implementation](../execution/real-system-readings/diagnostic-publication-timing-implementation.md)
and [review record](../execution/real-system-readings/diagnostic-publication-timing-review.md).
The instrumented diagnostic and fresh untraced full acceptance remain pending.
