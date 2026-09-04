# Native fixture acceptance — 2026-09-04

Result: PASS on Linux for the workspace visibility/collapse fixture scope. Verified source: `88343d5ed3be72865e52fc3d51a860649d8def83`. Final running binary SHA-256: `162facf9d5402761aa0ca3e39ee2c834903d0eee1008d9b024cd43cf90e67cf2`.

The root executor used real GPUI windows in private Xvfb/D-Bus sessions, XTEST pointer/keyboard events, AT-SPI, and llvmpipe Vulkan. The app used isolated `SYSTEM_PULSE_STATE_DIR` directories. All app shutdowns returned zero. Desktop preferences were unchanged.

## Results

- Edge splits, divider resizing, center/header merge rejection, and hide/re-enable preserved separate regions.
- Wheel, scrollbars, and keyboard reached both overflow axes and process row 499. Table-edge wheel and Tab reached the surrounding workspace.
- Collapse retained independent row state and selected meters. CPU restored measured 1328×280 after collapsing to 36 pixels; the compact header remained readable at 320 pixels wide.
- Full fixture cycles showed current, stale, and unavailable compact readings with retained units. Model/app tests verified continued bounded history.
- All 15 disclosure controls responded to Enter and Space; AT-SPI emitted 30 expanded-state changes. The local adapter patch includes provenance and two regression tests.
- Repeated settled focus revealed the complete control border on both axes. Deliberate scrolling stayed unchanged across a fixture tick.
- Shrinking 1440×1000 to 960×640 and growing back preserved saved state, native panel order, and disclosure choices.
- Immediate resize/quit without Save restored height 332. A final restart preserved mixed panel/row collapse and CPU's measured 320×280 split geometry. Preset recall and GPU discovery reversal/disconnect/reconnect preserved identities.
- Invalid 9,647-byte layout input survived collapse, Save, and preset recall unchanged. Explicit recovery archived the exact original before writing a valid layout; keyboard navigation remained usable afterward.

## Automated checks and evidence

Final checks passed: Base dock 205, Base resizable 13, UI dock 19, model 15, app 21, and AT-SPI adapter 2 tests — **275 total**. Affected-package formatting, strict combined Clippy (`--all-targets --no-deps -- -D warnings`), `cargo build --locked -p system-pulse`, and diff checks passed. Independent component spec/quality reviews and final source review passed.

The companion design repository retains exact commands, logs, native result JSON, accessibility trees, screenshots, checkpoint binary hashes, and the interactive driver at:

`/home/shawn/workspace2/task-manager/docs/superpowers/execution/artifacts/2026-09-04/`

Its report is `docs/superpowers/execution/2026-09-04-workspace-visibility.md`. Run instructions and repeatable scenarios are in [README.md](README.md).

This is a deterministic interaction proof. Live collectors, process control, production styling, full preset management, and performance targets remain outside its scope. Linux results do not establish macOS or Windows acceptance.
