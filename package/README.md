# System Pulse for Linux

A native desktop monitor with live CPU, memory, GPU, disk, network and process readings. Summary opens first, with fixed tabs for CPU, Memory, GPU, Disks, Network, Energy, Thermals, Processes and Settings.

## Run or install

Extract the archive and run `./system-pulse`, or install for your user:

```sh
python3 install.py
"$HOME/.local/bin/system-pulse"
```

Installation adds System Pulse to the desktop application menu. No root access is needed. The installer needs Python 3.11 or newer; the installed application does not need Python. To choose a different location, use `python3 install.py --prefix /absolute/path`. Repeating an unchanged installation is safe. The installer refuses to overwrite unrelated or modified files.

This package is built on Ubuntu 26.04 for x86-64 Linux with glibc. It uses the host's X11/Wayland session, libxcb, libxkbcommon-x11 and Vulkan driver. It is not a static binary. `build.json` records the actual build environment and linked libraries; `ldd ./system-pulse` checks runtime libraries on another host.

## Use the workspace

- Click a tab, use Left/Right/Home/End while a tab has focus, or cycle screens with Ctrl+Tab and Ctrl+Shift+Tab. Each screen scrolls as needed.
- Choose a named device above GPU, Disks or Network. Energy and Thermals select measured sensors. Long menus scroll and support Up/Down and Return.
- Open **Settings → Visible sensors** to show or hide readings by device. Unavailable sensors reappear when readings recover; failed, stale and warming-up states remain explicit.
- Search processes by name, PID or user and click headings to sort. Select a row for current details and confirmed End task or Force quit actions. Process arrows/Home/End move the selection; Left/Right scroll columns.
- **Settings** also provides themes, interface/numeric fonts, sampling intervals and named presets. Screen selection, device identities and preferences save automatically and restore on restart. Older docked configurations retain their preferences and open Summary.

Configuration lives in `$XDG_CONFIG_HOME/system-pulse`, or `~/.config/system-pulse`. `SYSTEM_PULSE_STATE_DIR=/another/directory ./system-pulse` runs with isolated state. Invalid saved input is retained until you explicitly accept recovered settings.

## Remove or update

```sh
python3 "$HOME/.local/lib/system-pulse/install.py" --uninstall
```

For a custom installation, include the same `--prefix`. Removal preserves configuration, unknown files and modified installed files; it reports any retained modified files. To update, remove the old installation, then install the new archive. Your saved workspace and presets remain available.

## Source and notices

`source.tar.gz` contains the committed workspace and its Cargo.lock. Extract it and run `cargo build --release --locked -p system-pulse` from its root; Cargo resolves the pinned external sources. The application uses GPL-3.0-or-later; see `COPYING`. `LICENSES.html` and `dependency-licenses.json` contain the dependency notices, and `notices/` contains font and collector source notices. Fonts and UI assets are embedded in the executable.

`build.json` identifies this build. Linux package verification and the separate platform/hardware acceptance records live in the source workspace's `docs/execution/`. A Linux package does not establish native Intel discrete GPU or macOS acceptance.
