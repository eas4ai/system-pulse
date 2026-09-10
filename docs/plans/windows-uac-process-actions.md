# Windows UAC process actions and GPUI Kit 0.6.1

Contract: [WUAC-001 through WUAC-007](../spec/windows-uac-process-actions.md).
All work stays local unless the developer separately authorizes a push or CI.

- [x] Activate the approved commitment, declare mechanisms and scope, and record the framework upgrade design after inspecting upstream and local patches.
- [ ] In progress: upgrade GPUI Kit and reconcile companion/native patches; verify the locked graph and applicable local checks.
- [ ] Implement Windows native process identity and graceful/forceful controls with boundary tests.
- [ ] Implement one-action UAC helper launch/result handling and responsive confirmation/error UI; verify ordinary, cancellation, denial and stale-target paths.
- [ ] Collect native Windows approval/credential/cancellation and packaged-layout evidence; run Linux/macOS preservation checks and update support documentation.
- [ ] Record final adversarial review, resolve findings separately, and finish Cairn evidence. No hosted CI or publication is included without separate authorization.
