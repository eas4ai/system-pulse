# Navigation crosses an exiting process

A second diagnostic logged at most 128 existing selection calls and the
last 100 identities from already-read snapshots. It added no native scans,
keys, or sleeps and changed no budget constants. Observation overhead can
affect timing; this is not acceptance evidence. See [artifacts and hashes](native-navigation-exit-diagnostic.json).

This run completed the held-input checks and entered process navigation.
The 128 logged selection calls had no exceptions and took at most
63.059 ms each. The prior selection scan timeout was not reproduced and
is not established as a traversal performance defect.

Navigation later acknowledged `process:580577:71238526`, waited for a
newer snapshot, then crashed when that snapshot no longer contained the
selected identity. The controlled target `process:560792:71220890` still
existed. The loop indexes the previous selected identity without checking
its continued membership. This is a concrete harness lifecycle defect.

The loop also sends at most two keys per batch and then waits for another
collection snapshot. It approached its unchanged 180-second deadline while
crossing the real process population. A correction needs explicit handling
of selection disappearance and a navigation cadence independent of the
one-second collector interval, while preserving native acknowledgements,
identity checks, freshness, and the original total and batch deadlines.

The owned application and shared transport were reaped, with no cleanup
errors or forced transport kill. Earlier focus, burst, and freshness
failures remain unresolved observations.
