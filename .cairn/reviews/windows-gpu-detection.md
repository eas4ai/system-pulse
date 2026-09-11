commitment: windows-gpu-detection
commit: a05e90aa3764f5c45cac89d5ebf3945a8d40c94c
examined:
  - WGPU-001 contract, falsifier and discovery decision
  - SetupAPI inventory, PnP interface resolution and D3DKMT resource ownership
  - Counter resets, memory scope and optional NVIDIA identity reconciliation
  - GPU visibility, accessibility and diagnostic publication recovery
  - Native package provenance, independent observations and platform preservation
findings:

## Final review

WGPU-001 passed in receipt 20260911T123129434Z. No production or mechanism
code changed during this review. The review found no actionable defect.

| Attack | Result |
| --- | --- |
| Missing vendor telemetry hides a healthy adapter | SetupAPI owns discovery. Optional name, PCI and LUID metadata cannot remove the adapter. Failed discovery retains known identities with failed readings and disables stale NVIDIA mappings. Initial failure creates no synthetic device. |
| Reordering, identical device models or runtime LUID changes merge devices | Full normalized PnP instance IDs own persistence. Exact PnP-filtered display interfaces supply only runtime LUIDs. Conflicting interface LUIDs fail telemetry. Duplicate and ambiguous PCI mappings cannot receive NVIDIA data; neither names nor enumeration indices are fallbacks. |
| Driver reset or multiple engines fabricate utilization | Per-node baselines include PnP identity and LUID. Missing, removed and failed samples evict baselines. Counter regression and impossible deltas warm up again. The reported value is the busiest engine, with original tick and time operands retained. |
| Integrated memory becomes fictitious discrete VRAM | Dedicated resident segments and reserved dedicated system memory retain their explicit scope. Shared resident bytes have no capacity ratio. Overflow, invalid aperture and impossible dedicated totals fail explicitly. |
| Native errors leak resources or read invalid buffers | Device sets and graphics handles have scoped cleanup; normal adapter close errors are checked. Buffers, interface lists, device/node/segment counts and arithmetic are bounded. Registry types and lengths are checked. Native requests initialize the appropriate union and use writable output storage. |
| Unsupported sensors vanish or appear as zero | GPU-specific channel selection includes unavailable readings while retaining user visibility choices. Sensor values remain absent with reasons. Actual packaged screenshots show legible identity, utilization, separate memory labels and Unavailable temperature/power. |
| Diagnostic readers corrupt state or stall the UI | Only transient background publication retries Windows errors 5/32, at most ten 10ms waits. Persistent failure retains the old record, cleans the temporary file and permits later recovery. Durable configuration policy is unchanged. Native regression tests establish both short-reader recovery and bounded persistent-reader failure. |
| A receipt accepts an unrelated binary or a visually broken screen | Production source, build, packaged binary, capture harness and artifact hashes are checked. Raw readings are reconciled against independent Windows counters for the same LUID. Both actual screenshots were inspected, including error-banner absence; accessibility alone cannot establish that. |

## Failure demonstrations and evidence

Eight acceptance-verifier tests exercise both valid records and violating
inventory, fabricated/missing readings, arithmetic, adapter matching, accessible
labels and process preservation. The native GPU regression failed with the
original missing-LUID implementation and passed after exact device-interface
resolution. The short-reader storage regression failed before the bounded retry
and passed afterward. Earlier captures with unavailable telemetry, missing
accessible labels and a diagnostic save error remain retained separately; none
is substituted for the final native capture.

The accepted production revision is 251cb72fabc02ca17282af08af5864d8058dcf06.
The final package ran unelevated on Windows 11 with Intel Iris Xe. Inventory,
scheduler and memory comparisons, diagnostic and normal launches, process rows
and clean tray exits passed. Windows ran 245 ordinary tests plus the explicit
hardware GPU test, Clippy and a release/package build. macOS ran 254 tests and
Clippy against that revision. Linux acceptance reran application, model and
collector tests. The complete Python harness suite passed 577 tests.

## Limits and production self-audit

AMD/NVIDIA hardware, multiple physical adapters and physical removal were not
available for native testing; their boundary tests establish behavior, not
hardware telemetry accuracy. Unsupported temperature, power and clocks remain
explicit. No driver installation, hosted CI, push or release was performed.
Completed process-action implementation is preserved; this capture verifies
process rows and ordinary lifetime, not a new full UAC consent replay.

Windows Clippy reported one chunk-iteration style suggestion. macOS retained
nine dependency warnings and the existing block future-compatibility notice.
Ripwire quality-delta crashed; no clean result is claimed. Its final committed
test-gate reported no changed symbols and adds no test coverage. Graph transport
was closed, so focused source inspection used Tilth and the earlier Ripwire
results.

Reviewed the imported production rules for scope, minimal changes,
maintainability, boundaries, errors, privileges, state recovery, bounded work,
verification, evidence honesty and readable documentation. Implementation and
required verification are complete, with the hardware limits above.
