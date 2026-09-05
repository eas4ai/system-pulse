# Native process cell lookup review

Candidate: `7f7c515c8024a5dfc7ac68259429642f8a74898c`.

## Specification review

Independent reviewer ran 47 focused native tests successfully, then reproduced
an Important identity-boundary finding at native_driver.py:623–633. An alive
exact-ID cached row bypasses current Processes-panel membership and row
uniqueness checks. Detached rows and duplicate same-ID rows are accepted.
Panel reacquisition can also populate the cache from an unrelated panel and
return that foreign row's cell. This finding is recorded before correction.

Status: open. The correction must establish row membership and uniqueness
within the current Processes panel, preserving the same deadline and pruning
unrelated cell descendants. Independent re-review remains required.

Quality review and focused/full native acceptance have not run for this
candidate. Final commitment review remains pending.

## Correction awaiting re-review

Candidate `0d4e644536db283eb154ccd1d52a2eb810f6549d` removes the global
row-cache fast path. Every lookup scans current Processes row identities
while skipping unrelated cells, then checks the unique matching row's cells.
The worker reproduced all three findings before correction and reported
50 focused native tests and 154 full Python tests passing, plus Ruff and
diff checks. Independent specification re-review is pending. Actual native
timing remains unverified; the five-second deadline is unchanged.

## Specification re-review

Independent SPEC PASS on `0d4e6445`. All 50 focused native tests passed.
The reviewer reran all three original adversarial probes: detached rows
time out under the original deadline, duplicate rows fail, and foreign
rows cannot replace the actual Processes row. The finding above is closed.
Identity, cell uniqueness, metric comparisons, generic discovery, and
strict exit behavior remain intact. Quality review is in progress.

## Quality finding before correction

Independent QUALITY ran all 50 focused tests successfully but found an
Important cache boundary at native_driver.py:610–621. A live cached panel
bypasses current application membership, name, role, and panel uniqueness.
A detached cached panel still supplied accepted cells after the root's
Processes panel was replaced with an empty panel. Renamed and duplicate
panels also bypassed validation. The reviewer reproduced all three cases.

Status: open. Establish the unique current Processes panel before validating
its row and cells. Preserve the same deadline and traversal bounds.

## Panel correction awaiting re-review

Candidate `9855844578294950934a444f8e39e2e7c3457a3b` removes the panel-cache
shortcut. The current application tree must supply exactly one matching
Processes panel before row and cell verification. Four new regressions
failed first, then passed: detached, renamed, wrong-role, and duplicate
panels. The worker reported 54 focused native tests, 158 full Python tests,
Ruff, formatting, and diff checks passing. Independent re-reviews are
pending. Full app-container and row traversal now occurs on every lookup;
native timing under the unchanged deadline remains to be measured.

## Final mechanism correction reviews

Both independent reviewers passed candidate `98558445`. Each ran all 54
focused tests. SPEC also checked a shared deadline across all three scans,
slow discovery rejection, pruning, and detached-panel replacement. QUALITY
reran the three original panel probes. No findings remain for this correction.
The implementation's full Python suite passed all 158 tests.

Focused native verification has not passed: one run exhausted /tmp inodes;
the next hit the unchanged freshness gate during navigation before invoking
this helper. See [storage failure](native-tmp-inode-exhaustion.md) and
[freshness failure](native-navigation-stale-frame.md). Native lookup timing
and final acceptance remain unverified.

## Monitor body pruning candidate

Candidate `18a7c978c07a3424244ddbd2e16dd62f7d636631` follows the observed
15-second panel discovery timeout. Only process-cell panel discovery
opts into pruning body viewports that match their live traversed named
parent monitor. The workspace viewport remains traversable. Default
walk and strict exit semantics remain unchanged.

The worker reported 64 focused native tests and 168 full Python tests
passing, plus Ruff and diff checks. Four new tests reproduced the old
body traversal failure; six further tests preserve malformed-boundary,
layout, default, strict, and deadline behavior. Independent SPEC then
QUALITY review and actual native timing remain pending.

## Monitor body pruning reviews

Independent SPEC and QUALITY PASS on `18a7c978`. Each ran all 64 focused
native tests. SPEC checked a 151-monitor/1,350-process synthetic shape,
malformed names, defunct parents, parentless viewports, and unchanged
budgets and metric/exit methods. QUALITY ran five additional probes for
transient boundary reads, node limits, strict failures, and generic lookup.
No findings remain. Actual native timing is still pending.
