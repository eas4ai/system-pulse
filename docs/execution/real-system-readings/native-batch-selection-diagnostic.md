# Bounded native selection diagnostic

This instrumented run is diagnostic only and remains FAIL. Six offline
scenarios preserved original native/frame query order, arguments, and
outcomes. Python instrumentation adds overhead. The 512-event in-memory
ring saved only on navigation failure; it retained 512 of 1,730 events
(19.63 seconds, polls 108–153), dropping 1,218 earlier events.

Independent review found 44 complete selection scans: 15 exact endpoints,
17 previous batch origins, and 12 with no instantiated selected row. Every
empty result placed the expected PID outside the first/last instantiated
row span. Expected and target identities remained in retained snapshots.
All 148 membership checks passed. Selection scans took 26.7–101.5 ms,
median 57.7 ms. Two incomplete scans triggered rediscovery lasting
2.292 and 2.308 seconds.

All retained absence episodes recovered. The longest lasted 3.382 seconds
and 2.897 seconds, each including rediscovery; other episodes took
0.209–0.666 seconds. There were 23 absent/different-selection retries and
six publication-coherence retries. Final poll 152 found no selection;
poll 153 acknowledged its endpoint 0.264 seconds later.

The run then stopped on accepted-frame age 2.020 seconds, exceeding the
unchanged two-second limit. That failure is separate from selection
retries. This trace does not reproduce the earlier eight-second timeout,
prove sustained viewport drift, or establish model selection loss. Its
truncated window and instrumentation limit causal claims.

The source permits identity-preserving viewport shifts, and the earlier
untraced capture places the expected row five indices above the viewport.
A narrowly gated nonselecting reveal is under contract review; no product
change or cause-specific fix is claimed here.
[Artifacts and hashes](native-batch-selection-diagnostic.json).
