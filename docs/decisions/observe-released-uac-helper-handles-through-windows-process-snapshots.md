# Observe released UAC helper handles through Windows process snapshots

Level: Judged
Decided by: Codex
Rests on: WUAC-004 WUAC-006
Would be wrong if: A missing or unclassified process handle is treated as absent, the dashboard is already gone when observed, snapshot resources leak, or any unrelated process is mutated.

## Decision

After each administrator UAC case settles, keep the disposable dashboard alive at a bounded observation checkpoint. The elevated observer validates its PID, creation time and executable and captures only its handle table through the documented Windows Process Snapshot API, with no memory or thread capture. Filter process-handle records to the owned target and the helper PID independently observed by the native process trace. Require no helper-process handle remains, including when the timeout helper is still alive. Fail on incomplete classification or capture/cleanup errors. Release snapshot and walk-marker resources on every path and acknowledge the checkpoint so normal dashboard cleanup can proceed. Pair this native observation with a source ownership review for token, target, caller, Restart Manager and COM resources. Do not use an arbitrary total-handle-count tolerance.

## Realized by

- 589a62a9 Verify released UAC helper handles in the live dashboard
