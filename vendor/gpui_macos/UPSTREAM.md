# GPUI Pre macOS provenance

This directory patches the released `gpui-pre-macos` 0.3.2 package used by
GPUI Kit 0.6.0. The published package records Zed source revision
`801c087af22dd189dc1aa49e2f370b4f04190b19`. Its normalized registry manifest
pins the matching GPUI Pre 0.3.2 packages. Root Cargo patches the crates.io
package name `gpui-pre-macos`; the library name remains `gpui_macos`.

Registry archive SHA-256:
`66a1e7a41b11c83b121b7bf729537c5b46dad91ef0cf221851cfb287cbe0fe33`.
`UPSTREAM.json` records the original source and manifest hashes. The Apache
license is retained unchanged. An empty `[workspace]` table keeps standalone
formatting commands independent of the enclosing application's workspace.

The only production source change is the per-invocation autorelease pool in
`src/dispatcher.rs`. The released upstream dispatcher is byte-identical to
the previously patched dispatcher before that correction, so the reviewed
pool boundary and `dispatcher_lifetime_tests.rs` are retained verbatim.
All other upstream source is copied from the 0.3.2 package.

The private-source integration test covers destruction, retained objects,
owned results, pending polls, cancellation and actual native dispatch queues.
The separate `macos_application_lifetime` executable constructs the linked
platform application and checks its real background executor. The application
also retains its construction/teardown autorelease pool in `src/application.rs`.

Run formatting from the repository root:

```sh
cargo fmt --manifest-path vendor/gpui_macos/Cargo.toml -- --check
```

On macOS, run `cargo test --locked -p system-pulse --test macos_dispatcher_lifetime`
and the application lifetime cases documented in the migration evidence.
Linux compilation does not establish macOS behavior. Earlier lifetime evidence
is recorded in `docs/execution/intel-and-apple-gpus/apple-pool-correction.md`
against its original dependency graph.
