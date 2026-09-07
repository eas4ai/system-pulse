# Local AT-SPI cache signal framing patch

This directory vendors `accesskit_unix` 0.22.1 from the crates.io archive.
`UPSTREAM.json` records the archive hash, original files and AccessKit revision
`c88605b96d04431f9c3c792464a0f2f253480e94` (`platforms/unix`). The retained
MIT, Apache and Chromium license notices come from that same revision.

## Defect and correction

The released adapter passes cache structs directly to zbus `emit_signal`.
zbus interprets their outer structure as the argument list, so it emits
`(so)(so)(so)iiassusau` for AddAccessible and `so` for RemoveAccessible.
AT-SPI requires one structured argument: `((so)(so)(so)iiassusau)` and `(so)`.
The native Linux replay observed libatspi rejecting both malformed signals.

The private cache emitter now wraps its body in one tuple. A shared body helper
lets regression tests inspect the actual serialized D-Bus signature field and
round-trip the payload. Inspecting parsed signatures alone is insufficient:
zvariant normalizes argument sequences and structures to the same form.
Both tests fail with the original unwrapped body and pass with the correction.
The private generic bound changes from DynamicType to Type for tuple encoding;
both existing callers use statically typed AT-SPI payloads.

- Production change: `src/atspi/bus.rs`.
- Regression tests: `src/atspi/cache_signal_tests.rs`.
- Manifest: empty standalone workspace, root patch and workspace exclusion.
- All other upstream source remains unchanged.

```sh
cargo test --locked -p accesskit_unix --lib
```

The seven Unix adapter tests and nine common adapter tests pass on Linux.
Native replay must also pass before delivery; the wire defect alone does not
prove the cause of the earlier held-input acknowledgement timeout.

Protocol: [GNOME AT-SPI Cache interface](https://raw.githubusercontent.com/GNOME/at-spi2-core/main/xml/Cache.xml).
Remove this patch when the selected upstream release passes the wire regressions
and native replay. Keep the separate common-adapter expansion-state patch.
