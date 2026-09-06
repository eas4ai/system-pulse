# GPU acceptance implementation

Task 4 implementation status: DONE_WITH_CONCERNS. The independent acceptance mechanism is ready for review; the failed Linux preservation run remains unresolved. Hardware accuracy acceptance remains pending for Intel integrated, Intel discrete and Apple Silicon. The available AMD host supplies preservation and native transport evidence only.

## Work tracking

- Complete: independent raw collectors, arithmetic replay, adversarial verifier tests, and native helper readiness.
- Complete: mechanism tests, native helper compile/readiness, scoped lint/format and self-audit.
- In progress: Task 4 independent SPEC then QUALITY review and the unresolved preservation concern, owned by the orchestrator.

## Implementation

The existing Rust collectors and application are unchanged. The aggregate in `scripts/system-pulse/gpu_verify.py` runs the GPU verifier tests and the complete existing Linux acceptance command. It then ingests at most one original report for each required hardware class. Its default command returns failure when a required class is absent; development mode emits no Cairn acceptance lines.

The evidence verifier hashes original files, checks source and executable bindings, replays native inventory and observer normalization, and independently recomputes every required GPU field. It rejects duplicate JSON keys, nonfinite numbers, changed units/scopes/physical identities, omitted fields, counter resets, unknown state mappings, missing query windows, stale native text, invalid availability and failed process cleanup. Source operands are captured independently; production conversion functions are not imported.

The modules separate these responsibilities:

| Files under scripts/system-pulse | Responsibility |
| --- | --- |
| gpu_verify.py, gpu_evidence.py | Aggregate, artifact validation and requirement results |
| gpu_arithmetic.py, gpu_intel_arithmetic.py, gpu_samples.py | Counter brackets, measured intervals, formulas and complete field coverage |
| gpu_apple_capture.py, gpu_apple_native.m | Native Apple inventory/observations and bounded Metal workload |
| gpu_intel_capture.py, gpu_intel_sources.py | Native i915/xe DRM, sysfs, perf and source metadata |
| gpu_host_capture.py, gpu_capture.py | Build/source retention, capture phases and owned process cleanup |
| gpu_apple_ax.m, gpu_linux_ax.py, gpu_desktop.py | Native desktop census, actions, clipping and displayed values |
| gpu_originals.py | Bind normalized actions, states, phases and runtime binaries to originals |

Apple checks use the predeclared [comparison protocol](apple-native-comparison-protocol.md). Residency and energy counters are bracketed by entirely preceding/following independent queries after clock-domain mapping. Power uses measured endpoints; frequency uses validated per-state mapping and active residency. Shared allocation and in-use remain separate scalar byte measurements. The [SMC software guard](../../decisions/report-unvalidated-apple-smc-temperatures-as-unavailable.md) retains raw bytes and withholds attributed values below 15 C; independent HID temperatures are unaffected. Every enumerated HID service is retained, including missing product attributes.

Native controls have a semantic control name and a separate native selector. Empty accessibility IDs remain empty. A label selector must resolve exactly one visible native object in the physical GPU panel/viewport. Meter selectors delimit a sensor using its real value-label identifier. The helper performs the action on that same resolved object in the same invocation and retains its native identity, attributes and before/after trees. The verifier binds the selector to the executed helper argv and PID, and checks the actual saved preference change.

Linux clipping uses the uniquely matched same-PID X11 top-level window when AT-SPI reports invalid window geometry. It retains the native window ID, raw geometry and translated screen position, then replays descendant viewport clipping from native ancestry. It does not substitute screen dimensions. Apple uses AX window and viewport geometry. Neither diagnostic publication nor a zero-size/truncated accessibility tree establishes display.

Every child has an external deadline, retained stdout/stderr, executable hash, PID and cleanup record. Descendants remaining after a leader exits are terminated within a bounded cleanup period. Apple setup and observation/workload loops drain autorelease pools; `OBJC_DEBUG_MISSING_POOLS=YES` is retained for every native process and missing-pool warnings reject a host report.

## Commands and capture contract

From a clean committed checkout, run the aggregate with three original capture directories:

```sh
rtk proxy python3 -B scripts/system-pulse/gpu_verify.py --output /absolute/fresh/gpu-aggregate --report /absolute/intel-integrated-capture --report /absolute/intel-discrete-capture --report /absolute/apple-capture
```

The equivalent report list is `SYSTEM_PULSE_GPU_REPORTS`, separated by the host path separator. Omitting any required class leaves the applicable GPU requirements failing. A local verifier-only check is:

```sh
rtk proxy python3 -B scripts/system-pulse/gpu_verify.py --development-tests-only --output /absolute/fresh/gpu-development
```

On the native host, use `gpu_host_capture.py` with fresh output outside the checkout, an existing build cache, and a predeclared action plan:

```sh
rtk proxy python3 -B scripts/system-pulse/gpu_host_capture.py --output /absolute/fresh/native-attempt --target-dir /absolute/build-cache --action-plan /absolute/action-plan.json
```

Intel additionally requires the independently selected PCI address via `--pci` and a finite task-owned workload argv encoded as JSON via `--load-command`. Its command must finish successfully inside the declared load phase and 20-second process deadline. Apple creates its own serial 4 MiB Metal workload on the independently matched registry ID. A locked Mac console rejects capture before application launch.

The action plan is a JSON array of 6–60 steps. Each step has `name`, semantic `target`, `selector`, `method` and optional `phase`/scroll `value`. It must cover panel collapse, sensor collapse, scrolling, interval and meter changes. The capture adds the restart/restoration action. For example, the interval step is:

```json
{"name":"interval","target":"workspace:interval:500","selector":{"within":"System Pulse","label":"0.5 s"},"method":"press","phase":"interval"}
```

GPU panel selectors use `{"within":"PHYSICAL_MONITOR_ID","label":"Collapse ACTUAL_GPU_TITLE"}`. Sensor controls use `within: "PHYSICAL_MONITOR_ID:viewport"` and their exact native label. Meter selectors additionally use `after: "PHYSICAL_MONITOR_ID:value:PHYSICAL_SENSOR_ID"`. Scroll selectors use the real `identifier` of the workspace or GPU viewport. The semantic targets remain `PHYSICAL_MONITOR_ID:collapse`, `PHYSICAL_MONITOR_ID:row:PHYSICAL_SENSOR_ID` and `PHYSICAL_MONITOR_ID:meter:PHYSICAL_SENSOR_ID`. Plan enough scroll steps to observe every independently inventoried field; there is no index or first-match fallback.

Before measurement, the capture retains inventory, the action-plan hash, field formulas/precision, timing bounds and idle/load/interval/recovery phases. It records 60 collector samples and a bounded independent observer stream, plus actual consumed app snapshots and saved state. Readiness waits are bounded; failed measurements are not silently retried. Failure-recovery injection is explicitly not performed on the native machine; the recovery phase follows workload completion and deterministic adapter tests cover failure/reset sequences.

Failed attempts remain on disk. The report manifest retains original source files, native binaries, commands, logs, inventories, samples, native actions, saved states and lifecycle records. A copied PASS flag or helper-readiness report cannot substitute for this report format.

## Verification evidence

The task-owned artifact root is `/home/shawn/workspace2/task-manager-artifacts/gpu-task4`.

- GPU verifier suite: 42 tests passed, including actual bounded child/descendant cleanup.
- Ruff lint and format checks passed for the 20 new Python modules/tests; clang-format dry-run with warnings as errors passed for both Objective-C sources. Final development CLI verification retained 42 passing tests at `development-final-20260906/gpu-verifier-tests.log`, SHA-256 `b4c882c0d40b3a266bedfeb3d20aa91c7812dbffdc0d8c71436c273fe11d5a0c`, and emitted no Cairn acceptance lines.
- Final Mac helper compile/readiness: `helper-20260906T145000Z`, with a 41-file transfer manifest in `transferred-20260906T145000Z.json`. Compiler PID 5716, inventory 5726, observer 5730 and workload 5731 exited 0, were reaped and left no process group. Their stderr files are empty with pool diagnostics enabled. Forty frames replayed 11 independently inventoried fields. Native helper SHA-256: `f597990b74edc331ba0cf6f43b221c807578d5c86c7db8de13b17446526d4eea`. The later final AX correction represents disjoint clips as finite zero-area rectangles. `helper-ax-final-20260906` compiled that final source with clang PID 5836, exit 0/reaped/absent and empty stderr. Final AX source SHA-256: `1b949eb681a63fd729501f79222622cec053232e43aaa048eb6a5aa5d3d1fcef`; compiled helper SHA-256: `53e540cd3978f19d09a9df2cc5067b02661990a05a44333fcfcd5ebe1f75e885`. Original transfer manifest: `transferred-helper-ax-final-20260906.json`.
- Final Linux transport smoke: `linux-ax-final-20260906`. App PID 2142485; native census/action/close PIDs 2143904, 2144298 and 2144537; private-session group 2142431. All exited 0, were reaped and left no group. The wrapper retained its SIGTERM cleanup of task-owned portal descendants. The native census contained 967 nodes, 148 fully visible; the empty-ID AT-SPI button changed saved interval 1000 to 500 ms and WM_DELETE_WINDOW closed the app normally. Raw X11 geometry and all clipping were replayed.
- Earlier native attempts, including failures and the successful `linux-ax-20260906T143600Z` run, remain under the same artifact root. The [locked desktop findings](apple-gui-preflight-findings.md) explain why no Mac GUI accuracy claim is made.
- Full Linux preservation: `preservation-20260906` failed the unchanged native held-input freshness check. All 425 Python and 422 selected Rust tests, formatting, strict Clippy, build and independent host checks passed. Native launch, metrics, collapse, charts and inner scrolling passed before a 2.026-second observation exceeded the 2.0-second limit. The first held-input observation was already 1.9439 seconds old; the breach occurred 111.775 ms after key press. Sequence 69 collected in 182.803 ms and was accepted 153.013 ms later. Subsequent sequences 70–75 appeared. The originals do not establish a cause. The existing opt-in publication diagnostic at `publication-diagnostic-20260906` completed focused process PASS and is ineligible for acceptance. Its held-Up check retained 54 observations without errors, sequences 71–76, maximum age 1.289118335 seconds. The final ring contains 64 published records for sequences 123–186, no overwrite or sidecar errors, and maximum acceptance-to-rename time 252.929 ms. These later traced records do not demonstrate the earlier cause. The failed full attempt remains failed; see the orchestrator-owned [failure record](gpu-linux-preservation-failure.md).

## Remaining native acceptance

Intel integrated and discrete hardware are unavailable in this task. Apple observer/workload readiness is established, but the console remains locked, and the separate application autorelease-pool finding belongs to Task 5. The new GPU mechanism therefore has no complete hardware-class accuracy report yet. Final committed captures, all matrix comparisons and aggregate Cairn receipts belong to Task 5 after independent review.

## Self-audit

The implementation was checked against all 14 production rules. The mechanism preserves existing source and acceptance contracts, rejects unsupported evidence, bounds its children and native traversals, retains failures, and has no known remaining helper-source defect. The known full-preservation failure is disclosed above and is not converted into a pass. Independent review, a demonstrated cause for that failure, fresh untraced preservation and final hardware-class acceptance remain required.
