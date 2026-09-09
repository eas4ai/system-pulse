# Keep one normal desktop instance and focus it on relaunch

Surfaced from: PROC-004
Captured: 2026-09-09T14:01:44.956Z

The developer observed two running instances during privilege verification and expects task-manager single-instance behavior. A second normal launch should activate the existing application instead of creating another UI or tray icon. The one-action privileged helper must remain separate and must not acquire the GUI instance lock. Define per-user/session behavior, crash recovery and isolated native-test operation in the next agreed contract before implementation.
