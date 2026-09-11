# Windows GPU detection parity

Contract: [WGPU-001](../spec/windows-gpu-detection.md).

- [x] Map independent Windows inventory, telemetry and existing identity paths; record the implementation and acceptance decision. Reviewed SetupAPI, LHM D3DKMT, existing NVML and physical reading boundaries.
- [x] Implement vendor-independent discovery and available usage/memory readings; verify vendor/identity/removal/error boundaries and Linux/macOS preservation.
- [x] Build and package on Windows; compare Iris Xe with independent native inventory and readings and inspect the actual GPU screen.
- [x] Commit passing acceptance evidence, review the completed work and finish Cairn verification.

Native verification must leave the dashboard unelevated. Missing hardware is a
telemetry coverage limit; it does not justify dropping healthy detected adapters.
Low-level sensor drivers are outside this implementation unless separately decided.

Acceptance passed in Cairn receipt 20260911T123129434Z. The final read-only review
found no actionable defect; hardware and tooling limits are recorded in
[the review](../../.cairn/reviews/windows-gpu-detection.md).
