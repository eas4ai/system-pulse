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
