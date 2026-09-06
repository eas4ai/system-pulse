# Pending keyboard endpoint failure

Fresh untraced focused capture `pulse-process-lookup-b9safeex/native` failed
at the source commit retained in [its metadata and artifact record](native-pending-endpoint-failure.json).
The final-proof endpoint correction had passed SPEC and QUALITY reviews.
This run stopped earlier, during acknowledgement of an intermediate batch.

Launch, live metrics, collapse, charts, and inner scrolling passed.
Vertical, exact-64-Up, and horizontal held-input evidence was retained.
The controlled child `3576994:74087154` appeared and remained in the failure
snapshot. Final child acknowledgement, cell inspection, and exit were not
reached.

The last batch at monotonic 740889.497684248 issued two Up keys from
`3592741:22147376`, expecting `3578380:74088807` at index 1321 in sequence
105. It retained no acknowledgement. The selected-row scan exceeded the
batch deadline at 740897.462730754. In the failure frame at sequence
113/revision 112, the expected identity is absent and the controlled child
remains at index 1316. The screenshot begins with PID 3592542, which maps
to index 1320 in that frame; no selected row is highlighted.

The only journal entries after that batch are two Up keys and the failure
screenshot. There is no recovery or stale-frame artifact. The failure
snapshot does not show when the expected identity disappeared, whether
it was ever selected, or each failed scan's result. Its absence is not
independent exit proof, and the screenshot is not model-clear evidence.
The run remains FAIL.

The failing _navigate batch call uses navigation_selection with its default
reconcile=False. The existing reconcile=True path can return no instantiated
selection when the expected identity is absent from a coherent snapshot;
the caller then performs explicit Home/End recovery. Whether that policy
also covers an unacknowledged intermediate endpoint is under independent
contract assessment. No successful endpoint may be inferred from absence,
and controlled-target loss must remain a failure.

The application and private transport exited, with their PIDs absent at
cleanup. Existing eight-second batch, 180-second navigation, freshness,
unique current-panel, and exact final-selection requirements remain intact.
