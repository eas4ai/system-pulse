# Process table improvements — completed verification

All five PROC requirements have passing committed Cairn evidence at
`20260909T153100594Z` / `20260909T153100595Z`. The
[final review](../../../.cairn/reviews/process-table-improvements.md) found no
additional actionable defect.

- The table fills available width, retains aligned headers/rows and scrolls at minimum width.
- Search stays compact; Mac hides Threads while Linux retains it.
- End and Force Quit request OS authentication only when ordinary permission is insufficient.
- Both hosts passed actual system cancellation, authenticated End/Force Quit and expired-target rejection with an unprivileged UI.
- Selection, sorting, filtering, ordinary controls and Linux package acceptance pass.

[Verification and retained failures](authentication-verification.md),
[progress](progress.md), and [native receipts](evidence/) provide the evidence.
The complete Linux package run passed 1,063 preservation tests plus ten
input-focus tests and all native/package stages. Final verifier testing passed
530 Python tests, 129 application tests and the collector suite.

Production source is unchanged from `7c203bc9`; later commits record verification
and review. The earlier performance and GPU commitments remain incomplete.
This record does not claim those targets or additional hardware coverage.
