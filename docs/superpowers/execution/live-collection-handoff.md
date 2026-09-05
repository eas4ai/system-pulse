# Resume: real system collection

The user restarted the harness and invoked `/existing-project`. Resume the real-collection task through the adoption drafts; do not repeat the completed workspace implementation.

## User direction

The user rejected simulated readings as the delivered system monitor. The assistant acknowledged that the fixture proof was too narrow, proposed real collectors feeding the existing panels with simulation confined to tests, and the user replied **“ok”**. This authorizes moving that work forward. Earlier authorization to use subagents remains applicable. Do not ask again whether real readings or subagents are wanted.

User layout requirements remain: **no UI tabs**, scroll to panels, explicit independent panel/row collapse, retained useful compact readings, and persistent layout choices. Unsupported metrics must be labeled unavailable, never replaced with invented readings.

## Existing verified implementation

- Design repository: `/home/shawn/workspace2/task-manager`.
- Implementation worktree: `/home/shawn/workspace2/task-manager-worktrees/workspace-visibility`.
- Implementation branch: `feat/system-pulse-workspace`.
- Verified fixture acceptance documentation: `9f2f3ad0382ce4c7ce0aadfc0c4ed88588ad95af`.
- Adoption drafts begin at `822635ff044df53b60258ad645c7dbf01fc0287b`; inspect Git history for later documentation commits.
- Historical fixture source baseline: `88343d5ed3be72865e52fc3d51a860649d8def83`. Inspect current source HEAD and worktree status before resuming.
- Backing framework clone: `/home/shawn/workspace2/gpui-component`.
- Application: `examples/system_pulse`; pure model: `examples/system_pulse/model`.
- The existing `examples/system_monitor` is unchanged and may contain reusable real collector patterns.
- Verified fixture baseline: **275 tests**, affected-package formatting, strict all-target Clippy, native build, and independent reviews passed. Linux native interaction checks passed. This does **not** establish real collection.
- Full evidence: [workspace execution report](2026-09-04-workspace-visibility.md), including committed artifacts and interactive native driver.

## Current task state

The developer explicitly **confirmed** LIVE-001–013 and their falsifiers, then added NVIDIA support despite having no NVIDIA GPU installed. No further scope approval is needed for these collectors or subagents.

1. Complete: cited recon, agreed LIVE contract, implementation plan, roadmap/current commitment and executable baseline mechanism.
2. Complete: host collector crate and bounded sampling service, with independent spec and quality review.
3. Complete: real devices/readings/process rows, physical meters, stable state and test-only fixtures, with independent spec and quality review.
4. Complete: shared connection-attribution raw evidence and malformed-row privacy fixes, independently spec/quality reviewed.
5. Complete: native keyboard repaint coalescing, eight focused native cases, independent spec/quality reviews.
6. **In progress:** executable independent host/native acceptance, then final review.

Activation is committed as `55087aa6` in the source worktree. Read `docs/spec/live-collection.md`, `docs/plans/real-system-readings.md`, and `docs/commitments/real-system-readings.md` there. Historical READ/VIEW/STATE specs remain Observed. The new source-root AGENTS working agreement was created from the existing-project skill's template; the design repository's existing AGENTS remains untouched.

Cairn's first committed baseline check failed on the actual production fixture dependency and retained receipts for all LIVE requirements. `cairn wake` reports **Resolvable: implement LIVE-001**. `.cairn/in-progress` records that source action. Do not rerun the aggregate repeatedly while implementation is incomplete; use focused tests and retain failing receipts.

The collector attribution follow-up is committed through `bbfc24905d5566d37e655be2412b105e9edab218`; both spec and quality reviews passed. App/model integration and the subsequent held-key input starvation fix passed both reviews. One source implementer at a time; independent spec then quality review follows each coherent task. Root owns execution documentation and independent acceptance preparation.

Host preflight found 32 logical CPUs and two Radeon AI PRO R9700 GPUs, with readable utilization, VRAM, temperatures, average SoC power, graphics/memory clocks and fan RPM. Stable AMD IDs and exact sources are in source `docs/execution/real-system-readings/host-preflight.md`. NVIDIA backend API research and the verification design are adjacent documents. NVIDIA deterministic adapter tests and graceful-absence tests are required; actual NVIDIA hardware accuracy remains explicitly unverified until run on such hardware.

The collector is committed through `c217818d`; independent spec and quality reviews passed after fixing shared-MAC interface identity collisions, public counter-helper retention, and common-backend query timestamps. All 35 collector tests, scoped strict Clippy and formatting passed. Source `docs/execution/real-system-readings/collector-review.md` records the review results. Root independently checked 2,509 external counter brackets and 754 derived values in a real-host probe; this is supporting evidence, not final acceptance.

Live integration is committed through `9c6034b456a0a50d6a8b7a708d36dddd8d6cbd4b`, with independent spec and quality PASS. All 65 app/model tests and scoped strict Clippy passed independently. Review fixes preserve stale diagnostic timing/labels, absent summary units, stable exported process accessibility IDs, and coherent 16 MiB configuration read/write bounds. The original valid 451-panel oversized-state failure now round-trips, and rejected saves preserve previous state. See source `docs/execution/real-system-readings/integration-review.md`.

Real native smoke discovered 151 monitors, 862 sensors and over 1,200 processes. Root separately verified CPU keyboard focus/collapse at 960×640, expanded accessibility events, continuing real sample sequences, and clean app exit. Root also launched a real child named `pulse ) probe`, confirmed its PID/start/name and RSS conversion in collector snapshots, then confirmed exit. A subsequent cached native metric query matched visible CPU text at one unchanged sequence/revision within the declared age bound. These remain supporting checks; full arithmetic/formatting and native replay acceptance are pending.

Task 2a adds shared raw interface ownership and TCP4/TCP6 local-address/state query evidence, with ports/remotes/owners excluded. Spec review found two malformed-row disclosure cases; structural validation in `bbfc2490` resolves both. The reviewer independently passed 43 collector tests, nine malformed-row probes and 72 host attribution comparisons. Quality review also passed. See source `docs/execution/real-system-readings/attribution-review.md`.

Task 2b now addresses a confirmed native defect. Each process navigation key triggers a synchronous full layout while X11 drains queued input; foreground live delivery waits for that queue. Ordinary Up held for three seconds at 25 Hz caused over fourteen seconds of stale accepted data. The collector continued normally, and delivery recovered when input drained. Use one pending next-frame repaint per owning view while retaining every selection/scroll movement. Source plan and `native-freeze.md` record the task; complete report is `/tmp/system-pulse-freeze-investigation/REPORT.md`. Attribution reviews passed, and the app worker now has a narrow pending-frame fix with three red-first burst regressions. It is committed as `88d92e6c`, with the selected-identity test correction at `5d38680e`; both reviews passed. Its 44 app tests, 24 model tests, scoped strict Clippy/formatting/build pass. All eight native held/burst/directional cases pass with maximum accepted age 1.531 seconds; normal window close returned zero in 0.403 seconds. Failed temporary harness attempts remain distinct from passing cases. Candidate binary hash and exact artifacts are in source `native-freeze.md`. No final acceptance or completion is claimed.

Task 3 implementation context is prepared at `/tmp/system-pulse-acceptance-implementation-brief.md`, with detailed native instructions at `/tmp/system-pulse-native-prep-3WGkPz/TASK3-NATIVE-BRIEF.md`. The existing plan/verification design remain authoritative. Independent contract review confirmed combined retained-history tests, live insertion-path review and actual collapsed-panel/chart replay suffice; latest-only diagnostics must not be described as direct observation of all historical points. No extra history-export product feature is required without a concrete discrepancy.

## Working rules

Follow root user instructions and imported files: `/home/shawn/.codex/{RTK,TILTH,PARTNERSHIP}.md` and `/home/shawn/.claude/BEST_PRACTICES.md`; any repository-specific production standard overrides the global copy. Keep one todo in progress, and verify before marking complete.

Prefix shell commands with `rtk`; use `rtk proxy` for unsupported commands. Prefer codebase-memory-mcp for code discovery and index first if stale/missing; use `tilth` when graph results are insufficient. The framework graph project is `home-shawn-workspace2-task-manager-worktrees-workspace-visibility`.

Use the Superpowers workflow already requested, with source ownership and independent spec/quality reviews. User authorization persists; avoid redundant permission requests. Do not merge, push, or remove the existing worktree merely to resume.

The design repository's existing `AGENTS.md`, `docs/System Pulse.html`, `docs/files.zip`, and `reference/` are intentional untracked inputs. Preserve them. The original instruction explicitly prohibited modifying an existing `AGENTS.md`.

## Run and verify baseline

Run from the implementation worktree:

```sh
rtk cargo run -p system-pulse
rtk cargo test --locked -p system-pulse --lib
```

The old baseline used simulated readings. Committed integration uses real collection and has passed both reviews. Collector attribution and native repaint fixes are reviewed; full acceptance remains; inspect current state before judging completion. The prior verification report contains the complete affected-package commands and Linux native harness setup. Do not rerun all baseline checks without a reason; inspect status first and use focused checks as changes are made.

Current Task 3 worker: `implement_live_acceptance`, sole source owner for `scripts/system-pulse/`, acceptance execution docs, and app README/acceptance instructions. Root owns spec/glossary/plan/Cairn metadata and this design-repo handoff. Initial 13 independent verifier cases were observed failing before implementation and now pass. A focused fresh host run captured real sensor/process arithmetic, corrected clock-interval counter brackets and a real child lifecycle; its unresolved coverage hardening and native runner work are not final acceptance. Do not run the Cairn aggregate until the complete committed candidate is ready.


### Task 3 findings retained on 2026-09-05

The independent verifier now keeps every required process-counter bracket mandatory. Host-03's original passing summary was corrected to failure: 16 missing endpoints came from collector startup, not demonstrated host churn. Host-04 retained 46 missing endpoints across compiler/database identities; ownership cannot be inferred because ancestry was not captured. Host-06, a single coordinated quiet run, failed before comparisons because the harness incorrectly assumed a zombie's I/O remained readable. These are failed development runs, never aggregate acceptance. The worker is correcting owned-process lifetime coordination and preserving early-failure evidence. No narrower process cohort or tolerance has been approved.

Native-06's second GPU label was inside the window but clipped behind the toolbar. Root screenshot review rejected that visibility claim. Native-08 confirmed the accessibility ancestor tree omits the workspace clip, so coordinates alone cannot establish visibility. The acceptance worker now also owns a minimal semantic viewport accessibility change in app `workspace.rs` and the nested process viewport if required. Keep this as a separate candidate with a failing regression, native evidence, independent spec review, then quality review. Report any focus-reveal behavior defect before expanding the change. Existing CPU/RAM/one-GPU and compact-state observations remain supporting evidence only.

Development artifacts are under `/tmp/system-pulse-verifier-implementation-zpswl3j9/`. The independent host diagnoses are `/tmp/pulse-missing-bracket-diagnosis-b_98k_go/report.md` and `/tmp/pulse-host04-bracket-diagnosis/report.md`. Aggregate scripts are still uncommitted and incomplete. Root retains ownership of Cairn metadata and must not issue another known-incomplete aggregate check.


### Viewport review and host-07

The minimal native viewport source change is complete at `217941e52595eea7ef35e15dbe12d68a1e0d6b95`, with independent SPEC and QUALITY PASS. Existing workspace, sensor-body, process-table and process-row containers expose stable native identities and clipping bounds. All 45 app tests passed. Root's committed build matched the native-09 binary SHA `e87f0f8c56481c9c298f03a262ff256eb8621dc6100e6a14238eee540306eeec`. Root visually checked CPU, RAM and both GPU headers against actual clip bounds. Native-09 was geometry-only and has no normal shutdown receipt; final replay still requires one. See source `viewport-review.md` and its 16-file artifact manifest. No confirmed focus deadline failure required a behavior change.

The corrected host lifecycle supervises only the owned collector: four raw newline-complete snapshots, observed SIGSTOP with PID/start identity, readable live final counters, then expected SIGTERM/SIGCONT termination. It rejects complete or partial extra output and preserves early-failure evidence. Twenty-two Python regressions passed after observed red failures.

Host-07 completed that lifecycle but retained an overall strict failure: 48 missing mandatory endpoints across seven process identities, including browser processes born during capture. Its 41,288 successful counter brackets, 2,218 exact sensor comparisons and 16,014 process-field comparisons are supporting evidence only. Artifacts remain under `/tmp/system-pulse-verifier-implementation-zpswl3j9/host-07`. The assessor is diagnosing omissions while the worker continues full native split/divider, recovery, process, persistence and chart replay. Do not retry until green or silently exclude transient processes. No narrower bracket contract has been approved.


### Current focused acceptance progress

Host-08 passed all strict checks after a measured sampler correction: process census and readings first, newly enumerated PIDs before old ones, no 50 ms idle gap, bounded observation. It recorded 41,744 brackets, 2,219 exact sensor comparisons, 16,240 process fields and 96 interface checks with zero missing endpoints. No population exclusions or changed bounds. Independent reconstruction is in progress; this is focused preparation, not the final committed aggregate.

Native-11 passed launch, metrics, collapse and physical chart capture. Root reviewed the complete CPU sparkline with 0–100% scale, matching 9.7% native label and advancing sequences 44/45/46; combined history scope remains unchanged. Native-10 failed an incorrect harness meter-order expectation (actual Number → Line → Bar → Sparkline → Radial). Native-11 then failed because its new divider was offscreen; native-12/13 failed split acknowledgement. The worker and read-only investigator are diagnosing actual drag bounds/edge hit regions, not yet claiming a product defect. Native-13 retains a failure screenshot and panel bounds. Worker is also completing the brief's inner-edge wheel/Tab escape, selection preservation, nondefault interval persistence and recovery assertions before another full replay.
