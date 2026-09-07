# System Pulse for Linux

A native desktop monitor with live CPU, memory, GPU, disk, network and process readings. The first workspace keeps CPU, memory, the first discovered GPU and processes in separate dock panels.

## Run or install

Extract the archive and run `./system-pulse`, or install for your user:

```sh
python3 install.py
"$HOME/.local/bin/system-pulse"
```

Installation adds System Pulse to the desktop application menu. No root access is needed. The installer needs Python 3.11 or newer; the installed application does not need Python. To choose a different location, use `python3 install.py --prefix /absolute/path`. Repeating an unchanged installation is safe. The installer refuses to overwrite unrelated or modified files.

This package is built on Ubuntu 26.04 for x86-64 Linux with glibc. It uses the host's X11/Wayland session, libxcb, libxkbcommon-x11 and Vulkan driver. It is not a static binary. `build.json` records the actual build environment and linked libraries; `ldd ./system-pulse` checks runtime libraries on another host.

## Use the workspace

- Drag a panel title to split or move it. Use its arrow to collapse it or × to hide it. Monitor buttons across the top show hidden hardware; that strip scrolls when the host has many devices.
- Right-click a sensor, or open its ⋯ menu, to change its compatible meter, visibility or order. CPU core tiles retain the same controls. Missing and stale readings remain explicit.
- Search processes by name, PID or user. Click a column heading to sort. Select a row, then use End task or Force quit; confirmation identifies the process. End task requests graceful termination. Force quit stops it immediately. Failures appear in the panel.
- Open **Settings & presets** for themes, interface/numeric fonts, sampling intervals and named presets. Settings scroll independently of the workspace. Save current creates a named preset; Use recalls one. Rename, overwrite and delete ask for confirmation where appropriate. Default, Minimal, GPU Focus and Developer are protected templates. The top Save preset/Recall preset buttons retain the separate legacy quick slot.
- Layout and settings save automatically. **Save** writes immediately. Alt+PageUp/PageDown scrolls the workspace; Alt+Left/Right scrolls it horizontally. Tab moves between controls. Process arrows and Home/End move the selection.

Configuration lives in `$XDG_CONFIG_HOME/system-pulse`, or `~/.config/system-pulse`. `SYSTEM_PULSE_STATE_DIR=/another/directory ./system-pulse` runs with isolated state. Invalid saved input is retained until you explicitly accept a recovered layout.

## Remove or update

```sh
python3 "$HOME/.local/lib/system-pulse/install.py" --uninstall
```

For a custom installation, include the same `--prefix`. Removal preserves configuration, unknown files and modified installed files; it reports any retained modified files. To update, remove the old installation, then install the new archive. Your saved workspace and presets remain available.

## Source and notices

`source.tar.gz` contains the committed workspace and its Cargo.lock. Extract it and run `cargo build --release --locked -p system-pulse` from its root; Cargo resolves the pinned external sources. The application uses GPL-3.0-or-later; see `COPYING`. `LICENSES.html` and `dependency-licenses.json` contain the dependency notices, and `notices/` contains font and collector source notices. Fonts and UI assets are embedded in the executable.

`build.json` identifies this build. Linux package verification and the separate platform/hardware acceptance records live in the source workspace's `docs/execution/`. A Linux package does not establish native Intel discrete GPU or macOS acceptance.
