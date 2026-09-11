commitment: windows-uac-process-actions
commit: f3f825a8372282ce68de20bafc59b93db645181f
examined:
  - WUAC-001 through WUAC-007 and current falsifiers
  - Windows retained process identity, Restart Manager and force termination
  - helper entry, parser, caller validation, elevation and result protocol
  - UI request capture, background dispatch and shared pending state
  - resource ownership, native timeout access masks and receipt provenance
  - GPUI patch reconciliation and Linux/macOS/Windows preservation
  - README, user guide and packaged instructions
findings:

## Final review — 2026-09-11

All seven requirements have passing committed evidence: WUAC-007 at
20260911T104052943Z, WUAC-001 at 20260911T104107654Z, and WUAC-002 through
WUAC-006 at 20260911T104130279Z. No code changed during this review.

| Attack | Result |
| --- | --- |
| A recycled PID or changed selection redirects an action | Confirmation owns the original identity/action. The worker moves that request, and each native action retains its identity-checked process handle. Full FILETIME survives parsing and collection. Force termination uses that handle; Restart Manager receives exactly its PID and full creation time. Native wrong-tick, exited-target and consent-stale cases pass. |
| Graceful closure reaches another window or becomes forceful | Window enumeration checks support only; no HWND becomes an action destination. The private Restart Manager registration has one process and no files/services. Affected-set/type checks fail closed and shutdown flags are zero. Cooperative/refusing/windowless native cases and unrelated controls pass. |
| Permission denial turns validation failure into elevation | The ordinary path verifies identity and protection before permission escalation. Failed safety probes map to ordinary errors. Only typed action permission denial reaches the one authentication call; the elevated helper cannot recurse. Native ordinary, denial and cancellation cases pass. |
| Extra arguments, executable search or GUI initialization cross the helper boundary | The entry runs before application/assets/tray initialization and exits after one action. Exact argument count, decimal ranges and two closed action tokens are checked. Caller elevation and executable identity are validated. ShellExecuteEx receives a canonical absolute executable separately from integer/enum parameters. Native malformed entries and packaged paths with spaces/non-ASCII pass. |
| A pending dialog freezes monitoring or permits duplicate helpers | Dispatch runs off the UI thread. Workspace-owned busy state guards preparation and confirmation and survives panel recreation. Actual delayed-consent sampling progressed for over eight seconds, duplicate controls remained disabled, and native traces observed one helper per approved action. |
| A timeout is reported as success or untouched target | Unknown/crash/timeout result codes report uncertainty and ask the user to check the process list; there is no automatic retry. Exit, closure request and termination pending have distinct results. Native helper crash and 120-second timeout cases pass. |
| A finished action retains privileged or wait handles | OwnedHandle scopes release target, caller, token and helper handles; COM and Restart Manager have paired cleanup. Native snapshots run while the dashboard is still alive. Timeout retains exactly one 0x1000 collector query handle to the still-live helper, zero synchronization/termination handles. Four native positive controls establish access-mask classification. The supervisor then cleans its suspended helper and targets. |
| Historical receipts conceal an untested harness or executable | Every artifact is hashed; executable/package/build and current production source agree. Only the exact pinned 80f1cd41 harness is accepted for the nine non-timeout cases, whose zero-helper-handle proof is stronger. Unknown revisions and legacy timeout receipts fail tests. The timeout uses the current harness. Failed attempts remain separate. |
| Upgrade or documentation claims exceed proof | GPUI Kit 0.6.1 and compatible dependencies retain reviewed local fixes, including non-finite geometry and disabled action accessibility. Fresh automated and native preservation is tied to production source 3e6923e3. User-facing Windows text distinguishes graceful/forceful results, administrator-only elevation and unsigned publisher status. Historical progress files retain the state when recorded; this review records current acceptance. |

## Evidence and limits

Fresh production preservation includes 1,714 Linux Rust workspace tests,
formatting and Clippy without warning promotion; 1,674 Mac workspace tests,
Clippy, release build and native lifetime checks; 230 native Windows tests and
release build; Linux package/native replay; and Mac/Windows desktop replay.
The later harness suite passed 569 Python tests. The final UAC gate reran its
16 focused evidence tests and validated all ten native receipts, the package,
resource controls and retained platform checks.

This acceptance covers administrator consent on the observed Windows host.
Standard-user credential entry, signing, protected-process bypass, other GPU
hardware, hosted CI and release publication are outside it. No credentials or
UAC screen pixels were collected. The timeout rerun has native elevation proof;
there was no separate human acknowledgment of that rerun when recorded.

Ripwire test-gate exits zero for the final documentation/evidence change.
Quality-delta exits 2 with broad reference-tree findings (755 gating entries);
no clean whole-repository quality result is claimed. Graph discovery was
unavailable because its transport was closed; focused source inspection used
Ripwire and Tilth. The scoped source and evidence review found no additional
actionable defect.

## Production self-audit

Reviewed all imported production rules: understood scope and contracts, bounded
changes, maintainability, strict request boundaries, errors and credentials,
privilege isolation, state/lifecycle behavior, responsiveness, tracked work,
executed tests, evidence limits and consistent user-facing semantics. The
commitment has no known missing requirement or failing acceptance check.
Windows GPU detection remains the separately requested next commitment.
