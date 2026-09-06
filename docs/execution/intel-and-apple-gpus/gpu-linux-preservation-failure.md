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

## Reader syscall diagnostic

A later supporting run used the exact `ece89eae` harness and the same application
binary, with the existing publication-timing diagnostic and `strace` on the
Python reader and its threads. The tracer detached children at execution; root
confirmed that the application itself had no syscall tracer. Its external
launcher retained the original harness bytes, command, seven-minute deadline
and unchanged two-second freshness limit at `gpu-task4/root-read-syscalls-20260906`.

This run failed with `native discovery deadline exceeded; incomplete tree`
during process selection. It retained no stale-frame receipt and did not
reproduce the earlier freshness failure. The held-Up, left and right observations
contained no errors, with maximum ages of 1.373, 1.577 and 1.346 seconds. Among
1,852 completed diagnostic-file `read` calls, including reconciled interleaved
calls, the maximum traced duration was 8.158 ms. The final publication ring
contained 64 published records, sequences 98–161, with maximum
acceptance-to-rename duration 465.405 ms and no overwritten pending entries or
sidecar errors. These observations describe this instrumented attempt; they
cannot explain the earlier 756.549 ms read boundary or establish an uninstrumented
accessibility regression.

The private-session wrapper exited 1 within its deadline. Cleanup terminated
application PID 2758735 with exit -15; transport PID 2758664 exited zero. Root
confirmed the wrapper, application, transport, reader and tracer PIDs and process
groups were absent. The evidence record binds 22 originals, including the trace,
launcher, failure, timing ring and cleanup. This diagnostic remains failed and
ineligible for acceptance. No performance correction is justified by it, and
the original uninstrumented failures remain unresolved.

## Garbage-collection diagnostic

The next bounded run tested whether Python garbage collection accounted for the
slow read boundary. It used an immutable copy of the `ece89eae` harness and the
same application binary, with publication tracing disabled. An external bootstrap
recorded reader GC callbacks; it changed no application, harness or freshness
logic. This reader instrumentation makes the result supporting evidence only.

It failed during inner scrolling with sequence 76 at age 2.262533388 seconds;
failure-evidence collection also rejected sequence 77 at 2.288014013 seconds.
The reads took 5.203485 and 2.868464 ms, with parsing taking 25.217928 and
27.847089 ms. Both opened-file identities still matched the pathname at the
age check. Using each check's monotonic read duration, the frames were already
approximately 2.232 and 2.257 seconds old when reading began. No GC event
overlapped either read. All 513 recorded collections are retained, without
callback errors or evictions; the longest collection lasted 28.514036 ms.

This reproduction does not support the GC hypothesis. It establishes that a
long read is not necessary for a freshness failure, but does not explain the
earlier 756.549 ms read or identify which application/publication stage delayed
the newer records. No source correction follows from these observations alone.

Originals remain at `gpu-task4/root-reader-gc-20260906`; the evidence record binds
17 files, including the immutable harness manifest, instrumentation, both stale
receipts and GC events. The wrapper exited 1 after 79.675 seconds, within its
420-second deadline. Failure cleanup terminated the app with exit -15; transport
exited zero. Root confirmed the wrapper, reader, app and transport PIDs and
process groups were absent. All previous failures remain retained and unresolved.


## Publication and OS-wait diagnostic

A subsequent bounded, instrumented focused replay passed in 159.79 seconds.
It used the unchanged application binary and immutable `ece89eae` harness, with
existing publication tracing and an external 100 ms OS observer. No stale frame
was reproduced. The final 64 writer records (sequences 96–159) had a maximum
acceptance-to-rename time of 276.740 ms, no overwritten submissions and no sidecar
errors. Global I/O pressure remained high (some `avg10` 40.01–48.48), which by
itself does not identify the cause of the earlier failures. Sampled thread waits
are observations, not continuous blocking durations.

The observer retained 1,541 samples without errors and joined. Its thread-name
filter included additional application threads; its maximum sample cost was
14.294 ms. The launcher also used the design repository as its working directory,
so the session's `source_commit` is not valid implementation-source attribution.
That mistake remains in the original record and is qualified separately; the
immutable harness manifest and verified application binary hash identify this
diagnostic. Neither this run nor its metadata can serve as acceptance evidence.

Root verified all 167 retained originals, lifecycle/stream hashes, and absence of
the application, transport and owned wrapper processes/groups. The external
`gpu-task4/root-publication-os-20260906/root-verification.json` holds those hashes,
OS observations, timing maxima and source qualification; its own hash is retained
in the [structured record](gpu-linux-preservation-failure.json). The earlier
uninstrumented failures remain failed. This diagnostic justifies no source fix.

## Untraced application with OS observation

The next diagnostic disabled internal publication tracing and restricted the
external 100 ms observer to the identified application main, collector and
diagnostic-writer threads. It used the same historical application binary and
immutable harness, launched from the implementation directory. This fixes the
previous diagnostic's working-directory attribution error; the current HEAD
still does not establish the historical binary's source provenance.

The run failed after 151.951 seconds during process navigation, with `native
discovery deadline exceeded; incomplete tree`. It retained no stale-frame
receipt. Held-Up, left and right checks recorded 41, 64 and 59 observations,
without errors; maximum accepted ages were 1.721, 1.462 and 1.918 seconds.

The observer joined with 1,508 samples, no observer errors and a maximum sample
cost of 7.193 ms. The collector and writer each disappeared in the final cleanup
sample. The longest sequence of writer samples in `rq_qos_wait` comprised eight
observations spanning 705.854 ms. These samples do not prove continuous blocking
between observations or establish the cause of another run's stale frame.

The final navigation batch exhausted its unchanged eight-second deadline while
the overall navigation deadline remained in the future. Intermediate native
scans observed the expected selected process, but the required final proof did
not finish. Three panel rediscoveries in that batch consumed 1.196, 1.940 and
2.007 seconds; the last was aborted at the deadline. The record does not yet
establish whether this is an application or harness defect.

Originals remain at `gpu-task5/linux-untraced-os-20260906`. Root verified all 184
manifest entries and the application, transport and wrapper lifecycle records;
all three processes and their groups were absent. A separate, reproducible
analysis at `gpu-task5/linux-untraced-os-analysis-20260906` reverified that manifest
and preserved the sampled waits and navigation observations. The structured
record binds both. This supporting diagnostic remains failed and does not clear
either original freshness failure. No acceptance limit or production behavior
has changed in response to it.

## Writer syscall diagnostic and tracing limits

A later diagnostic traced descendant write, rename and flush calls, with internal
publication timing disabled. Two setup attempts were retained separately. The
first was canceled when strace reported that the syscall-count limit disabled
its requested seccomp filtering. The second failed before session metadata:
the diagnostic's inherited file-size limit terminated the required source
identification helper with `SIGXFSZ`. These are diagnostic configuration failures,
not application performance evidence. Root verified cleanup and retained 140 and
139 original files respectively.

The third attempt removed both incompatible limits and guarded only the trace
output externally. It reproduced stale sequence 15, revision 37 during metric
comparison, at ages 2.029702256 and 2.357475496 seconds. It retained 76 completed
writer syscalls, reconciling interleaved unfinished/resumed calls. Maximum write
duration was 3.101 ms; maximum rename duration was 248.508 ms, well before the
rejected observations. No flush call appeared on the writer thread.

This run has a material tracing limitation: the collector was observed in a
ptrace stop in 113 of its 297 complete samples. Its last two retained collections
took 1.349 and 1.242 seconds, and the service skipped missed sampling slots.
Tracing therefore changed the collection timing. The reproduced stale frame
cannot establish the cause of the earlier uninstrumented failures, and does not
justify a storage or sampling correction. Any further syscall investigation
needs to isolate the writer from the collector and UI threads.

The third run remains at `gpu-task5/linux-writer-syscalls-guarded-20260906`;
the earlier configuration attempts use the adjacent `linux-writer-syscalls-20260906`
and `linux-writer-syscalls-filtered-20260906` directories. After the native replay
failed, app and transport cleanup completed. Root then stopped the tracer still
following private-session descendants, preserving that distinction in its
lifecycle record. All 290 traced process/thread IDs and the application,
transport and tracer process groups were absent. The observer joined without
errors. The structured record binds the reproducible analysis and all three
attempts; no original failed result has been replaced.

## Writer-only syscall diagnostic

The next diagnostic attached strace only to the owned diagnostic-writer thread.
A bounded control first proved ancestor attachment and cleanup without changing
OS tracing permissions. In the application run, every complete main-thread
sample (1,756) and collector sample (1,755) had `TracerPid: 0`; all 1,755 complete
writer samples identified the owned tracer. The observer retained 1,774 samples
without errors, with maximum sample cost 6.050 ms. This addresses the previous
whole-process tracer's collector interference, but remains instrumentation.

The native replay failed after 178.619 seconds during process navigation. It
retained no stale-frame receipt. Held-Up, left and right checks had 54, 63 and
50 observations, no errors, and maximum accepted ages of 1.516, 1.406 and
1.481 seconds. The trace contained 176 complete writes and 176 complete renames,
with no unfinished/resumed calls left unresolved. Maximum write duration was
3.195 ms; maximum rename duration was 81.304 ms. The longest interval from
acceptance to write start was 258.039 ms. That interval includes construction,
queueing, serialization and opening the file; it is not a pure CPU or storage
measurement. This attempt does not establish the cause of either uninstrumented
freshness failure or justify a performance correction.

The navigation failure is more specific than the terminal discovery error.
After a partial scan encountered a defunct node, repeated complete scans found
nine instantiated rows and no selected row. Their mapped span remained
1221–1229; the frozen expected endpoint index was 1219. No recovery wheel or panel
rediscovery occurred in that batch. The unchanged eight-second batch deadline
expired with approximately 96 seconds remaining in the overall navigation
budget. These observations warrant source investigation; they do not yet prove
an application defect or justify loosening recovery eligibility.

Originals remain at `gpu-task5/linux-writer-only-20260906`, with the control at
`gpu-task5/writer-only-tracer/control-01`. Reproducible analysis at
`gpu-task5/linux-writer-only-analysis-20260906` binds 204 files, validates the
harness/helper manifests and lifecycle stream hashes, and confirms absence of
all 27 recorded process/thread IDs and their process groups across both runs.
Application failure cleanup exited -15; transport and tracer exited zero.
The monitor reaped its descendants, terminating two remaining private-session
children, and recorded no remaining children. These are cleanup outcomes, not
an orderly application-close pass. The historical application binary and
harness remain identified by their original byte hashes; the launch-directory
HEAD is explicitly qualified and does not establish current-source acceptance.
All earlier failures remain retained and unresolved.

## Post-correction aggregate budget failure

After the process-reveal correction passed both source reviews, the next full
preservation attempt stopped before native replay. Its expanded 444-test Python
suite exceeded the aggregate runner's 30-second deadline. The retained Task 4
successful suite had taken 34.043 seconds; a new unchanged-suite timing diagnostic
passed all 444 tests in 34.240 seconds. The [recorded finding](linux-python-budget-finding.md)
requires correcting only the complete suite's execution budget while preserving
mandatory coverage and every native freshness, navigation and comparison bound.
The failed attempt and timing diagnostic remain separately classified; neither
supplies a native result or resolves the original freshness failures.

## External supervisor correction after the budget fix

The fresh run `gpu-task5/linux-preservation-61e8ceef-20260906` completed 444 Python tests in 38.016 seconds, within the corrected deadline, with one failure: `test_owned_process_cleans_descendants_after_leader_exits`. Rust, host and native stages were not reached. Root retained all 12 original files and verified the four owned process IDs/groups absent in the adjacent `-root-verification.json`.

The cause was root's external task supervisor. It acted as a child subreaper but waited until the complete command exited to reap adopted children. A terminated orphan therefore retained its zombie process group while the unchanged test checked cleanup. The isolated existing test reproduced the failure in 4.049 seconds under the original helper. Root's external `preservation-owner-reap.py` reaps adopted children during execution while leaving the direct command to Popen; the same test then passed in 0.053 seconds. Both owners and all recorded children/groups were absent afterward. `gpu-task5/owner-reap-verification.json` retains commands, streams and hashes. No repository source, test, freshness limit or acceptance condition changed. The original helper and failed runs remain intact. Fresh full preservation is still required.
