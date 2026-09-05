# Navigation retries discard validated panel membership

Untraced run `47bab9aa` passed the repaired application-root boundary and
held-input sequence, then acknowledged several child-navigation batches.
A later eight-second endpoint deadline expired during panel reacquisition.
The retained trace does not identify which observation caused each retry.
[Artifacts and hashes](native-navigation-retry-observations.json).

Source shows an avoidable cost: navigation_selection clears its local path
when an observation starts and restores it only after frame coherence
passes. A changed publication therefore discards a path whose before/after
membership checks both passed, causing full discovery on the next poll.
Retaining that path for pacing does not permit reusing rejected selection
results or indices; all those observations must still be repeated.

A diagnostic intended to trace this behavior failed earlier: held-up-25hz
ended with no selected process and timed out. It produced zero navigation
observations. Its result does not identify this navigation failure's cause.
The held-input failure is under separate read-only investigation.

Add a deterministic regression for the observable rediscovery cost and
preserve local validated membership through intermediate coherence or
selected-node retries. Failed links and incomplete/exceptional scans
still require reacquisition. Final target proof must retain fresh full
panel uniqueness even across retries. All deadlines remain unchanged.
