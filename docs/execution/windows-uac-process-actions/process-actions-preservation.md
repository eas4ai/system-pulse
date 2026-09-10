# Process-action preservation verification

Status: incomplete. The current Mac desktop is locked, so WUAC-007 cannot pass
against the process-action implementation yet. Real Windows UAC verification and
the final commitment review also remain pending.

These observations use committed source
`3e6923e3976398458af61588cb73c1a94d08ea59`, which includes implementation
`47617b85e9f0b86ad0440f60dead49ad4cd561f8`. The initial GPUI upgrade's accepted
records remain under `upgrade/`; this follow-up does not replace their history.

## Passing observations

- [Automated checks](process-actions-preservation/automated.json): formatting,
  1,714 Rust workspace tests, workspace Clippy without warning promotion, and
  553 Python tests.
- [Linux application acceptance](process-actions-preservation/linux-application-manifest.json):
  native tabbed preservation and process controls, ten keyboard input tests,
  release packaging, packaged application replay, tray behavior and installed
  launch. The package validator passed. Summary and Processes screenshots were
  inspected.
- [Mac build checks](process-actions-preservation/macos-build.json): 1,674 workspace
  tests, Clippy, release build, five dispatcher tests and four application lifetime
  cases. The native lifetime tests passed with missing-pool diagnostics enabled
  only in their child environments.
- [Windows build](process-actions-preservation/windows-build.log): 230 native tests
  and release build; the embedded manifest retains `asInvoker` and
  `uiAccess=false`.
- [Windows runtime](process-actions-preservation/windows-runtime/result.json): all
  ten screens, live readings, process filtering and sorting, saved settings,
  dashboard recreation from the tray and normal Quit. All eight screenshots were
  [reviewed](process-actions-preservation/windows-runtime/visual-review.json), and
  artifact, reading, interaction, source and binary checks passed.
- [Windows ZIP](process-actions-preservation/windows-package.json): built on the
  native host from a clean Git tree transferred in a verified bundle. Archive
  inventory, source blobs, executable identity and license notices passed the
  existing package validator. The executable matches the native build hash.
- [Packaged Windows actions](process-actions-preservation/windows-ordinary-actions/result.json):
  all seven ordinary cases passed from the extracted ZIP under a path containing
  spaces and non-ASCII text. They cover confirmation cancellation, cooperative and
  refusing GUI closure, unavailable windowless closure, Force quit, an exited
  selection and responsiveness during delayed closure. Independent and collected
  creation identities match. The dashboard stayed unelevated, the unrelated
  control was unaffected, malformed/unelevated helper entries were refused, and
  all owned processes were cleaned up. The complete package/action validator
  passed. Force/graceful confirmation, unavailable closure and delayed-result
  screenshots were inspected. These observations do not establish UAC consent.

## Failed attempts retained

The first Linux native replay passed, but a concurrent Cargo invocation replaced
the shared debug executable before the final hash comparison. The aggregate
correctly failed. A fresh complete acceptance run with no competing Linux build
passed. The original receipt remains at
`/home/shawn/.cache/system-pulse-windows-actions/linux-acceptance-3e6923e3/`.

The first Mac lifetime launcher applied missing-pool instrumentation to Python as
well as its native children and produced pool diagnostics. The direct child-only
run passed without those diagnostics. Both attempts remain in
`/home/shawn/.cache/system-pulse-windows-actions/macos-native-3e6923e3/`.

The first Windows runtime run could not find one visible tray icon after closing
the dashboard. Inspection found no leftover application icons, and a controlled
live observation found the expected single icon. A fresh run of the unchanged
harness and executable passed every check. The failed run remains at
`/home/shawn/.cache/system-pulse-test-tmp/system-pulse-native-windows-7lv9qkkt/`.
This establishes a passing repeat observation; it does not establish the cause
of the first tray-discovery failure.

## Current blocker

The [Mac desktop attempt](process-actions-preservation/macos-preservation/result.json)
failed because the session at `10.66.231.181` is locked. Its owned application was
cleaned up and confirmed exited. Unlock that session before collecting a fresh
preservation run. Do not substitute the initial upgrade's older runtime evidence
for this source revision.
