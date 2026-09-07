# Adoption draft review

Historical adoption review, before live implementation. References to missing collectors describe that baseline. See the [current overview](spec/overview.md) and [implementation plan](plans/real-system-readings.md) for reviewed changes and pending acceptance.

Status: Draft review, 2026-09-04

The reviewed text is `docs/spec/{overview,glossary,readings,rendering,workspace-state,live-collection}.md`; code evidence is pinned to `9f2f3ad0382ce4c7ce0aadfc0c4ed88588ad95af`.

## What the review attacked

- **Simulation mistaken for a contract:** Observed fixture generation, row count, and percentage clamping deliberately remain a record of what exists. LIVE requirements state the intended replacement. No new text is marked Agreed.
- **Green tests with fake values:** LIVE-001 combines source checks, collector tests, and native host comparison. A source import change alone cannot satisfy real collection.
- **False physical meaning:** LIVE-004/005 distinguish byte deltas from rates, percentages from quantities, shared-device I/O from per-volume attribution, and backend fan units from RPM.
- **Unavailable as a loophole:** The metric matrix requires source/capability accounting. Missing code is not reported as missing hardware; failed reads do not silently become zero.
- **Unbounded dynamic state:** Existing HistoryStore caps each deque, not its key count. LIVE-009 explicitly covers repeated device churn and bounded delivery.
- **Identity and migration loss:** LIVE-007 covers absence, reordered discovery, fixture identities, invalid original input, and restart; PID reuse receives a separate process-table case.
- **UI blocking and weakened regression scope:** Slow-backend navigation is a falsifier, and the established workspace regressions remain acceptance constraints.
- **Repository/evidence mismatch:** Formal specs and the future commitment live in the application worktree. The separate design repository retains the cited recon and historical documents.

## Outcome

Independent review found two acceptance loopholes: required fields could have been reported as unimplemented without blocking completion, and host comparisons had no explicit mismatch failure rule. LIVE-012 now makes every accessible, attributable required field a completion condition. LIVE-013 now requires predeclared semantics/windows/bounds, rejects unexplained discrepancies, and tests the verifier with deliberately wrong inputs. A sysinfo failure-path citation in the recon was also corrected to the actual zero-returning helper.

The draft is ready for developer correction of the proposed LIVE text and falsifiers. Its executable mechanisms are not yet implemented; no collector acceptance is claimed. Creating an Agreed requirement or an active commitment before confirmation would violate the invoked existing-project workflow.

The current source worktree contains no collector changes. The historical 275-test/native fixture evidence remains historical, not a new recon test run. Spec-lint and documentation validation results are recorded in the recon closing notes after those commands run.
