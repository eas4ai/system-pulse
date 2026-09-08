# Collector reuse: measured result

Status: Verified preservation; performance targets still fail.

The locked native release from `4c9c03cb72844032fb469123ee9856572c483fb4`
has SHA-256 `e3946d9a126418e59c249e097805c2a680c1899d2aebdea9453263d170ef8c6f`.
It contains counter visitation stored with each baseline and bounded GPU HID
connection reuse. Every counter and temperature query still runs at the selected
one-second interval. Failed observations invalidate continuity.

## Fixed comparison

All twelve observations completed on the comparison MacBook. Each used the
unchanged warm-up, duration, alternating order, binary identity and window-state
checks. No profiler or diagnostic writer ran in a scored window.

| Mode | Reference CPU | Candidate CPU | Candidate/reference | Reduction | Gate |
| --- | ---: | ---: | ---: | ---: | --- |
| Summary | 12.639845% | 9.931880% | 0.785760 | 21.4240% | FAIL |
| Tray only | 11.087284% | 7.722946% | 0.696559 | 30.3441% | FAIL |

CPU percentages use one logical CPU as 100 percent. Both required ratios remain
above 0.5. These are total improvements over the agreed reference, not savings
attributed to this last change alone. The earlier guarded-sysinfo comparison is
retained under `evidence/prior-415bc41-20260908/`.

## Preservation

- Linux: 109 collector tests and 157 application/model tests passed; strict
  Clippy, formatting and the complete native/package application acceptance passed.
- Mac: application, model and collector tests, including all three new HID
  lifecycle tests, strict Clippy and the locked release build passed.
- Native Mac preservation passed: live coverage, filesystem arithmetic,
  background sampling/history, settings, close/reopen and orderly Quit.
- Controlled tests cover counter eviction/reappearance, failed baseline reads,
  changing HID values and identities, empty discovery, failed reads, reconnect
  and repeated connection failure without retained state.

This Mac has **no attributable GPU HID temperature service**, in both the
reference and candidate snapshots. Its two available GPU temperatures come from
SMC and change across the retained frames. The HID path therefore reconnects
after each empty attributable result. Its new reuse branch is tested but does
not provide an established saving on this host. No physical GPU removal was
performed; that limitation remains covered only by controlled lifecycle tests.

## Remaining cost

The separate 15-second tray Time Profiler recording sampled 1,154 ms of CPU:
836 ms on the collector thread and 273 ms on the main thread, with 64 ms lacking
a resolved stack. Inclusive stack weights include 309 ms in process refresh,
145 ms in Apple GPU collection, 62 ms in HID reading, 116 ms in snapshot delivery
and 42 ms in process-row presentation. These weights overlap and must not be
added. Sampling profiles locate work; the paired CPU observations decide the gate.

The application still formats process rows and updates panel state on snapshot
delivery even when the process screen is not displayed. A separate service
would not itself remove that work or the collector's native reads. Application
snapshot/presentation changes require an extension of the current source scope.

## Evidence and interim audit

Receipts for this revision are in `evidence/prior-4c9c03c-20260908/`; full native runs, trace/XML and Linux
acceptance artifacts are retained in
`/home/shawn/workspace2/task-manager-artifacts/macos-performance/`, under
`paired-hid-reuse-20260908T143000Z`, `cpu-profile-hid-reuse-20260908T143000Z`,
`preserve-hid-reuse-20260908T143000Z`, and `linux-hid-reuse-20260908T142400Z`.
The native Mac copies remain under its existing performance artifact directory.

Ripwire reported no existing-symbol quality regression. Its new-symbol findings
were the native types/trait dispatch and tests it did not connect, plus test-module
length. Its test gate returned 4 with an unmodeled Rust test map; the actual Rust
and native tests above ran and passed. This is not a claim that the Ripwire test
gate passed.

Reviewed the change against the production rules: bounded ownership, fresh
observations, unchanged public counter API, invalidation, failure recovery,
unrelated-file preservation and truthful evidence. The production acceptance
standard is not yet met because PERF-001 and PERF-002 fail. This is an interim
record, not delivery or the commitment's final adversarial review.
