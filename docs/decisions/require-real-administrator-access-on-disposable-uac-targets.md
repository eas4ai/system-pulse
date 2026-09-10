# Require real administrator access on disposable UAC targets

Level: Judged
Decided by: Codex
Rests on: WUAC-002 WUAC-006
Would be wrong if: The fixture grants the limited observer termination rights, denies the elevated observer, changes unrelated objects, or hides an application authorization failure.

## Decision

Native preflight showed OpenProcess termination access succeeds from the medium integrity dashboard account to its high integrity same-user fixture without debug privilege. Elevation alone is therefore insufficient for the intended access-denied test. Set an explicit process DACL only on the retained, job-owned disposable UAC fixture: LocalSystem and enabled Administrators receive full process access; everyone receives only query-limited and synchronization rights. Independently require a fresh termination open to succeed from the elevated observer with debug privilege removed and fail with ERROR_ACCESS_DENIED from the limited UI observer before the application action. Keep the separate deny-after-elevation fault layered on this fixture. Preserve all production permission checks and real human UAC requirements.

## Realized by

- 911893341df0dc04fb8822fd7ce05252a7081f64 Require administrator termination access on owned UAC fixtures
