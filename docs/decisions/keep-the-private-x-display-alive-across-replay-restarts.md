# Keep the private X display alive across replay restarts

Level: Judged
Decided by: agent
Rests on: PERF-005
Would be wrong if: The private display survives wrapper cleanup, changes application recovery semantics, or another startup reset occurs despite disabling automatic resets.

## Decision

The replacement Linux run passed device and process checks but an Xlib connection setup failed during recovery. Xvfb currently resets when its last client closes, and its diagnostics are discarded. An isolated 100-connection probe observed 99 display resets under the existing flags and zero with -noreset; neither probe reproduced the connection error, so the specific failure cause remains an inference. Keep the owned display running across application restarts with -noreset and retain Xvfb stderr in the existing bounded session log. xvfb-run continues to own and terminate the server when the entire replay exits. Preserve all application freshness, recovery and shutdown assertions.

## Realized by

(none yet: recorded, not built)
