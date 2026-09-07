# Collector review record

Status: Task 1 passed independent spec and quality review. This is not final live application acceptance.

## Source and focused verification

- `8b7c35b9`: real collector crate, bounded sampling service, and diagnostic command.
- `9c9d059c`: CPU thread count uses the kernel's total scheduling-entity count in `/proc/loadavg`; 32 focused tests passed.
- `19099472`: independent interface identities for equal MACs/shared hardware parents; 33 focused tests, strict all-target Clippy, rustfmt, and whitespace checks passed in the implementer's run.
- `75498c85`: documentation and baseline Cairn receipts only; no collector source change.

Development host captures are `/tmp/pulse-collector-host-final.jsonl` and `/tmp/pulse-collector-thread-check.jsonl`. The first contains 32 logical CPUs, two AMD GPUs, 24 interfaces, 123 filesystem monitors, and 1,246 readable process rows; capture duration was about 145.6 ms. The implementer independently recomputed 4,397 derived values from preserved counters and timestamps. These captures precede final application integration and do not claim native UI accuracy or NVIDIA hardware verification.

## Independent spec review

The reviewer inspected all collector modules, scheduling, CLI, capability documentation, and dependency additions, and independently ran 32 tests at `9c9d059c`. It found one P1: MAC-only virtual interface IDs could alias, sharing counter baselines between distinct interfaces. Hardware parent plus MAC could also collide.

The fix always adds a per-interface discriminator, rather than adding it only after detecting a collision. Tests exercise equal MACs with unequal counters, reversed discovery order, removal and reappearance, for virtual and shared-hardware-parent interfaces. Existing-interface rates remain independent; returning interfaces warm up. OS/admin interface rename changes identity, as documented.

The reviewer rechecked `19099472` and independently ran three focused network tests. **Task 1 spec review passed**, with no remaining findings. App integration and native acceptance are outside that bounded pass.

## Independent quality review

The separate quality reviewer inspected all collector source/test modules, README, and Cargo changes at `19099472`. It requested two P2 fixes:

1. Public `Counters::retain` prunes baselines but leaves historical `touched` identities; external callers cannot invoke the crate-private reset. Prune both collections or reduce visibility, and test the public churn path.
2. The common sysinfo backend captures some timestamps before component/disk refresh, load and uptime queries. Record post-query observation times and query windows so variable refresh duration cannot distort rate intervals.

Both findings were fixed in `c217818d3f5295d982fe5c8f9909165eef18a525`. The implementer ran 35 tests, locked strict all-target Clippy, rustfmt and whitespace checks successfully. The quality reviewer independently reran the public counter churn test, portable timing regression, and common-backend host smoke test (three passed), plus the scoped whitespace check. **Task 1 quality review passed**, with no remaining concrete findings. No code changes or test reruns were made by the quality reviewer during its initial review.

The reviewer also confirmed the process census boundary: Linux enumeration failure produces a failed `linux-processes` diagnostic and no `cpu:host/processes` reading. UI integration must consume that reading rather than infer a successful census count from `rows.len()`.
