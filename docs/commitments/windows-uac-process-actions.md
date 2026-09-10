# Windows UAC process actions

Status: Draft 2026-09-10 — awaiting activation
Slug: windows-uac-process-actions
Requirements: WUAC-001, WUAC-002, WUAC-003, WUAC-004, WUAC-005, WUAC-006

Contract: [Windows UAC process actions](../spec/windows-uac-process-actions.md).

Outcome: Windows users can perform the graceful-close and force-termination actions with
ordinary permissions where sufficient, and approve one elevated helper through
UAC when necessary, while the monitor stays unelevated and responsive.

Scope: Windows native process identity and process-control backend; the existing
helper entry and authentication dispatch; action/confirmation/result UI; targeted
tests and Windows native harnesses; necessary packaging and support documentation.
Retain existing Linux/macOS behavior. The exclusions and execution policy in the
contract apply.

Done requires all six requirements to have committed-source passing evidence,
actual UAC approval/cancellation and stale-target observations, packaged-layout
verification, preservation checks and a recorded final review with no unresolved
findings. Merely compiling on Windows is insufficient.

Activation requires moving the roadmap's Current line. This draft neither activates implementation nor declares the prior
release-candidate commitment complete. Its remaining bookkeeping stays visible.
