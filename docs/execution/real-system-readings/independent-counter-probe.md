# Independent counter probe

Status: preliminary source-verification probe during UI integration; not final native acceptance.

The reviewed collector diagnostic binary was rebuilt with `rtk cargo build --locked -p system-pulse-collectors --bin pulse-snapshot`. An independent Python observer read CPU, network and block-device counters every 10 ms while the binary produced three real one-second snapshots.

Result: **2,509 source observations passed external counter brackets; 754 main-monitor derived readings recomputed exactly; zero failures.** Process-rate comparisons, scalar conversions, capability coverage and native rendering remain part of the final acceptance runner.

Artifacts: `/tmp/pulse-independent-counter-probe-9fc555o7/` contains `snapshots.jsonl`, `observations.json`, and `result.json`, including the diagnostic binary SHA-256. The capture uses actual host sources and does not substitute fixture values.

## Comparison method

For each snapshot anchor, the collector-relative to Unix offset lies in `[unix_ns - monotonic_after_ns, unix_ns - monotonic_before_ns]`. Map the source query start and completion through that interval. Select the nearest external read completed before the earliest possible query start and the nearest external read begun after its latest possible completion. Require each captured cumulative counter to lie between those independent values. Missing brackets and out-of-range counters fail.

Recompute CPU utilization from the first eight CPU counters with idle/iowait excluded from busy and guest counters excluded from total. Network throughput is byte delta divided by measured elapsed seconds. Block throughput uses sector delta times 512; IOPS uses completed-operation delta; mean latency uses operation-time delta divided by completed operations. Floating operation order follows the documented formulas, before any display rounding.

The final executable verifier must additionally record paired external wall/monotonic clock anchors and reject wall-clock steps, exercise intentional unit/normalization/interval/bracket corruptions, inspect required source capabilities, and compare the native UI against its accepted real snapshots. This preliminary probe establishes that the proposed external-bracketing method works on this host; it does not replace those checks.

## Independent process probe

A separate finite collector probe launched a real child named `pulse ) probe`, independently read its stat PID/start ticks/name before and after two captures, checked its one thread and exact RSS page conversion, then terminated it and confirmed absence from the next capture. It passed with PID 665562 and start ticks 65809074. Artifacts: `/tmp/pulse-independent-process-probe-9gopmber/`, including present/absent snapshots, result and binary hash. This also challenges process-name parsing with an internal closing parenthesis. Native process-table acceptance remains pending.
