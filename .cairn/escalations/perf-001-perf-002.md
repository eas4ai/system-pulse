DECISION

Question:   Extend the current commitment to permit the reviewed sysinfo process-refresh fix?
Recommend:  Approve the narrow dependency change described in docs/execution/macos-performance/process-refresh-proposal.md, then remeasure.
Because:    Summary CPU fell 14.5 percent and tray CPU fell 21.7 percent; profiling locates unnecessary process-argument reads in sysinfo, outside the collector-only scope.
If wrong:   Skipping a needed metadata read could break process freshness; the proposal requires targeted tests and native preservation before acceptance.
Instead:    Keep the verified improvements and the 50 percent target pending without changing the dependency.

Reply: ok | instead | ask. If this isn't clear, ask me to explain it another way before you decide.

Concerns: PERF-001 PERF-002
Status: open
Raised: 2026-09-08T13:13:26.518Z
Raised after: PERF-001=5 PERF-002=5
Answer: ok
Answered: 2026-09-08T13:30:05.260Z
Answered after: PERF-001=5 PERF-002=5
Answered order: 2
