# Workspace verification artifacts

These records support the [execution report](../../2026-09-04-workspace-visibility.md). They contain deterministic fixture data, not host telemetry. `manifest.json` records file hashes and sizes.

- `checks/`: final source `88343d5e`; six suites totaling 275 tests, formatting, Clippy, build, and diff checks. `results.json` contains exact commands and exit codes; `.log.gz` files retain their exact output.
- `native/focus/` and `native/mixed/`: final binary `162facf9…e67cf2`; strict settled two-axis reveal, deliberate scrolling, resize preservation, and mixed panel/row state across restart. JSON trees record actual native bounds and states.
- `native/disclosures/`: reviewed app `27e74915` with AT-SPI patch `277a6429`, binary `3e4dfdba…b486f`; all 15 controls exercised with Enter and Space, producing 30 expanded-state events. The later border correction does not change disclosure behavior.
- `native/persistence/`: app checkpoint `444b7de3`, binary and measured geometry in `result.json`; immediate resize/quit and byte-preserving invalid-layout recovery. The compressed invalid original is fixture JSON intentionally containing an incompatible multi-panel group. Gzip preserves its exact bytes and the raw command logs, including terminal blank lines.
- `native/compact/`: cycle and unit evidence from checkpoint/reviewed binaries. The full panel cycle used running binary `3f06b633a48402a1a6155623cae345ba613da68a69b1918129e0b984e695c59a`; reviewed unit/minimum-width screenshots used `3e4dfdbad4fabdfccdeac9f677931c6ad674adf361e815fd91f5c0415ebb486f`.
- Remaining native files show stable GPU identity, keyboard use after recovery, and table-to-workspace wheel routing. They supplement the result records.

## Reproduce native interactions

`native_driver.py` is the retained interactive test harness. It needs Linux, Xvfb, D-Bus, Vulkan software rendering, and Python bindings for AT-SPI, Xlib, and Pillow. Run with an absolute binary path and a new output directory:

```sh
rtk proxy xvfb-run -a -s '-screen 0 1440x1000x24 -nolisten tcp' \
  dbus-run-session -- env WAYLAND_DISPLAY= \
  VK_DRIVER_FILES=/usr/share/vulkan/icd.d/lvp_icd.json \
  /usr/bin/python3 native_driver.py /absolute/path/to/system-pulse /tmp/pulse-check
```

After the ready record, send one JSON command per line:

```json
{"op":"focus","name":"Collapse Settings","role":"button","settle":2}
{"op":"focus","name":"Collapse CPU","role":"button","settle":2}
{"op":"key","keys":["Return"],"settle":2}
{"op":"tree","file":"tree.json","summary":true}
{"op":"screenshot","file":"workspace.png"}
{"op":"quit"}
```

The driver records the running executable hash and keeps state in its output directory. Allow rendered frames between focus transitions; query actual bounds before pointer drags. Use the application README's scenario checklist for the full sequence. This driver is an interactive harness, not a single unattended acceptance command. A private desktop-portal child can retain the terminal after the app reports exit zero; interrupt that finished harness session to close its private bus. Linux results do not establish macOS or Windows acceptance.
