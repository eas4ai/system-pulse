# Windows GPU detection verification

Status: implementation in progress; native evidence pending.

Completed prior commitment: Cairn reported Windows UAC process actions and GPUI
Kit 0.6.1 Done on 2026-09-11. Its final review is
`.cairn/reviews/windows-uac-process-actions.md`.

Current work adds SetupAPI PnP inventory, optional D3DKMT scheduler/memory
readings, exact PCI reconciliation with NVML and explicit unavailable GPU rows.
New sources are `crates/collectors/src/windows_gpu.rs` and its `native.rs` and
`tests.rs` children. Host and NVML integration preserve the other platforms.

Editing checks executed so far:
- Collector library: 128 tests passed after correcting a floating-point test tolerance.
- Windows MSVC collector/tests cross-check passed after correcting the SDK query pointer mutability.
- GPU UI regression passed, including explicit unavailable readings and user-hidden sensors.
- Application/model/collector tests: 298 passed across 13 suites.
- Windows collector Clippy passed with three warnings, subsequently addressed; recheck pending. Native Windows compilation/execution is still required.

Resume through `cairn wake` and reconcile the existing build-decision action.
The implementation decision has not yet been marked realized. The acceptance
mechanism is declared, but `scripts/system-pulse/windows_gpu_verify.py` remains
to be implemented. Its baseline failure is honest pending evidence, not a pass.
Demonstrate that the verifier rejects a missing adapter/invalid reading and
accepts the corrected case before recording acceptance.

Next: finish UI and collector checks, inspect native buffer/identity/cleanup
boundaries, commit the candidate, build on the existing Windows host, collect
independent inventory and current graphics readings, inspect the packaged GPU
screen, run platform preservation, then record final acceptance and review.
Native host: shawn@10.66.231.23. Existing Windows build script is
`scripts/system-pulse/windows_build_verify.py`; its native target cache is
`C:\Users\shawn\workspace\system-pulse-build-target`. Keep new GPU evidence separate
from the completed UAC package at source 3e6923e3. No native process is currently
waiting for UAC approval. Do not start hosted CI or publish.

No Windows GPU acceptance or AMD/NVIDIA hardware telemetry accuracy is claimed.
