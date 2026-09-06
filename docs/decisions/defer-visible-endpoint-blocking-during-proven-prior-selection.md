# Defer visible endpoint blocking during proven prior selection

Level: Judged
Decided by: agent
Rests on: LIVE-003, LIVE-010 and LIVE-013 require fresh exact native proof. Full capture z4iqe4_o observations 283-285 prove the bound prior ACK and visible unselected destination set a permanent block before keys became observable.
Would be wrong if: The deferral accepts a new endpoint without fresh exact selected proof, authorizes input while prior selection persists, outlives its initial publication prefix, clears a justified block, permits arbitrary unselected rows or competitors, changes default scopes or relaxes any deadline/comparison.
History: This narrows the prior decision to retain visible-unselected endpoint blocking: within a proven initial exact prior-selected prefix, destination visibility does not establish keyboard processing. The previous hidden-selection inference remains rejected. Judged is sufficient because only observational deferral changes and later exact native proof is mandatory.

## Decision

For intermediate pending arrow batches only, defer a new recovery block while the existing proven initial prior-selected prefix remains active, whether the expected endpoint is present-unselected or absent from the complete native row scan. Remove only the expected-absent restriction within that prefix exemption. Preserve bounded positive native ACK/issue-frame/dispatch binding, permanent expiry on any publication advance, coherent absence or different selection, and existing blocks. The deferred observation grants no input or acknowledgement. Outside that prefix preserve distinct-competitor and instantiated-unselected-expected blocking. Keep fresh strict globally unique coherent absence/reindex/span/clipping/final membership/publication checks and separate fresh exact expected-selected native proof after nonselecting reveal. If dispatched keys did not change model selection, revealing an unselected expected row must fail. No diagnostic model-selection inference, timeout change, additional retry, query, retained frame/native object, production change or default-scope change. Preserve intermediate pending exit proof, Home/End/reconciliation/final controlled-target/inspection/pre-exit/held behavior, all sixteen metrics and controlled exit. Write a failing reproduction of the captured prior-selected/visible-unselected expected prefix before correction; verify later coherent absence/reindex/reveal/exact ACK. Add or retain persistent-prefix timeout, lost keys/unselected revealed endpoint, missing/malformed proof, expiry/recurrence/publication advance, distinct competitor, existing-block and deadline cases. Run focused/full Python checks, relevant Ruff and whitespace/document checks; one implementer followed by independent SPEC and QUALITY. Then fresh untraced focused and full committed acceptance. Retain all previous failures. See docs/execution/real-system-readings/native-prior-visible-endpoint-review.md.

Independent SPEC and QUALITY passed with no findings. See the
[code review](../execution/real-system-readings/native-prior-visible-endpoint-code-review.md).
Fresh focused/full acceptance and final commitment review remain pending.

## Realized by

- a5a8908acf8892b50c98984e4f86f7fb1ad16b0d fix: defer visible endpoint block during proven prior selection
