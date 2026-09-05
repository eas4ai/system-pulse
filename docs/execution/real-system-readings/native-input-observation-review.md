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
