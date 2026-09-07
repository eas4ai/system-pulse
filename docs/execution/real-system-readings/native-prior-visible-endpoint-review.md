# Prior-selected prefix with visible unselected endpoint

Read-only diagnosis of the [full aggregate failure](native-prior-selection-full-failure.md)
against `cb4067242d958dac081523d89b92c35371b195be`. Root and independent reviewer
`trace_publication` inspected the retained observations and source without changing
code or running another native session.

## Finding

Observation 283 positively acknowledged `process:1944648:43459871` under publication
147, render revision 146 and acceptance time 1788672959016092927. Its row was the
fourth row in mapped span 1243–1251, so its actual index was 1246. The acknowledgement
capture searches the returned frame for that identity; it does not retain the
previous batch's old endpoint index 1241. The next two Up keys expected index 1244,
`process:1944646:43459871`, with the same complete publication tuple. The existing
prior-proof binding is consistent with those facts.

Observations 284 and 285 saw the exactly prior selected identity and an instantiated
unselected expected identity in a complete coherent span. The driver exempts the
prior-selected prefix only when expected is absent from native rows. Consequently,
its visible-expected clause set a new permanent block at observation 284. The
remaining observations saw no selected row after publication advanced. The block
prevented recovery qualification and the batch expired. This establishes the
branch responsible for blocking, not hidden model selection or successful recovery.

## Bounded correction

During the already proven initial prior-selected prefix, defer setting a new block
whether expected is instantiated or absent. A still-visible prior selection with
the destination present and unselected is consistent with the native tree before
keyboard processing. It adds no proof that the dispatched keys were processed.
The condition alone cannot justify treating the batch as permanently conflicting.

Keep exact prior positive ACK/issue/dispatch binding and expiry on any publication
advance, coherent absence or different selection. A deferred observation grants no
ACK or input and cannot clear an existing block. Outside this proven prefix, an
instantiated unselected expected row and every distinct competitor still block.

Later recovery must still show a fresh coherent complete unique span, no selection,
expected outside that span after reindexing, and original endpoint inside the span.
Fresh global discovery precedes physical input. After a nonselecting wheel, only
fresh exact selected expected proof can acknowledge. If the model never processed
the keys and the revealed expected row is unselected, the proof fails. Thus the
correction cannot turn missing key processing into a successful endpoint ACK.
Keep all original deadlines, final-target/inspection/pre-exit behavior, sixteen
mandatory child comparisons and controlled exit.

## Verification required

Reproduce prior selected with expected present, then coherent absence/reindex and
fresh exact expected selection. Cover persistent prior selection to timeout, lost
keys leaving expected unselected after reveal, absent/malformed prior proof,
expiry then recurrence, publication change, distinct competitors, an already set
block and journal/deadline failure. Preserve default-scope regressions. Independent
SPEC and QUALITY reviews must follow implementation before focused/full native
verification. No counterfactual recovery or full acceptance pass is claimed here.
