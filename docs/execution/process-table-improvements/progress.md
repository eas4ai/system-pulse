# Process table improvements

- [ ] In progress: inspect existing table, controls and verification; implement and verify responsive width and compact search.
- [ ] Pending: implement and verify platform column visibility.
- [ ] Pending: record authentication design, implement and verify privileged actions.
- [ ] Pending: run committed acceptance and review all five requirements.

The previous performance pass is suspended, with its CPU targets unmet and
its verified preservation evidence retained. No further optimization is planned.

## PROC-001 work in progress

The original table left unused width at 1280 pixels. A new rendered-layout
regression reproduced this before the fix. The table now uses available width
with the content width as its minimum; the Name heading and cells receive excess
space, and virtualized rows fill their root allocation. The test checks header
and row alignment across 1280, 1800, 2560, 960 and 1280 pixel window sizes.
The targeted regression and all 127 application tests pass. Linux development
replay also passes: 1280 and 1800 pixel windows fill their width; minimum-width
horizontal scrolling exposes User with aligned headers and cells. Five receipt
validation tests pass, and the extended Swift accessibility helper compiles.
Committed Linux/Mac resize evidence remains pending; the Mac session is locked.

The process-table mechanism is declared. Its initial run records missing verifier
implementation as unverified; no PROC requirement has a passing Cairn receipt.
