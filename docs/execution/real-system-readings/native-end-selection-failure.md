# Native End selection acknowledgement failure

The untraced focused process run at `320c6d7e` failed before exercising
the reviewed gesture correction. Launch, metrics, collapse, charts, and
inner scrolling passed. Held-input preparation sent End and waited eight
seconds for `process:4186560:70974873` selection, then timed out.

Artifacts and hashes are in [the retained record](native-end-selection-failure.json).
The last diagnostic frame has render revision 96. The failure screenshot
shows the Processes table at its initial rows; that does not establish
whether focus, selection, or a changing process snapshot caused the failure.
No cause or successful native gesture verification is claimed. Read-only
diagnosis is in progress. All existing deadlines remain unchanged.

The owned app exited on cleanup and no longer existed in procfs. The
transport exited normally with no cleanup errors or forced kill. The
focused failure is retained separately from Cairn aggregate receipts.
