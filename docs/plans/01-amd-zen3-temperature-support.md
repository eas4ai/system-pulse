# AMD Zen 3 package temperature support

User-requested follow-up to the tested Ramag port, based on System Pulse
`f1be5d51d24c21fa8c740be79200bdda3df3a00c`.

## Scope and acceptance

Support one AMD Zen 3 physical package with CPUID family 0x19 / model 0x21,
including Ryzen 9 5900X. Keep the existing Intel 0x9a package DTS behavior.
Use the unmodified official signed PawnIO.Modules 0.2.11 AMDFamily17 module,
only `ioctl_read_smn(0x59800)`, and a bounded shared PCI mutex. Tag and validate
Intel/AMD operands separately. Check CPU/driver availability before elevation,
retain specific short-lived helper errors, and never substitute zero for failure.
Keep identity checks, cancellation, watchdogs and the unelevated dashboard.

Update source notices, user setup instructions and the independent Windows
acceptance verifier for AMD raw operands and scope. Driver installation requires
user approval. Do not change GPU/EMI sampling, publish a release or alter
unrelated work.

## Validation

- Run collector thermal tests, application tests, formatting and workspace
  all-target Clippy; keep any platform warnings visible.
- Run the verifier's Python tests, including invalid AMD raw operands, stale
  clocks, source mismatch and exact decoded temperature.
- Build and run the complete local System Pulse executable. Close its old
  instance before launching the new one. Use Computer Use for Thermals.
- Record actual driver/hardware evidence separately from synthetic operands.
  Install PawnIO only after user approval. Docker is not applicable.

`cairn wake` cannot run on this Windows host: Cairn and rtk are not installed.
This user-authorized pull request records ordinary local validation; it does
not claim Cairn acceptance, signed-package acceptance, CI success or untested
Linux/macOS hardware results. Existing Cairn records remain unchanged.

## Rollback boundary

Revert this feature commit to restore the Intel-only collector, bundled modules,
verifier and setup documentation. Shared PawnIO installation is managed separately
and is not removed by reverting application code.

## Local validation results

Windows collector library tests: 120 passed, 1 ignored (the existing WDDM native
test). Application library tests: 136 passed. Formatting and workspace all-target
Clippy passed; Clippy reported three existing `chunks_exact_to_as_chunks` warnings
in `windows_energy.rs` and `windows_gpu/native.rs`, none in thermal code.

The full local System Pulse executable built successfully with
`cargo build --locked -p system-pulse`. Computer Use launched that executable
after confirming there was no old System Pulse process. On the Thermals page,
the CPU package card showed a live 67.4 °C reading. Disabling CPU temperatures
removed the CPU card and returned the hottest-sensor display to the GPU. Enabling
CPU temperatures again restored a live 68.0 °C reading; GPU temperature remained
available throughout.

After the user approved installation, the official PawnIO 2.2.0 installer passed
Authenticode and pinned SHA-256 checks, exited successfully, and installed a
running PawnIO driver. The independent probe identified AMD family 0x19/model
0x21 and one CPU package. Opening PawnIO and loading the pinned AMD module both
succeeded. Three reads of the fixed SMN offset 0x59800 returned eight bytes with
no error and decoded to 75.375 °C, 77.5 °C, and 77.625 °C. The raw probe output
remains in the local temporary verification directory and is not committed.

Ramag's already committed and pushed CPU-temperature change was also tested in
the full locally built executable. Its CPU package card showed live readings
between 68.6 °C and 75.4 °C; disabling sampling removed the CPU card and made
the Enable action available again. Re-enabling through the live window restored
CPU readings. The successful independent probe corroborates the shared AMD
sensor path.

Validation passed: collector library tests (120 passed, 1 ignored WDDM-native
test), application library tests (136 passed), 47 Python verifier and packaging
tests, workspace formatting, and workspace all-target Clippy. Clippy emitted
three existing `chunks_exact_to_as_chunks` warnings in `windows_energy.rs` and
`windows_gpu/native.rs`; thermal code emitted none. The two PowerShell acceptance
scripts parsed successfully, and the probe's processor-package check returned
one package without opening PawnIO. `git diff --check` passed. Hosted CI and
Docker tests were not run; Cairn and rtk are unavailable on this Windows host,
so this PR claims ordinary local validation only.
