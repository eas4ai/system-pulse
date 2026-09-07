# Combined CPU tray graph

Implementation: `6e7687aeb0c381e73ab95407800418810ce7fcdf`.
Tray fork: `eas4ai/gpui-kit-tray` at `5e0f637069e6d5ba8bdee6872f1ed935348642a0`.

The tray renders the existing aggregate CPU history on a fixed 0–100% scale. Closing the dashboard retains its sampler and bounded history while the tray is available. Activation reopens the saved screen with fresh native controls. Quit preserves settings and exits. An absent host retains ordinary close-to-exit behavior; losing the host while hidden restores the dashboard.

Verification completed on Linux:

- Workspace tests, 481 Python tests, rustfmt and strict Clippy passed.
- Separate specification and code quality reviews approved the application and tray fork.
- The full packaged application gate passed: preservation, input focus, dependency notices, native product replay, tray replay, and isolated installation/removal.
- Native tray protocol checks covered aggregate CPU tooltip accuracy, changing icon bytes, background sampling, reopened history, light-theme preferences, keyboard input, host loss/return, menu Quit and absent-host shutdown.
- Reopened CPU history grew from 3.9 to 8.9 seconds during the packaged tray replay.

Evidence is under `/home/shawn/workspace2/task-manager-artifacts/cpu-tray/application-acceptance-r2/`, with `application-manifest.json` recording the complete pass. The first aggregate attempt failed the existing two-second snapshot-age limit during device navigation (3.534 seconds). Its evidence remains under `application-acceptance/`; an unchanged full rerun passed without relaxing that limit. The cause of that transient delay was not established.

The package includes 582 dependency notices, including the pinned Apache-2.0 tray fork. Its executable was installed at `/home/shawn/.cargo/bin/system-pulse` with SHA-256 `aebd8c7616dad930dd8f43a35defa82c550b265ebe7a1f1b26b6462f8565f93d`. The previous executable was backed up and the running application was left untouched. Restart System Pulse to use the tray.

macOS, Windows and other desktop shells were not exercised by this Linux verification.
