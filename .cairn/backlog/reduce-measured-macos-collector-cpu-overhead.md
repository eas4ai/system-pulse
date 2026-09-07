# Reduce measured macOS collector CPU overhead

Surfaced from: finish-application
Captured: 2026-09-07T23:19:20.795Z

The developer approved a focused performance commitment on 2026-09-07: reduce native Mac release CPU by at least 50 percent in both Summary and tray-only modes, measured in three 60-second windows per mode against the unchanged release at the same one-second interval. Preserve live readings, history, errors, discovery and interaction. Baseline af243cf2 is 12.69 percent Summary and 11.46 percent tray in preliminary 30-second measurements; approximately 10 percentage points come from the collector.
