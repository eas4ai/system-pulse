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
