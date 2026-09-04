# System Pulse fixture workspace

This native interaction proof uses deterministic simulated readings. It does not inspect or control real processes and does not run operating-system collectors.

From the fork workspace root:

    rtk cargo run -p system-pulse
    rtk cargo test -p system-pulse --lib

State is stored under `system-pulse-fixture` in the platform configuration directory. `SYSTEM_PULSE_STATE_DIR` selects an isolated directory for interaction checks. Reads are bounded to 1 MiB. Atomic temporary-file replacement and ordered revisions protect background saves. Invalid layout bytes remain untouched until explicit recovery; read failures block saving until the error is corrected and the app restarts. Closing the final window flushes current divider preferences without clicking Save. One preset slot is provided to verify save/recall behavior. Full preset management is outside this proof.

The default is a vertical stress-test arrangement so the outer viewport must scroll. It deliberately differs from the production left/right layout in the feature specification. Default panels and rows are expanded. A panel title is the drag handle. The buttons beside it expand/collapse and hide the panel. The toolbar re-enables hidden panels. Row controls independently fold the meter, hide the sensor, and change meter type. Compact summaries keep updating every second through a deterministic 12-tick cycle, including simulated unavailable/stale states. Histories keep the latest 120 samples for every fixture sensor, including hidden or collapsed sensors; charts leave gaps for stale and unavailable readings. Meter values are normalized demonstration data, not measurements.

The dock geometry contract is 320×220 pixels minimum, 420×280 preferred, and 36 pixels for a collapsed header. These are the deliberate pixel boundary; ordinary controls and table measurements follow the rem scale.

Alt+PageUp/PageDown scrolls the workspace vertically; Alt+Left/Right scrolls horizontally. The table uses Up/Down/Home/End; Tab leaves it. Scrollbars provide an independent pointer route to the workspace even when the pointer is over the table.

## Native acceptance record

Linux native acceptance passed on 2026-09-04 at source commit `88343d5e`. The final combined checks passed 275 tests, package formatting, strict all-target Clippy, and the locked native build. The [dated acceptance record](NATIVE_ACCEPTANCE.md) distinguishes automated checks from display-level interactions and identifies the retained evidence. Use the scenarios below when repeating acceptance on another build or platform.

The repository-local [AT-SPI adapter patch](../../vendor/accesskit_atspi_common/PATCH.md) preserves expanded/expandable state without changing dependency versions. Linux native checks verified all 15 disclosure controls and their expanded-state change signals.

1. At the minimum 960×640 window, scroll to all eight panels with the wheel and workspace scrollbar. Resize the window smaller/larger within the supported limit; no panel visibility or collapse state changes.
2. Drag CPU by its title to the right and below GPU A. Both edge placements work. Attempt center and header drops: source identity and position remain intact, and no tab strip or tab group appears. Drag each exposed divider and verify measured regions resize. Record CPU's resized width and height, collapse it, then expand it and compare against the recorded dimensions. Repeat with collapsed CPU beside a taller expanded neighbor: CPU remains header-only, the neighbor keeps its useful body, and expansion restores CPU's preference. Place enough panels side by side to exceed the viewport width and reach every panel using both the horizontal scrollbar and Alt+Left/Right. Close/re-add a monitor and verify it appears as its own region.
3. Collapse CPU's overall row, collapse CPU, then expand CPU. The overall row remains compact in its original position. Change its meter while compact, hide/show it, and expand it. The selected meter returns with continuous bounded history.
4. Keep CPU collapsed through a complete 12-tick fixture cycle. Its summary updates and explicitly says Unavailable/Stale at the defined ticks. Settings collapse keeps only its title and controls. GPU A and B retain independent state despite discovery-order reversal.
5. Scroll within the long process table to row 499, then reach Settings with the workspace scrollbar and keyboard shortcuts. Wheel over the table scrolls its rows; at its vertical edge the ancestor remains scrollable. Tab out of the table and navigate to a panel above the viewport; focus is revealed without losing the selected process row.
6. Focus every expansion control and activate Enter and Space. Inspect the accessibility tree: each is a button with a descriptive name and expanded state. Activating header buttons never starts a drag. Collapse a panel while a descendant has focus using the native test command path; focus lands on its expansion button.
7. Save a preset with mixed panel/row collapse, change both, and recall. Restart the app and compare placement, expanded preferences, and collapse states. Disconnect/reconnect GPU A and reverse discovery; state remains associated with fixture A, never fixture B.
8. Close the app. Preserve a copy of workspace.json, insert a second child into a tabs group, and restart. A valid default opens with an error; original workspace.json bytes remain unchanged after normal interactions. The “Accept recovered layout” action writes workspace.rejected.json before accepting the currently recovered valid layout. Verify a normal preset recall cannot bypass the recovery gate.

Linux is the primary interaction-proof platform. On macOS, follow the fork's `docs/ACCESSIBILITY-UI-TESTING.md` to run a signed .app before accessibility inspection; a bare cargo-run process is insufficient evidence there. Record any platform unavailable to the executor. Do not infer cross-platform acceptance from Linux results.
