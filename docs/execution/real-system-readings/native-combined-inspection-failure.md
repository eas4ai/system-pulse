# Combined diagnostic: inspection recovery deadline

The combined publication/navigation diagnostic against `36c308161f10de30fd7db0f3dfd89e66824e5457`
finished **FAIL**. It is instrumented supporting evidence, not acceptance.
The [record](native-combined-inspection-failure.json) retains all 130 artifact
hashes, complete bounded publication history, metric coverage, final journal,
metadata and cleanup. Artifacts: `/home/shawn/workspace2/task-manager-artifacts/tmp/pulse-publication-diagnostic-poelu223/native`.

The file and running executable SHA-256 match `7dbcd3adfae54db64e3ed5f32cf728ee55684fd1429c95c1bbd1e72a770340e7`.
Application PID 1243229 was terminated in cleanup and no longer existed. Private
transport PID 1243195 exited zero without forced kill and no longer existed.

## Native outcome

Launch, metrics (two GPUs), collapse, charts (two GPU temperatures), and inner
scrolling passed. Held-input artifacts exist but the enclosing case was not
finally marked PASS. Navigation reached child `process:1251996:75193351`.
Thirteen of sixteen child metric artifacts were retained: eight initial cells,
left, and visible columns one through four. Visible columns five and six,
right and controlled exit did not complete.

The five-second visible-column-five inspection deadline was
752040.717823216. Missing-row preparation established the exact child had moved
from the last successful metric reference at index 1144 (sequence 194) to index
1143 (sequence 197), outside instantiated span 1144–1152. Nonselecting Up wheel
inputs were journaled after reveal events at 752039055110574 and 752039308456227.
Those reveal events occurred 3.337287 and
3.590633 seconds into the original five-second
budget, leaving 1.662713 and
1.409367 seconds. Both events retained the same
sequence and span. The later strict selection walk exhausted that deadline.
No new deadline, exact selection acknowledgement or successful metric followed.

The screenshot timestamp is 752040746972796, approximately 29 ms after the
deadline. It shows the child partly clipped beneath the table header. The later
failure frame, sequence 199/revision 198, retains that exact child at index 1138.
These later observations do not establish selection or complete row visibility
at the deadline. Independent source/evidence diagnosis is pending.

No stale-frame receipt was generated. No navigation-failure history exists:
the active Navigate operation had already completed before this inspection.
The added history is scoped to that operation, not later metric preparation.

## Publication timing

The final sidecar retains 64 published records, sequences 136–199, after 198
submissions/dequeues and 134 evictions. There were zero pending overwrites,
sidecar errors, primary errors or timing errors. Every retained stage is complete.

| Stage | Median ms | Maximum ms |
| --- | ---: | ---: |
| model | 22.273008 | 29.195751 |
| construction | 6.658848 | 9.645413 |
| queue | 0.015527 | 0.205911 |
| json conversion | 85.312478 | 116.362611 |
| serialization | 101.376151 | 114.007147 |
| temporary write | 1.298957 | 1.673646 |
| rename | 0.360707 | 8.893318 |
| acceptance to rename | 218.624425 | 248.065261 |

Durations use the writer's own monotonic offsets. Harness and writer clock
origins are distinct and are retained separately. This run does not reproduce
or explain the previous stale-frame failure. Complete publication records do
not identify the cause of the inspection's native scan timeout. Instrumentation
and bounded retention limit inference. No performance remedy or acceptance
relaxation is inferred; fresh untraced full acceptance and final review remain
required.
