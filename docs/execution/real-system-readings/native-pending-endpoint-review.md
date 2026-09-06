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
