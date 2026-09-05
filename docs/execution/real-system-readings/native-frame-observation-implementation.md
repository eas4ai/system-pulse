# Native frame read observations

Implemented the [retained freshness observations decision](../../decisions/retain-stale-frame-read-identity-and-timing.md)
against base `3c2cc78b`. Independent SPEC and QUALITY review remain pending.

## Behavior

[`Native.frame`](../../../scripts/system-pulse/native_driver.py) opens the
diagnostic pathname once and reads its contents once. It records monotonic
nanosecond timestamps before opening, after reading, after parsing, and just
before the existing wall-clock age calculation. The opened descriptor stays
open through parsing and `fstat`; it closes before the pathname `stat`.
The pathname observation finishes before the age-check timestamps and validation.

The existing stale-frame artifact retains `checked_unix_ns`, `age_seconds`,
`limit_seconds`, and the original `frame`, including its acceptance time,
sequence, and render revision. The new `observation` object contains:

| Field | Observation |
| --- | --- |
| `read_started_monotonic_ns` | Before opening the diagnostic file. |
| `read_completed_monotonic_ns` | After the one content read, before JSON parsing. |
| `parse_completed_monotonic_ns` | After JSON parsing, before descriptor metadata. |
| `age_checked_monotonic_ns` | After pathname metadata, immediately before the existing wall-clock check. |
| `opened_file` | `device` and `inode` from the opened descriptor's `fstat`. |
| `pathname_before_check` | `device` and `inode` from the pathname's subsequent `stat`. |
| `errors` | Metadata field names mapped to exception type and message. |

Unavailable metadata fields are null. Timing and identity exceptions are caught
only around metadata collection and retained in `errors`. The stale artifact
uses `age_checked_monotonic_ns` in its filename. If that observation clock call
failed, it uses the existing `checked_unix_ns` instead; this prevents a clock
failure from replacing the stale assertion while naming the artifact.

The original age formula, interval-derived bound, PID failure priority, fresh
return value, and stale assertion remain in place. Fresh frames return without
an artifact, and wrong-PID frames still fail before saving a stale artifact.
Real open, read, JSON parse, wall-clock, and artifact-write errors retain their
failure behavior. There is no additional frame read, retry, or wait.

## Verification

The new frame tests ran against the original reader first: 8 tests produced
5 expected failing assertions, covering absent observations and a diagnostic
clock failure that replaced the stale verdict. After implementation, all
8 passed. The 72 existing navigation tests also passed; their only change is
the file-like open/read fixture and the metadata globals it supplies.

Final checks used the shared artifact temporary directory:

```sh
rtk proxy env TMPDIR=/home/shawn/workspace2/task-manager-artifacts/tmp /home/linuxbrew/.linuxbrew/opt/python@3.14/bin/python3.14 -B -m unittest discover -s scripts/system-pulse -p 'test_native*.py'
rtk proxy env TMPDIR=/home/shawn/workspace2/task-manager-artifacts/tmp /home/linuxbrew/.linuxbrew/opt/python@3.14/bin/python3.14 -B -m unittest discover -s scripts/system-pulse -p 'test_*.py'
rtk proxy ruff check scripts/system-pulse/native_driver.py scripts/system-pulse/test_native_frame.py scripts/system-pulse/test_native_navigation.py
rtk proxy ruff format --check scripts/system-pulse/native_driver.py scripts/system-pulse/test_native_frame.py scripts/system-pulse/test_native_navigation.py
rtk git diff --check
```

Results: 175 native tests passed; all 279 Python tests passed. Ruff lint,
formatting, and whitespace checks passed. The frame tests cover ordered timing,
one open/read, three sampling intervals and their exact freshness boundaries,
future timestamps, PID precedence, metadata failures, and real read/parse errors.
Atomic replacement during the read and during parsing uses actual temporary
files. Both cases retain distinct opened/pathname inode identities before the
wall-clock check and still reject the originally read stale frame.

## Limits and self-audit

These are controlled fixture observations. No native capture, Rust build, or
live acceptance ran for this change. The earlier 2.019802319-second rejection
still has no observed cause. Matching inode identities cannot prove publication
stalled, and differing identities alone cannot establish when acceptance
occurred. Metadata collection adds work before the original wall-clock age
check; the recorded stages expose that elapsed interval without relaxing its
bound.

Reviewed all 14 production rules. The change is confined to frame observation,
its tests, and this note. Metadata failures remain explicit, the descriptor
closes on failure, and the original validation contracts remain intact. No
known implementation defect remains from this self-audit. Independent review
and the next actual acceptance observation remain separate work.
