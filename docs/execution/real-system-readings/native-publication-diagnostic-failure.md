# Publication timing diagnostic: navigation deadline failure

The single instrumented process diagnostic against `b53a030e70878444e91500262a5d104ef77e3991`
finished **FAIL**. It is supporting diagnosis, not final acceptance. The previous
full aggregate remains FAIL. The [machine-readable record](native-publication-diagnostic-failure.json)
retains metadata, timings, outcomes and hashes for all 97 artifact files.

Artifacts: `/home/shawn/workspace2/task-manager-artifacts/tmp/pulse-publication-diagnostic-sjpr0a2l/native`. The application and running executable hashes both match
`7dbcd3adfae54db64e3ed5f32cf728ee55684fd1429c95c1bbd1e72a770340e7`. Application PID 415504 was terminated during cleanup
and no longer existed; private transport PID 415445 exited zero without forced kill.

## Observed publication timing

The last sidecar retains 64 published records, sequences 60–123. Its counters show
122 submissions and dequeues, 58 evictions, zero overwritten pending records and
zero sidecar errors. Every retained publication has complete observed stages,
with no primary or timing error. The ring does not retain every earlier attempt.

| Stage | Median ms | Maximum ms |
| --- | ---: | ---: |
| model | 22.308438 | 29.537268 |
| construction | 7.018086 | 8.944481 |
| submission | 0.004646 | 0.007693 |
| queue | 0.012634 | 0.854114 |
| json conversion | 88.424875 | 194.668286 |
| serialization | 103.380910 | 118.572909 |
| temporary write | 1.348988 | 2.515767 |
| rename | 0.391676 | 17.515506 |
| acceptance to rename | 227.372646 | 339.992596 |

These durations use the writer's own monotonic offsets. The original writer and
harness clock anchors are retained separately; no unrelated clocks were directly
subtracted. Consecutive retained acceptance intervals range from
717.733355 to 1260.431798 ms (median 1004.756273 ms).

This run retained no stale-frame receipt. Its complete retained stages do not
explain the prior 2.197-second-old observation, and they do not justify a source
performance change. Instrumentation and limited retention constrain inference.

## Native failure

Launch, metrics, collapse, charts and inner scrolling passed. Held Up, exact
64 Up, and horizontal held-input artifacts were retained with joined observers;
their enclosing case was not finally marked PASS. The controlled child
`process:426299:74791029` was independently observed after launch.

An intermediate two-Up batch issued at monotonic ns 747928841444139 expected
`process:3919203:65379799` at index 1392. A matching independent pre-dispatch
stat observation was retained. The last acknowledged identity was
`process:3919229:65379802`. No acknowledgement, terminal stat, interruption or
reveal event followed the failed batch. Its existing eight-second deadline
expired inside the strict accessibility selection scan: `native discovery
deadline exceeded; incomplete tree`.

The later failure frame is sequence 123/revision 122. It still contains the exact
expected identity at index 1383, the last acknowledged identity at 1385, and the
controlled child at 997. The screenshot taken after failure shows no highlighted
row, with PID 3919454 first visible. These later artifacts support reindexing and
continued endpoint presence; they do not prove endpoint exit or selection state
at the deadline. No child metric comparison or controlled exit proof completed.

Independent read-only navigation diagnosis is pending. All freshness, identity,
metric and deadline requirements remain unchanged. Fresh untraced full acceptance
and final review remain required.
