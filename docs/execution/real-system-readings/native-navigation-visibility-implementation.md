# Native navigation endpoint visibility

Implements the Judged decision
`reveal-a-navigation-endpoint-shifted-outside-native-visibility` in the verifier.
Production behavior, held-input observation, generic discovery, strict exit,
and the independent cell metric checks are unchanged.

## Observation and physical recovery

Navigation retains the exact expected PID/start identity and its numeric index
from the snapshot used to issue each physical key batch, including Home/End.
The existing complete strict selection scan optionally collects the row IDs
and rows viewport it already visits. Recovery requires an unambiguous contiguous
mapping into the same fresh coherent frame, no instantiated selection, an absent
endpoint outside that span, a changed endpoint index, and the original numeric
index inside the current span. Unknown, duplicate, missing, or noncontiguous row
evidence cannot authorize a scroll. An observed different selection or an
instantiated unselected endpoint prevents that acknowledgement from using recovery.

Before authorizing the gesture, navigation rediscovers the unique current panel
and repeats eligibility against a fresh scan/frame. That eligibility record stays
fixed throughout the gesture; a span moved by our wheel is not reinterpreted as
new collection evidence. One physical vertical wheel step is issued per complete
observation. Its pointer lies in the intersection of the actual rows viewport,
native viewport ancestors, and private window. The existing ordinary parent/child
link validation is shared with the viewport ancestry and checked around geometry.
Workspace clipping evidence is required.

Intermediate wheel observations reuse validated local panel links. Invalidation
requires reacquisition. Once the exact selected endpoint fits vertically inside
the clipped viewport, success rediscovers the unique current panel and repeats
the complete selection/frame/vertical-visibility proof; retries of that final
proof also rediscover it. Horizontal row overflow is allowed here because the
separate per-cell metric checks retain their full horizontal and vertical clips.
No keys or selection-changing actions are issued by recovery. All discovery,
geometry, wheel steps, retries, and final proof share the original eight-second
batch and 180-second navigation deadlines.

The journal records `navigation-endpoint-reveal` with the immutable identity,
original/current indices, eligibility/current spans, eligibility publication,
physical point/direction, deadline, and explicit nonselecting action. A separate
`navigation-endpoint-reveal-proof` identifies the successful recovery proof.
These records do not claim keyboard-only visibility through process churn.

## Verification

RED: with the new argument accepted but the original observation behavior,
both shifted-endpoint success tests expired at the original deadline without
scrolling. GREEN adds 17 tests (with rejection subcases) to the existing 49
navigation tests, including the actual key-issue boundary, upward/downward
recovery, fractional vertical clipping, pre/post-scroll panel uniqueness,
identity loss/reuse, foreign or absent selection, incomplete/ambiguous spans,
stale/changing frames, detached viewport membership, and slow geometry/input.

The focused native suite passes 161 tests. The full Python suite passes 265
tests using the required Python 3.14 executable and workspace artifact TMPDIR.
Scoped Ruff lint/format and whitespace checks pass. No live session or build was
run. These deterministic checks prove the supported recovery protocol; they do
not establish the cause of the prior native timeout or its real-session timing.

## SPEC correction: discard rejected pre-scroll permission

The independent SPEC probe changed the snapshot during geometry acquisition:
the tentative endpoint moved from index 2 to its original index 5, while the
instantiated span moved from 5–7 to 8–10. The rejected observation incorrectly
left its old eligibility available for a later wheel. The exact probe and its
geometry-exception variant both reproduced false success before correction;
a duplicate-panel variant also demonstrated a wheel before renewed uniqueness.

Eligibility is now tentative until a physical wheel dispatch completes. Every
rejected or exceptional observation before that point discards the candidate
record and local path, requiring unique discovery and fresh eligibility again.
After dispatch, the established gesture keeps its original record across its
own scroll steps, under the unchanged deadline. The existing fractional-step
test verifies that intended reuse.

After this correction, 68 navigation, 163 focused native, and 267 full Python
tests pass. Scoped Ruff lint/format and `git diff --check` pass. No live run or
build was performed.

## QUALITY correction: include journals in the dispatch deadline

The independent QUALITY probe delayed either `navigation-endpoint-reveal` or
`wheel` journaling by eight seconds. The last observation guard preceded both
synchronous writes, so the real wheel method still emitted motion, press, and
release at 8.25 seconds despite the original deadline of eight seconds. RED
reproduced both delayed writes, including dispatch exactly at eight seconds.

Recovery now passes its original absolute deadline into `wheel`. An optional
keyword-only guard runs after wheel journaling, immediately before the first
XTest input. Both writes therefore count against the original budget. Generic
wheel callers retain their existing behavior. Once a permitted dispatch presses
the button, release and sync still complete if time expires. The existing
eight-second batch and 180-second navigation bounds, immutable recovery record,
multi-step reuse, unique final panel proof, and independent metric checks remain.

GREEN blocks every XTest event in both delayed-journal cases. Additional checks
cover successful dispatch and fresh proof after both writes consume time,
release cleanup after a slow press, and generic wheel input in both directions.
The 72 navigation, 167 focused native, and 271 full Python tests pass with
`/home/linuxbrew/.linuxbrew/opt/python@3.14/bin/python3.14 -B` and
`TMPDIR=/home/shawn/workspace2/task-manager-artifacts/tmp`. Scoped Ruff lint,
Ruff format checking, and `git diff --check` pass. No live capture, build, or
Cairn check was run for this correction.
