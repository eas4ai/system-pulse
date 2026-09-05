# Repeated cell discovery exhausts a scroll gesture

Untraced candidate `a0458736` passed launch, metrics, collapse, charts,
inner scrolling, all eight initial process-cell comparisons, and visible
columns zero through four. Panel discovery now completes in roughly one
second. Column five requires three Right movements. The visibility helper
repeats full membership discovery before every visibility and movement
poll, exhausting the original five-second gesture deadline.

Retained journal shows Right events at monotonic 709487017, 709488929, and
709490836 ms. Repeated lookups consume roughly 0.8–1.0 seconds each. The
final lookup expires while checking movement. Artifact root:
`/home/shawn/workspace2/task-manager-artifacts/tmp/pulse-process-lookup-gq69tkie/native`.
The failed result remains unchanged. No freshness failure occurred in this run.

The visibility gesture can retain its initially verified live cell and
reacquire on replacement under the same absolute deadline. The separate
final metric call still performs fresh current-tree membership, uniqueness,
value, frame, and clipping verification. Reuse during movement must not
turn a stale node into accepted metric evidence. Regression coverage will
include realistic lookup cost, replacement, wrong identity, slow bounds,
and exhaustion of the original deadline.
