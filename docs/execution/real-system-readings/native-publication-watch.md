# Publication timing and panel discovery observations

The bounded diagnostic-only capture retained 795 frame reads and 1,229
thread/file polls. Read plus parse time had median 25.397 ms, p95 36.808 ms,
and maximum 57.869 ms. Checked acceptance age never exceeded 1.660481
seconds. Thirty reads observed an inode replacement before the final path
check; none caused a freshness failure. No substantial observer scheduling
gap or observer read error was recorded.

Five startup polls found the first published revision aged 2.030–2.430
seconds. The main thread was busy, the diagnostic thread slept, and the
collector continued. The harness made no frame checks during that interval.
This shows a startup acceptance/delivery gap, without identifying the main
thread's work. Later published ages stayed below 1.566 seconds. A single
sampled diagnostic rename waited on a buffer and completed by the next
poll, without breaching freshness. These observations do not explain
either earlier stale frame, and do not validate the fsync hypothesis.

The run instead failed during process-cell panel discovery. The current
helper's full application walk, despite pruning process cells, exhausted
its original 15-second deadline. The frame described 151 monitors and
1,350 processes. Current panel membership must remain verified, but finding
a panel does not require visiting its sensor or process contents.

Actual retained native ancestry is application, frame, workspace:viewport,
named monitor panel, monitor-id:viewport, then its contents. Both monitor
and body viewport have native role `panel` in the pinned adapter. During
panel discovery, a viewport matching its traversed named parent monitor
can be pruned while keeping layout and sibling panels visible. See
[the decision](../../decisions/discover-panels-without-traversing-monitor-bodies.md).

The capture is not acceptance evidence; instrumentation changes scheduling.
Sampling can miss short stalls. See [artifact hashes](native-publication-watch.json).
