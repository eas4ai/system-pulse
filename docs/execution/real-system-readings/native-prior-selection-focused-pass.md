# Fresh focused process replay after prior-selection reviews

The untraced focused replay against `243f2eaea4c177ccc3f2c9f2f4b817bd4ccfb593` finished
**PASS**, with all sixteen controlled-child metric comparisons and controlled
exit. The [record](native-prior-selection-focused-pass.json) retains all 138 artifact
hashes, metadata, metrics, held-input summaries, child termination, recovery
journal and cleanup. Artifacts: `/home/shawn/workspace2/task-manager-artifacts/tmp/pulse-navigation-observation-ahs5so4_/native`.

The file and running-executable SHA-256 both match
`7dbcd3adfae54db64e3ed5f32cf728ee55684fd1429c95c1bbd1e72a770340e7`. Application PID 1674159 and private transport
PID 1674053 both exited zero and no longer existed, with no forced transport kill.
This is supporting focused verification; full committed acceptance remains open.

## Process and recovery evidence

Child `process:1681776:75673924` matched independent stat/name/UID/I/O observations.
Eight initial cell comparisons, left, six visible columns and right all completed.
Fresh exact selected-child proof preceded shutdown. The native tree and snapshot
then acknowledged exit, and the independently retained terminal stat returned
ENOENT. The child exited with the expected termination signal.

There were 118 arrow batches and 117 independent baseline-stat receipts. No
navigation recovery or interrupted-batch event occurred; this pass does not
measure intermediate recovery timing or prove that the previous failure would
have recovered. Failed captures retain their original outcomes.

Cell inspection did exercise nonselecting recovery after the child's index moved
from 1181 to 1180, outside span 1181–1189. Two upward wheel inputs were followed
by fresh exact selected-child proof in span 1175–1184, then successful metric
comparisons. That operation used the existing fifteen-second discovery deadline
756830.323434986. It does not constitute measured five-second recovery proof.

## Held and exact-input observations

All four observers joined and retained at least three accepted sequences under
the unchanged two-second freshness limit. Exact 64 Up matched the expected
PID/start identity `process:3464898:73972247` after all 64 keys.

| Artifact | Observations | Maximum age seconds |
| --- | ---: | ---: |
| held-up-25hz.json | 53 | 1.322868924 |
| exact-64-up.json | 23 | 1.253748899 |
| held-table-left.json | 64 | 1.576762276 |
| held-table-right.json | 54 | 1.276288882 |

Launch, two-GPU metrics, collapse, two GPU temperature charts and inner scrolling
also passed. Full aggregate acceptance and final independent review remain
required. NVIDIA hardware accuracy, macOS/Windows native behavior and physical
device removal retain their stated verification limits.
