# GPU memory presentation and persistence integration

Status: Task 3 closed after independent [SPEC](memory-spec-review.md) and
[QUALITY](memory-quality-review.md) approval. The implementation and required
local checks passed. Root also verified a [native Mac build and 63 app tests](memory-mac-build.md).
This is not commitment closure or native GPU accuracy/GUI acceptance.

Source commit: `4db68c71304d368977265e31ba365b121fcfd9f0`
(`fix: preserve GPU memory freshness and physical identities`).
The implementation marker used base
`49aab2daf8f5574068ae13c6c05f9ce4e639532d` and was removed after the source commit.
Root-owned documentation advanced separately during implementation.

## Changes

[LiveState and conversion](../../../examples/system_pulse/src/live.rs) now retain
the complete physical ID when disambiguating same-name GPU titles. Successful
measurements still use their original native observation timestamp. An explicit
failed, unavailable or warming-up outcome discards any retained value and uses
the snapshot capture time for that outcome. Raw observations remain unchanged.

A repeated or older native measurement no longer aborts acceptance of fresh
independent fields. History ages in place, skips previously observed timestamps,
and retains its existing bounds. The Processes census uses the same handling;
its failed outcome can replace an old cached count without manufacturing a new
measured count.

No collector, model schema, saved key, compatibility table or meter renderer
change was required. Existing mappings already preserve Intel shared allocations
as byte counters and Apple shared allocation/in-use readings as byte scalars.
Dedicated VRAM remains capacity; a missing or zero total yields no capacity
ratio. The renderer already requires a positive capacity total for a bar.

## Integration coverage

Seven [application integration tests](../../../examples/system_pulse/src/live/gpu_tests.rs)
exercise real snapshot acceptance, model histories, presentation labels, meter
compatibility and `Session` serialization/restoration. Inputs are test-only
descriptor shapes, not native accuracy evidence.

- Intel `/shared-region-0` and `/local-region-3`, Apple `/shared-allocated` and
  `/shared-in-use`, and historical AMD/NVIDIA `/vram` retain their physical
  quantities, byte units, allocation/capacity values and visible labels.
- Shared GPU allocation has no total or compatible capacity bar. Valid dedicated
  VRAM produces the expected used/total ratio and capacity label. Unknown/zero
  dedicated totals do not borrow separately supplied system RAM or process
  memory. Native source/unit/meaning rejection remains covered at the existing
  Intel and Apple adapter boundaries; the UI adds no display-string parser.
- Mixed-vendor saved IDs, monitor metadata, panel collapse, sensor visibility,
  collapse, order and meter choices survive serialization, absence and reordered
  rediscovery. An incompatible saved bar falls back to Number without rewriting
  the saved choice. Absent histories are evicted and retained metadata supplies
  unavailable byte labels.
- Equal-name Apple path fixtures
  `gpu:apple:IODeviceTree:/arm-io/sgx@4000000` and
  `gpu:apple:IODeviceTree:/arm-io-1/sgx@4000000` previously produced identical
  `GPU · /sgx@4000000` title prefixes. Full IDs distinguish them. The second path
  is an adversarial identity fixture, not a claimed observed second Apple GPU.
- Repeated and older Apple source captures retain their original time and become
  stale while fresh independent fields advance. Failed/unavailable/warming-up
  outcomes discard cached operands; a later retry carrying an old measured value
  cannot erase the newer outcome. A genuinely new capture recovers normally.
- Repeated host census observations do not abort mixed GPU snapshots. Census
  failure replaces the cached count with a valueless failed outcome. Histories
  remain bounded throughout these sequences.

## Verification performed

These were local development checks, not `cairn check` receipts. Commands ran
from the source worktree using its cached target directory on Linux.

| Command | Observed result |
| --- | --- |
| `rtk cargo test --locked -p system-pulse --lib live::gpu_tests` before fixes | Corrected regression run: 3 passed, 3 failed, 56 filtered out. Failures were the equal-label collision and two `Reading timestamps must increase within each series` errors. |
| Same focused command after the initial fixes and extended older/retry cases | 6 passed, 56 filtered out. |
| `rtk cargo test --locked -p system-pulse --lib live::gpu_tests::gpu_fresh_snapshot_survives_repeated_host_census_observation` before the census fix | 0 passed, 1 failed, 62 filtered out; `Reading timestamps must increase within each series`. |
| `rtk cargo test --locked -p system-pulse-collectors` | 96 passed across 3 suites. |
| `rtk cargo test --locked -p system-pulse-model` | 24 passed across 5 suites. |
| `rtk cargo test --locked -p system-pulse --lib` | Initial 62 passed; final source and seven new integration tests: 63 passed, zero failures. |
| `rtk cargo clippy --locked -p system-pulse-collectors -p system-pulse-model -p system-pulse --all-targets --no-deps -- -D warnings` | Passed. |
| `rtk cargo clippy --locked -p system-pulse --all-targets --no-deps -- -D warnings` | Passed again after the census change and final fixture corrections. |
| `rtk proxy rustfmt --check --edition 2024 examples/system_pulse/src/live.rs examples/system_pulse/src/live/gpu_tests.rs` | Passed on final source. |
| `rtk git diff --check` | Passed. |

The first exploratory focused run also had 3 passes and 3 failures: two timestamp
errors and an incorrect test assertion banning `/` from the entire visible label,
which included a valid Apple identity path. That assertion was corrected to check
the numeric text. An initially suspected Intel PCI-domain truncation was not a
defect: a full BDF fits the prior twelve-character suffix. The actual collision
regression uses the Apple paths above. Neither exploratory mistake is counted as
a production defect.

The original failed command outputs remain in the local RTK logs:
`~/.local/share/rtk/tee/1788696311_cargo_test.log` (exploratory),
`~/.local/share/rtk/tee/1788696340_cargo_test.log` (corrected three regressions), and
`~/.local/share/rtk/tee/1788696563_cargo_test.log` (census regression). Their failure
counts, exact failure messages and collision values are retained above.

## Production self-audit

Reviewed against machine `BEST_PRACTICES.md` version 1.1.0; no repository override
was present. The implementer is satisfied with this scoped change and found no
remaining issue requiring revision before independent review.

| Rules | Review |
| --- | --- |
| 1–3: understand, minimize, maintain | Read the agreed GPU/LIVE contracts and current source paths; production edits stay in `live.rs`, with one coherent test module. Existing memory mappings were covered without gratuitous changes. |
| 4–5: boundaries and errors | Original measurement times, units, IDs and raw source records remain intact. Explicit unsuccessful outcomes cannot publish retained operands as measured values. |
| 6: security | No new I/O, dependency, unsafe code, permissions, secrets or external side effects. |
| 7: survivable state | Actual Session round-trip and rediscovery checks preserve schema, full keys and all saved choices, including incompatible choices. Existing rejected-input recovery is unchanged. |
| 8: reliability | No new poller or unbounded storage. Repeated and older captures do not append history points or block fresh independent fields. |
| 9–11: tracking, testing, honesty | One implementation item remained in progress until code and verification were complete. Reproduced failures preceded their fixes; counts above are from commands actually run. Native evidence and independent reviews remain separate. |
| 12–14: partnership, audit, clarity | Root reviewed the timestamp/outcome distinction and census scope. Changes and limitations are stated here without claiming aggregate acceptance. |

No native GUI painting, hardware accuracy, sleep/wake, physical removal or full
workspace acceptance was performed by this task. Intel Linux hardware coverage
and the independent native acceptance work remain outside this record. Apple
backend/SMC policy and the earlier native lifetime fixes were not changed.
