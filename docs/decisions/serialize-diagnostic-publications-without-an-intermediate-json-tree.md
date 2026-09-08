# Serialize diagnostic publications without an intermediate JSON tree

Level: Judged
Decided by: agent
Rests on: PERF-003,PERF-005
Would be wrong if: Direct serialization changes the decoded diagnostic payload, loses publication failure handling, or fails to reduce the measured writer delay.

## Decision

The retained Linux timing replay shows sequence 112 accepted before the stale read but only atomically published about 1.8 ms afterward. JSON conversion and serialization consumed about 339 ms; no queue backlog or slow rename explains that attempt. Serialize the existing Publication directly into its JSON string, preserving every field and the atomic writer, error handling and strict freshness checks. Keep obsolete conversion timing fields null to describe an absent stage. Verify decoded payload equivalence, writer failure tests and native replay before claiming the failure fixed.

## Realized by

- 53b570cfc279d4df4fa030846bb5f6aadf242d2f Serialize diagnostic snapshots without an intermediate JSON tree

