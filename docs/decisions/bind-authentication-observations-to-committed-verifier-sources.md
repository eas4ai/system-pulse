# Bind authentication observations to committed verifier sources

Level: Judged
Decided by: agent
Rests on: PROC-004 PROC-005
Would be wrong if: A receipt can pass without matching committed runtime helpers, current production source, or the current outcome validators.

## Decision

Record the exact committed observer revision separately from the application revision and verify every runtime helper digest against that tree. Continue to require identical current production source and current structured outcome validation. This preserves valid Mac observations when Linux-only cancellation verification changes; do not rewrite observed outcomes or ignore new falsifiers.

## Realized by

- b72f773cb358e3341400b52a2cd8b6a8f846227d Verify KDE cancellation using identity-bound operating system evidence
