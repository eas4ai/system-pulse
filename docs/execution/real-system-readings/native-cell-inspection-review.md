# Controlled-child inspection review

## Connected pre-exit premise finding

Independent SPEC assessment reproduced two failures in the existing generic
acknowledgement used after three fresh sequences and before child shutdown.
This boundary is present at plan base `78b101b8`; the inspection worker left
it unchanged in the first candidate as instructed.

With a live detached cached selected child and a different selection in the
current panel, acknowledgement returned the cache without scanning current
selection or checking membership. With no usable cache and the exact child
shifted outside the instantiated span, it instead exhausted five seconds
without scrolling. Two independent offline probes reproduced these cases.

The later strict exit check cannot retrospectively prove that the live child
was selected immediately before stopping it. This demonstrates a missing
premise, not a complete false exit acceptance.

Status: open. Replace only this controlled-child pre-exit acknowledgement
with the inspection-owned strict exact-selection proof, using the frozen
last successful metric evidence and the same five-second deadline. Keep
generic/held acknowledgement, stop_child, and strict exit verification
unchanged. Permit only the recorded nonselecting displacement preparation.

No live capture, build, or repository mutation occurred during assessment.

## Implementation specification review

Candidates: `b7dd5553` and `adfd96a7`. Independent SPEC review passed with
no findings; the connected pre-exit premise finding is closed.

The reviewer verified acknowledgement capture from the existing coherent
proof, frozen caller-owned inspection evidence, and success-only reference
advancement. Preparation retains the caller's deadline, cannot supply a
cell, and requires independent strict eligibility and fresh selection proof.
All sixteen comparisons remain wired. Generic/held behaviour and strict
exit verification are unchanged.

Independent verification passed 21 inspection, 196 focused native, and
300 full Python tests, scoped Ruff lint/format, and whitespace checks.
Extra probes covered integrated lookup/recovery/metric validation, wrong
labels without reference advancement, displacement after three sequence
observations, detached-cache rejection, and eight malformed or foreign-session
evidence cases. No live capture or build ran. QUALITY review and actual
native/aggregate acceptance remain pending.
