# System Pulse

System Pulse displays real Linux host snapshots in reference-based tabbed screens. CPU, memory, discovered GPUs, volumes, network interfaces, and processes use physical quantities and stable identities. Unavailable or failed sources retain truthful status; simulated readings are confined to tests.

From the repository root:

```sh
rtk proxy cargo run --locked -p system-pulse
rtk proxy cargo test --locked -p system-pulse --lib
rtk proxy python3 -B scripts/system-pulse/verify.py
```

The mandatory verifier builds and checks the affected packages, exercises independent proc/sysfs arithmetic and counter brackets, and replays native interactions in a private Xvfb/DBus session. It writes complete logs and fresh host/native evidence outside the checkout. Missing steps or counter brackets fail the aggregate. See [acceptance implementation status](execution/real-system-readings/acceptance-implementation.md) for recorded results and remaining verification.

`SYSTEM_PULSE_STATE_DIR` selects an isolated configuration directory. `SYSTEM_PULSE_DIAGNOSTICS_PATH` optionally exports the accepted live snapshot and rendered entries for acceptance inspection. Process arguments and environments are not collected. The process table uses PID and start ticks together, so an exited identity cannot silently become a reused PID.

Click a tab to open Summary, CPU, Memory, GPU, Disks, Network, Energy, Thermals, Processes or Settings. With a tab focused, Left/Right and Home/End select tabs. Ctrl+Tab and Ctrl+Shift+Tab cycle screens from their content. The last screen and explicit device choices save automatically. The reference-based screens replace the former dock canvas; old dock metadata remains compatible.

The system tray shows one combined CPU load graph on a fixed 0–100% scale. Its tooltip shows the current load or unavailable status. Closing the dashboard keeps monitoring and history running while the tray is available. Click the icon or choose **Open System Pulse** to reopen your current screen; choose **Quit** from the tray menu to exit. Without a tray host, closing the window exits normally. If the tray host disappears while the window is closed, the dashboard reopens.

Choose a named device above GPU, Disks or Network. Energy and Thermals select an individual measured sensor. Long selectors scroll and support Up/Down and Return. A disconnected saved device stays unavailable instead of silently selecting another. Thermals identifies the hottest current sensor even when a different or unavailable sensor is selected.

Charts show physical units and the actual captured time span. Gaps represent missing or delayed data. Percentage and capacity meters use their known scale; frequency, temperature, power and throughput meters follow the observed chart range. Hover Summary's compact meters for their sensor names and scale notes. The five subsystem cards show history graphs; Disks plots read/write I/O and retains used/total space above the graph. Network plots receive and transmit throughput. Disk capacity describes a filesystem; its read/write history describes the backing block device. Energy is a named sensor reading, not an inferred system total.

Unavailable sensor rows stay hidden until they recover. Failed, stale and warming-up readings retain explicit labels.

Summary's five subsystem graphs share one row on wide windows. Smaller windows use full-width rows of three and two cards, with no empty trailing column.

Settings contains appearance, sampling and preset controls. Existing sensor visibility preferences remain part of saved presets.

Network initially follows the Linux main-table default route (IPv4 before IPv6), then a physical interface if no default route is present. Choosing an interface saves your selection and takes precedence over automatic selection.

Process counters marked **No access** could not be read because the OS denied access; hover for the original error.

The process table searches name, PID and user and sorts each column using physical values. Select a row to inspect its current details. Up/Down/Home/End navigate rows, Left/Right scroll columns and Tab leaves the table. Hover a clipped cell for its full value or failure reason. The table expands with the window; search stays compact. macOS omits Threads. Process CPU uses one core as 100% and can exceed it.

End task and Force quit require confirmation and report visible errors. When an action needs administrative permission, the operating system asks you to authenticate. Enter your password only in that system dialog. System Pulse never receives or saves it, and its dashboard keeps running as your normal user. Cancelling authentication leaves the process unchanged. Linux and macOS verify the selected process identity after authentication and use kernel identity checks when signaling. macOS versions without the required native support report an error. Administrative permission does not override OS protection of protected processes.

Linux authenticated actions require `/usr/bin/pkexec` (polkit) and a running desktop authentication agent, normally supplied by KDE or GNOME. Ordinary actions on your own processes work without it. System Pulse does not use a terminal password prompt.

On Windows, **End task** requests graceful closure of the selected application's windows. The application may ask to save work or refuse to close. A windowless or otherwise unsupported target reports that graceful close is unavailable; **Force quit** remains a separately confirmed action. Force quit can lose unsaved work and affects only the selected process, not its children. The confirmation retains the selected PID and complete native creation identity even if the table order or selection changes.

Windows first tries the action with your existing permissions. If identity and safety checks pass but the action needs more permissions, Windows can open a UAC consent or administrator-credential dialog for one short-lived helper. A process whose safety cannot be verified is refused without requesting elevation. Enter credentials only into Windows. The dashboard keeps running with its original privileges, and another action cannot be submitted while authorization is pending. Cancelling UAC starts no helper action. The helper verifies the process identity again after approval; a process that exited or changed identity is refused. System Pulse does not enable debug privileges or bypass protected-process restrictions.

Windows reports a closure request, pending termination and observed exit separately. If the helper times out or cannot confirm its result, check the process list before trying again: an uncertain result does not establish that the process was untouched. Windows executables are currently unsigned; UAC may identify an unknown publisher. Normal launch does not request elevation. The [Windows action commitment](commitments/windows-uac-process-actions.md) tracks the required native approval, cancellation and packaged-helper verification.

**Settings** contains dark/light themes, bundled interface and numeric fonts, sampling intervals and named presets. Geometric screen headings use the bundled Michroma font. Save current workspace creates a named preset; Use recalls it. Rename, overwrite and delete retain confirmation and cancellation behavior. Built-in presets keep their saved sensor preferences and open Summary; fixed tabs remain reachable. The legacy quick preset file imports into the library as Imported preset when that library is first created.

The application saves settings automatically. Invalid saved bytes remain untouched across normal shutdown and restart until **Accept recovered settings** archives them and writes a valid replacement. Test or troubleshoot with a separate `SYSTEM_PULSE_STATE_DIR` to leave your normal workspace intact.

See [Linux package instructions](../package/README.md) for installation, removal, runtime requirements and the user guide. Build an archive from a committed tree with `python3 -B scripts/system-pulse/package_linux.py --output /outside/checkout/package-output --cargo-about /path/to/cargo-about`; it builds the release binary, gathers dependency notices, archives source and writes a checksummed installable package. The notice generator is cargo-about 0.9.2 (`cargo install cargo-about --version 0.9.2 --locked --features cli`).

Run `rtk proxy python3 -B scripts/system-pulse/application_acceptance.py` from a committed tree for the complete Linux product gate. It first verifies collector accuracy, compatibility and tabbed interactions, then builds the package and exercises native process actions, contexts, settings, presets, restart, isolated installation and removal. Process signals target test-owned children; the protected application case sends no signal. Set `SYSTEM_PULSE_CARGO_ABOUT` if the pinned notice generator is outside PATH, and optionally set `SYSTEM_PULSE_APPLICATION_OUTPUT` to a fresh directory outside the checkout. Historical APP/LIVE gate records retain their original scope. Neither it nor a Linux package verifies missing Intel/Apple hardware.

Linux is the primary validation platform. NVIDIA adapter tests do not establish hardware accuracy without an actual GPU comparison; DriverNotLoaded is not an accuracy pass. macOS, Windows, and physical device removal remain unverified where unavailable. The [historical fixture acceptance](native-fixture-acceptance.md) records the earlier deterministic interaction proof and does not establish live-reading accuracy.
