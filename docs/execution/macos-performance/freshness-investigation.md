# Linux diagnostic freshness investigation

Status: In progress.

- [ ] In progress: remove intermediate diagnostic JSON allocation and verify payload, failure handling and native publication timing.
- [ ] Pending: run complete Linux acceptance and record committed evidence.
- [ ] Pending: complete Mac performance and preservation evidence, then review the commitment.

Two complete Linux acceptance runs failed at device-label lookup in
`tabbed_replay.py:101`, with accepted-frame ages 2.290 and 2.003 seconds.
The diagnostic replay failed at the same read with age 2.112 seconds.
The developer authorized continued investigation through `perf-005`.

The third replay is retained under
`/home/shawn/workspace2/task-manager-artifacts/macos-performance/summary-fix-timing-20260908T204000Z`.
Its stale-frame receipt has sequence 111, accepted at 1788900026037332097 ns,
checked at 1788900028148957829 ns. Writer sequence 112 began acceptance at
112016760089 ns after its clock origin and completed atomic publication at
112423896599 ns. The origin wall-clock bracket is
1788899915726830281–1788899915726831356 ns. Publication therefore completed
about 1.77 ms after the failing read. JSON conversion took 128.76 ms and
serialization 209.89 ms. The worker queue had no overwritten records; file
replacement itself took under one millisecond. These observations identify
writer work as a contributor, not proof that all scheduling delays are solved.

The proposed direct serializer preserves the decoded JSON payload, atomic
replacement and strict two-second freshness check. Skipped conversion timing
fields remain null. No acceptance pass is claimed until the checks run.

Application checks passed: 126 tests, strict Clippy, formatting and debug build.
The direct-publication regression covers decoded equivalence, maximum u64
counters, non-finite JSON nulls and Unicode labels. Existing writer failure
and timing tests passed. Native replay remains pending.

Ripwire edit-check found no incompatible caller. Its definition-count warning
mixes same-named reference symbols. Repository-wide quality-delta exited 2
with reference-tree inventory changes; test-gate exited 4 with unmodelled
script gates and broad existing coverage findings. Neither is claimed as a
passing check. Full output is retained in the adjacent external artifact
directory `direct-json-review/`.
