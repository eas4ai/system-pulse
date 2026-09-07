# Bundled GPUI foundation

System Pulse uses this local `gpui-base` library for dock layout, scrolling, focus, accessibility and interaction behavior. It is part of the application dependency tree and is not published from this repository.

The source originated in [GPUI Component](https://github.com/longbridge/gpui-component). Local application fixes include dock preservation and exact transition completion. Its Apache-2.0 license is retained in [LICENSE-APACHE](LICENSE-APACHE).

From the System Pulse repository root, run `cargo test --locked -p gpui-base` to verify this library. `cargo test --locked --workspace` includes it in the application workspace checks.
