# UI frame pacing and collection

Status: Observed 2026-09-05; proposed frame ceiling is not implemented.

The developer proposed a UI ceiling of 120 Hz, reduced to the display rate on a slower monitor, with independent collection at 500–1,000 ms. The agent recommends demand-driven rendering for active scrolling/animation and repaint only when static content changes.

Current collection uses a dedicated worker and a latest-only slot, defaulting to 1,000 ms and supporting 500/1,000/2,000/5,000 ms (`collectors/src/service.rs:8`). UI delivery checks that slot every 100 ms (`src/workspace.rs:421`). There is no perpetual application animation-frame loop. Keyboard repaint requests coalesce on the next frame (`src/workspace.rs:684`); other panel notifications remain immediate.

Pinned GPUI `f66ed399` handles platform frame scheduling. Its X11 backend uses an XRandR mode with a 60 Hz fallback and does not re-query timing when the window moves screens or the configuration changes (`gpui_linux/src/linux/x11/client.rs:1902`). Wayland uses compositor frame callbacks and parks idle loops (`gpui_linux/src/linux/wayland/window.rs:1901`). No explicit 120 Hz application ceiling exists. Robust current-monitor tracking and that ceiling would require a separate change.

Frame requests, view rendering, presented frames, and diagnostic model publication are distinct. Diagnostics precede repaint notification (`src/workspace.rs:547`) and are not native presentation acknowledgements.

This was read-only source inspection. No refresh-rate feature, test, build or native capture was performed, and no new requirement was agreed through this discussion.

Paths above are relative to `examples/system_pulse/`, except the GPUI paths, which are relative to the pinned Zed checkout's `crates/` directory.
