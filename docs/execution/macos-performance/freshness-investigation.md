# Linux diagnostic freshness investigation

Status: Linux and Mac preservation passed; final CPU comparison completed below target.

- [x] Complete: remove intermediate diagnostic JSON allocation and verify payload, failure handling and native publication timing.
- [x] Complete: run complete Linux acceptance and retain the committed-source receipt.
- [x] Complete: record the completed Mac comparison, committed gate results and the developer’s decision to stop optimization.
- [ ] In progress: record the authorized transition to process-table work.

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

The direct serializer preserves the decoded JSON payload, atomic
replacement and strict two-second freshness check. Skipped conversion timing
fields remain null. Native verification and its limits are recorded below.

Application checks passed: 126 tests, strict Clippy, formatting and debug build.
The direct-publication regression covers decoded equivalence, maximum u64
counters, non-finite JSON nulls and Unicode labels. Existing writer failure
and timing tests passed. Native replay results are recorded below.

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
Mac CPU measurements. The later complete Linux package run is recorded below.

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
incompatible caller. Complete acceptance results follow.

## Passing complete Linux acceptance

`linux-direct-json-persistent-display-20260908T211000Z/` passed against
`cf534f1fc322fe8693987cc7bf81ecec7fea35a2`: 1,025 preservation tests, ten
input-focus tests, host checks, complete debug and packaged native replays,
package provenance, tray behavior and isolated installation. All recovery
sessions completed normally. The source-matching receipt is retained in
[evidence/pending-cf534f1f](evidence/pending-cf534f1f/README.md).

The Mac candidate passed 222 application/model/collector tests, strict
Clippy and its locked release build. Its SHA-256 is
`c20f6dd276aa7a519098191416beceb86d2651257101c50e35bc546d8b6c50d0`.
The developer's smoke instance was left intact. Fresh native runtime and
paired CPU measurements await host availability.

## Interim source review

The direct serializer preserves decoded data and atomic publication; only
JSON field order and the absence of the intermediate conversion stage
change. Error reporting, bounded pending work, diagnostic opt-in behavior
and sampling remain intact. The private display remains authenticated and
TCP-disabled, with the wrapper owning shutdown and bounded log transport.
The new tests exercise payload edge cases and real display continuity.
No process privilege or column changes were implemented; those requests
are recorded in the backlog.

Final Ripwire quality-delta exited 2 with broad reference-tree findings.
Its default test gate saw a clean tree and no changed files; an explicit
touched-file test gate exited 4 with broad unresolved coverage mappings.
Neither establishes a clean static gate for this change. Actual Rust,
Python, host and native checks above passed. Full reports are retained
in the external `direct-json-final-review/` directory. This interim review
does not substitute for the final commitment review after all PERF gates pass.

## Final native comparison

The fresh `cf534f1fc322fe8693987cc7bf81ecec7fea35a2` candidate passed native
Mac preservation, including the ordinary UI without diagnostics. All twelve
paired CPU observations completed. Aggregate Summary CPU fell from 12.7801%
to 10.0064% of one CPU (21.7% reduction). Tray-only CPU fell from 11.0807%
to 7.3179% (34.0% reduction). Neither meets the unchanged 50% target.

The full current receipts are in [evidence](evidence/measurements.json).
The previous complete set remains in `evidence/prior-6b25bd5-20260908/`.
Raw run logs are retained in the external `paired-direct-json-20260908T213000Z/`
and `preserve-direct-json-20260908T213000Z/` artifact directories.
The coordinator restored the developer's original app and recorded successful
release of the owned wake assertions.

The developer agreed on 2026-09-08 to finish this running comparison and
stop further optimization, then move to the requested process-table work.
This is a stop decision, not a passing performance commitment or a lowered target.

The committed gate at `ef11de3e` ran all eleven verifier regression tests
and recorded passes for PERF-003 through PERF-006. PERF-001 and PERF-002
remain unverified in Cairn because their target checks did not pass; the
mechanism exited 1. The [stop decision](../../decisions/stop-mac-optimization-after-the-final-paired-comparison.md)
records the developer's agreement.
