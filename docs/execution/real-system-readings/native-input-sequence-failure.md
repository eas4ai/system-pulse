# Exact input sequence evidence failure

The untraced focused run at `3d5786fa` passed launch, live metrics, collapse,
charts, and inner scrolling. Held Up recorded signed movement between exact
PID/start identities, with six fresh sequences and no publication errors.
The exact 64-Up burst acknowledged its expected PID/start identity and
recorded the matching signed movement.

The subsequent sequence wait acknowledged progression, but the input
observer retained only sequences 82 and 83. Its 18 observations had no
errors and a maximum age of 1.393 seconds. The required three distinct
fresh sequences were missing, so the run correctly remained FAIL.

The retained journal and input records distinguish this failure from the
earlier missing-selection observations. The relationship between the
sequence wait and observer completion is under read-only investigation.
No navigation or controlled-child exit proof was reached. Owned application
and private transport cleanup completed. [Artifacts and hashes](native-input-sequence-failure.json).

## Recorded diagnosis

Read-only review confirmed two evidence lists: Native.sequences observes
three actual publications, while check_input_record counts only the watcher
list. exercise discards the main-thread records and stops the watcher
immediately. No synchronization saves the third main-thread publication.
This identifies an evidence-recording race, not an observed collector or
input failure. The original run remains FAIL.

Retain age immediately after each existing sequences frame read, then append
those actual sequence/age observations to the same saved list before
shutdown. Preserve every watcher observation and error, the three distinct
sequence requirement, existing reads, and the original wait deadline. Never
compute earlier observations' ages at return time or infer a zero age.
