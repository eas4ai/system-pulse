# Mac collector optimization

Status: implemented; Linux and native Mac preservation passed; native comparison completed below the required reduction.

The first change retains the Apple Silicon temperature discovery connection.
Every sample still enumerates sensors, removes absent entries and requests
current temperatures. An empty inventory or missing reading causes a new
connection on the next sample. Controlled tests cover changing readings,
discovery, removal, failed reads, reconnection and repeated empty discovery.

The developer then approved actual filesystem used/total bytes, matching Linux,
instead of macOS's estimate that includes potentially reclaimable space.
Mac volume discovery and I/O still use new sysinfo objects each sample. Capacity
uses a separate fresh `statvfs` query with checked arithmetic, raw operands,
its actual query window and explicit unsuccessful readings. No disk inventory
or capacity value is cached. Other portable capacity backends are unchanged.

## Exploratory evidence

These isolated ten-iteration probes locate cost. They are not whole-application
comparisons and do not establish the agreed 50 percent reduction.

| Probe | CPU milliseconds per operation |
| --- | ---: |
| Recreate temperature discovery | 21.809 |
| Retain temperature connection and refresh discovery/readings | 7.534 |
| Recreate account list | 1.444 |
| Recreate disks with all fields | 57.936 |
| Discover disks without capacity or I/O | 1.911 |
| Refresh retained disk I/O | 7.306 |
| Fresh Foundation capacity URL queries | 50.754 |
| Explicitly clear capacity property caches before reading | 51.381 |

Raw results are retained in [probes](probes/). Skipping disk-type queries and
delaying capacity queries until after filtering gave little improvement.
Retained capacity reads appeared extremely cheap, but Core Foundation caches
properties; keeping those values would not prove freshness. Clearing caches
kept the original cost. This led to the developer-approved capacity definition,
not a slower query interval. Account caching remains unnecessary unless the
whole-application comparison shows more work is needed.

## Verification state

The optimized native release at
`8f480a4fe1605ad496e41b25d670d41c555e10c7` has SHA-256
`30fbb2ed3b576b280ce28c3a7eadd58988dd4aaac374529840010762f22684dd`.
Native application/model/collector tests, strict Clippy and the locked release
build passed. The [build record](evidence/native-build.json) retains their exits
and remote logs. The unchanged reference binary remains separately preserved.

The [invalid native attempts](evidence/invalid/) contain no scored observations.
Preflight initially mistook the OS's idle launchd-owned spindump service for an
active profiler, then encountered unsupported accessibility resizing and
missing screen content. A native session query confirmed the Mac was locked.
The revised helper rejects locked sessions, checks actual WindowServer bounds,
and resizes through native input. It still needs unlocked-session verification.
No invalid attempt is counted toward the required three paired observations.

The preliminary recon's 1280-by-880 label was a nominal intended size, not
independent native size evidence. Formal measurements require observed
1280-by-880 WindowServer bounds before and after each visible run. The verifier
also requires binary/source identity, one-second settings, warmup, elapsed time,
process survival, mode, paired order, and valid CPU counters. Seven automated
comparison tests pass, including negative cases. Cairn has recorded PERF-006
passing; PERF-001 through PERF-005 remain unverified.

Linux preservation passed 1,014 automated tests, formatting, strict Clippy,
the build, independent host comparisons and the complete tabbed native replay.
Ten input-focus tests also passed. The first application aggregate then stopped
at packaging because the new evidence files were still uncommitted. Its retained
output is `task-manager-artifacts/macos-performance/linux-application-20260908T001028Z`.
That attempt is not a package pass.

The clean run at `linux-application-20260908T001957Z` passed preservation and
input focus again, then found the pinned notice generator outside `PATH`.
The existing continuation procedure verified the unchanged source, passed
step logs and all preservation artifact hashes before executing the unchanged
remaining application-gate statements with cargo-about 0.9.2. Packaging, native
packaged product replay, tray/history/reopen checks, and isolated
installation/removal all passed. The [passing manifest](evidence/linux-application-manifest.json)
records the continuation and retained steps. Both original failed manifests
remain in [invalid](evidence/invalid/); neither was overwritten or relabeled.

The Mac session still reported locked after this Linux work. Native input
permission is available, and the current native helpers compile and pass their
comparison tests. Completing the commitment now requires an unlocked Mac for
the twelve scored observations and the separate native preservation checks.
No 50 percent improvement, final commitment review, publication or optimized
Mac installation is claimed.

## Unlocked retry after the Mac update

On 2026-09-08 the developer confirmed an update and reboot and requested another
attempt. The Mac reported macOS 26.6.1, eight M1 Pro logical CPUs, AC power and an
unlocked session. A fixed three-second startup delay initially missed the
Summary accessibility tree. The helper now waits up to fifteen seconds for the
actual Summary tab before preparation. Native preparation, observed 1280-by-880
bounds and orderly Quit succeeded. The failed startup receipt is retained.

The first timed retry exposed a verifier unit bug: PROC_PIDTASKINFO returns Mach
ticks, which had been labeled nanoseconds. Apple's
[kernel implementation](https://github.com/apple-oss-distributions/xnu/blob/main/osfmk/kern/bsd_kern.c)
assigns Mach-time user and system counters. The helper now reads the native
timebase and converts those counters before comparing them with elapsed
nanoseconds. On this Mac the factor is 125/3. An independent calibration measured
0.29999425 CPU seconds against getrusage's 0.299995 seconds. Nine verifier tests
passed on both Mac and Linux, including conversion and missing/invalid-unit
rejection. The interrupted, unconverted receipt is retained as invalid; its
understated absolute percentages are not performance evidence.

The complete fresh [measurement set](evidence/measurements.json) retains all
twelve observations, alternating pair order, thirty-second warmups and
sixty-second scored windows. No compiler, profiler or diagnostic writer ran
during scored windows. Both modes used the same unchanged release binaries.

| Mode | Reference CPU | Candidate CPU | Reduction | Required reduction |
| --- | ---: | ---: | ---: | ---: |
| Summary | 12.6051% | 10.7757% | 14.5133% | at least 50% |
| Tray-only | 11.0961% | 8.6845% | 21.7339% | at least 50% |

Percentages use one logical CPU as 100%. Both targets fail. These observations
must remain retained even if later work improves the result. The next step is
profiling of the remaining cost.

Native preservation subsequently passed after the helper waited for reopened
screen controls, not just the window object. The original readiness failure is
retained under evidence/invalid. The passing
[native receipt](evidence/native-preservation/result.json) includes equal
reference/candidate sensor and monitor coverage, fresh statvfs arithmetic and
independent capacity checks, background sequence advancement with no window,
saved and reopened settings, continued history, native interaction and clean
Quit. This is preservation evidence, not a pass for either CPU target.

## Profiling the remaining work

Separate ten-second native stack samples are retained outside the repository at
`task-manager-artifacts/macos-performance/profile-candidate-20260908T130400Z`.
They identify temperature IPC, process refresh and account enumeration as
frequently sampled collector stacks. These samples include blocked threads;
their counts are not CPU percentages.

The developer suggested debugging macros. The isolated
[stage probe](probes/stage-cpu.rs) uses a small `stage!` macro around the same
sysinfo refresh calls, measures collector-thread CPU with
`clock_gettime(CLOCK_THREAD_CPUTIME_ID)` and elapsed time with `Instant`, and
prints after all stages. It leaves the release application unchanged. The probe
compiled in release mode against sysinfo 0.37.2 and ran twelve one-second
iterations. All [raw rows](probes/stage-cpu-20260908.txt) are retained. Means below
exclude the explicitly retained first iteration for startup:

| Stage | CPU ms/sample | Elapsed ms/sample |
| --- | ---: | ---: |
| CPU refresh | 0.168 | 0.173 |
| Memory refresh | 0.050 | 0.051 |
| Process refresh | 35.612 | 36.232 |
| Network refresh | 1.232 | 1.232 |
| Temperature refresh | 4.190 | 71.080 |
| Account enumeration | 1.295 | 24.185 |
| Disk discovery and I/O without capacity | 4.707 | 4.864 |

This is an isolated API probe, not a complete application profile or acceptance
comparison. Temperature and account wall time mostly reflect waiting. Process
refresh is the largest measured CPU stage. No new reduction is claimed from
profiling alone.

## Checkpoint self-audit

The production changes stay in the collector and introduce no dependency,
worker, interval change or saved-state schema change. Live capacity has fresh
query windows, checked raw arithmetic and explicit failures. Reused temperature
state is bounded by current discovery and reconnects after unsuccessful reads.
Controlled tests, native builds and Linux acceptance support those changes.
The performance and native Mac preservation claims remain withheld until their
required observations pass. The remaining work is verification, final review
and delivery; this checkpoint is not a completed release.
