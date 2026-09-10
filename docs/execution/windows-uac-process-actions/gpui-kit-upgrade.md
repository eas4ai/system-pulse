# GPUI Kit 0.6.1 upgrade

The developer requested the latest stable GPUI Kit on 2026-09-10. crates.io
reported 0.6.1, not yanked. The upstream source revision recorded in the published
package is `36b51819deb52c947a79f8de29e0e9175eda7464`.

## Source reconciliation

The comparison used published 0.6.0 and 0.6.1 archives, each verified against its
crates.io SHA-256 before extraction. Application-specific code was merged with
the upstream delta, not overwritten with a new checkout.

| Package | 0.6.1 archive SHA-256 |
| --- | --- |
| gpui-kit | a74f10f4499d99378c73c0251541a5d92bde45cb83dd658f0618fb32769d5898 |
| gpui-base | 9d45dcaaeac889bf1e7757db1beb26c9043c8ea3156651facc11c6be56bb6722 |
| gpui-component | 52b7ab4921dc9d2624648fb40580067bfe0f47dd14f5f8f6e070d40c6d4246d4 |

The facade, base, component, macros and assets resolve to 0.6.1. The existing
compatible GPUI Pre 0.3.2 family is retained, including the macOS native patch.
AccessKit and sysinfo local patches are unchanged. The required Tree-sitter
dependency moves from 0.26.8 to 0.26.13; upstream no longer requires syntect,
removing it and its unused transitive dependencies from the lockfile.

Retained library differences cover Separate dock policy, absolute and collapsed
extents, hidden-panel drag handling, exact motion completion, owned test fixtures,
and local focus/accessibility behavior. All 36 additional library regression
test names remain present; see [inventory](retained-library-tests.json). This
inventory is a preservation aid, not a substitute for executing the tests.

Manifest conflicts preserve `publish = false`, the local workspace layout and
the omitted upstream benchmark. The rich-text fixture conflict retains the
existing local fixture rather than depending on upstream examples. Base keeps
its application-specific README; upstream component README packaging metadata
is not imported into the application documentation.

Two new upstream icon tests initially failed compilation because they referenced
the original monorepo's assets directory. They now use the existing build-script
icon-directory metadata from `gpui-kit-assets`; their assertions are unchanged.

The existing non-finite dock geometry regression then exposed an endless frame
loop introduced by upstream's new deferred resize notification. Non-finite
container extents are now rejected before updating the resizable state or
queuing a settling frame. The original test passes unchanged, as do the upstream
mixed-sizing/caller-owned-state tests. Valid geometry still schedules the new
settling frame.

The native acceptance command also contained a split `-D`, `warnings` argument
pair missed by the earlier literal-string search. It is removed in accordance
with the developer's standing instruction; warnings remain visible.

## Verification state

Editing checks passed: 1,708 Rust workspace tests, no ignored tests; workspace
formatting; resolved-graph verification. The first workspace attempt was stopped
after isolating the non-finite geometry loop; it is not counted as a pass.
Full workspace Clippy also passed without warning promotion, and all 544 Python
tests passed. Committed-source native/package evidence remains pending.

The graph verifier rejects an old kit, duplicate/mixed GPUI runtime, and missing
local patches. Its full mode additionally validates source-bound automated,
Linux package, Mac build/runtime and Windows build/runtime records; graph-only
success cannot produce WUAC-007 acceptance.
