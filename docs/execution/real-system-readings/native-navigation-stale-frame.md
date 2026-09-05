# Native navigation freshness failure

The focused process run at `98558445` passed launch, metrics, collapse,
charts, and inner scrolling, then failed while waiting for a new navigation
snapshot: `accepted frame stale: 2.014s (limit 2.0s)`. It had not reached the
new process-cell lookup. The last two Up events were sent at monotonic
705175531 ms and selection acknowledged at 705175824 ms. Prior snapshots
were advancing roughly once per second. Root requested independent diagnosis
of the retained stale frames and source scheduling. No cause is claimed yet.

This run used workspace-disk temporary storage after the separately recorded
/tmp inode exhaustion. Failed evidence is unchanged. The original freshness
bound still applies. Focused process acceptance, full aggregate, and final
review remain pending. See [artifact record](native-navigation-stale-frame.json).
