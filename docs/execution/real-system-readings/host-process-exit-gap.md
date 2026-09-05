# Independent observation of exiting processes

The run against `95af71831a34eea84b8b8c5fa0673a9a378e305b` passed 459 automated tests, formatting, Clippy, and builds. Host verification retained 43,118 counter brackets, 468 stable totals, 2,217 exact readings, 17,313 process field checks, and 96 interface comparisons, but six mandatory counter brackets were missing. Native replay did not start. The capture remains FAIL.

Two independent diagnoses distinguish the missing observations:

- `1798219:69722748` existed in the first ordinary census. It never entered the supplemental candidate set, which admits PIDs absent from the current ordinary census. Its four missing endpoints expose that admission limit. The earlier retention repair applies only after admission.
- `1803234:69723096` was admitted and retained. Its last successful independent stat read ended about 6.893 ms before the collector query. The next independent attempt began about 13.087 ms after that query and returned ENOENT. The process exited between observations, so retention worked but no successful later counter observation existed.

An admission change alone cannot resolve the second case. Faster independent sampling cannot guarantee a successful observation after every uncontrolled process's final read. Neither exit nor a matching earlier value proves a later counter value. No counter is inferred, no comparison bound is relaxed, and no old failure is reclassified.

[The compact record](host-process-exit-gap.json) preserves original query windows, independent successful windows, result counts and artifact hashes. The next acceptance decision must address this observation limit explicitly. The reporting repair alone does not close it.
