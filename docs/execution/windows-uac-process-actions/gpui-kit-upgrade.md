# GPUI Kit 0.6.1 upgrade

The initial upgrade evidence below is historical. The subsequent process-action
changes require [fresh preservation verification](process-actions-preservation.md),
whose native observations now pass on Linux, macOS and Windows.

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
tests passed.

Checks against committed source `36343dbe5ef2244465ca65e59c3b531d268fafd4`
also passed formatting, all 1,708 workspace tests, Clippy and 544 Python tests.
The retained [automated record](upgrade/automated.json) binds each command to
its exit status and log hash.

Linux full application acceptance passed: tabbed preservation with 1,087 tests
and native replay, ten input-focus tests, release packaging with 537 dependency
notices, packaged product replay, tray lifetime and installed launch. The
[package manifest](upgrade/linux-application-manifest.json) retains the source,
binary and artifact identities. Its referenced logs and artifacts remain in the
persistent local verification directory.

Native Mac workspace tests, Clippy and release build passed. All 36 retained
regression test names appear as passed in the Mac workspace log. Five dispatcher
tests and four application lifetime cases (success, error, unwind and background)
passed with missing-autorelease-pool diagnostics enabled. The first launcher
incorrectly applied those diagnostics to Cargo itself, and a subsequent lifetime
invocation passed an unsupported libtest argument to the custom harness. Both
failed launcher attempts are retained. Compiling separately and invoking the
test executables with their actual supported arguments passed without pool
diagnostics; no application code changed in response to these launcher errors.
See the [Mac build record](upgrade/macos-build.json).

The [native Mac preservation run](upgrade/macos-preservation/result.json) passed
against the retained pre-upgrade binary: monitor/sensor identity coverage,
independent volume capacities, settings, screen navigation, close-to-tray,
background collection/history, reopen and Quit. A separate normal launch with
diagnostics disabled verified visible Summary and Processes rows.

Windows passed 219 tests across 13 suites with none ignored, followed by its
native release build. The executable SHA-256 is
`10ba139f186f64ca275900efc8e49ae9c7a45c262cb48206415e1475b53f2994`.
The [runtime record](upgrade/windows-runtime/result.json) binds the exact binary
to the [build log](upgrade/windows-build.log). Runtime replay passed as an
unelevated user: all ten screens, process filtering and both PID sort directions,
live host readings, settings persistence, dashboard recreation from the tray and
clean Quit in diagnostic and normal launches. All eight screenshots were
inspected; the [visual review](upgrade/windows-runtime/visual-review.json) records
readable layouts, unavailable GPU/Thermals/Energy and the two correct tray commands.

The combined upgrade verifier passed locally after validating all retained
records. Cairn committed-tree evidence is recorded separately after this evidence
document is committed. These observations verify framework preservation; they
do not claim that the Windows UAC process backend has been implemented.

The graph verifier rejects an old kit, duplicate/mixed GPUI runtime, and missing
local patches. Its full mode additionally validates source-bound automated,
Linux package, Mac build/runtime and Windows build/runtime records; graph-only
success cannot produce WUAC-007 acceptance.

## Process-action accessibility follow-up

The subsequent Windows action harness found that Kit 0.6.1's disabled buttons
block activation and use disabled colors but leave their AccessKit node enabled.
The component Button now exposes `StatefulInteractiveElement` through its existing
stable root, matching its base Button. System Pulse uses the native node hook to
publish the disabled state of its two process-action buttons. This keeps the fix
within the action UI and preserves caller-provided accessibility behavior in
other controls. The application tests and all 17 component button tests pass on
Linux; fresh native and committed-source preservation evidence is still required
for this follow-up.
