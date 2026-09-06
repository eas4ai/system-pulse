# Linux preservation: native freshness failure

The Task 4 full Linux preservation run finished **FAIL**. The native replay
rejected an accepted frame older than the unchanged two-second limit during
held input. This remains an unresolved GPU-007 preservation result; passing
helper tests or a later diagnostic cannot clear it.

Originals are retained outside the checkout at
`/home/shawn/workspace2/task-manager-artifacts/gpu-task4/preservation-20260906`.
The [evidence record](gpu-linux-preservation-failure.json) binds the original
failure, input observations, cleanup and completed check logs by size and hash.
The failed run has not been overwritten or reclassified.

This was development verification while Task 4 helper changes were uncommitted,
not a Cairn receipt. Session metadata records HEAD `fa28a5b3` and matching
application-file/running-executable hashes. The retained harness manifest
identifies the actual Python sources used by the native replay.

## What ran

All 847 automated tests passed: 425 Python, 205 base dock, 13 resizable,
19 component dock, 24 model, 63 application, 96 collector and 2 AT-SPI tests.
Source guard, formatting, strict Clippy, the application/collector build and
independent Linux host comparisons also passed. Root independently checked
all 16 completed-step log hashes and parsed the nonempty test summaries.

Native launch, metric comparisons, collapse, charts and inner scrolling passed.
Held input then failed with `input starved fresh publication`; later native
cases did not complete. This error names the failed assertion, not a proven
cause in the application's input or collection pipeline.

## Retained observation

The first observation in `native/session-01/held-up-25hz.json` contains sequence
69 at age 1.943904796 seconds. The next observation rejects a frame at 2.026
seconds. Later observations contain advancing sequences through 75. These
records establish a freshness failure near input startup; they do not establish
continuous publication starvation, host contention or a defect in a particular
collector. No performance correction follows from these observations alone.

Failure cleanup terminated task-owned application PID 2151647 with exit -15
and confirmed its absence. Private transport PID 2151615 exited zero and was
absent without a forced kill. This was failure cleanup, not an orderly native
application-close pass.

## Next verification

The subsequent focused run used the existing opt-in
[publication timing diagnostic](../real-system-readings/diagnostic-publication-timing-implementation.md)
at `gpu-task4/publication-diagnostic-20260906`. It passed the focused process
replay, with 54 held-Up observations, no observation errors and a maximum
accepted age of 1.289118335 seconds. It did not reproduce the original failure.

The final timing ring retained 64 published records, sequences 123–186, with
no overwritten pending entries or sidecar errors. Within those records,
maximum acceptance-to-rename time was 252.928856 ms, JSON conversion
104.372965 ms, serialization 130.001714 ms and queue time 0.950605 ms.
These are durations within the writer's clock. These later records do not
establish the cause of the earlier failed run. Application PID 2174810 and
transport PID 2174803 both exited zero and were confirmed absent.

The instrumented result is ineligible for acceptance. Preserve both attempts
and the two-second freshness limit. Record any demonstrated source finding
before correcting it, then obtain a fresh uninstrumented full preservation
result. No source performance change was justified by this diagnostic.

Task 4's mechanism review and the pending
[Mac lifetime correction](../../decisions/drain-autoreleased-objects-at-mac-application-and-dispatcher-boundaries.md)
do not resolve this Linux result. The [implementation plan](../../plans/intel-and-apple-gpus.md)
keeps complete preservation and native hardware evidence in Task 5.

## Uninstrumented focused follow-up

Root subsequently ran the existing focused process replay without publication
tracing, using the same application binary hash as the first failed run.
Originals are retained at `gpu-task4/root-untraced-process-20260906`. It failed
during process navigation at an accepted frame age of 2.170598230 seconds,
against the unchanged two-second limit. The earlier held-Up check retained
53 observations without errors, with maximum age 1.588976673 seconds. The
freshness failure therefore recurred after passing the earlier failure point.

The retained stale receipt identifies snapshot sequence 159, render revision
158 and the exact single-read observation. Reading took 756.548678 ms; parsing
took 18.923204 ms. The opened file had device/inode `66318/222695170`, while
the pathname check before the age decision saw `66318/222695171`. This proves
that the pathname referred to a different file by the check. It does not
establish that replacement's contents or freshness, why the read took that
long, or a cause in the application. Do not reread to erase the rejected
observation or change its freshness limit.

The outer replay PID 2285479 exited 1 within its 420-second deadline and was
reaped with no surviving process group. Failure cleanup terminated application
PID 2285620 with exit -15 and confirmed its absence; private transport PID
2285609 exited zero and was absent. No root-owned native job remains from this
attempt. Both uninstrumented failures remain failed. The observed read boundary
is a lead for further diagnosis, not a demonstrated performance correction.
