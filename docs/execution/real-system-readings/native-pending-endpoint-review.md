# Pending endpoint disappearance review

## Independent diagnosis

Source assessed: `6a23389228da70e46fa81481803a5ce63aaece9e`.
The [retained failed capture](native-pending-endpoint-failure.md) remains FAIL.
No implementation is authorized by this diagnosis alone.

SPEC found that existing decisions cover recovery after an acknowledged
selection disappears, or visibility recovery while an endpoint still
exists. Abandoning an unacknowledged endpoint is a distinct transition and
requires an explicit decision. Snapshot absence proves neither process
exit nor prior selection, model clearing, or successful keyboard input.

QUALITY reproduced the missing transition with actual navigate: End, Up,
Up targeted an intermediate PID/start that then disappeared from the
snapshot and instantiated rows while the controlled child survived.
Current code exhausted the original eight-second deadline without a
successful acknowledgement. A diagnostic reconcile=True shortcut returned
(None, frame, path), misleadingly journaled selected-endpoint acknowledgement,
then crashed when _navigate dereferenced selected[0]. It is not a correction.

The reviewer passed 76 existing navigation tests. Neither reviewer edited
source or ran a live app or build. Existing disappearance coverage starts
after acknowledgement and does not cover the new boundary.

Any continuation needs an explicit interrupted, unverified batch outcome,
frozen issue evidence, fresh coherent complete unique/current native proof,
no instantiated selected identity, and a surviving controlled target.
If classified as an exit, retain independent exact-identity terminal
evidence; never infer exit from snapshot absence. Home/End recovery and its
new exact endpoint proof must share the original remaining batch and total
deadlines. Final target proof and every mandatory comparison remain required.

Status: decision assessment pending. No batch disappearance counts as a
successful endpoint, and no new recovery source has been implemented.

## Prospective decision assessment

SPEC assessed the explicit interrupted/unverified protocol as a new Judged
verifier decision within the existing product contract. Transient intermediate
lifetimes need not survive navigation, but their missing acknowledgement
cannot be passed. Require an independent matching stat observation before
dispatch and terminal ENOENT/ESRCH evidence after coherent disappearance.
Only pending intermediate arrow batches qualify; the controlled target and
recovery endpoint do not. Predispatch disappearance sends no input and
replans within the original remaining deadline. All errors, PID reuse,
current-selection guards, final comparisons, and original budgets remain.

QUALITY source discovery identified host_capture.observe and
host_accuracy.parse_process_stat as reusable stat-only observation pieces.
The former preserves source, independent monotonic windows and actual errors;
the latter requires explicit retention of the literal stat text if needed.
Use driver-side query and dispatch times for ordering, not unmapped collector
clock values. Represent interruption explicitly and revalidate publication
and panel after terminal evidence. Do not reach a deadline reset until a
real exact endpoint acknowledgement succeeds.

Neither prospective assessment changed source or ran tests, live captures,
or builds. The new [decision](../../decisions/recover-a-pending-navigation-batch-after-proven-endpoint-exit.md)
is recorded before implementation; implementation and its reviews remain
pending. The original failed capture remains failed.

## First implementation specification review

Candidate: `69ac6897f49fef802f27a30999986343ec33d7d0`.
Status: open P1 terminal revalidation coherence finding. The complete SPEC
verdict found this one defect; corrective work follows this recorded review.

An independent actual-navigate probe used fresh one-second publications
and a synthetic 1.1-second full global discovery cost. Terminal revalidation
compares a current publication with the frame from before the terminal
read and a second full discovery. Each attempt therefore rejects otherwise
valid evidence. Three terminal ENOENT observations and seven discoveries
exhausted the original deadline without recovery. A zero-cost control passed.

Bracket a fresh complete native eligibility observation after the required
full discovery. Preserve independent terminal provenance, current uniqueness,
strict selection/membership checks, target survival, absence and reuse guards,
and original deadlines. Do not require the global discovery itself to fit
one collector publication or use helper microbenchmarks as end-to-end proof.
These costs are a synthetic reproduction, not measured native timings.

Independent verification passed 23 pending and 227 native tests, scoped Ruff
lint/format, and diff checks. Controls at 0.0 and 0.3 seconds per discovery
passed; the 1.1-second case failed with fixed per-publication acceptance
timestamps. No other finding was established. No source edits, live runs,
builds, or Cairn mutations occurred during review; the full Python suite
was not independently rerun.
