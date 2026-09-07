# Tabbed screens execution record

Status: implementation and native acceptance in progress. This record does not claim delivery or a passing final gate.

The 2026-09-07 developer request replaces the visible dock canvas with screens guided by the eight TMOG reference images. The [design](../superpowers/specs/2026-09-07-tabbed-screens-design.md), [plan](../superpowers/plans/2026-09-07-tabbed-screens.md), [current specification](../feature-spec-dockable-system-monitor.md) and [user guide](../user-guide.md) describe the resulting contract.

Development uses `design/tabbed-ui` from application main `a9f77ad55f13ae1d4ed71a540a1d0a167a0da1d4`. Evidence is outside the checkout at `/home/shawn/workspace2/task-manager-artifacts/tabbed-ui-20260907/`.

Implemented: ten fixed native tabs, device identity persistence, timestamped charts and segmented meters, reference-derived layouts, process details and sensor visibility. Existing sampling, identity-safe process operations, configuration ordering, preset imports and malformed-input guards remain in use. Dock metadata and compatibility tests remain; old no-tabs native cases do not validate the new root.

Observed development checks include chart/model/navigation/populated-screen tests, all application library tests, Clippy and several native previews. Previews caught and drove fixes for duplicate Energy accessibility IDs, ambiguous GPU labels, clipped device menus, small chart labels and unavailable thermal selections. Development previews and failed replays are retained; they do not replace the final source-bound acceptance evidence.

The final source, native/product/package results, screenshot review, installation and integration records will be added after those checks complete. Intel/Apple hardware validation and native Mac GUI review remain outside this Linux redesign proof. GitHub automation remains disabled.
