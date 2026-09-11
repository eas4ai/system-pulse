# Windows GPU detection parity

Status: Agreed 2026-09-11
Prefix: WGPU

The developer requires Windows to have the same GPU detection coverage as Linux.
This addition covers discovery and visible adapter identity across Intel, AMD and
NVIDIA; it does not permit inventing telemetry when a device or driver exposes
none. The missing Windows energy and thermal readings remain a separately
recorded product issue.

[WGPU-001] Windows MUST discover and display Intel, AMD and NVIDIA graphics adapters, including integrated, discrete and multiple-adapter systems, independently of vendor telemetry initialization. Missing vendor libraries or unsupported sensor APIs MUST leave the detected adapter visible with explicit per-reading availability. Discovery MUST retain distinct adapter identities and avoid duplicate devices when vendor telemetry is also available.
Falsifier: a healthy Intel, AMD or NVIDIA adapter reported by the independent Windows inventory is absent solely because its telemetry backend is missing; multiple adapters collapse into one or appear twice; unsupported readings are fabricated or presented as measured zero; or Linux GPU detection regresses.
Mechanism: compare actual Windows adapter discovery against an independent native inventory on the available Intel Iris Xe host; boundary tests for Intel, AMD, NVIDIA, multiple adapters, refresh/removal, failed discovery and missing telemetry; reconcile identity with existing NVIDIA telemetry; run collector/model tests and native packaged UI observation. Tests for unavailable AMD/NVIDIA hardware do not establish hardware telemetry accuracy.

## References and execution

The developer supplied local reference snapshots `reference/cores-0.43.0/` and
`reference/LibreHardwareMonitor-0.9.6/`, and
`reference/hwinfo-c-11/` ([lfreist/hwinfo](https://github.com/lfreist/hwinfo)). Cores uses LibreHardwareMonitor for its
Windows hardware backend. Inspect those implementations and preserve applicable
notices for reused code. Keep reference trees separate from application source.

Complete the already-running Windows UAC verification before activating this
commitment. Windows GPU discovery must not require elevating the dashboard.
Any low-level sensor driver installation needs its own concrete reviewed decision;
providing these references does not authorize installing a driver. Native testing
must preserve Linux/macOS behavior and the completed Windows process controls.
