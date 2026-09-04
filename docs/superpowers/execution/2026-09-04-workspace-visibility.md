# Workspace Implementation Evidence

Status: Native fixture proof complete and verified on Linux, 2026-09-04. The user authorized execution with subagents. This completes the [workspace plan](../plans/2026-09-04-workspace-visibility.md), not the full system-monitor product.

## Source and scope

- Source repository: `eas4ai/gpui-component`, baseline `ba3433f0740ee5ba2b1db459af49229caf0c1bcc`.
- Branch: `feat/system-pulse-workspace`.
- Worktree: `/home/shawn/workspace2/task-manager-worktrees/workspace-visibility`.
- Verified source commit: `88343d5ed3be72865e52fc3d51a860649d8def83`; subsequent documentation commits do not change the binary.
- Final running binary SHA-256: `162facf9d5402761aa0ca3e39ee2c834903d0eee1008d9b024cd43cf90e67cf2`.
- App: `examples/system_pulse`; pure model: `examples/system_pulse/model`. Existing `examples/system_monitor` is unchanged.

The app uses eight separate fixture panels, one one-second sample loop, bounded histories, and simulated current/stale/unavailable readings. It proves scrolling, split movement, independent collapse, and recoverable presentation state. Live OS collectors, process control, metric accuracy, complete presets, production styling, and performance targets remain outside this slice. macOS and Windows native acceptance was not run.

Run from the framework worktree:

```sh
rtk cargo run -p system-pulse
```

## Completed work

- [x] Prepare isolated worktree and verify baseline.
- [x] Implement and independently review separate-panel docking.
- [x] Implement and independently review presentation state.
- [x] Implement and independently review collapse geometry.
- [x] Implement and independently review the native fixture app and AT-SPI correction.
- [x] Run integrated checks, native acceptance, final source review, and production self-audit.

The existing design-repository `AGENTS.md` was preserved. Reference projects and original brainstorming inputs were not modified.

## Automated verification

The root agent ran every command below on the final source commit. All exited zero. [Full command results](artifacts/2026-09-04/checks/results.json) and unfiltered logs are retained.

| Command | Result |
| --- | --- |
| `cargo test --locked -p gpui-base --lib dock::` | 205 passed |
| `cargo test --locked -p gpui-base --lib resizable::` | 13 passed |
| `cargo test --locked -p gpui-component --lib dock::` | 19 passed |
| `cargo test --locked -p system-pulse-model` | 15 passed |
| `cargo test --locked -p system-pulse --lib` | 21 passed |
| `cargo test --locked -p accesskit_atspi_common --lib` | 2 passed |

Total: **275 tests passed**. Package formatting, combined strict Clippy (`--all-targets --no-deps -- -D warnings`), locked native build, and `git diff --check` also passed. These are the affected-package checks, not a claim that every test in the upstream repository was run.

## Native acceptance

Linux checks used real GPUI windows in isolated Xvfb/D-Bus sessions, XTEST pointer/keyboard events, AT-SPI inspection, and llvmpipe Vulkan. Window sizes included 960×640 and 1440×1000. Accessibility activation used a private bus launcher and an in-memory settings backend; desktop preferences were not changed. Every tested app closed gracefully with exit code zero.

| Contract | Observed result |
| --- | --- |
| WV-01, WV-03 | Right/bottom edge moves and divider resizing worked. Center/header merge attempts preserved source position and identity. Hide/re-enable left eight unique singleton regions. No UI tab groups appeared. |
| WV-02, WV-04 | Wheel, scrollbars, and Alt navigation reached both overflow axes. The process table reached row 499; Tab exited it; wheel at its boundary reached the ancestor. Shrink/grow preserved native panel order, disclosure states, and the complete saved state. |
| WV-05–WV-08 | Initial panels/rows expanded. CPU row collapse survived its panel cycle and meter change/hide/show. A resized CPU restored 1328×280 after a 36-pixel collapse beside an expanded neighbor. A compact panel remained readable at exactly 320 pixels wide. |
| WV-06, WV-07, WV-09 | Thirteen screenshots covered a complete twelve-tick collapsed fixture cycle with current, unavailable, and stale summaries. Compact unavailable rows retained their unit. State/history tests verified bounded, uninterrupted sampling and gaps while bodies were hidden. |
| WV-10 | All 15 disclosure controls responded to Enter and Space and exposed Expandable/Expanded correctly; 30 native expanded-state events were recorded. Controls did not start drags. GPUI tests verified descendant-focus recovery; native checks verified focus after explicit invalid-state recovery. |
| WV-04, WV-10 | Settled repeated focus revealed the full border on both axes. A focused CPU control stayed at `[1112,-422,26,28]` across a fixture tick after deliberate scrolling; revisiting focus revealed it at `[926,178,26,28]` inside the minimum window. |
| WV-11 | Immediate divider resize/quit without Save restored height 332; collapse/expand returned 36/332. Preset recall and discovery reversal/disconnect/reconnect retained GPU identities. A final restart preserved collapsed GPU A, expanded GPU B/CPU, compact CPU overall row, split order, and CPU's 320×280 geometry. |
| WV-12 | Invalid 9,647-byte input stayed byte-for-byte unchanged after collapse, Save, and preset recall. Explicit acceptance archived those exact bytes before saving eight valid regions. A separate replay confirmed keyboard scrolling and Tab remained usable after recovery. |

Selected machine-readable records, trees, screenshots, and the native driver are in the [artifact bundle](artifacts/2026-09-04/README.md). Screenshots supplement interaction assertions; they are not the sole proof.

## Review findings resolved

Independent spec and quality reviews passed for every component, followed by an integrated source review. The final focus delta received separate spec and quality reviews; neither had remaining findings. A final scope audit prompted explicit shrink/grow and mixed-state restart replays, which passed.

- Prerequisites: `385bc286` removed a stray `centred` token blocking baseline compilation; 197 baseline dock tests then passed. `d16ff11a` simplified an equivalent calendar boolean expression; eight calendar tests passed before and after.
- Dock policy: `3eac4c5d`, `cfe12c90`, `ed45f48c`, `43813bb4`, `3e1075e3` implement separate regions, checked mutations, finite-size validation, and stale-preview cleanup. Default Tabbed compatibility remains intact.
- Model: `700b747f`, `7489aecb`, `afa1cfa3` add stable presentation/history state and order-exhaustion compaction. The 16,384 dimension bound was in the approved plan.
- Geometry: `a352bb16`, `b4de4d18` fix opt-in hidden-slot allocation, fixed-header redistribution, preferred-size growth, and cancellation when the active resize source disappears.
- App: `444b7de3`, `27e74915`, `88343d5e` implement the fixture, quit/recovery behavior, retained units, focus recovery, and inclusion of existing one-pixel borders in reveal measurements.
- Accessibility: `277a6429` vendors a narrowly patched `accesskit_atspi_common` 0.18.1 with upstream provenance and licenses. Two adapter regressions and native disclosure signals verify the correction; dependency versions did not change.

Test-process note: the model's three initial suites failed together against missing exports; they were not three separate red runs. Later review regressions had individual failing/passing checks. An apparent large focus displacement from a fast mixed driver sequence was not reproduced with settled native events. Two artificial focus requests without an intervening rendered frame are coalesced by GPUI; that diagnostic is not counted as acceptance. The confirmed one-pixel clipping defect received a strict repeated regression and native replay.

## Delivery audit

The production self-audit covered scope, compatibility, ownership, input validation, bounded storage/history, save ordering, recovery, dependency provenance, focused regression tests, documentation, and honest platform limits. No known required fixes remain for this fixture scope. The implementation branch and worktree are preserved for use and review; integration into another branch is separate.
