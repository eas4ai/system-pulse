# Mac performance review

## Contract review before implementation

Examined the six PERF requirements against the approved proposal: two separate mode targets, unchanged one-second readings and identity, cache failure/removal/recovery, continued interaction/history, and a verifier that rejects missing or manipulated data. The proposed mechanism records every repetition and compares summed CPU time over summed elapsed time. Safe negative examples will include an unchanged candidate (ratio 1.0), missing/short runs, wrong identities or modes, counter regression and non-finite inputs. None may pass.

The existing Linux acceptance cannot establish native Mac performance. Three paired 60-second windows per mode on the same machine are mandatory. Initial 20/30-second observations are discovery evidence only. Cached disk values with no failure result are an explicit correctness hazard, not an acceptable tradeoff for the CPU target. Missing Intel hardware and old scope findings remain separate and incomplete.

Implementation and final review are pending. No passing mechanism, performance reduction or complete commitment is claimed by this review.
