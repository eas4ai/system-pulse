# Fresh inspection candidate replay: earlier navigation failure

The focused untraced replay against `c7a89e7815cfc245f77cc55e208a22f2d8261bb9` finished
**FAIL** before the controlled child reached cell inspection. The reviewed
inspection consolidation was therefore not exercised by this capture. The
[machine-readable record](native-inspection-eligibility-focused-result.json)
retains all 97 artifact hashes, metadata, cleanup, the final journal, and bounded
navigation failure observations. Artifacts: `/home/shawn/workspace2/task-manager-artifacts/tmp/pulse-navigation-observation-u12hxbrp/native`.

The file and running executable SHA-256 both match
`7dbcd3adfae54db64e3ed5f32cf728ee55684fd1429c95c1bbd1e72a770340e7`. Application PID 1401741 was terminated in
cleanup and no longer existed. Private transport PID 1401729 exited zero,
without forced kill, and no longer existed.

Launch, metrics (two GPUs), collapse, charts (two GPU temperatures) and inner
scrolling passed. Held-input artifacts were retained but the enclosing case was
not finally marked PASS. No child metric comparison or controlled exit completed.
No stale-frame receipt or publication timing sidecar was generated.

## Interrupted observation

The last exact acknowledgement was `process:3023548:64910375` at
753704878537512. The next two-Up batch expected `process:3023538:64910368`,
issued at index 1299 in sequence 127/revision 126. Its matching independent
pre-dispatch stat observation succeeded. Both keys were issued, with the same
eight-second deadline 753712.882013126 and total navigation deadline
753850.377701343. The controlled child was `process:1409326:75366940`.

The history observed 212 records, evicted 148 and retained the last 64. All 47
records for the failed batch remain. Observations 166 and 167 saw the exact
previously acknowledged identity selected, at span 1301–1309 in sequence 127.
Observation 166 permanently latched recovery blocking as competing selection.
Forty later observations reported no instantiated selection; five rejected a
changed publication bracket. The blocking flag remained set through the deadline.
No recovery input, interruption acknowledgement or successful batch proof followed.

All 47 selection scans completed, taking 21.112559–48.267214 ms.
The last complete observations map instantiated rows to span 1299–1307 in
sequence 135/revision 134. The later failure frame with that sequence/revision
retains the expected identity at 1298, the last acknowledged identity at 1300,
and the controlled child at 1153. The screenshot after failure shows no highlighted
row and starts with PID 3023539. It cannot prove hidden model selection or that
recovery would have succeeded.

The [independent review](native-prior-acknowledgement-review.md) supports a bounded
initial prior-ACK case in the same issued publication, for intermediate arrows
only. A separate decision records that correction; later strict input guards and
successful counterfactual recovery remain unproven. The current failed capture remains failed; fresh full
aggregate acceptance and final review remain required.
