# Visible endpoint during a proven prior-selected prefix

The [retained failure diagnosis](native-prior-visible-endpoint-review.md) found
that a positively acknowledged prior row remained selected while the pending
endpoint was instantiated and unselected. That initial observation permanently
blocked later recovery. The [bounded decision](../../decisions/defer-visible-endpoint-blocking-during-proven-prior-selection.md)
authorizes deferring this new block inside the existing proven prior prefix.

## Change

The only driver change removes the expected-absent condition from the proven
prior-selected exemption. Endpoint visibility no longer disqualifies that prefix.
The separate no-selection/visible-expected blocker remains. The exemption neither
acknowledges the endpoint nor authorizes input, and cannot clear an existing block.
Proof binding, publication and selection expiry, strict fresh recovery discovery,
post-reveal exact selected proof, deadlines and default scopes are unchanged.

The regression follows two coherent prior-selected scans with the expected row
visible. Both scans precede any wheel input. A later publication reindexes the
endpoint from 17 to 16 outside the complete instantiated span. Coherent absence
then qualifies a nonselecting reveal, and a fresh exact selected endpoint proves
the acknowledgement before navigation reaches the controlled target.

## Verification

Before the driver edit, the new positive regression failed with one error:
`TimeoutError: selected process:17:100: original deadline expired`.
After the one-line change, the same regression passed. The prior-selection suite
passes 20 tests, including visible persistent prior selection through the original
batch timeout, missing and sixteen malformed proof variants, coherent absence
and publication expiry, recurrence, distinct competitors, a previously justified
block, lost keys leaving the revealed endpoint unselected, and both recovery
journal deadline failures. Existing default-scope and bounded-ACK tests remain.
The persistent-prefix timeout uses the supported 5000 ms interval to keep the
immutable frame fresh through the unchanged eight-second batch deadline.

Commands ran from the repository root unless noted:

```sh
# From scripts/system-pulse: RED before source edit, GREEN afterward.
rtk proxy /home/linuxbrew/.linuxbrew/opt/python@3.14/bin/python3.14 -B -m unittest test_native_prior_selection.PriorSelectionTests.test_visible_expected_prior_prefix_defers_until_fresh_exact_ack

# From scripts/system-pulse: prior selection, navigation and pending endpoints.
rtk proxy /home/linuxbrew/.linuxbrew/opt/python@3.14/bin/python3.14 -B -m unittest test_native_prior_selection test_native_navigation test_native_pending_endpoint

rtk proxy env TMPDIR=/home/shawn/workspace2/task-manager-artifacts/tmp /home/linuxbrew/.linuxbrew/opt/python@3.14/bin/python3.14 -B -m unittest discover -s scripts/system-pulse -p 'test_*.py'
rtk proxy /home/shawn/.local/bin/ruff check scripts/system-pulse/native_driver.py scripts/system-pulse/test_native_prior_selection.py
rtk proxy /home/shawn/.local/bin/ruff format --check scripts/system-pulse/native_driver.py scripts/system-pulse/test_native_prior_selection.py
rtk proxy git diff --check
```

The combined focused suite passed 126 tests; the full Python suite passed 383.
Ruff lint and formatting checks, `git diff --check`, and local Markdown link
resolution passed. The initial formatting check requested a test-file wrap; Ruff
applied it and the final check passed.

No application source, acceptance comparison, timeout, observation query or
artifact schema changed. No native replay or build ran for this implementation.
Independent SPEC then QUALITY review and fresh untraced focused/full committed
native acceptance remain required. Earlier failed captures remain evidence;
fixture success does not establish a successful native replay.
