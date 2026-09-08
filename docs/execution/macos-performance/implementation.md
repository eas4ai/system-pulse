# Mac collector optimization

Status: implemented; native CPU and preservation acceptance pending.

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
This is not a package pass; a clean committed aggregate is still required.
