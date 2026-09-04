# Separate Dock Panels Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an application enforce separate split regions, with no panel merging and no source loss after rejected operations.

**Architecture:** Add an opt-in `PanelPolicy::Separate` to `DockArea`; existing consumers retain `PanelPolicy::Tabbed`. Validate persisted structure before loading, preflight moves on a candidate tree before touching either live region, and register new panels directly into singleton split leaves. Propagate merge permission into base drop handling and the standard UI renderer, while retaining edge dragging and framework geometry.

**Tech Stack:** Rust 2024, `gpui-base`, `gpui-component`, existing GPUI test fixtures, `anyhow`, existing dock state serialization.

---

## Execution boundary and requirements

This is a plan, not an implementation. Execute it in the authorized `eas4ai/gpui-component` worktree based on `ba3433f0740ee5ba2b1db459af49229caf0c1bcc`, after the overview's checkout prerequisites. All command paths below are relative to that repository root. They are not commands for the current documentation workspace. Keep exactly one execution task in progress; finish its code and verification before marking it complete.

This plan covers the framework portions of WV-01, WV-03, and WV-12 in [the approved spec](../specs/2026-09-04-workspace-visibility-design.md). Plan 03 owns collapse/overflow geometry and Plan 04 owns application controls, stable identities, raw-invalid-input retention, error presentation, and autosave recovery. This plan never rewrites a rejected saved layout, silently converts tabs into splits, or adds a second layout implementation.

A singleton internal `Tabs` node is the existing framework's panel leaf; it does not represent user-facing tabs. The invariant is at most one panel per group, no tiles, and no merge target accepted under `Separate`. Empty framework containers are allowed where the existing normalizer retains an empty root.

## Public integration contract

- `PanelPolicy::{Tabbed, Separate}` is exported from `gpui_base::dock` and the `gpui_component::dock` facade; `Tabbed` remains the default.
- `PanelPolicy::validate_state(&DockAreaState) -> anyhow::Result<()>` checks a borrowed saved state without mutating it. In `Separate` mode it checks singleton groups, child structure, split axes/sizes, dock placement, and excludes tiles. Payload JSON belongs to the application's own validator.
- `DockArea::set_panel_policy(policy, window, cx) -> Result<()>` validates existing trees before switching. Call it before installing or loading this application's state.
- `DockArea::try_set_center(layout, window, cx)` and `try_set_dock(placement, layout, window, cx)` return `Result<()>`; old setters retain their signatures and leave the layout unchanged on a rejected installation.
- `DockArea::try_move_panel(panel, target, window, cx) -> Result<()>` rejects invalid targets before detaching the source. The existing `move_panel` and `split_at` entry points route through that check.
- `DockArea::add_panel_split_view(panel: Arc<dyn PanelView>, node: NodeId, placement: Placement, size: Option<Pixels>, window, cx) -> Result<()>` inserts a new registered panel into a singleton leaf. Use a UI `panel_handle` when passing an entity that supplies UI titles/controls.
- Existing `add_panel` and `add_panel_view` insert below the first group in `Separate` mode; re-adding a live panel is a no-op. Adding to an empty region creates its first singleton. A rejected explicit tile insertion remains a no-op.
- `DockArea::load` runs the borrowed structural validator before changing version, caches, layout, or registrations. The application must retain the original serialized bytes and manage recovery/autosave; this API does not own a file.
- `TabGroupContext::allows_merging()` lets renderers omit header/tab merge targets. Base independently rejects these drops, including drops with no valid preview.

The geometry plan may read `DockArea::panel_policy()` or the private `panel_policy` field. This plan does not change `render_node`, expanded dimensions, the `Panel` extent contract, or workspace scrolling.

## File responsibilities

| File | Responsibility |
| --- | --- |
| `crates/base/src/dock/policy.rs` | Mode, borrowed state validation, candidate-tree validation, pure regression tests. |
| `crates/base/src/dock/mod.rs` | Public policy export. |
| `crates/ui/src/dock/mod.rs` | Matching UI facade export, covered by its existing export-parity test. |
| `crates/base/src/dock/dock_area.rs` | Checked installation, insertion, movement, load gate, and propagation of group constraints. |
| `crates/base/src/dock/separate_panels_tests.rs` | GPUI regression tests using the existing `TestPanel`, theme setup, container identity, and dump fixtures. |
| `crates/base/src/dock/tab_group.rs` | Merge permission and explicit rejection of center/header targets; preserve all edge targets. |
| `crates/ui/src/dock/tab_panel.rs` | Standard tab renderer uses the merge permission for header drop targets. |

The diffs below are complete and ordered. Save each diff to its named temporary patch file using the editor, then run its check/apply commands. Do not apply later patches before earlier ones. New public APIs in a failing test are defined by the immediately following implementation patch.

### Task 1: Define the separate-panel policy and persisted-state validator

**Files:**

- Create: `crates/base/src/dock/policy.rs`
- Modify: `crates/base/src/dock/mod.rs`
- Modify/Test: `crates/ui/src/dock/mod.rs` (`every_base_dock_export_is_reachable_from_here`)
- Test: inline tests in `policy.rs`

- [ ] **Step 1: Add the failing regression tests.**

Save this diff as `/tmp/wv01-01-tests.patch`.

```diff
diff --git a/crates/base/src/dock/mod.rs b/crates/base/src/dock/mod.rs
--- a/crates/base/src/dock/mod.rs
+++ b/crates/base/src/dock/mod.rs
@@ -174,6 +174,7 @@
 mod drag;
 pub mod layout;
 mod panel;
+mod policy;
 mod registry;
 mod state;
 mod state_convert;
@@ -194,6 +195,7 @@
     TilePanel,
 };
 pub use panel::{Panel, PanelEvent, PanelView};
+pub use policy::PanelPolicy;
 pub use registry::{PanelBuildContext, PanelRegistry, register_panel};
 pub use state::{DockAreaState, DockPlacement, DockState, PanelInfo, PanelState, TileMeta};
 /// Both halves of the persistence seam. `PaneTree::to_state` reads panel
diff --git a/crates/base/src/dock/policy.rs b/crates/base/src/dock/policy.rs
new file mode 100644
--- /dev/null
+++ b/crates/base/src/dock/policy.rs
@@ -0,0 +1,96 @@
+#[cfg(test)]
+mod tests {
+    use super::*;
+    use gpui::px;
+
+    fn group(names: &[&str]) -> PanelState {
+        PanelState {
+            panel_name: "TabPanel".into(),
+            children: names.iter().map(|name| PanelState::new(*name)).collect(),
+            info: PanelInfo::tabs(0),
+        }
+    }
+
+    fn state(center: PanelState) -> DockAreaState {
+        DockAreaState {
+            center,
+            ..Default::default()
+        }
+    }
+
+    #[test]
+    fn separate_policy_rejects_multigroup_without_changing_input() {
+        let input = state(group(&["CPU", "GPU"]));
+        let original = input.clone();
+        assert!(PanelPolicy::Separate.validate_state(&input).is_err());
+        assert_eq!(input, original);
+        assert!(PanelPolicy::Tabbed.validate_state(&input).is_ok());
+    }
+
+    #[test]
+    fn separate_policy_accepts_vertical_singletons_and_empty_workspace() {
+        let input = state(PanelState {
+            panel_name: "StackPanel".into(),
+            children: vec![group(&["CPU"]), group(&["GPU"])],
+            info: PanelInfo::Stack {
+                sizes: vec![px(320.), px(240.)],
+                axis: 1,
+            },
+        });
+        assert!(PanelPolicy::Separate.validate_state(&input).is_ok());
+        let empty = state(PanelState {
+            panel_name: "StackPanel".into(),
+            children: vec![],
+            info: PanelInfo::Stack {
+                sizes: vec![],
+                axis: 1,
+            },
+        });
+        assert!(PanelPolicy::Separate.validate_state(&empty).is_ok());
+    }
+
+    #[test]
+    fn separate_policy_rejects_nested_and_side_dock_incompatibilities() {
+        let invalid = group(&["CPU", "GPU"]);
+        let mut input = state(group(&["Memory"]));
+        input.left_dock = Some(super::super::DockState::new(
+            invalid,
+            DockPlacement::Left,
+            px(240.),
+            true,
+        ));
+        assert!(PanelPolicy::Separate.validate_state(&input).is_err());
+        input.left_dock = None;
+        input.center.children = vec![group(&["CPU"])];
+        assert!(PanelPolicy::Separate.validate_state(&input).is_err());
+    }
+
+    #[test]
+    fn separate_policy_rejects_tiles_and_bad_geometry() {
+        let mut input = state(PanelState {
+            panel_name: "Tiles".into(),
+            children: vec![],
+            info: PanelInfo::Tiles { metas: vec![] },
+        });
+        assert!(PanelPolicy::Separate.validate_state(&input).is_err());
+        input.center = PanelState {
+            panel_name: "StackPanel".into(),
+            children: vec![group(&["CPU"])],
+            info: PanelInfo::Stack {
+                sizes: vec![px(f32::NAN)],
+                axis: 1,
+            },
+        };
+        assert!(PanelPolicy::Separate.validate_state(&input).is_err());
+        input.center.info = PanelInfo::Stack {
+            sizes: vec![px(20.)],
+            axis: 2,
+        };
+        assert!(PanelPolicy::Separate.validate_state(&input).is_err());
+        input.center.info = PanelInfo::Stack {
+            sizes: vec![],
+            axis: 1,
+        };
+        assert!(PanelPolicy::Separate.validate_state(&input).is_err());
+    }
+}
```

```bash
rtk git apply --check /tmp/wv01-01-tests.patch
rtk git apply /tmp/wv01-01-tests.patch
```

- [ ] **Step 2: Run the tests and record the expected failure.**

```bash
rtk cargo test -p gpui-base --lib separate_policy_ -- --nocapture
```

Expected: compilation fails because the policy APIs used by these tests do not exist yet. An unavailable system library, dependency checkout, or toolchain is an environment blocker, not the expected red result. Record it separately.

- [ ] **Step 3: Apply the implementation.**

Save this diff as `/tmp/wv01-01-impl.patch`.

```diff
diff --git a/crates/base/src/dock/policy.rs b/crates/base/src/dock/policy.rs
--- a/crates/base/src/dock/policy.rs
+++ b/crates/base/src/dock/policy.rs
@@ -1,3 +1,136 @@
+//! Optional layout restrictions owned by DockArea, not by individual panels.
+
+use anyhow::{Result, ensure};
+use std::collections::HashSet;
+
+use super::{DockAreaState, DockPlacement, PaneRef, PaneTree, PanelInfo, PanelState};
+
+#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
+pub enum PanelPolicy {
+    /// Preserve the framework's tab groups and tiles.
+    #[default]
+    Tabbed,
+    /// Every panel occupies one singleton leaf within a split arrangement.
+    Separate,
+}
+
+impl PanelPolicy {
+    pub fn allows_merging(self) -> bool {
+        self == Self::Tabbed
+    }
+
+    /// Check persisted input before constructing panels or changing live state.
+    /// The caller retains the original input when this returns an error.
+    pub fn validate_state(self, state: &DockAreaState) -> Result<()> {
+        if self == Self::Tabbed {
+            return Ok(());
+        }
+        self.validate_panel_state(&state.center)?;
+        for (expected, dock) in [
+            (DockPlacement::Left, state.left_dock.as_ref()),
+            (DockPlacement::Right, state.right_dock.as_ref()),
+            (DockPlacement::Bottom, state.bottom_dock.as_ref()),
+        ] {
+            if let Some(dock) = dock {
+                ensure!(
+                    dock.placement() == expected,
+                    "dock placement does not match its field"
+                );
+                ensure!(
+                    f32::from(dock.size()).is_finite() && f32::from(dock.size()) > 0.,
+                    "invalid dock size"
+                );
+                self.validate_panel_state(dock.panel())?;
+            }
+        }
+        Ok(())
+    }
+
+    fn validate_panel_state(self, root: &PanelState) -> Result<()> {
+        let mut pending = vec![root];
+        while let Some(node) = pending.pop() {
+            match &node.info {
+                PanelInfo::Stack { sizes, axis } => {
+                    ensure!(*axis <= 1, "invalid split axis");
+                    ensure!(
+                        sizes.len() == node.children.len(),
+                        "split size count does not match children"
+                    );
+                    ensure!(
+                        sizes
+                            .iter()
+                            .all(|size| f32::from(*size).is_finite() && f32::from(*size) >= 0.),
+                        "invalid split size"
+                    );
+                }
+                PanelInfo::Tabs { active_index } => {
+                    ensure!(
+                        node.children.len() <= 1 && *active_index == 0,
+                        "separate panels require singleton groups"
+                    );
+                    ensure!(
+                        node.children
+                            .first()
+                            .is_none_or(|child| matches!(child.info, PanelInfo::Panel(_))),
+                        "a singleton group must contain a panel"
+                    );
+                }
+                PanelInfo::Panel(_) => {
+                    ensure!(
+                        node.children.is_empty(),
+                        "panel leaf contains layout children"
+                    );
+                }
+                PanelInfo::Tiles { .. } => anyhow::bail!("tiles are not separate split regions"),
+            }
+            pending.extend(node.children.iter());
+        }
+        Ok(())
+    }
+
+    pub(crate) fn validate_tree(self, tree: &PaneTree) -> Result<()> {
+        if self == Self::Tabbed {
+            return Ok(());
+        }
+        let mut ids = HashSet::new();
+        for node in tree.node_ids() {
+            match tree
+                .find_node(node)
+                .expect("node came from this tree")
+                .kind()
+            {
+                PaneRef::Tabs { panels, .. } => {
+                    ensure!(
+                        panels.len() <= 1,
+                        "separate panels require singleton groups"
+                    );
+                    for panel in panels {
+                        ensure!(ids.insert(*panel), "panel occupies more than one region");
+                    }
+                }
+                PaneRef::Tiles { .. } => anyhow::bail!("tiles are not separate split regions"),
+                PaneRef::Split {
+                    children, sizes, ..
+                } => {
+                    ensure!(
+                        children.len() == sizes.len(),
+                        "split size count does not match children"
+                    );
+                    ensure!(
+                        sizes.iter().all(|size| {
+                            size.is_none_or(|size| {
+                                f32::from(size).is_finite() && size >= gpui::px(0.)
+                            })
+                        }),
+                        "invalid split size"
+                    );
+                }
+            }
+        }
+        Ok(())
+    }
+}
+
 #[cfg(test)]
 mod tests {
     use super::*;
diff --git a/crates/ui/src/dock/mod.rs b/crates/ui/src/dock/mod.rs
--- a/crates/ui/src/dock/mod.rs
+++ b/crates/ui/src/dock/mod.rs
@@ -53,9 +53,9 @@
     DockLayout, DockPlacement, DockSizing, DockState, DragPanel, DropIndicator,
     DropPlaceholderBounds, DropTarget, EditResult, HANDLE_SIZE, InsertTarget, NodeId, PaneNode,
     PaneRef, PaneTree, PanelBuildContext, PanelBuilder, PanelEvent, PanelId, PanelInfo,
-    PanelRegistry, PanelSource, PanelState, ResizeSide, RootKind, TabGroup, TabGroupConstraints,
-    TabGroupContext, TabGroupEvent, TabGroupRenderer, TileContext, TileMeta, TilePanel, TilesEvent,
-    TilesRenderer, TilesState, register_panel,
+    PanelPolicy, PanelRegistry, PanelSource, PanelState, ResizeSide, RootKind, TabGroup,
+    TabGroupConstraints, TabGroupContext, TabGroupEvent, TabGroupRenderer, TileContext, TileMeta,
+    TilePanel, TilesEvent, TilesRenderer, TilesState, register_panel,
 };
 pub use panel::*;
 pub use tab_panel::DragPanelPreview;
```

```bash
rtk git apply --check /tmp/wv01-01-impl.patch
rtk git apply /tmp/wv01-01-impl.patch
```

- [ ] **Step 4: Verify the behavior.**

```bash
rtk cargo test -p gpui-base --lib separate_policy_ -- --nocapture
```

Expected: all four policy tests pass. Existing tabbed state remains accepted under the default policy; separate mode rejects multi-panel groups, invalid nesting, tiles, and malformed geometry. The existing facade test must also pass; it catches a base export that is missing from `gpui_component::dock` without maintaining another hand-written list.

```bash
rtk cargo test -p gpui-component --lib every_base_dock_export_is_reachable_from_here -- --nocapture
```

- [ ] **Step 5: Commit the verified change.**

```bash
rtk git add crates/base/src/dock/policy.rs crates/base/src/dock/mod.rs crates/ui/src/dock/mod.rs
rtk git commit -m "feat(dock): add opt-in separate-panel policy"
```

### Task 2: Make layout installation, moves, and singleton insertion transactional

**Files:**

- Modify: `crates/base/src/dock/dock_area.rs`
- Create/Test: `crates/base/src/dock/separate_panels_tests.rs`

- [ ] **Step 1: Add the failing regression tests.**

Save this diff as `/tmp/wv01-02-tests.patch`.

```diff
diff --git a/crates/base/src/dock/dock_area.rs b/crates/base/src/dock/dock_area.rs
--- a/crates/base/src/dock/dock_area.rs
+++ b/crates/base/src/dock/dock_area.rs
@@ -4461,3 +4461,7 @@
         );
     }
 }
+
+#[cfg(test)]
+#[path = "separate_panels_tests.rs"]
+mod separate_panels_tests;
diff --git a/crates/base/src/dock/separate_panels_tests.rs b/crates/base/src/dock/separate_panels_tests.rs
new file mode 100644
--- /dev/null
+++ b/crates/base/src/dock/separate_panels_tests.rs
@@ -0,0 +1,300 @@
+use super::*;
+use crate::dock::test_support::{TestPanel, drain, log_of};
+use gpui::{TestAppContext, VisualTestContext};
+
+fn setup(cx: &mut TestAppContext) -> (Entity<DockArea>, &mut VisualTestContext) {
+    cx.update(|cx| {
+        let _ = crate::Theme::global_mut(cx);
+    });
+    cx.add_window_view(|window, cx| DockArea::new("separate-test", Some(1), window, cx))
+}
+
+fn assert_singletons(area: &DockArea) {
+    PanelPolicy::Separate.validate_tree(&area.center).unwrap();
+    for pane in area.docks.values() {
+        PanelPolicy::Separate.validate_tree(&pane.tree).unwrap();
+    }
+}
+
+#[gpui::test]
+fn separate_default_preserves_tabs_and_policy_change_is_transactional(cx: &mut TestAppContext) {
+    let (area, cx) = setup(cx);
+    cx.update(|window, cx| {
+        let alpha = TestPanel::new("Alpha", cx);
+        let beta = TestPanel::new("Beta", cx);
+        area.update(cx, |area, cx| {
+            area.set_center(DockLayout::tabs().panel(alpha).panel(beta), window, cx);
+            let before = area.dump(cx);
+            assert!(
+                area.set_panel_policy(PanelPolicy::Separate, window, cx)
+                    .is_err()
+            );
+            assert_eq!(area.panel_policy(), PanelPolicy::Tabbed);
+            assert_eq!(area.dump(cx), before);
+        });
+    });
+}
+
+#[gpui::test]
+fn separate_install_and_load_reject_before_live_state_changes(cx: &mut TestAppContext) {
+    let (area, cx) = setup(cx);
+    let log = log_of();
+    cx.update(|window, cx| {
+        let alpha = TestPanel::logging("Alpha", &log, cx);
+        let beta = TestPanel::logging("Beta", &log, cx);
+        area.update(cx, |area, cx| {
+            area.set_panel_policy(PanelPolicy::Separate, window, cx)
+                .unwrap();
+            area.try_set_center(DockLayout::tabs().panel(alpha.clone()), window, cx)
+                .unwrap();
+            let before = area.dump(cx);
+            let entities = area.container_entity_ids();
+            drain(&log);
+            assert!(
+                area.try_set_center(
+                    DockLayout::tabs().panel(alpha.clone()).panel(beta.clone()),
+                    window,
+                    cx,
+                )
+                .is_err()
+            );
+            assert!(
+                area.try_set_dock(
+                    DockPlacement::Left,
+                    DockLayout::tabs().panel(alpha).panel(beta),
+                    window,
+                    cx,
+                )
+                .is_err()
+            );
+            let invalid = DockAreaState {
+                version: Some(999),
+                center: PanelState {
+                    panel_name: "TabPanel".into(),
+                    children: vec![PanelState::new("CPU"), PanelState::new("GPU")],
+                    info: PanelInfo::tabs(0),
+                },
+                ..Default::default()
+            };
+            let original = invalid.clone();
+            assert!(area.load(invalid.clone(), window, cx).is_err());
+            assert_eq!(invalid, original);
+            assert_eq!(area.dump(cx), before);
+            assert_eq!(area.container_entity_ids(), entities);
+            assert!(drain(&log).is_empty());
+            assert_singletons(area);
+        });
+    });
+}
+
+#[gpui::test]
+fn separate_merge_rejection_preserves_both_regions_and_source_handle(cx: &mut TestAppContext) {
+    let (area, cx) = setup(cx);
+    cx.update(|window, cx| {
+        let alpha = TestPanel::new("Alpha", cx);
+        let beta = TestPanel::new("Beta", cx);
+        let alpha_id = PanelId::from(alpha.entity_id());
+        let beta_id = PanelId::from(beta.entity_id());
+        area.update(cx, |area, cx| {
+            area.set_panel_policy(PanelPolicy::Separate, window, cx)
+                .unwrap();
+            area.try_set_center(DockLayout::tabs().panel(alpha.clone()), window, cx)
+                .unwrap();
+            area.try_set_dock(
+                DockPlacement::Left,
+                DockLayout::tabs().panel(beta),
+                window,
+                cx,
+            )
+            .unwrap();
+            let target = area
+                .layout(DockPlacement::Left)
+                .unwrap()
+                .find_panel_node(beta_id)
+                .unwrap();
+            let before = area.dump(cx);
+            let entities = area.container_entity_ids();
+            assert!(
+                area.try_move_panel(
+                    alpha_id,
+                    InsertTarget::Tabs {
+                        node: target,
+                        ix: None,
+                        activate: true,
+                    },
+                    window,
+                    cx
+                )
+                .is_err()
+            );
+            assert!(
+                area.try_move_panel(
+                    alpha_id,
+                    InsertTarget::Split {
+                        node: NodeId::from_u64(u64::MAX),
+                        placement: Placement::Top,
+                        size: None,
+                    },
+                    window,
+                    cx
+                )
+                .is_err()
+            );
+            assert_eq!(area.dump(cx), before);
+            assert_eq!(area.container_entity_ids(), entities);
+            assert_eq!(
+                area.panel(alpha_id)
+                    .unwrap()
+                    .as_any()
+                    .downcast_ref::<Entity<TestPanel>>()
+                    .unwrap()
+                    .entity_id(),
+                alpha.entity_id()
+            );
+            assert_singletons(area);
+        });
+    });
+}
+
+#[gpui::test]
+fn separate_edge_moves_and_reinsertion_keep_every_panel_in_its_own_region(cx: &mut TestAppContext) {
+    let (area, cx) = setup(cx);
+    cx.update(|window, cx| {
+        let alpha = TestPanel::new("Alpha", cx);
+        let beta = TestPanel::new("Beta", cx);
+        let gamma = TestPanel::new("Gamma", cx);
+        let alpha_id = PanelId::from(alpha.entity_id());
+        let beta_id = PanelId::from(beta.entity_id());
+        let gamma_id = PanelId::from(gamma.entity_id());
+        area.update(cx, |area, cx| {
+            area.set_panel_policy(PanelPolicy::Separate, window, cx)
+                .unwrap();
+            area.try_set_center(
+                DockLayout::v_split()
+                    .child(DockLayout::tabs().panel(alpha.clone()), Some(px(200.)))
+                    .child(DockLayout::tabs().panel(beta), Some(px(200.))),
+                window,
+                cx,
+            )
+            .unwrap();
+            for placement in [
+                Placement::Left,
+                Placement::Right,
+                Placement::Top,
+                Placement::Bottom,
+            ] {
+                let node = area.center.find_panel_node(beta_id).unwrap();
+                area.try_move_panel(
+                    alpha_id,
+                    InsertTarget::Split {
+                        node,
+                        placement,
+                        size: None,
+                    },
+                    window,
+                    cx,
+                )
+                .unwrap();
+                assert_ne!(
+                    area.center.find_panel_node(alpha_id),
+                    area.center.find_panel_node(beta_id)
+                );
+                assert_singletons(area);
+            }
+            let target = area.center.find_panel_node(beta_id).unwrap();
+            area.add_panel_split_view(
+                Arc::new(gamma),
+                target,
+                Placement::Bottom,
+                Some(px(200.)),
+                window,
+                cx,
+            )
+            .unwrap();
+            assert!(area.center.contains_panel(gamma_id));
+            area.remove_panel(alpha.clone(), window, cx);
+            area.add_panel(alpha, DockPlacement::Center, None, window, cx);
+            assert_eq!(area.center.panels().count(), 3);
+            assert_singletons(area);
+            let dump = area.dump(cx);
+            PanelPolicy::Separate.validate_state(&dump).unwrap();
+        });
+    });
+}
+
+#[gpui::test]
+fn separate_failed_insert_does_not_register_a_panel_or_replace_a_live_handle(
+    cx: &mut TestAppContext,
+) {
+    let (area, cx) = setup(cx);
+    cx.update(|window, cx| {
+        let alpha = TestPanel::new("Alpha", cx);
+        let beta = TestPanel::new("Beta", cx);
+        let beta_id = PanelId::from(beta.entity_id());
+        let alpha_id = PanelId::from(alpha.entity_id());
+        area.update(cx, |area, cx| {
+            area.set_panel_policy(PanelPolicy::Separate, window, cx)
+                .unwrap();
+            area.try_set_center(DockLayout::tabs().panel(alpha.clone()), window, cx)
+                .unwrap();
+            let before = area.dump(cx);
+            assert!(
+                area.add_panel_split_view(
+                    Arc::new(beta),
+                    NodeId::from_u64(u64::MAX),
+                    Placement::Top,
+                    None,
+                    window,
+                    cx
+                )
+                .is_err()
+            );
+            assert!(area.panel(beta_id).is_none());
+            let node = area.center.find_panel_node(alpha_id).unwrap();
+            assert!(
+                area.add_panel_split_view(Arc::new(alpha), node, Placement::Top, None, window, cx)
+                    .is_err()
+            );
+            assert_eq!(area.dump(cx), before);
+        });
+    });
+}
+
+#[gpui::test]
+fn separate_checked_move_rejects_wrong_node_kind_even_in_default_mode(cx: &mut TestAppContext) {
+    let (area, cx) = setup(cx);
+    cx.update(|window, cx| {
+        let alpha = TestPanel::new("Alpha", cx);
+        let beta = TestPanel::new("Beta", cx);
+        let gamma = TestPanel::new("Gamma", cx);
+        let alpha_id = PanelId::from(alpha.entity_id());
+        area.update(cx, |area, cx| {
+            area.set_center(DockLayout::tabs().panel(alpha), window, cx);
+            area.set_dock(
+                DockPlacement::Left,
+                DockLayout::h_split()
+                    .child(DockLayout::tabs().panel(beta), None)
+                    .child(DockLayout::tabs().panel(gamma), None),
+                window,
+                cx,
+            );
+            let node = area.layout(DockPlacement::Left).unwrap().root().id();
+            let before = area.dump(cx);
+            assert!(
+                area.try_move_panel(
+                    alpha_id,
+                    InsertTarget::Tabs {
+                        node,
+                        ix: None,
+                        activate: true
+                    },
+                    window,
+                    cx
+                )
+                .is_err()
+            );
+            assert_eq!(area.dump(cx), before);
+            assert!(area.panel(alpha_id).is_some());
+        });
+    });
+}
```

```bash
rtk git apply --check /tmp/wv01-02-tests.patch
rtk git apply /tmp/wv01-02-tests.patch
```

- [ ] **Step 2: Run the tests and record the expected failure.**

```bash
rtk cargo test -p gpui-base --lib dock::dock_area::separate_panels_tests:: -- --nocapture
```

Expected: compilation fails because the policy APIs used by these tests do not exist yet. An unavailable system library, dependency checkout, or toolchain is an environment blocker, not the expected red result. Record it separately.

- [ ] **Step 3: Apply the implementation.**

Save this diff as `/tmp/wv01-02-impl.patch`.

```diff
diff --git a/crates/base/src/dock/dock_area.rs b/crates/base/src/dock/dock_area.rs
--- a/crates/base/src/dock/dock_area.rs
+++ b/crates/base/src/dock/dock_area.rs
@@ -7,7 +7,7 @@
     sync::Arc,
 };

-use anyhow::Result;
+use anyhow::{Result, ensure};
 use gpui::{
     AnyElement, AnyView, App, AppContext as _, Axis, Bounds, Context, Div, Empty, Entity,
     EventEmitter, FocusHandle, Focusable, InteractiveElement as _, IntoElement, ParentElement,
@@ -28,6 +28,7 @@
         PanelId, RootKind,
     },
     panel::{LivePanels, Panel, PanelEvent, PanelView},
+    policy::PanelPolicy,
     registry::{PanelBuildContext, PanelRegistry},
     state::{DockAreaState, DockPlacement, DockState, PanelInfo, PanelState, TileMeta},
     state_convert::{PanelBuilder, PanelSource as _},
@@ -133,6 +134,7 @@
     panels: HashMap<PanelId, Arc<dyn PanelView>>,

     locked: bool,
+    panel_policy: PanelPolicy,
     zoomed: Option<Zoomed>,
     focus_handle: FocusHandle,
     renderer: Rc<dyn DockAreaRenderer>,
@@ -166,6 +168,7 @@
             tiles: HashMap::new(),
             panels: HashMap::new(),
             locked: false,
+            panel_policy: PanelPolicy::default(),
             zoomed: None,
             focus_handle: cx.focus_handle(),
             renderer: Rc::new(BareDockArea),
@@ -222,6 +225,54 @@
         self.panels.get(&panel)
     }

+    pub fn panel_policy(&self) -> PanelPolicy {
+        self.panel_policy
+    }
+
+    /// Opt in before installing or loading the application's layout.
+    pub fn set_panel_policy(
+        &mut self,
+        policy: PanelPolicy,
+        window: &mut Window,
+        cx: &mut Context<Self>,
+    ) -> Result<()> {
+        policy.validate_tree(&self.center)?;
+        let mut ids: HashSet<PanelId> = self.center.panels().collect();
+        for pane in self.docks.values() {
+            policy.validate_tree(&pane.tree)?;
+            if policy == PanelPolicy::Separate {
+                for panel in pane.tree.panels() {
+                    ensure!(ids.insert(panel), "panel occupies more than one region");
+                }
+            }
+        }
+        self.panel_policy = policy;
+        self.reconcile(window, cx);
+        Ok(())
+    }
+
+    fn validate_install(&self, tree: &PaneTree, placement: DockPlacement) -> Result<()> {
+        self.panel_policy.validate_tree(tree)?;
+        if self.panel_policy == PanelPolicy::Separate {
+            let incoming: HashSet<_> = tree.panels().collect();
+            if placement != DockPlacement::Center {
+                ensure!(
+                    !self.center.panels().any(|id| incoming.contains(&id)),
+                    "panel already belongs to center"
+                );
+            }
+            for (other, pane) in &self.docks {
+                if *other != placement {
+                    ensure!(
+                        !pane.tree.panels().any(|id| incoming.contains(&id)),
+                        "panel already belongs to another dock"
+                    );
+                }
+            }
+        }
+        Ok(())
+    }
+
     pub fn is_locked(&self) -> bool {
         self.locked
     }
@@ -254,11 +305,24 @@
     /// Replace the center region with a described layout. Whatever was there
     /// leaves the dock, so its panels are told [`Panel::on_removed`].
     pub fn set_center(&mut self, layout: DockLayout, window: &mut Window, cx: &mut Context<Self>) {
+        if let Err(error) = self.try_set_center(layout, window, cx) {
+            tracing::warn!(%error, "dock layout rejected");
+        }
+    }
+
+    pub fn try_set_center(
+        &mut self,
+        layout: DockLayout,
+        window: &mut Window,
+        cx: &mut Context<Self>,
+    ) -> Result<()> {
         let (tree, panels) = PaneTree::from_layout(layout, RootKind::Split);
+        self.validate_install(&tree, DockPlacement::Center)?;
         self.center = tree;
         self.panels.extend(panels);
         self.reconcile(window, cx);
         cx.emit(DockEvent::LayoutChanged);
+        Ok(())
     }

     /// Replace one dock with a described layout, creating the dock if the area
@@ -274,11 +338,23 @@
         window: &mut Window,
         cx: &mut Context<Self>,
     ) {
+        if let Err(error) = self.try_set_dock(placement, layout, window, cx) {
+            tracing::warn!(%error, "dock layout rejected");
+        }
+    }
+
+    pub fn try_set_dock(
+        &mut self,
+        placement: DockPlacement,
+        layout: DockLayout,
+        window: &mut Window,
+        cx: &mut Context<Self>,
+    ) -> Result<()> {
         if placement == DockPlacement::Center {
-            return self.set_center(layout, window, cx);
-        }
-
+            return self.try_set_center(layout, window, cx);
+        }
         let (tree, panels) = PaneTree::from_layout(layout, RootKind::Any);
+        self.validate_install(&tree, placement)?;
         let dock = self
             .docks
             .get(&placement)
@@ -288,6 +364,7 @@
         self.panels.extend(panels);
         self.reconcile(window, cx);
         cx.emit(DockEvent::LayoutChanged);
+        Ok(())
     }

     /// Take a dock away entirely, panels and all. Distinct from
@@ -482,6 +559,33 @@
         window: &mut Window,
         cx: &mut Context<Self>,
     ) {
+        if self.panel_policy == PanelPolicy::Separate {
+            let Added::Anywhere(size) = added else {
+                return;
+            };
+            // Re-adding a live panel must not duplicate or relocate it.
+            if self.panels.contains_key(&id) {
+                return;
+            }
+            let result = if let Some(tree) = self.layout(placement) {
+                let node = first_tab_group(tree.root()).unwrap_or(tree.root().id());
+                self.add_panel_split_view(panel, node, Placement::Bottom, size, window, cx)
+            } else {
+                let layout = DockLayout::tabs().panel_view(panel, cx);
+                let result = self.try_set_dock(placement, layout, window, cx);
+                if result.is_ok() {
+                    if let Some(size) = size {
+                        self.set_dock_size(placement, size, window, cx);
+                    }
+                }
+                result
+            };
+            if let Err(error) = result {
+                tracing::warn!(%error, "panel insertion rejected");
+            }
+            return;
+        }
+
         // The registration is written before the target is resolved, because
         // both want `&mut self`, so an add that finds nowhere to put the panel
         // has to undo it. *Undo*, not remove: adding a panel the dock already
@@ -565,6 +669,51 @@
         self.commit(result, window, cx);
     }

+    /// Register a new panel directly in a singleton region beside `node`.
+    /// Rejection leaves both registration and the live layout unchanged.
+    pub fn add_panel_split_view(
+        &mut self,
+        panel: Arc<dyn PanelView>,
+        node: NodeId,
+        placement: Placement,
+        size: Option<Pixels>,
+        window: &mut Window,
+        cx: &mut Context<Self>,
+    ) -> Result<()> {
+        let id = panel.panel_id(cx);
+        ensure!(
+            !self.panels.contains_key(&id),
+            "panel already belongs to this dock area"
+        );
+        ensure!(
+            size.is_none_or(|size| f32::from(size).is_finite() && size > px(0.)),
+            "invalid split size"
+        );
+        let region = self
+            .placement_of_node(node)
+            .ok_or_else(|| anyhow::anyhow!("split target no longer exists"))?;
+        let target = InsertTarget::Split {
+            node,
+            placement,
+            size,
+        };
+        let mut candidate = self.layout(region).expect("target region exists").clone();
+        ensure!(
+            candidate.insert_panel(id, target).changed(),
+            "split insertion was not accepted"
+        );
+        self.validate_install(&candidate, region)?;
+
+        self.adopt_measured_sizes(region, cx);
+        self.panels.insert(id, panel);
+        let result = self
+            .tree_mut(region)
+            .expect("target region exists")
+            .insert_panel(id, target);
+        self.commit(result, window, cx);
+        Ok(())
+    }
+
     /// Put the view map back the way an add found it, for one that placed
     /// nothing. `previous` is what [`HashMap::insert`] handed back.
     fn restore_registration(&mut self, id: PanelId, previous: Option<Arc<dyn PanelView>>) {
@@ -587,6 +736,66 @@
     /// Move a panel to a new home. The panel never leaves the dock, so it is
     /// never told it was removed.
     pub fn move_panel(
+        &mut self,
+        panel: PanelId,
+        target: InsertTarget,
+        window: &mut Window,
+        cx: &mut Context<Self>,
+    ) {
+        if let Err(error) = self.try_move_panel(panel, target, window, cx) {
+            tracing::debug!(%error, "panel move rejected");
+        }
+    }
+
+    /// Validate a move on a candidate tree before changing either live region.
+    pub fn try_move_panel(
+        &mut self,
+        panel: PanelId,
+        target: InsertTarget,
+        window: &mut Window,
+        cx: &mut Context<Self>,
+    ) -> Result<()> {
+        ensure!(self.panels.contains_key(&panel), "panel is not registered");
+        let source = self
+            .placement_of_panel(panel)
+            .ok_or_else(|| anyhow::anyhow!("source panel no longer exists"))?;
+        let destination = self
+            .placement_of_node(target_node(&target))
+            .ok_or_else(|| anyhow::anyhow!("drop target no longer exists"))?;
+        if self.panel_policy == PanelPolicy::Separate {
+            ensure!(
+                matches!(target, InsertTarget::Split { .. }),
+                "merging panels is disabled"
+            );
+        }
+        if let InsertTarget::Split {
+            size: Some(size), ..
+        } = target
+        {
+            ensure!(
+                f32::from(size).is_finite() && size > px(0.),
+                "invalid split size"
+            );
+        }
+        let mut candidate = self
+            .layout(destination)
+            .expect("destination exists")
+            .clone();
+        let changed = if source == destination {
+            candidate.move_panel(panel, target).changed()
+        } else {
+            candidate.insert_panel(panel, target).changed()
+        };
+        ensure!(
+            changed && candidate.contains_panel(panel),
+            "drop target cannot accept this panel"
+        );
+        self.panel_policy.validate_tree(&candidate)?;
+        self.move_panel_unchecked(panel, target, window, cx);
+        Ok(())
+    }
+
+    fn move_panel_unchecked(
         &mut self,
         panel: PanelId,
         target: InsertTarget,
@@ -665,15 +874,16 @@
         window: &mut Window,
         cx: &mut Context<Self>,
     ) {
-        let Some(region) = self.placement_of_node(node) else {
-            return;
-        };
-        self.adopt_measured_sizes(region, cx);
-        let Some(tree) = self.tree_mut(region) else {
-            return;
-        };
-        let result = tree.split(node, panel, placement, None);
-        self.commit(result, window, cx);
+        self.move_panel(
+            panel,
+            InsertTarget::Split {
+                node,
+                placement,
+                size: None,
+            },
+            window,
+            cx,
+        );
     }

     fn remove_panel_id(&mut self, panel: PanelId, window: &mut Window, cx: &mut Context<Self>) {
@@ -818,6 +1028,7 @@
         window: &mut Window,
         cx: &mut Context<Self>,
     ) -> Result<()> {
+        self.panel_policy.validate_state(&state)?;
         self.version = state.version;
         self.zoomed = None;
         // Nothing in the old layout survives a load, so the caches are
```

```bash
rtk git apply --check /tmp/wv01-02-impl.patch
rtk git apply /tmp/wv01-02-impl.patch
```

- [ ] **Step 4: Verify the behavior.**

```bash
rtk cargo test -p gpui-base --lib dock::dock_area::separate_panels_tests:: -- --nocapture
```

Expected: all six tests pass. Rejected state preserves the old version, layout, entity identities, and panel registrations; all four edge placements and remove/reinsert keep singleton groups. The default mode still allows tabs, and an invalid cross-region destination no longer loses its source.

- [ ] **Step 5: Commit the verified change.**

```bash
rtk git add crates/base/src/dock/dock_area.rs crates/base/src/dock/separate_panels_tests.rs
rtk git commit -m "feat(dock): reject invalid edits before changing live panels"
```

### Task 3: Reject merge previews and drops while keeping split dragging

**Files:**

- Modify/Test: `crates/base/src/dock/tab_group.rs`
- Modify: `crates/base/src/dock/dock_area.rs`
- Modify: `crates/ui/src/dock/tab_panel.rs`

- [ ] **Step 1: Add the failing regression tests.**

Save this diff as `/tmp/wv01-03-tests.patch`.

```diff
diff --git a/crates/base/src/dock/tab_group.rs b/crates/base/src/dock/tab_group.rs
--- a/crates/base/src/dock/tab_group.rs
+++ b/crates/base/src/dock/tab_group.rs
@@ -1811,4 +1811,89 @@
         );
         assert!(cx.update(|_, cx| group.read(cx).drop_indicator.is_none()));
     }
+    #[gpui::test]
+    fn separate_groups_reject_center_and_header_drops_without_disabling_edges(
+        cx: &mut TestAppContext,
+    ) {
+        let log = log_of();
+        let (group, _panels, cx) = build_group(&log, &["a"], cx);
+        let events = record_events(&group, cx);
+        let drag = DragPanel::new(PanelId::from_u64(99), elsewhere());
+        cx.update(|window, cx| {
+            group.update(cx, |group, cx| {
+                group.set_constraints(
+                    TabGroupConstraints::in_split(false).allow_merging(false),
+                    window,
+                    cx,
+                );
+                let context = group.context(cx);
+                assert!(context.is_draggable());
+                assert!(context.is_droppable());
+                assert!(!context.allows_merging());
+                group.sync_drop_placeholder(
+                    content_bounds(),
+                    None,
+                    drag.drag_session_id(),
+                    DropPlaceholderBounds::for_placement(content_bounds(), None),
+                    cx,
+                );
+                assert!(group.drop_indicator.is_none());
+                group.on_drop(&drag, None, true, cx);
+                group.sync_drop_placeholder(
+                    content_bounds(),
+                    Some(Placement::Right),
+                    drag.drag_session_id(),
+                    DropPlaceholderBounds::for_placement(content_bounds(), None),
+                    cx,
+                );
+                group.on_drop(&drag, Some(0), true, cx);
+                group.emit_drag_drop(&AnyDrag::new("fixture"), None, cx);
+            });
+        });
+        cx.run_until_parked();
+        assert!(events.borrow().is_empty());
+    }
+
+    #[gpui::test]
+    fn separate_groups_still_emit_all_four_edge_moves(cx: &mut TestAppContext) {
+        let log = log_of();
+        let (group, _panels, cx) = build_group(&log, &["a"], cx);
+        let events = record_events(&group, cx);
+        let drag = DragPanel::new(PanelId::from_u64(99), elsewhere());
+        cx.update(|window, cx| {
+            group.update(cx, |group, cx| {
+                group.set_constraints(
+                    TabGroupConstraints::in_split(false).allow_merging(false),
+                    window,
+                    cx,
+                );
+                for placement in [
+                    Placement::Left,
+                    Placement::Right,
+                    Placement::Top,
+                    Placement::Bottom,
+                ] {
+                    group.sync_drop_placeholder(
+                        content_bounds(),
+                        Some(placement),
+                        drag.drag_session_id(),
+                        DropPlaceholderBounds::for_placement(content_bounds(), None),
+                        cx,
+                    );
+                    assert_eq!(group.drop_indicator.unwrap().placement(), Some(placement));
+                    group.on_drop(&drag, None, true, cx);
+                }
+            });
+        });
+        cx.run_until_parked();
+        assert_eq!(
+            *events.borrow(),
+            vec![
+                "drop panel 99 from 7 split 1 Left",
+                "drop panel 99 from 7 split 1 Right",
+                "drop panel 99 from 7 split 1 Top",
+                "drop panel 99 from 7 split 1 Bottom",
+            ]
+        );
+    }
 }
```

```bash
rtk git apply --check /tmp/wv01-03-tests.patch
rtk git apply /tmp/wv01-03-tests.patch
```

- [ ] **Step 2: Run the tests and record the expected failure.**

```bash
rtk cargo test -p gpui-base --lib separate_groups_ -- --nocapture
```

Expected: compilation fails because the policy APIs used by these tests do not exist yet. An unavailable system library, dependency checkout, or toolchain is an environment blocker, not the expected red result. Record it separately.

- [ ] **Step 3: Apply the implementation.**

Save this diff as `/tmp/wv01-03-impl.patch`.

```diff
diff --git a/crates/base/src/dock/dock_area.rs b/crates/base/src/dock/dock_area.rs
--- a/crates/base/src/dock/dock_area.rs
+++ b/crates/base/src/dock/dock_area.rs
@@ -1251,7 +1251,11 @@
                         // Every group must be told this. A group nobody has
                         // constrained stays `sealed()` and silently declines
                         // drags, drops and closes.
-                        group.set_constraints(constraints, window, cx);
+                        group.set_constraints(
+                            constraints.allow_merging(self.panel_policy.allows_merging()),
+                            window,
+                            cx,
+                        );
                         group.sync_from_tree(views, active_ix, window, cx);
                     });
                 }
diff --git a/crates/base/src/dock/tab_group.rs b/crates/base/src/dock/tab_group.rs
--- a/crates/base/src/dock/tab_group.rs
+++ b/crates/base/src/dock/tab_group.rs
@@ -62,6 +62,7 @@
 pub struct TabGroupConstraints {
     alone: bool,
     dock_locked: bool,
+    allow_merging: bool,
     collapsed: bool,
     closable: bool,
 }
@@ -73,6 +74,7 @@
         Self {
             alone: true,
             dock_locked: true,
+            allow_merging: false,
             collapsed: false,
             closable: false,
         }
@@ -85,6 +87,7 @@
         Self {
             alone,
             dock_locked: false,
+            allow_merging: true,
             collapsed: false,
             closable: true,
         }
@@ -93,6 +96,11 @@
     /// Whether the dock as a whole forbids rearranging.
     pub fn dock_locked(mut self, dock_locked: bool) -> Self {
         self.dock_locked = dock_locked;
+        self
+    }
+
+    pub fn allow_merging(mut self, allow: bool) -> Self {
+        self.allow_merging = allow;
         self
     }

@@ -283,6 +291,7 @@
             locked: self.is_locked(),
             draggable: self.draggable(cx),
             droppable: self.droppable(),
+            allow_merging: self.constraints.allow_merging,
             // A stale indicator would otherwise outlive a drag that was
             // cancelled while hovering this group.
             drop_indicator: cx
@@ -568,6 +577,10 @@
         source: DropPlaceholderBounds,
         cx: &mut Context<Self>,
     ) {
+        if !self.droppable() || (placement.is_none() && !self.constraints.allow_merging) {
+            self.clear_drop_indicator(cx);
+            return;
+        }
         let to = DropPlaceholderBounds::for_placement(bounds, placement);

         let restart = self.drop_indicator.is_none_or(|indicator| {
@@ -611,6 +624,10 @@
         placement: Option<Placement>,
         cx: &mut Context<Self>,
     ) {
+        if !self.droppable() || (placement.is_none() && !self.constraints.allow_merging) {
+            self.clear_drop_indicator(cx);
+            return;
+        }
         self.drop_indicator = None;
         cx.emit(TabGroupEvent::DragDrop {
             item: item.clone(),
@@ -640,6 +657,13 @@
             Some(_) => None,
             None => indicator.and_then(|indicator| indicator.placement()),
         };
+
+        // No indicator is also a merge request, so clearing a denied preview
+        // must not accidentally turn it into an accepted center drop.
+        if !self.droppable() || (placement.is_none() && !self.constraints.allow_merging) {
+            cx.notify();
+            return;
+        }

         // Dropping a panel back onto its own group is a move only when it
         // splits out of a group holding more than itself, or when it lands on
@@ -783,6 +807,7 @@
     locked: bool,
     draggable: bool,
     droppable: bool,
+    allow_merging: bool,
     closable: bool,
     drop_indicator: Option<DropIndicator>,
     on_select_tab: SelectTabHandler,
@@ -843,6 +868,11 @@

     pub fn is_droppable(&self) -> bool {
         self.droppable
+    }
+
+    /// Whether a title/tab drop may merge another panel into this group.
+    pub fn allows_merging(&self) -> bool {
+        self.droppable && self.allow_merging
     }

     pub fn select_tab(&self, ix: usize, window: &mut Window, cx: &mut App) {
@@ -1811,6 +1841,7 @@
         );
         assert!(cx.update(|_, cx| group.read(cx).drop_indicator.is_none()));
     }
+
     #[gpui::test]
     fn separate_groups_reject_center_and_header_drops_without_disabling_edges(
         cx: &mut TestAppContext,
diff --git a/crates/ui/src/dock/tab_panel.rs b/crates/ui/src/dock/tab_panel.rs
--- a/crates/ui/src/dock/tab_panel.rs
+++ b/crates/ui/src/dock/tab_panel.rs
@@ -439,7 +439,7 @@
         let is_bottom_dock = bottom_button.is_some();
         let collapsed = group.is_collapsed();

-        let droppable = group.is_droppable();
+        let droppable = group.allows_merging();
         let tabs_count = group.panels().len();
         let active_ix = group.active_ix();
         let displayed = group.active_panel().map(|panel| panel.panel_id(cx));
```

```bash
rtk git apply --check /tmp/wv01-03-impl.patch
rtk git apply /tmp/wv01-03-impl.patch
```

- [ ] **Step 4: Verify the behavior.**

```bash
rtk cargo test -p gpui-base --lib separate_groups_ -- --nocapture
```

Expected: both tests pass. Center/header and host-item merge drops emit no move; all four edge placements still emit moves. The denied preview cannot fall through into a merge when released.

- [ ] **Step 5: Commit the verified change.**

```bash
rtk git add crates/base/src/dock/dock_area.rs crates/base/src/dock/tab_group.rs crates/ui/src/dock/tab_panel.rs
rtk git commit -m "feat(dock): disable merge targets for separate panels"
```

### Task 4: Verify compatibility and hand off the framework seam

**Files:** the seven files listed above; no new code in this task.

- [ ] **Step 1: Run formatting and the complete dock regression suites.**

```bash
rtk cargo fmt --all -- --check
rtk cargo test -p gpui-base --lib dock:: -- --nocapture
rtk cargo test -p gpui-component --lib dock:: -- --nocapture
rtk cargo check -p gpui-base -p gpui-component --all-targets
```

Expected: formatting and compilation succeed; all existing and new dock tests pass. Existing tabbed/tiles tests exercise the unchanged default policy. If a failure exposes an invalid previously accepted move, fix the behavior while retaining the default's valid tab and tile operations; do not remove its test to make the suite pass.

- [ ] **Step 2: Review requirement evidence and hand off to geometry/application plans.**

Record the executed commands and actual outcomes in the overview's execution record. Verify that the geometry patch applies after these ordered patches before proceeding. Preserve the following boundary: framework tests prove state/drop decisions and transactionality; native application tests still must prove physical dragging, real headers, collapsed extents, scrolling, focus, and invalid-file recovery.

| Requirement | Evidence provided here | Remaining owner |
| --- | --- | --- |
| WV-01 | Four edge move tests; center/header rejection; failed moves preserve source registration and container identity. | Native app drag interaction and header controls. |
| WV-03 | New singleton insertion and remove/reinsert test. | Application visibility state and retained collapse choices. |
| WV-12 | Borrowed validation; rejected `load`/installation preserves live state. | Original-byte retention, default arrangement, recoverable error, autosave protection. |

## Plan verification performed

The proposed diffs were generated from the pinned source. The combined diff passed `git apply --check` against a separate temporary copy. All six red/green patches were also checked and applied sequentially in another temporary copy. `rustfmt --check --edition 2024 --config skip_children=true` passed for the six changed/new implementation/test files after application. These are patch-composition and Rust syntax/format checks, not type checks. The existing `every_base_dock_export_is_reachable_from_here` test body was also compiled and run as a standalone Rust test against the proposed base/UI module files: one passed, zero failed. Only its `include_str!` paths were redirected to the temporary copy; this did not build the framework crates.

No framework Cargo build, Cargo test, native launch, or application acceptance test ran while writing this plan. The original downloaded source and the application's repository source were not modified. This planning task writes only this Markdown document; temporary copies were used to validate the embedded patches.
