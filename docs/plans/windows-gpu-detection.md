# Windows GPU detection parity

Contract: [WGPU-001](../spec/windows-gpu-detection.md).

- [ ] In progress: map independent Windows inventory, telemetry and existing identity paths; record the implementation and acceptance decision.
- [ ] Implement vendor-independent discovery and available usage/memory readings; verify vendor/identity/removal/error boundaries and Linux/macOS preservation.
- [ ] Build and package on Windows; compare Iris Xe with independent native inventory and readings and inspect the actual GPU screen.
- [ ] Commit passing acceptance evidence, review the completed work and finish Cairn verification.

Native verification must leave the dashboard unelevated. Missing hardware is a
telemetry coverage limit; it does not justify dropping healthy detected adapters.
Low-level sensor drivers are outside this implementation unless separately decided.
