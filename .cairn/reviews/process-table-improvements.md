commitment: process-table-improvements
commit: ba78c6249fcd204b686176649d0fe94b483f2166
examined:
  - PROC-001 through PROC-005 and their current falsifiers
  - process layout, canonical columns, search, selection and asynchronous action dispatch
  - Linux pidfd and Mac audit-token signaling, helper parsing and OS authentication
  - restricted Mac process identity decoding and its native SDK checks
  - committed native receipts, observer provenance and Linux package evidence
findings:

## Final review — 2026-09-09

All five requirements passed committed Cairn verification at
`20260909T153100594Z` / `20260909T153100595Z`. No code changed during this
review. It examined behavior and evidence beyond the acceptance summary.

| Attack | Result |
| --- | --- |
| Headers drift from virtual rows or excess width becomes empty space | Headers and cells share canonical widths, with Name receiving extra space. Rows fill the same allocation. The table retains a content-width minimum and horizontal scrolling. Native ordinary/enlarged/minimum-width records pass on both hosts. |
| Hiding Threads changes User sorting or accessibility meaning | One platform column list drives headings, cells, details and sort acceptance. Canonical User remains column 7; accessible positions use the visible index. Search uses name/PID/User. Selection remains PID plus birth identity. Native filtering, clearing, User sort and Home/End observations pass. |
| A changed selection, recycled PID or authentication delay redirects a signal | Dispatch captures the original identity and action. Linux opens a pidfd before validating birth identity and signals that descriptor. Mac validates microsecond birth time against the combined BSD/kernel-generation observation and signals by audit token. Both hosts reject an expired target after real OS authentication; stale-generation native tests are retained. No numeric-PID fallback exists. |
| Permission failure silently elevates the UI or changes the requested operation | Only typed permission denial invokes authentication, on a worker. The helper mode runs before GUI/assets/state initialization, parses one bounded request and cannot recursively authenticate. Only Terminate and Kill are accepted. Normal UI UIDs are 1000 and 501 in the native receipts. |
| Password leakage, shell injection or false success | Password input belongs to the OS agent. The application uses no password stream or terminal fallback. Linux passes separate arguments to fixed pkexec; AppleScript quotes every argument and returns only numeric status. Invalid arguments, cancellation, denial and helper errors remain failures. Native End and Force Quit terminate only the owned targets. |
| Restricted Mac observation invents a usable identity | The fallback runs only on permission denial and requires the complete LP64 kernel record, matching PID, valid seconds and microseconds. Credentials and birth time come from one observation. SDK C accessor comparisons, invalid-record tests and actual root-process observation passed. |
| KDE generic denial is mislabeled as proof of cancellation | Generic failure alone cannot pass the cancellation validator. The Linux observer requires a single OS dialog initiation, a cancellation event and authorization failure for the exact app PID/start identity in the same time window; the target must survive. The actual KDE cancellation witness and negative correlation tests pass. The UI truthfully retains the OS's generic failure notice. |
| Historical helper hashes conceal different tested code | Each authentication receipt names its committed observer revision. Every helper digest is checked against that exact tree; both observer and binary revisions must match current production source. Current outcome validators still apply. This preserves the valid Mac observation across the Linux-only verifier correction without changing its outcomes. |
| Package or prior success hides missing checks and cleanup | The gate checks all stage statuses and log hashes, artifact sizes/digests, test counts, host validation, packaged native replay, tray and installed-source identity. The earlier failed attempts remain retained. All fixtures in both successful authentication runs are gone; the older interrupted Linux fixture has an identity-bound cleanup receipt. |

## Evidence and limits

The final gate passed 530 Python tests, 129 application tests and the collector
suite, and revalidated the native/package artifacts. Full Linux acceptance had
already passed 1,063 preservation tests, ten input-focus tests, live host
comparisons, native replay, packaging, packaged replay, tray and installation/
removal against the identical release binary. Mac build/native records retain
its application, collector and vendor checks. Tests were not rerun during this
read-only review.

Mac signaling depends on a private native interface; unsupported versions fail
closed and report an error. KDE may report cancellation as generic authorization
failure; this does not permit a signal. These are disclosed platform limits,
not claims of wider platform coverage. The earlier performance and GPU
commitments remain incomplete and outside this commitment.

Ripwire quality delta exits 2 with broad existing/reference findings; no clean
whole-repository quality claim is made. Its committed-tree test gate exits 0.
The scoped code and evidence review found no additional actionable defect.

## Production self-audit

Reviewed the completed work against the imported production rules: scope and
contracts, bounded changes, maintainability, input/identity validation, errors
and credentials, privilege boundaries, state/lifecycle behavior, performance,
todo accuracy, executed verification, honest limitations and documentation.
The requested commitment is implemented and verified; no known missing
requirement or failing commitment check remains. No unrelated optimization,
single-instance change, publication or additional commitment was added.
