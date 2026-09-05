# Native process navigation implementation

Implements the judged decision
[navigate-live-processes-independently-of-collection-cadence](../../decisions/navigate-live-processes-independently-of-collection-cadence.md).

## Protocol

Navigation retains the two-key cap, actual Home/End/Up/Down input, the original
180-second total deadline, and eight-second batch deadlines. It no longer waits
for a newer collector sequence after each batch. Every diagnostic read still
uses the existing application PID and accepted-frame age validation.

The initial panel discovery, invalidation recovery, and final target proof find
the unique current Processes panel using the existing bounded traversal with
validated monitor-body pruning. Intermediate endpoint observations retain only
a navigation-local ancestry path. Before and after each complete selected-row
scan, every ordinary parent-to-child link is validated through the application.
The application's registration is separately proved by enumerating the current
desktop children, requiring one exact accessible object for the application PID.
The check refreshes
individual nodes with `clear_cache_single`, rejects negative indices, verifies
the parent's current child at that index with accessible equality, and rereads
the child's parent to detect reparenting. It does not treat a live cached panel
or a parent pointer alone as membership evidence. Paths retain the existing
40-level ancestry bound; discovery and scans retain the native node bound.

Each endpoint acknowledgement scans the complete Processes subtree with cells
pruned and strict traversal enabled. It rejects multiple selected identities
and never uses the generic cached selected-row acknowledgement shortcut.
Fresh diagnostic frames bracket the selected-row observation; a changed
sequence or render revision causes another observation under the same deadline.
Potentially slow panel discovery occurs before this bracket, so a collector
publication during discovery does not prevent a later coherent observation.

If the previous exact PID/start identity disappears, navigation waits for its
native selection to clear. Only a complete observation can establish clearing.
It then sends a physical Home or End and acknowledges the exact boundary row
using the remainder of that same batch deadline. An unexplained different
selected identity is a failure, including reuse of the old PID with different
start ticks. The exact controlled target must remain present. Fresh indices
come from the coherent snapshot, never from a vanished identity's old position.

Final navigation success independently rediscovers the unique current panel on
every proof attempt and proves the exact target is selected. The replay's subsequent independent cell
metric proof is unchanged. Generic lookup/selection defaults, the separate
strict exit traversal and its newer-snapshot requirement, replay, Rust, and all
budget constants are unchanged.

## Verification

The tests execute the real Native class, frame validation, navigation, and
bounded traversal with simulated native nodes and time; no native session is
started. Initial RED: 16 tests ran with 13 errors, reproducing the unchanged
sequence timeout and vanished-selection/target `list.index` failures. Further
RED checks exposed extra keys after ancestor detachment, input before initial
panel uniqueness proof, transfer without a changed publication, and starvation
when full discovery spanned collector publications. Those checks now pass.

A representative latency regression covers a 355-row distance with one second
per full discovery, 0.3 seconds per strict row scan, and 0.5-second native key
delivery. Full discovery at every acknowledgement failed after 180.4 simulated
seconds with 81 rows remaining. Local validated ancestry completed 178 batches
in 154.45 simulated seconds. This is a protocol regression model, not a measured
native performance claim. A separate regression advances the collector during
1.25-second discovery and verifies subsequent coherent selection completes.

Final checks on the implementation:

- 29 navigation regressions; 100 focused native Python tests passed in 3.473 s.
- All 204 Python tests passed in 9.556 s with
  `/home/linuxbrew/.linuxbrew/opt/python@3.14/bin/python3.14 -B -m unittest discover -s scripts/system-pulse -p 'test_*.py'`.
- `TMPDIR=/home/shawn/workspace2/task-manager-artifacts/tmp` was supplied to tests.
- Ruff lint and formatting checks passed for both changed Python files.
- `git diff --check` passed.

Independent SPEC and QUALITY review and a fresh untraced native run remain the
parent's next steps. Actual native ancestry lookup cost and collection/selection
timing remain to be measured there; no live runs or builds were performed for
this implementation.

## Application registration correction

The subsequent retained diagnostic completed seven strict, pruned 927-node
discoveries, then rejected each path before an eighth scan expired. Four
captured paths showed all ordinary links matching, with the application itself
reporting a null parent and index -1. The prior fixture incorrectly represented
the application as an ordinary child with a desktop parent and index zero.

The pinned `accesskit_unix` 0.21.1 implementation explicitly returns a null
application Parent and `GetIndexInParent=-1` in
`src/atspi/interfaces/accessible.rs:167` and `:206`. It registers that root using
the desktop socket's `Embed` operation in `src/atspi/bus.rs:80`. Consequently,
ordinary parent/index validation must end at the application root.

The correction changes only that boundary. It enumerates current desktop
children under the supplied deadline and existing node bound, checks each
registration's liveness and PID, requires a unique match equal to the retained
application accessible, and rechecks the matched desktop slot, child count,
application liveness, and PID before success. Missing, defunct, duplicate,
replaced, and incomplete registrations fail validation. No application Parent
or index is required. Individual cache clearing and all ordinary link checks
remain in place.

The corrected fixture now uses the observed null-parent/-1-index semantics for
every navigation test. RED ran 42 tests with 14 failures and 16 errors, including
the reproduced eight-second panel-membership timeout. Thirteen new tests cover
registration success and negative boundaries. Final verification after this
correction: 42 navigation tests within 113 focused native tests, all 217 Python
tests, Ruff lint/format, and `git diff --check` passed with the same Python 3.14
and workspace TMPDIR commands above. No native run or build was performed for
the correction; independent reviews precede the parent's next native proof.

## Retain validated panel paths for pacing retries

The next source inspection found an avoidable retry cost: a changed publication
or replaced selected node discarded the panel path even after a complete strict
selection scan and successful post-scan membership validation. The next poll
therefore repeated full panel discovery. This is a demonstrated code-path cost,
not an established cause of the latest native failure: the diagnostic attempt
ended in the preceding held-input case and recorded no navigation observations.

Intermediate pacing now retains that validated path on those two retry branches.
It discards the rejected selection and snapshot indices, then repeats membership,
strict selection, exact identity, and fresh-frame checks. Failed membership,
incomplete scans, and exceptions still invalidate the path and require full
reacquisition. Final proof uses an explicit `fresh_panel` mode that rediscovers
the unique current panel on every retry, including a coherence rejection.
The existing traversal and recursive cache-clearing behavior are unchanged;
their contribution to native timing remains unmeasured.

Seven regressions cover frame-change cost, selected-node replacement, original
retry deadlines, failed post-scan membership, incomplete scans, transient
post-scan frame errors, and a duplicate panel introduced after the first final
proof's coherence rejection. RED reproduced three failures: five frame changes
with one-second discoveries exhausted the eight-second deadline, two selected
node replacements caused two unnecessary discoveries, and repeated coherence
changes caused 31 discoveries before timeout. All now pass without accepting
the rejected selection observations.

Final verification: 49 navigation tests within 120 focused native tests passed
in 3.815 s; all 224 Python tests passed in 9.525 s using the exact Python 3.14
and TMPDIR commands above. Ruff lint/format and `git diff --check` passed. No
native runs, builds, replay/Rust edits, or deadline changes were performed.
Independent SPEC and QUALITY review precede fresh native verification.
