# System Pulse CI binary

This archive contains a native release executable, dependency notices, build
metadata and the matching source. `build.json` identifies its operating system,
CPU architecture, source commit, compiler and linked runtime libraries.

## Run

- **Linux x86_64:** extract the `.tar.gz` and run `./system-pulse` from a graphical
  X11 or Wayland session. The build uses Ubuntu 24.04 and glibc, with host Vulkan,
  XCB and xkbcommon libraries. `ldd ./system-pulse` reports missing runtime libraries.
  To install for your user, run `python3 install.py`; Python 3.11 or newer is needed
  only by the installer. Its default prefix is `~/.local`.
- **macOS arm64:** extract the `.tar.gz` and run `./system-pulse` on Apple Silicon.
  This is an unsigned executable built on macOS 15, without a notarized `.app`
  installer. The archive does not support Intel Macs.
- **Windows x86_64:** extract the `.zip` and run `system-pulse.exe`. Keep the
  extracted directory intact. The build uses the Microsoft C++ runtime;
  `build.json` lists the imported DLLs. The executable is unsigned.

Closing the dashboard retains the CPU tray icon. Activate the icon to reopen
the dashboard, or use its **Quit** menu item to exit. The ten tabs include
Summary, CPU, Memory, GPU, Disks, Network, Energy, Thermals, Processes and Settings.
Use Settings for theme, fonts, sampling interval and presets; choices save
automatically. `SYSTEM_PULSE_STATE_DIR` selects an isolated state directory.

CPU, memory, disk, network and process support depends on the host. Missing
sensors remain explicit. Intel Windows GPU readings and Windows process thread
counts are not implemented. CI compilation
does not establish hardware sensor accuracy; native observations are retained
under `docs/execution/` in the included source.

On Windows, **End task** requests graceful closure; an application can ask to save
work or refuse. Windowless targets report graceful close unavailable. **Force
quit** is separately confirmed and warns about unsaved work. An action first
uses your current permissions; after identity and safety checks pass, an action
that needs more permissions can request one elevated helper through Windows UAC.
The helper uses this same extracted executable, including
when its directory contains spaces or non-ASCII characters. Normal dashboard
launch stays at the caller's privilege level. The executable is unsigned, so do
not expect a verified publisher in the UAC dialog. Enter any administrator
credentials only into Windows. Cancellation starts no helper action; an unknown
or pending outcome asks you to check the process list before trying again.

## Source and notices

`source.tar.gz` contains the committed application workspace, native patches,
build scripts and Cargo.lock. Extract it and run
`cargo build --release --locked -p system-pulse` with the platform's native build
prerequisites. Cargo downloads the pinned external dependency sources.
`SOURCE.txt` and `build.json` identify the exact revision.

System Pulse is GPL-3.0-or-later; see `COPYING`. `LICENSES.html` and
`dependency-licenses.json` include the resolved dependency licenses, including
local patched crates. `notices/` contains additional font and native-source
notices. Fonts and UI assets are embedded in the executable.

`package-files.json` records file checksums. The outer archive's SHA-256 is in
the accompanying `SHA256SUMS`. GitHub Actions artifacts expire; these CI archives
are build outputs, not a published or signed release.
