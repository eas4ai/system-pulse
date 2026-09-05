# Held-input observation review

Candidate: `caa06d742df2739149e46547ad1bc8b83b7030a6`.

Independent SPEC and QUALITY PASS. Each ran all 133 focused native tests.
SPEC also ran three probes for observation ordering, failure during later
sequence waiting with retained evidence and cleanup, and late selection
results. QUALITY ran two error-handling probes. No scoped findings remain.

Movement and matching PID/start evidence precede subsequent collection
waiting under shared absolute deadlines. The publication observer, three
fresh sequences, signed movement, exact 64-key burst, exact endpoint
acknowledgement, and cleanup remain intact. The worker passed all 237
Python tests and Ruff lint/format checks. No live session or build ran.

The earlier diagnostic remains FAIL. Fresh native/full acceptance and the
separate model/native selection evidence correction remain outstanding.

## Actual sequence observations retained

Independent SPEC and QUALITY PASS on
`25fdc7025e216640f0627f3a5593eb3e1f007918`. Each ran all 144 native tests.
SPEC also challenged duplicate sequences, stale main-reader observations,
and distinct ages captured at each read. All passed. The worker ran all
248 Python tests and Ruff checks successfully.

Each existing main-thread sequence observation now retains its read-time
age. exercise appends those actual sequence/age records before stopping
the watcher, preserving every watcher record and error. No reads, waits,
deadlines, counts, or existing return fields were removed or changed.
The evidence-recording race is closed; the retained native run remains
FAIL, and fresh native/full acceptance remains outstanding.
