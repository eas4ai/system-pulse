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

## First quality review

Status: open Important performance finding. Inspection keeps fresh_panel
true after wheel dispatch and therefore repeats full panel discovery during
intermediate observations despite having validated local membership links.

An independent probe exercised the actual horizontal helper, recovery, and
subsequent ordinary cell lookup with explicit synthetic costs: 1.0 second
per ordinary discovery and 0.6 seconds per strict panel discovery. The
candidate used two ordinary scans and four strict discoveries, failing the
five-second deadline at 5.4 seconds. An in-memory correction using established
local links after dispatch used three strict discoveries and passed at 4.8
seconds. These costs are illustrative, not measured native timings.

Allow fresh_panel to force discovery until first dispatch completes, then
permit validated local links. Preserve required discovery for preparation,
final proof, missing paths, and invalid membership. Do not change deadlines
or independent metric proof.

The reviewer passed 196 native tests, scoped Ruff lint/format, and diff checks
on the candidate, plus integrated metric/recovery and success-path probes.
The in-memory correction passed 93 navigation/inspection regressions. No
source edit, live capture, build, or Cairn mutation occurred during review.
