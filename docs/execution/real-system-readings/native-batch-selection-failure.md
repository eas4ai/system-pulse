# Native batch selection acknowledgement failure

The untraced focused run at `41c345a1` passed the corrected input sequence
evidence check, held Up, exact 64-Up endpoint acknowledgement, and both
horizontal held-table movements. It reached real child navigation and
acknowledged many two-key batches.

The last batch began at `process:2114665:66774976`, expected
`process:2098164:18509828`, and retained target
`process:1437033:71949607`. Its eight-second acknowledgement deadline
expired inside the strict selection scan. The overall navigation deadline
still had time remaining. The final stack identifies the timeout location,
not the reason earlier observations were rejected.

The failure screenshot begins with PID 2117428 and shows no selected
highlight. That is not proof of model selection clearing: this native
table is virtualized. Process lifetimes and snapshot order are under
read-only investigation. Preserve the FAIL outcome and original limits.
[Artifacts and hashes](native-batch-selection-failure.json).

## Retained chronology

Independent read-only review found the final batch used sequence 137 and
the failure frame sequence 145, revision 144. Origin, expected endpoint,
and controlled target all remained present with their exact start ticks.
Last-batch metadata implies origin index 1223 and expected index 1221;
at failure they were 1218 and 1216. Target remained index 1143. The
screenshot's first visible PID 2117428 maps to index 1221, five rows below
the expected endpoint. This is consistent with viewport drift after
collection, not proof of actual model selection loss.

Navigation used about 52.66 seconds of its 180-second budget. The last
batch acknowledgement exhausted its own eight seconds; no rejected
observations were retained. A bounded diagnostic will record existing
selection/frame/membership results and retry reasons in memory, without
extra native queries, input, or changed deadlines. Its output is diagnostic
only. A separate read-only trace checks the production viewport behavior.
