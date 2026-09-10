# Windows UAC process actions

Status: Agreed 2026-09-10
Slug: windows-uac-process-actions
Requirements: WUAC-001, WUAC-002, WUAC-003, WUAC-004, WUAC-005, WUAC-006, WUAC-007

Contract: [Windows UAC process actions](../spec/windows-uac-process-actions.md).

Outcome: Windows users can perform the graceful-close and force-termination actions with
ordinary permissions where sufficient, and approve one elevated helper through
UAC when necessary, while the monitor stays unelevated and responsive.

Scope: Windows native process identity and process-control backend; the existing
helper entry and authentication dispatch; action/confirmation/result UI; targeted
tests and Windows native harnesses; necessary packaging and support documentation; GPUI Kit 0.6.1 and required companion upgrades with local patch preservation.
Retain existing Linux/macOS behavior. The exclusions and execution policy in the
contract apply.

Done requires all seven requirements to have committed-source passing evidence,
actual UAC approval/cancellation and stale-target observations, packaged-layout
verification, preservation checks and a recorded final review with no unresolved
findings. Merely compiling on Windows is insufficient.

The developer confirmed the full single-commitment scope and then added the
latest GPUI Kit upgrade on 2026-09-10. This activation does not declare the prior
release-candidate commitment complete. Version 0.3.0 was published with passing
three-platform CI, but remaining Cairn bookkeeping retains its historical status.
