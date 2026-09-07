# Pending process reveal correction

Status: Implemented and locally verified; independent reviews and fresh native
preservation evidence remain pending. This record does not attribute the retained
native failures or claim GPU acceptance.

The [source finding](linux-pending-process-reveal-finding.md) and
[Judged decision](../../decisions/resolve-pending-process-reveals-by-identity-at-list-layout.md)
were committed at `a1421f5d8beac7012f1aba8b54e4d1de7c686b04` before this correction.
The [machine-readable record](linux-pending-process-reveal-correction.json) retains
commands, exits, counts, source hashes and external artifact hashes.

## Demonstrated failure

The regression uses real `WorkspaceView::accept_snapshot`, keyboard dispatch,
coalesced frame callbacks and GPUI virtual-list layout with 1,300 process rows.
It draws End, then moves Up to select A at index 1221. It asserts A is at the
top of the rendered viewport and row 1219 is not instantiated. After inserting
two earlier rows and drawing that publication, two Up keys select stable B
at index 1221. Restoring the original snapshot before the deferred frame moves
B to index 1219 without changing its PID/start-time identity.

Before the production change, the final identity assertion passed but the
rendered B row was absent. The unchanged-order snapshot control passed in the
same invocation: **1 passed, 1 failed, exit 101**. The retained
`red-top-boundary.log` has SHA-256
`3e4504e21e1acb77397138b38ed45fecde724b7b1698e78bbb49aa088b96f9f8`.
The pre-fix test file is retained as `red-native-tests.rs`; it can reproduce the
failure when substituted for the test file in an isolated checkout of the base.

Earlier runs exposed two test compilation issues and an absent debug selector;
these are retained as setup failures, not RED evidence. The first complete
interleaving passed because batching End with all Up movements put A at the
viewport bottom. The existing list's Top strategy reveals an offscreen item;
it does not unconditionally align that item to the top. Drawing End first
established the top-edge boundary described above. Production remained unchanged
until that boundary produced the observed failure.

## Correction and preservation checks

`MonitorPanel` now retains one pending vertical keyboard reveal flag. At process
table rendering, it consumes that flag and resolves the selected stable identity
against current rows before passing an index to the existing list. A cleared
selection consumes the flag without scrolling. Passive snapshots do not create
intent. Repaint coalescing, horizontal navigation and selection reconciliation
remain on their existing paths; the shared list API and native acceptance
guards are unchanged.

The same RED test and control then passed, followed by four focused tests:

- Snapshot reordering reveals the selected row within the actual rendered table
  bounds, excluding its border and header.
- Unchanged-order delivery preserves reveal and exactly one deferred callback.
- After consuming a reveal, manual wheel scrolling can leave selection offscreen;
  passive reordering and horizontal navigation preserve the vertical viewport.
- Removing the pending selected identity through PID reuse clears selection and
  does not scroll to the replacement; rediscovery does not restore selection.

All logs are outside the checkout under
`/home/shawn/workspace2/task-manager-artifacts/gpu-task5/linux-pending-reveal-20260906`.

| Check actually run | Result |
| --- | --- |
| Focused regression and control before correction | 1 passed, 1 failed; exit 101 |
| Same two tests after correction | 2 passed; exit 0 |
| All four focused pending-reveal tests | 4 passed; exit 0 |
| `rtk proxy cargo test --locked -p system-pulse --lib --tests` | 67 passed; exit 0 |
| `rtk proxy cargo fmt -p system-pulse -- --check` | Exit 0 |
| `rtk proxy cargo clippy --locked -p system-pulse --all-targets -- -D warnings` | Exit 0 |
| `rtk proxy cargo build --locked -p system-pulse` | Exit 0 |
| `rtk proxy git diff --check` | Exit 0 |

The app test count excludes the Linux-inapplicable macOS lifetime targets.
These are development checks, not committed Cairn receipts. No native workload,
GPU accuracy capture, full preservation acceptance or macOS test was run for
this correction. The original Linux freshness failures, Mac native proof and
missing Intel hardware evidence remain open. Independent specification review
and then a fresh quality review must assess the committed candidate.

## Production self-audit

Reviewed against machine `BEST_PRACTICES.md` version 1.1.0; no repository override
exists. The implementer is satisfied with this scoped candidate and found no
remaining revision needed before independent review.

| Rules | Audit |
| --- | --- |
| 1–3: understand, minimize, maintain | Recorded source path and actual RED precede the fix. Production changes remain in `panel.rs`; focused tests use the existing GPUI seam. |
| 4–5: contracts and errors | Stable PID/start-time identity, list API, snapshot reconciliation and native bounds are preserved. Removed selection produces no replacement scroll. |
| 6: security | No new I/O, dependencies, permissions, unsafe code or secrets in the implementation/evidence. |
| 7–8: state and reliability | One bounded flag is consumed once, including cleared selection. Tests preserve manual scrolling, passive delivery and coalesced repaint. |
| 9–11: tracking, verification, honesty | External todo retained one active item. Actual test counts/exits and setup failures are retained. Native and independent acceptance remain explicitly unverified. |
| 12–14: partnership, self-audit, language | Scope and reproduction refinements were reported to the orchestrator. This self-audit makes no independent-review claim. |
