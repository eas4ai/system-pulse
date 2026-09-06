# GPU memory integration specification review

Status: SPEC PASS on 2026-09-06. Independent quality review remains pending.

Independent reviewer `gpu_memory_spec` examined source
`4db68c71304d368977265e31ba365b121fcfd9f0` against base
`49aab2daf8f5574068ae13c6c05f9ce4e639532d`, with report HEAD
`2d175c6257dc09c82cc5caef367c05ba931f1ddb`. The review was read-only and found
no actionable specification gaps in Task 3.

## Verified behavior

The reviewer inspected the actual live conversion and acceptance paths, meter
renderer, panel compatibility fallback, model history and seven new GPU tests.
Shared GPU bytes retain Counter/Scalar quantities and distinct allocation labels;
dedicated VRAM retains Capacity. Unknown or zero totals cannot render a capacity
bar. Existing saved choices and full physical identities survive Session restore,
absence, reappearance and reordering. Duplicate GPU names retain distinct IDs.

Failed, unavailable and warming-up outcomes discard cached values while preserving
their explicit status. Successful values retain the original native observation
time. Repeated or older observations age without adding history points or
suppressing fresh independent fields, including the Processes census. Bounded
histories, retained metadata and compatible-meter fallback remain intact.

## Independent verification

- `rtk proxy cargo test -p system-pulse --lib gpu_`: 7 passed.
- `rtk proxy cargo test -p system-pulse-collectors -p system-pulse-model -p system-pulse`:
  183 passed: app 63, collectors 96, model 24.

Root separately checked the three original failing logs, their counts and error
messages, the source change scope, report links and whitespace. Copies of those
logs and their SHA-256 manifest are retained at
`/home/shawn/workspace2/task-manager-artifacts/gpu-memory-integration/4db68c71304d368977265e31ba365b121fcfd9f0/`.
The [implementation record](memory-integration.md) identifies the original commands
and distinguishes exploratory test corrections from actual production defects.

Formatting and Clippy were not independently rerun by this specification reviewer.
This review does not establish native hardware accuracy, native GUI behavior or
aggregate acceptance. Task 3 awaits independent quality approval; Tasks 4 and 5
remain unfinished.
