# System Pulse reconnaissance

Status: Observed. Inspected 2026-09-07 at `af243cf2dba5eb6c4cb19397c522c38eda640f45`.

The current work is the developer-approved reduction of native Mac release CPU overhead. The [performance contract](spec/performance.md) defines the intended outcome. The [original fixture recon](recon-2026-09-04.md) is preserved verbatim; its findings are accounted for below.

## Exists

| Finding | Evidence |
| --- | --- |
| The application belongs here, with collector/model crates, GPUI Kit 0.6 and locked sysinfo 0.37.2. | [Manifest](../Cargo.toml:1), [collector](../crates/collectors/Cargo.toml:1), [lock](../Cargo.lock), [publication](execution/task-manager-repository-publication.md). |
| Startup creates the tray and tabbed dashboard; production excludes fixture generation. | [Entry](../src/main.rs:3), [modules](../src/lib.rs:3), [tray](../src/tray.rs:23), [screens](../src/screens.rs:299). |
| One worker collects into one replaceable snapshot slot at 0.5/1/2/5 seconds; shutdown joins it. | [Service](../crates/collectors/src/service.rs:8), [worker](../crates/collectors/src/service.rs:75), [shutdown](../crates/collectors/src/service.rs:123). |
| Portable collection recreates temperature, user and disk inventories every sample. | [Components](../crates/collectors/src/host/portable.rs:132), [users](../crates/collectors/src/host/portable.rs:317), [disks](../crates/collectors/src/host/portable.rs:487). |
| Process CPU is normalized to one CPU, not the whole machine. | [Counter arithmetic](../crates/collectors/src/host/portable.rs:325). |
| Delivery polls every 100 ms but does not notify on an empty poll unless data becomes stale. Accepted snapshots refresh screen and retained panels. | [Timer](../src/window_lifetime.rs:59), [delivery](../src/workspace.rs:516), [notification](../src/workspace.rs:708). |
| Screen refresh updates hidden Processes and Settings entities, but rendering constructs only the active page. | [Refresh](../src/screens.rs:127), [render](../src/screens.rs:299). This is a candidate, not the measured dominant cost. |
| History is bounded; absent identities are evicted and stale marking does not create samples. | [History](../crates/model/src/readings.rs:68), [eviction](../crates/model/src/readings.rs:102). |
| Preliminary release CPU was 12.69 percent Summary and 11.46 percent tray-only; the collector accounts for about 9.68 and 9.98 points respectively. | [30-second measurements](execution/macos-performance/recon-measurements.json), [binary](execution/macos-performance/baseline-build.json). These are not final three-run acceptance. |

## Documented

| Coverage | Evidence |
| --- | --- |
| Real values, units, identity, errors, bounded scheduling and interaction remain obligations. | [LIVE contract](spec/live-collection.md:27), [GPU preservation](spec/gpu-collection.md:54). |
| Later developer direction replaced visible docking with fixed tabs and retained settings compatibility. | [Authority](superpowers/specs/2026-09-07-tabbed-screens-design.md:3), [product spec](feature-spec-dockable-system-monitor.md), [delivery](execution/tabbed-screens.md). |
| Closing the dashboard retains collection/history while tray hosting is available. | [Guide](../README.md:7), [detach](../src/window_lifetime.rs:5), [lifetime](../src/tray.rs:62). |
| Rust tests, Clippy, Python tests and native Linux/package checks exist. Native Mac performance needs separate measurements. | [Commands](../README.md), [acceptance](../scripts/system-pulse/application_acceptance.py), [protocol](plans/macos-performance.md). |

## Contradicted or incomplete

| Finding | Both sides and disposition |
| --- | --- |
| Formal APP/LIVE prose still requires the old docked/no-tabs presentation despite later developer direction. | [APP-003/004/006](spec/application.md:16), [LIVE-010](spec/live-collection.md:77) versus [later authority](superpowers/specs/2026-09-07-tabbed-screens-design.md:3) and [rendering](../src/screens.rs:299). Retain this drift for separate formal reconciliation; do not change layout during performance work. |
| Overview/glossary describe the previous visible workspace and removed framework products. | [Overview](spec/overview.md:5), [glossary](spec/glossary.md:21) versus [manifest](../Cargo.toml:46) and [README](../README.md:3). Vocabulary remains usable; old layout descriptions need reconciliation. |
| Cairn reports 1,173 historical scope paths under finish-application. | [Original verdict](execution/macos-performance/prior-scope-verdict.txt), [backlog](../.cairn/backlog/reconcile-retained-repository-migration-history.md), [publication](execution/task-manager-repository-publication.md). The new commitment does not close the old one or erase this finding. |
| Original fixture findings about missing real collection, processes, physical scales, identity and configurable sampling have implementation/evidence resolutions. | [Original recon](recon-2026-09-04.md), [live acceptance](execution/real-system-readings/final-acceptance-pass.md), [collector](../crates/collectors/src/host/portable.rs:32), [model](../crates/model/src/readings.rs), [service](../crates/collectors/src/service.rs). |
| Original deferred appearance, presets, process actions and packaging now have scoped Linux implementations and delivery records. | [Original recon](recon-2026-09-04.md), [Linux checkpoint](execution/linux-application-checkpoint.md), [tabbed delivery](execution/tabbed-screens.md), [guide](user-guide.md). Missing hardware evidence remains open. |

## Unverified and preserved limitations

| Limit | Evidence / next check |
| --- | --- |
| The 50 percent reduction is not implemented or verified yet. | [Target](spec/performance.md), [reference](execution/macos-performance/baseline-build.json); run three paired 60-second measurements per mode. |
| Inclusive stack samples include blocked OS calls and are not CPU attribution. | [Investigation notes](execution/macos-performance/measurement-notes.md); compare independent process/thread counters and controlled changes. |
| Reusing disk objects can retain old capacity after a failed refresh. | [Pinned-backend inspection](execution/macos-performance/measurement-notes.md), [current reconstruction](../crates/collectors/src/host/portable.rs:487). Leave unchanged unless fresh-read behavior is demonstrated. |
| Intel integrated/discrete and NVIDIA native accuracy, physical removal and unavailable platforms are not established by this Mac. | [GPU-008](spec/gpu-collection.md:62), [earlier recon](recon-2026-09-04.md), [existing acceptance limits](execution/real-system-readings/final-acceptance-pass.md). |
| Mac full-application autorelease-pool findings remain separately recorded. | [Decision](decisions/drain-autoreleased-objects-at-mac-application-and-dispatcher-boundaries.md), [review](execution/intel-and-apple-gpus/apple-pool-spec-review.md). Performance does not close them. |
| Reference licenses and unrelated framework code are outside this pass; CI configuration is not evidence of CI execution. | [Earlier recon](recon-2026-09-04.md), [licenses](../README.md), [instruction to keep automation disabled](superpowers/specs/2026-09-07-tabbed-screens-design.md). |

## Blast radius

| Area | Scope and preservation |
| --- | --- |
| Collector | [Host ownership](../crates/collectors/src/host/mod.rs:23), [portable collection](../crates/collectors/src/host/portable.rs:32), [lifecycle](../crates/collectors/src/service.rs:75): optimize measured discovery while preserving timing and backend selection. |
| Model/UI | [Acceptance](../src/workspace.rs:562), [screens](../src/screens.rs:127), [history](../crates/model/src/readings.rs), [tray](../src/tray.rs): preservation checks; code changes only if subsequent profiling justifies them. |
| Verification | [Collector tests](../crates/collectors/src/host/portable.rs:618), [service tests](../crates/collectors/src/service.rs:134), [screen tests](../src/screen_tests.rs), [native helpers](../scripts/system-pulse/), [protocol](plans/macos-performance.md). |

The working-agreement portion of AGENTS.md now matches the invoked skill template; repository-specific instructions remain. New PERF requirements were approved by the developer. This recon and historical READ/VIEW/STATE records remain Observed.
