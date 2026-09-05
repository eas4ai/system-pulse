# Retain stale-frame read identity and timing

Level: Judged
Decided by: agent
Rests on: LIVE-013 requires retained evidence for unexplained verification differences. The recorded diagnostic measured age 2.019802319 seconds, but lacked read timing and inode identities to distinguish publication delay from an atomic replacement read.
Would be wrong if: Metadata changes the freshness or PID verdict, adds content reads or waits, swallows real read/parse errors, replaces the original verdict on metadata failure, or claims an unobserved cause.
History: The reversed navigation decision overstated what native absence proved. This decision applies that lesson by retaining direct observations before selecting a freshness remedy. The level is Judged because observation ordering affects interpretation; no retry, relaxed bound, or publication fix is inferred.

## Decision

Implement the recorded Retain freshness read identity and timing plan. Native.frame keeps one content read, records read start/completion, parse completion and check times, fstat identity of the opened file, and pathname identity immediately before age validation. Include these observations with the existing stale frame, sequence, acceptance time, age and limit. Preserve the existing fail-fast age calculation, PID check, error semantics and return value. Metadata-only errors are recorded without replacing the original verdict; real open/read/parse failures remain failures. No extra frame read, retry, wait, freshness recovery or change to production publication. Test stage order, one content read, unchanged fresh/stale/PID outcomes, metadata failures, and atomic replacement before validation that records different identities while still rejecting the stale frame. Review SPEC then QUALITY before actual acceptance. This gathers evidence and does not assert a cause for earlier failures.

## Realized by

(none yet: recorded, not built)
