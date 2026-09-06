# Final navigation selection failure

Fresh untraced focused capture `pulse-process-lookup-lhicc91e/native` failed
at source `0cf236c2fedb7cd0895c6089f2b237465d2b58af`. The application and
executed binary hashes match the retained metadata. Artifact paths, hashes,
publication, input, and cleanup evidence are in the [capture record](native-final-selection-failure.json).

Launch, live metrics, collapse, charts, and inner scrolling passed. Retained
held-input artifacts include signed vertical/horizontal movement, the exact
64-Up endpoint, and joined observers. The controlled child appeared as
PID/start `3472632:73981302`. Its cell inspection and exit were not reached.

The final two-Up batch recorded endpoint index 1310 at sequence 109.
Intermediate selection acknowledged the exact child at monotonic
739831.693995592. Final confirmation exhausted its deadline at
739839.697177532 while discovering the unique current Processes panel.
The failure frame at sequence 117/revision 116 retains the same child at
index 1309. The screenshot starts with PID 3473422, which maps to index
1310 in that frame. No key, wheel, recovery, or stale-frame artifact follows
the intermediate acknowledgement; only the failure screenshot is journaled.

The stack locates the failure in the final navigation_selection call from
_navigate. Unlike the batch and reconciliation calls, it does not pass the
retained key-issued endpoint_index. This source omission prevents that call
from using the existing bounded displacement preparation. It is consistent
with the retained one-row displacement, but individual failed observations
and discovery durations were not captured. Neither an incomplete tree on
every retry nor the exact time spent in each operation is established.

The run remains FAIL. The application and private transport exited and
their PIDs no longer existed at cleanup. No change to production selection
or viewport behavior is justified by this capture. Independent source and
contract assessment precedes any verifier correction; existing freshness,
final uniqueness, exact identity, and deadline requirements remain intact.
