# Review of visible endpoint during prior selection

Candidate: `a5a8908acf8892b50c98984e4f86f7fb1ad16b0d`.
Base: `826dca7b38386248245933141735e6c85fbc6e88`.
Scope: native driver condition, prior-selection regressions and
[implementation receipt](native-prior-visible-endpoint-implementation.md).
Contract: [Judged decision](../../decisions/defer-visible-endpoint-blocking-during-proven-prior-selection.md).

## SPEC

Independent reviewer `trace_publication` reported PASS with no findings.
The one-line change matches the bounded decision and adds no input or ACK path.
Separate visible-expected/no-selection blocking, existing blocks, irreversible
prefix expiry, fresh exact expected-selection proof, deadlines and default scopes
remain. All three reviewed files matched the committed candidate bytes.

The reviewer ran 20 prior-selection tests and the combined 126-test prior-selection,
navigation and pending-endpoint suite. Six additional probes changed each of the
four publication fields, introduced coherent absence, or introduced another selected
identity; every case permanently expired the prefix, even after restoring prior
state. All checks passed. No source edits, native session, build or Cairn operation
occurred during review.

## QUALITY

Independent reviewer `review_publication_quality` reported PASS with no findings.
Twenty focused tests passed. Four additional probes dropped both arrow deliveries
despite completed dispatch evidence, delivered only the first arrow, selected a
wrong row after reveal, or exposed duplicate selected endpoints. Lost deliveries
never produced an endpoint ACK; a one-arrow competitor permanently prevented
reveal. Scoped Ruff, two-file formatting, candidate whitespace, two receipt links
and exact candidate bytes for all three files passed. No edits, native session,
build or Cairn action occurred.

Root reviewed the complete source/test diff and found no additional issue. The
change alters only the initial prefix's new-block condition. Fresh focused/full
native acceptance and final commitment review remain pending.
