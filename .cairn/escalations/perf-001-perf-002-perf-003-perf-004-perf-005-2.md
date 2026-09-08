DECISION

Question:   Authorize the bounded native-process-query proposal in docs/execution/macos-performance/native-process-query-proposal.md?
Recommend:  Probe combined fresh BSD/task reads; extend the sysinfo patch only if measured savings and preserved semantics support it.
Because:    Summary improved 25.26% and tray 33.86%, below 50%. Four complete comparisons missed both CPU targets; preservation passes do not satisfy them.
If wrong:   Combined reads could alter permission failures or PID-reuse handling; the probe, focused tests and unchanged native gates must reject that.
Instead:    Retain the verified presentation changes with both CPU targets open; do not lower the targets or claim completion.

Reply: ok | instead | ask. If this isn't clear, ask me to explain it another way before you decide.

Concerns: PERF-001 PERF-002 PERF-003 PERF-004 PERF-005
Status: open
Raised: 2026-09-08T15:49:39.068Z
Raised after: PERF-001=9 PERF-002=9 PERF-003=9 PERF-004=9 PERF-005=9
Answer: instead Investigate and fix the missing CPU processes reported during the release smoke test first. The proposed native-process-query extension is not approved.
Answered: 2026-09-08T20:15:37.382Z
Answered after: PERF-001=9 PERF-002=9 PERF-003=9 PERF-004=9 PERF-005=9
Answered order: 4
