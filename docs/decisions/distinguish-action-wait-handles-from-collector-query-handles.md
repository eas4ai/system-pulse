# Distinguish action wait handles from collector query handles

Level: Judged
Decided by: Codex
Supersedes: observe-released-uac-helper-handles-through-windows-process-snapshots
Cause: an unforeseen condition occurred
Rests on: WUAC-004 WUAC-006
Would be wrong if: A retained action wait handle is accepted as a collector handle, an unreviewed harness revision is accepted, or ordinary monitoring handles are classified without native access rights.

## Decision

The timeout fixture leaves its helper alive. The vendored sysinfo collector retains one process handle opened with query-information plus VM-read, or query-limited-information, while production process actions and WaitForSingleObject require SYNCHRONIZE. Extend native snapshots to record granted access and synchronization counts. Require the timeout helper to retain no wait or termination handle; allow only its single normal collector query handle with an exact reviewed read-only access mask. Preserve the nine completed UAC/ordinary observations from the exact 80f1cd41 harness revision: their zero-helper-handle proof is stronger than this distinction. Accept no arbitrary historical harness, and bind the compatibility exception to that reviewed revision and non-timeout cases. Rerun native positive controls including a query-only handle, then rerun the actual helper-timeout case. No production action behavior changes. Microsoft documents SYNCHRONIZE as mandatory for WaitForSingleObject and PSS_HANDLE_ENTRY.GrantedAccess as the captured access mask.

## Realized by

- fdb5e8c1 Classify timeout action handles separately from collector queries

References: [WaitForSingleObject](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-waitforsingleobject), [PSS_HANDLE_ENTRY](https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/ns-processsnapshot-pss_handle_entry), and `vendor/sysinfo/src/windows/process.rs:get_process_handler`.
