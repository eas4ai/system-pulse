# Deferred presentation: measured result

Status: Normal-launch UI regression reported after these checks. This candidate
is not preservation-complete and its CPU observations do not establish an
improvement with all required Summary content present.

The developer's release smoke test found an empty Top CPU processes card.
Diagnostics prepared process rows eagerly and masked the omission in native
preservation. The normal Summary path failed to prepare its visible rows.
See [the regression record](summary-process-regression.md). The records below
retain what ran; their passing exits did not detect this defect.

The locked release from `6b25bd585e0a119c7f740d6a14c4a9feca9278b1` has SHA-256
`b121b338adf6e9477b2035644af6119de3f38080a09dcabf1cf00599ba3c4bcf`.
It prepares process rows when displayed or inspected through diagnostics,
reconciles selection from raw identities, and refreshes the active screen.
Hidden-window collection and all monitored histories continue at one second.
Opening Processes uses the latest snapshot and its actual age.

## Complete native comparison

All twelve replacement observations passed the fixed comparability checks.
Each retained its native CPU counters, warmup, duration, process and binary
identity, one-second interval, window state and alternating pair order.
No compiler, profiler or diagnostic writer ran during the scored windows.

| Mode | Reference CPU | Candidate CPU | Candidate/reference | Reduction | Gate |
| --- | ---: | ---: | ---: | ---: | --- |
| Summary | 12.553058% | 9.382416% | 0.747421 | 25.2579% | FAIL |
| Tray only | 11.127433% | 7.359382% | 0.661373 | 33.8627% | FAIL |

CPU percentages use one logical CPU as 100 percent. These reductions are
relative to the agreed original reference, not attributable solely to this
presentation change. Both required ratios remain above 0.5.
The preceding collector comparison remains in `evidence/prior-4c9c03c-20260908/`.

The first set stopped when the candidate exited during its first scored window.
The app log was empty and no crash report appeared. The native AppKit log shows
a menu action followed by approved, orderly termination at 11:22:30 local time.
That explains the observed exit path, but does not identify who invoked it.
The interrupted receipt and bounded exit log remain under `evidence/invalid/`;
none of that set was included in the replacement comparison.

## Preservation and checks

- Application, model and collector tests passed on Linux and Mac. New tests
  cover deferred rows, immediate screen activation, PID reuse/removal, selected
  identities, failed/stale readings, closed-window history and reopening.
- Formatting, strict Clippy and the locked release build passed.
- Full Linux acceptance passed preservation, input focus, package creation,
  native packaged application replay, tray behavior and isolated installation.
- Native Mac preservation passed coverage and fresh filesystem arithmetic,
  background sampling/history, settings, close/reopen and orderly Quit.
- The existing physical-device-removal limitation remains: recovery tests are
  controlled tests, not a claim of physical Mac GPU removal.

## Separate CPU profiles

Fifteen-second Time Profiler captures followed thirty-second warmups. Their
running-stack weights locate cost; only the paired observations decide the gate.
Inclusive costs overlap and must not be added.

| Sampled CPU | Summary | Tray |
| --- | ---: | ---: |
| All threads | 1,448 ms | 1,156 ms |
| Collector thread | 815 ms | 862 ms |
| Main thread | 511 ms | 255 ms |
| Process refresh, inclusive | 280 ms | 287 ms |
| Snapshot delivery, inclusive | 82 ms | 90 ms |
| LiveState acceptance, inclusive | 16 ms | 17 ms |

Neither profile contains a process-row formatting sample. The collector remains
the largest tray cost. Sysinfo process refresh includes separate fresh BSD
identity, thread, task and disk calls. This observation does not establish that
combining calls preserves permissions, identity races or failed-read semantics,
or that it would reach 50 percent. No further dependency change is implemented.

## Evidence and interim audit

Current gate receipts are in `evidence/`. Full Linux/native artifacts, raw traces,
exported XML and parsed stacks remain under
`/home/shawn/workspace2/task-manager-artifacts/macos-performance/`:
`linux-presentation-20260908T151500Z`,
`preserve-presentation-20260908T151500Z`,
`paired-presentation-retry-20260908T152600Z`, and
`cpu-profile-presentation-{summary,tray}-20260908T151500Z`.
Native originals remain in the Mac performance artifact directory.

Ripwire quality checks completed after extracting the legacy-panel refresh
helper. Remaining findings included constructor/test size and unconnected Rust
symbols. Its test gate returned 4 because the Rust test map was unmodeled;
this is not a test-gate pass. The actual Rust and native checks above passed.

The interim production audit checked scope, retained histories, identity and
age handling, bounded cached presentation, diagnostic provenance, tests and
honest evidence. This is not final acceptance, installation or publication:
two required performance checks fail. The final commitment review remains due
only after all requirements pass.
