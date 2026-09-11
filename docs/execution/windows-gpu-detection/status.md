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
- Windows collector Clippy recheck passed with no issues after addressing three warnings.
- Native Windows tests/build are running against d5ac44902e64b1d675470ff97d17115f32948579. Log: `/home/shawn/workspace2/.system-pulse-test-tmp/system-pulse-windows-2else4ia/build.log`.

Resume through `cairn wake` and reconcile the existing implementation action.
The implementation and decision are committed. The acceptance verifier now checks inventory, exact scheduler/memory operands, independent counters matched by adapter LUID, native GPU labels, a normal launch without diagnostics and process-table/quit preservation. Eight safe violating/corrected-case tests passed; native PowerShell parsing passed. Acceptance still requires the actual packaged capture and visual review.

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

Desktop capture scripts `windows_gpu_collect.py` and `windows_gpu.ps1` are drafted. Python parsing and native PowerShell parsing passed; the actual packaged run has not happened. Whole-workspace Clippy passed with no issues. Independent Windows GPU Adapter Memory counters are readable and return distinct LUIDs; correlate the hardware adapter instead of summing all instances.

Final candidate: 58891256cb59e1fb405dc22d85db9c54c81c794a. Native Windows tests passed again; final release/package operation is running via `/home/shawn/workspace2/.system-pulse-test-tmp/finish_windows_gpu_build.py`, with logs in `windows-gpu-final-58891256/`. Native Mac application/model/collector preservation passed 254 tests and Clippy (nine existing vendor/sysinfo warnings and the existing block future-compatibility notice remain visible in retained logs). All 577 Python verification-tool tests passed. Windows cross-check, Windows collector Clippy and formatting passed after registry property type validation. Ripwire edit-check and quality-delta terminated with signal 11; no clean result is claimed. Its test-gate returned zero with no uncommitted code changes, so it supplies no additional test coverage.

The first packaged capture at 58891256 detected Iris Xe correctly but failed telemetry acceptance: DEVPKEY_Device_AdapterLuid was absent. The retained initial-missing-luid capture is not acceptance. A CM display-interface probe filtered by the exact PnP ID opened successfully and returned LUID 56855 (0xDE17), matching independent Windows counters; it closed its handle successfully. The explicit native WDDM regression failed before the fix and passed after resolving the LUID through the actual display interface. Normal discovery remains independent of this optional lookup.

The same capture showed a diagnostics save error. A native file probe reproduced Windows error 5 while a reader held the replaced file and success after closing it. The GPU capture now reads and closes before JSON parsing instead of holding Get-Content open through the pipeline. The verifier rejects a visible storage error and reports missing raw observations cleanly; its safe failure demonstrations passed again. Final packaged recapture remains pending.

Current candidate after the native fix: c7faab632fa755f3835b539c38fe26471898a402. Native Windows tests and the explicit ignored WDDM regression have passed; release/package operation is running via `/home/shawn/workspace2/.system-pulse-test-tmp/build_windows_gpu_interface.py`, with logs/package under `windows-gpu-final-c7faab63/`. All 577 verifier-tool tests passed again after tightening the native error checks. Their final log is retained as verifier-tests.log. The next action is packaged recapture with windows_gpu_collect.py, then arithmetic/counter/UI validation and a genuine screenshot review before Cairn acceptance.

The c7faab63 packaged capture passes independent inventory, exact scheduler/memory arithmetic and the matched Windows counter comparison. Both diagnostic and normal screenshots show measured GPU usage, dedicated memory (0 of 128 MiB) and shared memory (about 902 MiB), with explicit unavailable temperature/power and no storage error. Native accessibility exposed the dedicated-memory value without its label, so the full UI validator correctly failed. The GPU capacity section now follows the existing metric group pattern with a stable ID, Group role and its sensor label. Packaged accessibility recapture is required before acceptance. The full intermediate evidence is retained under readings-before-accessible-label.
