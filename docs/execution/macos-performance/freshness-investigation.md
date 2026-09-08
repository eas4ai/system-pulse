# Linux diagnostic freshness investigation

Status: In progress.

- [x] Complete: remove intermediate diagnostic JSON allocation and verify payload, failure handling and native publication timing.
- [ ] In progress: run complete Linux acceptance and record committed evidence.
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

The direct-serialization native replay passed and `validate_tabbed` validated
all 52 required artifacts, including normal shutdown and cleanup. No stale
frame receipts were recorded. Evidence: external artifact directory
`direct-json-native-20260908T205500Z/`. The last 64 retained publications had
median serialization 131.817 ms and maximum 152.560 ms. The earlier retained
63-publication window had median conversion-plus-serialization 268.095 ms
and maximum 360.490 ms. These debug diagnostic observations are not scored
Mac CPU measurements. The full Linux package gate remains pending.

## Complete Linux run follow-up

The first full run, `linux-direct-json-20260908T205500Z/`, passed
1,024 preservation tests, host checks, the complete native replay and
ten input-focus tests. Packaging stopped because the invocation omitted
the pinned `cargo-about` path. The tool is present at
`task-manager-artifacts/finish-application/tools/bin/cargo-about` and reports
version 0.9.2. This failed aggregate receipt is retained unchanged.

The replacement with the tool path,
`linux-direct-json-tool-path-20260908T210000Z/`, passed automated and host
checks and the native device, process-action, settings, minimum-window and
restart cases. During recovery, opening the next X connection failed with
`ConnectionClosedError: ... Connection reset by peer`. It recorded no
stale-frame failure. Xvfb errors were previously discarded by its wrapper.

An independent probe made 100 successive connections: the default Xvfb
configuration reset display properties 99 times, while `-noreset` preserved
them throughout. Neither probe reproduced the connection error; reset as
the cause of that particular failure remains an inference. The private
session now keeps Xvfb alive across application restarts and directs its
stderr into the existing session log. The wrapper still terminates the
owned server at overall session exit.

A real private-session regression test failed under the old flags because
the display lost its marker between connections, then passed with the new
flags. Both existing exit/output transport tests also passed. Probe receipts
and command analysis are retained under `xvfb-reconnect-probe/`.

All 493 Python verification tests passed after the display-lifetime change.
Ripwire found the private-session call contract unchanged, with no
incompatible caller. Complete native/package acceptance remains pending.
