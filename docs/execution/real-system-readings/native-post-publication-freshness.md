# Freshness failure after publication policy correction

The untraced focused run at `966b3a49` passed launch and metrics, then
failed during collapsed-state sequence progression: the retained accepted
frame was 2.037 seconds old against the unchanged two-second limit. The
new diagnostic publication policy does not resolve this failure.

The stale artifact contains sequence 33. Failure capture subsequently
obtained sequence 34, and the final latest file contained sequence 39.
No diagnostic write error was logged. These facts do not distinguish
a read race, publication delay, or scheduling delay. A more precise
diagnostic capture is being prepared before further production changes.

The failure occurred before process-cell lookup, so lookup timing and
exit synchronization remain unverified. See [artifact hashes](native-post-publication-freshness.json).
Final native acceptance, committed aggregate, and final review remain
pending. Original failure results and bounds remain unchanged.
