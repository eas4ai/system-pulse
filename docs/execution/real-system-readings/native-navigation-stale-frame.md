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

## Independent diagnosis

Published sequence 115 was 2.013604 seconds old at the failed check. The
complete retained `latest.2978356.tmp` held sequence 116, which would have
been only 0.997242 seconds old. Its source collection took 171.124 ms; UI
acceptance followed collection finish by 71.482 ms. The temporary file's
modification time preceded the failed check by 771.023 ms.

The newer data reached the diagnostic writer but was not published.
`storage.rs` writes the file, calls `sync_all`, then renames it. A delayed
flush, rename, or descheduling fits the evidence; no individual syscall
has yet been identified. The next diagnostic traces this publication
boundary under the original freshness limit. No collector delay or
general UI freeze is inferred from this run.
