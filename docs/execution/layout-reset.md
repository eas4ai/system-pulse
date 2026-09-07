# Layout reset recovery

Verified locally on Linux, 2026-09-07.

The toolbar now offers **Reset layout** independently of the docked Settings panel. Confirmation restores the Default panel arrangement, sizes, visibility and panel expansion. Sensor choices, theme/fonts, sampling interval, named presets and the quick preset remain intact. Cancel and Escape leave the workspace unchanged. Reset uses normal autosave and preserves rejected-input/read-error guards.

The regression test initially failed because the recovery control was absent. After implementation, all 90 application tests and 1,444 workspace tests passed; two existing macro doctests remain ignored. Formatting, application Clippy with warnings denied, debug build and release installation passed.

Native replay against both the debug and installed release binaries recovered a saved empty layout through the toolbar. It verified confirmation, Escape and pointer cancellation, Tab/Return confirmation, customized appearance/interval/sensor preservation, byte-identical preset files, autosave and restart. Before, confirmation, restored and restart screenshots were captured; confirmation and restored screens were inspected.

Evidence: `/home/shawn/workspace2/task-manager-artifacts/layout-reset-20260907/`. GitHub CI remains disabled at the developer's request. This change provides default-layout recovery; it does not retain a history of earlier autosaved arrangements. Saved custom arrangements remain available through presets.
