# Full native acceptance stale-frame failure

The fresh committed aggregate at `c5eae7ca384c1c9a32e0d25bb66f39a7fb82bc83`
failed in native process inspection. The [artifact record](native-full-stale-frame-failure.json)
retains all capture paths and hashes, exact commands, results and timing evidence.

All 693 automated tests passed: 338 Python and 355 Rust. Source guard,
formatting, strict Clippy, build, diff checks and independent host comparisons
passed. Host verification retained 43,790 counter brackets, 2,216 exact
readings, 17,632 process-field comparisons, 96 interface comparisons and
468 independent stable totals across four snapshots, with zero failed
brackets or unverified exit gaps. Native launch, metric values, collapse, charts and inner scrolling
passed. Fifteen child metric artifacts exist; the final rightmost comparison
and controlled process exit did not complete. Remaining native cases were not
reached. This is a failed aggregate, despite the earlier focused pass.

The failing frame had sequence 125, render revision 124 and accepted age
2.197136708 seconds, exceeding the unchanged 2-second limit. Reading took
3.803 milliseconds and parsing took 23.388 milliseconds. The opened inode
222692645 differed from pathname inode 222692644 before the age check.
A replacement therefore occurred during observation. The capture does not
retain that replacement inode's exact publication timestamp. Later failure
and final frames contain sequences 126 and 127. These observations do not
establish whether the delay came from diagnostic publication, UI delivery,
scheduling, or another stage. No retry, threshold change or causal fix is
claimed. A separate read-only investigation is pending.

The recorded executable hashes match. The application was stopped during
failure cleanup with exit code -15 and its PID was absent. The transport
exited zero without forced kill and was absent. The full commitment and
final review remain incomplete. Actual Cairn receipts mark LIVE-004,
LIVE-012 and LIVE-013 pass; the other ten requirements are unverified.
