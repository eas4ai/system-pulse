# Local AT-SPI expansion state patch

This directory vendors `accesskit_atspi_common` 0.19.1 for GPUI Kit 0.6.0.
System Pulse's disclosure buttons supply AccessKit's optional `expanded`
property, but this adapter release omits the corresponding AT-SPI states.
The patch maps a present property to `Expandable` and a true value to
`Expanded`. Existing state comparison emits the corresponding change events.

## Provenance

- Package: [accesskit_atspi_common 0.19.1](https://crates.io/crates/accesskit_atspi_common/0.19.1).
- Registry archive SHA-256: `023da0e5097f46df7092d5280b02efb9bbf8d93298daeced42652463e357d636`.
- Upstream revision: `c88605b96d04431f9c3c792464a0f2f253480e94`, directory `platforms/atspi-common`.
- `UPSTREAM.json` records original source and normalized manifest hashes.
- License notices fetched at that revision match the previously retained
  `LICENSE-MIT`, `LICENSE-APACHE`, and `LICENSE.chromium` files byte for byte.

## Local changes

- `src/node.rs`: expansion state mapping and registration of the regression module.
- `src/expansion_tests.rs`: unchanged real-adapter regression cases for absent,
  collapsed and expanded state, transitions and duplicate-event suppression.
- Root `Cargo.toml`: crates.io path patch and explicit workspace exclusion.
- Local manifest: an empty `[workspace]` table supports standalone formatting.

The unchanged regression tests fail against the unpatched 0.19.1 adapter and
pass after the mapping is applied. All nine adapter unit tests pass on Linux.

```sh
cargo test --locked -p accesskit_atspi_common --lib
```

Native D-Bus delivery must also be checked with the running application.
Remove the patch only when the selected upstream adapter passes both the
regression cases and native check.
