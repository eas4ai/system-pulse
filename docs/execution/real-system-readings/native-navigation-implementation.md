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
scan, every parent-to-child link is validated through the current desktop's
application child, including the exact application PID. The check refreshes
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

Final navigation success independently rediscovers the unique current panel and
proves the exact target is selected. The replay's subsequent independent cell
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
