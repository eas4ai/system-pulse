# Full native stale-frame investigation

Independent read-only SPEC investigation examined source capture `c5eae7ca`
and unchanged producer/reader files after the [failed full run](native-full-stale-frame-failure.md).
No source edits, tests, builds or new live runs formed this diagnosis.

The reader opened device/inode 66318/222692645, while the pathname referenced
66318/222692644 before validation. That directly proves replacement during
the observation. Read and parse took 3.802733 and 23.387523 milliseconds;
read start through age check took 27.697747 milliseconds. The frame was
already approximately 2.169439 seconds old at read start, assuming stable
wall/monotonic correspondence across that short window. No long parser pause
explains the 2.197136708-second age failure.

Failure occurred at the initial metric frame read for child-right, after
cell discovery and ancestor capture, before the sixteenth comparison. The
failure screenshot followed the age check by 177.885 milliseconds, and the
failure-frame file was read afterward. Its sequence 126 and the final latest
sequence 127 cannot identify the replacement inode's check-time contents;
late inode numbers may have been reused. Preserve this distinction.

For sequences 125–127, collection took 165.064, 170.003 and 177.418 milliseconds.
Acceptance followed collection completion by about 68.317, 69.150 and
65.983 milliseconds; acceptance intervals were 1005.846 and 1004.331
milliseconds. These samples do not demonstrate collector or pre-acceptance
UI lag. They do not measure later publication latency.

WorkspaceView::accept_snapshot timestamps acceptance before model/process
updates. WorkspaceView::publish_diagnostics then constructs rendered labels
synchronously. The bounded diagnostic worker later builds a JSON value,
serializes, writes a temporary file and atomically renames it. Transient
publication already omits fsync. The capture lacks stage timings across this
path, so it cannot assign the remaining delay to a particular stage.

The next bounded diagnostic is an opt-in publication timing ring in the
existing writer, retained by the harness. UI work adds only timestamp/memory
bookkeeping. Worker-only sidecar output must retain primary error semantics,
bounded history and partial failure records. Correlate PID/session, sequence,
revision, acceptance time, documented clock anchors, temporary inode and
construction/submission/dequeue/serialization/write/rename stages. Trace
failures and overwritten records remain explicit. Existing syscall tracing
can supplement a later ambiguity, but does not measure construction/queue
latency. Instrumented runs remain diagnostic; final acceptance is untraced.
