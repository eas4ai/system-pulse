# gpui_macos provenance

Source: <https://github.com/zed-industries/zed/tree/f66ed399cdde86092af8af3dc7b418abf45f37f8/crates/gpui_macos>.
The package is copied from the application's already locked Zed commit
`f66ed399cdde86092af8af3dc7b418abf45f37f8`. Its original package-local
`LICENSE-APACHE` is unchanged. `UPSTREAM.json` records the original 16 file
sizes/hashes and all 39 inherited dependency declarations before normalization.

The only production Rust change is the per-invocation autorelease pool in
`src/dispatcher.rs`. Its unit-test module covers native destruction, retained
objects, owned results, pending polls, cancellation, and actual native queues.
All other original Rust files are unchanged.

The local Cargo manifest expands inherited edition, publication, lint, and
dependency metadata. Former upstream workspace path dependencies use the exact
existing `https://github.com/zed-industries/zed` git SourceId, without a `rev`
query. Cargo.lock retains their selected commit and versions. Inherited default
features, explicit features, package aliases and target conditions are preserved.
The original package features and dev-dependencies are preserved as well.

The root patches only gpui_macos and excludes this package from workspace
membership. Making it a member would resolve its unrelated benchmark feature and
add criterion's dependency graph. The System Pulse macOS dispatcher integration
test instead compiles this exact private dispatcher source, using already locked
native dependencies. A separate application lifetime test constructs the actual
linked gpui_platform application and exercises its background executor, so source
inclusion is not the only production-wiring evidence. Tests add no product API.

Run formatting from the root with:

```sh
cargo fmt --manifest-path vendor/gpui_macos/Cargo.toml -- --check
```

Native verification commands and ownership evidence are recorded in
`docs/execution/intel-and-apple-gpus/apple-pool-correction.md`. Linux formatting or
compilation does not establish macOS lifetime behavior. The full application
lifecycle finding remains open until the separately required native replay.
