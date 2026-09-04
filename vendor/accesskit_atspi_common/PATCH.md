# Local AT-SPI expansion state patch

This directory vendors `accesskit_atspi_common` 0.18.1. System Pulse's
disclosure buttons supply AccessKit's optional `expanded` property, but this
release omits the corresponding AT-SPI states. The local patch maps a present
property to `Expandable` and a true value to `Expanded`. The adapter's existing
state comparison then emits the corresponding `StateChanged` events.

## Provenance

- Package: [accesskit_atspi_common 0.18.1](https://crates.io/crates/accesskit_atspi_common/0.18.1).
- Registry archive SHA-256:
  `1e8c61bee90b42a772d39d06a740207dc71a4e780004ace1db8d99fb1baaa954`.
- Upstream commit: `f40dfc01a0c0e76de535969f82fb35e19513737d`.
- Upstream directory: `platforms/atspi-common`.
- The 13 original Rust files, normalized registry `Cargo.toml`, and `README.md`
  were copied from the registry package and verified against the cached archive.
  The package version and all dependency requirements remain unchanged.
- Registry metadata, its nested lockfile, and the original manifest with
  upstream workspace inheritance are omitted.

The license files were omitted from the registry package. These exact upstream
files were retrieved at the recorded commit, preserving the notices referenced
by the source headers:

| File | Upstream source | SHA-256 |
| --- | --- | --- |
| `LICENSE-MIT` | [MIT license](https://raw.githubusercontent.com/AccessKit/accesskit/f40dfc01a0c0e76de535969f82fb35e19513737d/LICENSE-MIT) | `23f18e03dc49df91622fe2a76176497404e46ced8a715d9d2b67a7446571cca3` |
| `LICENSE-APACHE` | [Apache license](https://raw.githubusercontent.com/AccessKit/accesskit/f40dfc01a0c0e76de535969f82fb35e19513737d/LICENSE-APACHE) | `62c7a1e35f56406896d7aa7ca52d0cc0d272ac022b5d2796e7d6905db8a3636a` |
| `LICENSE.chromium` | [Chromium license](https://raw.githubusercontent.com/AccessKit/accesskit/f40dfc01a0c0e76de535969f82fb35e19513737d/LICENSE.chromium) | `845022e0c1db1abb41a6ba4cd3c4b674ec290f3359d9d3c78ae558d4c0ed9308` |

## Local changes

- `src/node.rs`: expansion state mapping and registration of the regression
  test module. Other upstream source files are unchanged.
- `src/expansion_tests.rs`: real adapter tests for absent, collapsed, and
  expanded state; state transitions; and repeated updates without duplicate
  expansion notifications.
- Root `Cargo.toml`: crates.io path patch and explicit workspace exclusion.
- Root `Cargo.lock`: registry source and checksum removed for this local package.

Run the tests from the repository root so Cargo uses the existing workspace
lockfile and dependency versions:

```sh
cargo test --locked -p accesskit_atspi_common --lib
cargo test --locked -p system-pulse --lib
cargo build --locked -p system-pulse
```

The adapter tests exercise state queries and callbacks. Native D-Bus delivery
must also be checked with the running Linux application. Remove this patch
when the pinned dependency is updated to a release that passes these regression
cases, then repeat the native check.
