# Cairn reporting adapter review

Candidate `a3db8b2668d04b379ea230c6467774b95b40e537` received SPEC PASS:
22 focused tests, 114 isolated artifact deletions, a manifest-write fault and
read-only retained-failure interpretation. Original full-run artifact obligations
remain covered. No retained evidence was modified.

QUALITY found two defects, so the candidate is not accepted:

1. JSON `false` and `0.0` exit codes compared equal to integer zero. Invalid or
missing cleanup PIDs also earned native passes. Require integer exit codes and
positive integer PIDs, and bind app cleanup PID to session metadata.
2. Deeply nested native JSON raised `RecursionError` during partial reporting,
replacing the original aggregate exception and suppressing earned host verdicts.
Treat invalid secondary evidence locally, retain the original failure and report
only the independently validated host group.

The worker is adding RED/GREEN regressions and narrow fixes. Independent SPEC
and QUALITY re-review and the full live aggregate remain pending.

## Corrected candidate

Source `5da24b21ddc6a9e8da69e39c9f22b6cc76de6bdd` resolves both findings.
Worker verification: 27 focused and 78 total Python tests passed, plus format
and diff checks. SPEC re-review independently passed 27 focused tests, retained
ten-pass interpretation with original aggregate failure, and the scoped diff.
QUALITY re-review independently passed 27 focused tests and 28 isolated probes,
including both original reproductions, malformed scalar/PID cases, session PID
binding, transport fields, original exception preservation and valid controls.
Both reviewers report cumulative PASS with no remaining scoped findings.

Fresh full host/native aggregate acceptance remains pending; these reviews and
retained-run probes do not substitute for it.
