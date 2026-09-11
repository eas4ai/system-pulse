# Windows GPU detection parity

Status: Agreed 2026-09-11; next after Windows UAC acceptance
Slug: windows-gpu-detection
Requirements: WGPU-001

Contract: [Windows GPU detection parity](../spec/windows-gpu-detection.md).

The developer requires Windows to detect the same GPU vendors as Linux, including
integrated, discrete and multiple adapters. Discovery must not depend on successful
vendor telemetry initialization. Preserve explicit physical units and unsupported
readings, Linux/macOS collection and the completed Windows process actions.

Done requires boundary tests, a native Intel Iris Xe inventory comparison and
packaged UI observation, preservation checks, current support documentation and a
clean final review. The supplied references are Cores 0.43.0 and
LibreHardwareMonitor 0.9.6. Missing energy and thermal providers remain a separately
recorded issue until their implementation scope and access requirements are settled.
