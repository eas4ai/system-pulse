# Tabbed screens execution record

Status: delivered on Linux. Implementation, native replay, package verification and local executable installation passed. Package revision `eead635a17500fa91d8466d8fee97c6f9a3c55ee` was pushed to application main; the final documentation receipt is tracked separately in the external delivery record.

The 2026-09-07 developer request replaces the visible dock canvas with screens guided by the eight TMOG reference images. The [design](../superpowers/specs/2026-09-07-tabbed-screens-design.md), [plan](../superpowers/plans/2026-09-07-tabbed-screens.md), [current specification](../feature-spec-dockable-system-monitor.md) and [user guide](../user-guide.md) describe the contract.

Implementation started from `a9f77ad55f13ae1d4ed71a540a1d0a167a0da1d4`. The complete application change is `4ad09f95`; final acceptance uses `33e81ad760a5338ac21446fea2d7b9f70ee6164e`. The later harness corrections do not change the 562 tracked runtime inputs. Evidence is retained outside the checkout at `/home/shawn/workspace2/task-manager-artifacts/tabbed-ui-20260907/`.

## Result

Ten fixed native tabs present live measurements, timestamped charts and segmented meters. Device identity persists across discovery order changes and restart. Processes retain search, sort, identity-safe task actions and selected-process details. Settings expose sensor visibility, appearance, sampling and presets. Invalid input remains untouched until explicit recovery. Legacy dock metadata remains compatible; historical no-tabs cases do not validate the current root.

Independent specification, chart and UI quality reviews approved the implementation after corrections for clipped menus, small chart labels, unavailable memory/thermal readings and focus after restoration. A separate acceptance review closed screenshot-failure cleanup and duplicate GPU label handling. Visual review covered all ten screens, dark/light appearance and 1280×880/960×640 layouts against the supplied references.

## Verification

- `cargo test --locked --workspace`: 1,507 passed, zero failed or ignored (`workspace-tests.log`).
- Final automated gate: 992 tests, formatting, Clippy, build and independent live source comparisons passed (`acceptance-r3/preservation/manifest.json`).
- Final debug native replay: all six required product flows and all 149 discovered GPU/volume/interface selections passed, including minimum size, process actions, presets, restart, missing-device state and corrupt-input recovery.
- Packaged release native replay and isolated install/repeat-install/restart/uninstall passed (`acceptance-r3-continuation/application-manifest.json`). Installation and removal preserved configuration and unowned files.
- The release binary SHA-256 is `6830b48f41193de79fe0ecd9a9f9bdb1228049793dc96973edd5a430c85c4a25`. These exact bytes were atomically installed at `/home/shawn/.cargo/bin/system-pulse`, with the prior executable backed up. The running user application and its configuration were left untouched.

The final gate initially stopped before packaging because cargo-about was outside PATH. `continue-package.py` verifies the unchanged source, retained passing logs and artifact hashes, then executes the existing package/product/installed gate statements with the installed cargo-about 0.9.2 path. The original failed manifest remains intact; the continuation records the completed steps explicitly. Earlier failed development runs are retained separately and are not counted as passes.

The final metadata-only package refresh includes this record and the Michroma font inventory hashes. Its executable matches the verified release byte-for-byte, and the refreshed archive passed installed smoke again. The final archive, installed smoke and publication hashes are recorded in `final-package.json` and `delivery.json` under the evidence directory.

## Limits

This is Linux verification. Intel/Apple hardware validation and native Mac GUI review remain separate and unverified for this redesign. GitHub Actions and automatic security fixes remain disabled. No unmeasured energy total, process energy score or thermal health state is fabricated to resemble a reference image.
