# Independent Memory state comparison failure

The untraced focused run at `310d3402` passed launch and metrics, then
failed the exact Memory panel dictionary comparison after CPU row/panel
collapse. It did not reach the reviewed navigation correction.
[Artifacts and hashes](native-memory-state-failure.json).

The comparison includes expanded geometry. Final Memory is visible and
expanded at 1424 by 280, with its eleven sensor choices at their normal
defaults. The initial dictionary was not retained, so the changed field
cannot be established. Source review found geometry capture across
visible expanded panels and asynchronous save-version acknowledgement;
these are hypotheses, not a proven cause or justification to weaken the
comparison. No Memory toggle appears in the input journal.

Retain the complete baseline returned by save_state and the complete
state used by the comparison. Keep the exact assertion and all timing
and input behavior. The additional records improve failure diagnosis
and do not establish a product correction.

The observability-only change passed all 204 Python tests in 9.763 seconds,
Ruff lint/format, and diff checks. It retains the same initial state return,
post-collapse state read, and exact Memory dictionary equality. Independent
review and the next native capture remain pending.
