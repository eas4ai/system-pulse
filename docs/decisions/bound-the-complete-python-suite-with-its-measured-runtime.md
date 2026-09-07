# Bound the complete Python suite with its measured runtime

Level: Judged
Decided by: agent
Rests on: GPU-007 and GPU-009 require complete preservation and rejection of missing tests; the expanded 444-test suite has two retained successful durations above the old aggregate 30-second limit.
Would be wrong if: The change skips tests, weakens failure detection, relaxes native freshness or comparison bounds, or leaves the automated stage without a finite deadline.

## Decision

Correct the runner budget mismatch recorded in docs/execution/intel-and-apple-gpus/linux-python-budget-finding.md. Increase only the aggregate full Python suite execution deadline from 30 to 60 seconds, above measured successful durations 34.043 and 34.240 seconds. Preserve exact discovery, all mandatory tests, nonempty-count validation, child cleanup and failure propagation. Leave every individual test/native-operation deadline and the two-second freshness limit unchanged. Retain the failed aggregate and supporting timing run; verify the complete Python stage through the actual Runner after the change. Use independent specification review followed by independent quality review, then rerun full uninstrumented preservation. This does not attribute or clear original native failures or missing hardware evidence.

## Realized by

- 61e8ceef4db8ce4c6f3114cc25437f9cd9ad3e5a fix: allow the complete Python suite a measured execution budget
