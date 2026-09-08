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
The committed Linux replay passes with build/source and harness provenance in
`evidence/linux/`. Mac application tests and its release build pass;
Mac resize observations also pass at 1280, 1440 and 960 pixels, including
horizontal access to User. The Mac verifier supports the host Python 3.9;
explicit length checks precede paired-column comparisons. Cairn validation
against the committed evidence is next.

The process-table mechanism is declared. Its initial run records missing verifier
implementation as unverified; no PROC requirement has a passing Cairn receipt.

Ripwire `process_row` edit-check found no signature change or incompatible caller.
The whole-repository quality delta exited 2 with broad existing/reference-symbol
findings; it is not a passing quality claim. The post-commit test gate reported
zero uncommitted changed symbols. Application and native checks provide the
behavioral verification above.
