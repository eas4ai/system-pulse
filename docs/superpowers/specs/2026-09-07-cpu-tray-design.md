# CPU tray graph

The user approved one small combined CPU-load graph, like the Windows Task Manager tray icon, and monitoring after closing the window.

Use the eas4ai/gpui-kit-tray fork with the same gpui-pre 0.3.2 dependency as System Pulse. Keep the fork generic and the CPU graph in this app.

Render one green CPU history graph in a small square RGBA icon, with a fixed 0–100% range and a current-value tooltip. Use the existing aggregate CPU samples and sampling interval. Missing/stale readings remain distinct from zero. The menu contains Open System Pulse and Quit; activating the icon opens or raises the dashboard. No extra meters or sensor configuration.

Retain the existing workspace and sampler when the native window closes. Continue accepting samples and bounded history without a Window. Recreate window-dependent views when reopening; preserve screen, device choices, settings and history. Use the ordinary autosave and orderly quit paths. Do not launch a second sampler.

On Linux, the library must report whether a tray host is available. A missing host must not leave the application hidden and unreachable: ordinary window closure exits when tray support is absent. If the host disappears while the window is closed, restore the window. Polling must continue while the icon is updating.

Alternatives considered: minimizing retains the taskbar window; GPUI hide is unimplemented on Linux. Retaining the monitoring owner while recreating views gives actual close-to-tray behavior without modifying GPUI.

Verify icon bytes, zero/full/missing/stale values, bounded history, close/reopen continuity, single collector, menu Quit, missing host, host recovery and dark/light panel visibility. Run app and fork tests, format/lint, then exercise the real Linux SNI/DBusMenu protocol in a private session. Preserve the user's running app and configuration during verification.
