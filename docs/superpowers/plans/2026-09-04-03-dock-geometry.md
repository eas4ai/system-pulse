# Dock Geometry and Scroll Extents Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve readable split-panel extents, release collapsed body space, and expose a canvas extent that the native workspace can scroll.

**Architecture:** Application panels supply minimum and preferred dimensions through an additive geometry hook. The separate-panel dock path measures its tree, constrains collapsed leaves to their headers, and explicitly reseeds cached split sizes after presentation changes. Existing default dock rendering remains unchanged.

**Tech Stack:** Rust 2024, GPUI, gpui-base, gpui-component, existing ResizableState and PaneTree.

---

## Execution context

Run in the gpui-component execution worktree after [plan 01](2026-09-04-01-dock-separate-panels.md). The approved requirements are [WV-02, WV-06, and WV-11](../specs/2026-09-04-workspace-visibility-design.md). [Plan 04](2026-09-04-04-native-workspace.md) owns the outer scroll container, app header/row rendering, measurement capture, and native interaction evidence.

The baseline is `ba3433f0740ee5ba2b1db459af49229caf0c1bcc`. Plan 01 introduces `PanelPolicy::Separate` and `DockArea::panel_policy`. This plan uses them and does not duplicate its movement or load changes.

## File responsibilities

| File | Responsibility |
| --- | --- |
| `crates/base/src/dock/geometry.rs` | PanelExtent and pure recursive geometry measurement. |
| `crates/base/src/dock/geometry_tests.rs` | Counterexamples for collapse, stale sizes, hidden panels, and minimum extents. |
| `crates/base/src/dock/panel.rs` | Optional geometry hook and object-safe forwarding. |
| `crates/base/src/dock/dock_area.rs` | Separate-panel rendering, center canvas extent, and cache refresh. |
| `crates/base/src/dock/mod.rs` | Module registration and public geometry type. |
| `crates/ui/src/dock/panel.rs` | Forward geometry through PanelHandle. |
| `crates/ui/src/dock/mod.rs` | Re-export PanelExtent for application consumers. |

## Public contract and ordering

- `PanelExtent::new(minimum, preferred)` includes the header in both sizes. `collapsed(header_height)` returns an extent with a fixed header-only height; it does not mutate the application's retained expanded dimensions.
- `BasePanel::dock_extent(&self, &App) -> Option<PanelExtent>` defaults to `None`. The separate-panel path supplies a 100×100 minimum and 400×280 preference for an unspecified panel. Application panels supply their own 320×220 minimum and model preference; collapsed headers are 36 pixels high.
- `DockArea::content_extent(&self, &App) -> Size<Pixels>` reports the **center** arrangement. The product uses that center exclusively; optional side docks are outside its layout composition.
- `DockArea::refresh_geometry(&mut self, &mut Window, &mut Context<Self>)` applies explicit collapse/expand/restoration changes to both tree sizes and the cached ResizableState. Capture the measured dimensions of **all expanded panels** first so an unrelated neighbor retains its user-resized dimensions.
- Call refresh after constructing the default arrangement, restoring a layout, or changing panel collapse. Do not call it on every reading or ordinary divider drag. The existing resize subscription retains the user's sizes for those paths.
- A collapsed panel next to a taller sibling has a header-only view; that sibling may still determine the shared row height. Collapsing does not turn a split tree into a masonry layout.
- The application must store expanded dimensions separately from the dumped dock tree: the tree correctly records the current collapsed layout. Plan 02 owns those retained dimensions.

## Task 1: Add regression tests before the geometry implementation

**Files:** Create `crates/base/src/dock/geometry_tests.rs`; modify `crates/base/src/dock/mod.rs`.

- [ ] **Step 1: Create the test file with this complete content.**

```rust
use gpui::{Axis, px, size};

use super::geometry::{PanelExtent, measure_node};
use super::{NodeId, PaneNode, PanelId, layout::NodeKind};

fn leaf(id: u64) -> PaneNode {
    PaneNode::new(
        NodeId::from_u64(id),
        NodeKind::Tabs {
            panels: vec![PanelId::from_u64(id)],
            active_ix: 0,
        },
    )
}

fn column() -> PaneNode {
    PaneNode::new(
        NodeId::from_u64(10),
        NodeKind::Split {
            axis: Axis::Vertical,
            children: vec![leaf(1), leaf(2)],
            sizes: vec![Some(px(480.)), Some(px(280.))],
        },
    )
}

fn expanded() -> PanelExtent {
    PanelExtent::new(size(px(320.), px(220.)), size(px(420.), px(280.)))
}

#[test]
fn collapse_releases_height_without_overwriting_expanded_preference() {
    let source = expanded();
    let collapsed = source.collapsed(px(36.));
    assert_eq!(source.preferred().height, px(280.));
    assert_eq!(collapsed.minimum().height, px(36.));
    assert_eq!(collapsed.preferred().height, px(36.));
    assert_eq!(collapsed.height_limit(), Some(px(36.)));
}

#[test]
fn stale_saved_split_height_cannot_expand_a_collapsed_panel() {
    let measured = measure_node(
        &column(),
        &|id| {
            Some(if id.as_u64() == 1 {
                expanded().collapsed(px(36.))
            } else {
                expanded()
            })
        },
        true,
    )
    .unwrap();
    assert_eq!(measured.extent.preferred(), size(px(420.), px(316.)));
    assert_eq!(measured.extent.minimum(), size(px(320.), px(256.)));
}

#[test]
fn explicit_expansion_reseeds_from_retained_preferences() {
    let preferred = measure_node(&column(), &|_| Some(expanded()), false).unwrap();
    let saved = measure_node(&column(), &|_| Some(expanded()), true).unwrap();
    assert_eq!(preferred.extent.preferred().height, px(560.));
    assert_eq!(saved.extent.preferred().height, px(760.));
}

#[test]
fn hidden_panel_has_no_slot_but_collapsed_panel_retains_header() {
    let measured = measure_node(
        &column(),
        &|id| (id.as_u64() == 1).then(|| expanded().collapsed(px(36.))),
        false,
    )
    .unwrap();
    assert_eq!(measured.children.len(), 1);
    assert_eq!(measured.extent.preferred().height, px(36.));
    assert_eq!(measured.extent.height_limit(), Some(px(36.)));
}

#[test]
fn horizontal_sibling_does_not_force_collapsed_body_to_request_height() {
    let row = PaneNode::new(
        NodeId::from_u64(11),
        NodeKind::Split {
            axis: Axis::Horizontal,
            children: vec![leaf(1), leaf(2)],
            sizes: vec![None, None],
        },
    );
    let measured = measure_node(
        &row,
        &|id| {
            Some(if id.as_u64() == 1 {
                expanded().collapsed(px(36.))
            } else {
                expanded()
            })
        },
        false,
    )
    .unwrap();
    assert_eq!(measured.extent.preferred(), size(px(840.), px(280.)));
    assert_eq!(
        measured
            .find(NodeId::from_u64(1))
            .unwrap()
            .extent
            .height_limit(),
        Some(px(36.))
    );
    assert_eq!(measured.extent.height_limit(), None);
}

#[test]
fn saved_sizes_never_compress_panels_below_readable_minimum() {
    let root = PaneNode::new(
        NodeId::from_u64(12),
        NodeKind::Split {
            axis: Axis::Vertical,
            children: vec![leaf(1)],
            sizes: vec![Some(px(8.))],
        },
    );
    let measured = measure_node(&root, &|_| Some(expanded()), true).unwrap();
    assert_eq!(measured.extent.preferred().height, px(220.));
}
```

- [ ] **Step 2: Append this test-module registration to `crates/base/src/dock/mod.rs`.**

```rust
#[cfg(test)]
mod geometry_tests;
```

- [ ] **Step 3: Run the targeted tests and confirm the missing geometry module is the failure.**

```sh
rtk cargo test -p gpui-base --lib dock::geometry_tests
```

Expected before implementation: compilation fails because `super::geometry` does not exist. A toolchain, native-library, or dependency-download failure is an environment failure, not this expected test failure.

## Task 2: Implement the geometry hook, measurement, and render path

**Files:** All seven files listed above; Task 1's test file remains unchanged.

- [ ] **Step 1: Save this complete diff as `/tmp/system-pulse-dock-geometry.patch`.** It applies to the pinned source after plan 01; retain the test-module registration from Task 1.

```diff
--- a/crates/base/src/dock/mod.rs
+++ b/crates/base/src/dock/mod.rs
@@ -169,6 +169,9 @@
 //! `crates/ui/src/dock` is the production skin over the same seam.

 mod active;
+mod geometry;
+pub use geometry::PanelExtent;
+
 mod dock_area;
 mod dock_placement;
 mod drag;
--- a/crates/base/src/dock/panel.rs
+++ b/crates/base/src/dock/panel.rs
@@ -21,6 +21,11 @@
 pub trait Panel: EventEmitter<PanelEvent> + Render + Focusable {
     /// Identifies the panel in persisted layouts. Once chosen, never change it.
     fn panel_name(&self) -> &'static str;
+
+    /// Optional geometry for a separate-panel workspace.
+    fn dock_extent(&self, _cx: &App) -> Option<super::PanelExtent> {
+        None
+    }

     /// Whether the panel is drawn at all. A hidden panel keeps its place in
     /// the layout tree and its tab, and reappears when this turns back on;
@@ -98,6 +103,9 @@
 pub trait PanelView: 'static + Send + Sync {
     fn panel_name(&self, cx: &App) -> &'static str;
     fn panel_id(&self, cx: &App) -> PanelId;
+    fn dock_extent(&self, _cx: &App) -> Option<super::PanelExtent> {
+        None
+    }
     fn closable(&self, cx: &App) -> bool;
     fn zoomable(&self, cx: &App) -> bool;
     fn visible(&self, cx: &App) -> bool;
@@ -132,6 +140,10 @@
 }

 impl<T: Panel> PanelView for Entity<T> {
+    fn dock_extent(&self, cx: &App) -> Option<super::PanelExtent> {
+        self.read(cx).dock_extent(cx)
+    }
+
     fn panel_name(&self, cx: &App) -> &'static str {
         self.read(cx).panel_name()
     }
--- a/crates/base/src/dock/dock_area.rs
+++ b/crates/base/src/dock/dock_area.rs
@@ -1603,6 +1603,12 @@
 impl DockArea {
     /// Lower one container to an element.
     fn render_node(&self, node: &PaneNode, window: &mut Window, cx: &mut App) -> AnyElement {
+        if self.panel_policy == super::PanelPolicy::Separate {
+            return match self.measure_geometry(node, cx, true) {
+                Some(measured) => self.render_geometry_node(node, &measured, window, cx),
+                None => Empty.into_any_element(),
+            };
+        }
         match node.kind() {
             PaneRef::Split {
                 axis,
@@ -4680,3 +4686,183 @@
 #[cfg(test)]
 #[path = "separate_panels_tests.rs"]
 mod separate_panels_tests;
+
+impl DockArea {
+    /// The size needed by this separate-panel center, before viewport growth.
+    /// Applications put the area in a scroll container of at least this size.
+    pub fn content_extent(&self, cx: &App) -> gpui::Size<Pixels> {
+        if self.panel_policy != super::PanelPolicy::Separate {
+            return self.bounds.size;
+        }
+        self.measure_geometry(self.center.root(), cx, true)
+            .map(|node| node.extent.preferred())
+            .unwrap_or_else(|| gpui::size(px(0.), px(0.)))
+    }
+
+    fn measure_geometry(
+        &self,
+        node: &PaneNode,
+        cx: &App,
+        honor_sizes: bool,
+    ) -> Option<super::geometry::MeasuredNode> {
+        super::geometry::measure_node(
+            node,
+            &|id| {
+                let panel = self.panels.get(&id)?;
+                if !panel.visible(cx) {
+                    return None;
+                }
+                Some(panel.dock_extent(cx).unwrap_or_else(|| {
+                    super::PanelExtent::new(
+                        gpui::size(PANEL_MIN_SIZE, PANEL_MIN_SIZE),
+                        gpui::size(px(400.), px(280.)),
+                    )
+                }))
+            },
+            honor_sizes,
+        )
+    }
+
+    /// Apply an explicit presentation change. Before calling, the application
+    /// captures measured sizes of expanded panels into its presentation model.
+    /// Ordinary divider drags do not call this: their cache/tree sizes prevail.
+    pub fn refresh_geometry(&mut self, _window: &mut Window, cx: &mut Context<Self>) {
+        if self.panel_policy != super::PanelPolicy::Separate {
+            return;
+        }
+        let mut updates = Vec::new();
+        for placement in [
+            DockPlacement::Center,
+            DockPlacement::Left,
+            DockPlacement::Right,
+            DockPlacement::Bottom,
+        ] {
+            let Some(tree) = self.layout(placement) else {
+                continue;
+            };
+            let measured = self.measure_geometry(tree.root(), cx, false);
+            tree.root().walk(&mut |node| {
+                let PaneRef::Split { axis, children, .. } = node.kind() else {
+                    return;
+                };
+                let sizes = children
+                    .iter()
+                    .map(|child| {
+                        let value = measured.as_ref().and_then(|root| root.find(child.id()));
+                        Some(
+                            value
+                                .map(|child| match axis {
+                                    Axis::Horizontal => child.extent.preferred().width,
+                                    Axis::Vertical => child.extent.preferred().height,
+                                })
+                                .unwrap_or(px(0.)),
+                        )
+                    })
+                    .collect::<Vec<_>>();
+                updates.push((placement, node.id(), axis, sizes));
+            });
+        }
+        let mut changed = false;
+        for (placement, node, axis, sizes) in updates {
+            if let Some(tree) = self.tree_mut(placement) {
+                changed |= tree.set_sizes(node, sizes.clone()).changed();
+            }
+            if let Some(cached) = self.splits.get(&node) {
+                cached.entity.update(cx, |state, cx| {
+                    state.sync_panels_count(axis, sizes.len(), cx);
+                    state.adopt_sizes(&sizes, cx);
+                });
+            }
+        }
+        if changed {
+            cx.emit(DockEvent::LayoutChanged);
+        }
+        cx.notify();
+    }
+
+    fn render_geometry_node(
+        &self,
+        node: &PaneNode,
+        measured: &super::geometry::MeasuredNode,
+        window: &mut Window,
+        cx: &mut App,
+    ) -> AnyElement {
+        match node.kind() {
+            PaneRef::Split { axis, children, .. } => {
+                let grows = children.iter().rposition(|child| {
+                    measured.find(child.id()).is_some_and(|child| {
+                        axis == Axis::Horizontal || child.extent.height_limit().is_none()
+                    })
+                });
+                let mut panels = Vec::with_capacity(children.len());
+                for (ix, child) in children.iter().enumerate() {
+                    let Some(child_geometry) = measured.find(child.id()) else {
+                        panels.push(resizable_panel().visible(false));
+                        continue;
+                    };
+                    let extent = child_geometry.extent;
+                    let (minimum, preferred, maximum) = match axis {
+                        Axis::Horizontal => (
+                            extent.minimum().width,
+                            extent.preferred().width,
+                            Pixels::MAX,
+                        ),
+                        Axis::Vertical => (
+                            extent.minimum().height,
+                            extent.preferred().height,
+                            extent.height_limit().unwrap_or(Pixels::MAX),
+                        ),
+                    };
+                    panels.push(
+                        resizable_panel()
+                            .size(preferred)
+                            .size_range(minimum..maximum)
+                            .when(Some(ix) != grows, |panel| panel.flex_none())
+                            .child(self.render_geometry_node(child, child_geometry, window, cx)),
+                    );
+                }
+                let group = match axis {
+                    Axis::Horizontal => h_resizable(("dock-split", node.id().as_u64())),
+                    Axis::Vertical => v_resizable(("dock-split", node.id().as_u64())),
+                }
+                .when_some(self.splits.get(&node.id()), |group, cached| {
+                    group.with_state(&cached.entity)
+                })
+                .with_handle_appearance({
+                    let renderer = self.renderer.clone();
+                    Rc::new(move |handle, window, cx| {
+                        renderer.render_split_handle(handle, window, cx)
+                    })
+                })
+                .children(panels);
+                self.renderer
+                    .split_frame(node.id(), axis, window, cx)
+                    .size_full()
+                    .min_w(measured.extent.minimum().width)
+                    .min_h(measured.extent.minimum().height)
+                    .when_some(measured.extent.height_limit(), |frame, height| {
+                        frame.h(height).max_h(height)
+                    })
+                    .overflow_hidden()
+                    .child(group)
+                    .into_any_element()
+            }
+            PaneRef::Tabs { .. } => {
+                let Some(group) = self.groups.get(&node.id()) else {
+                    return Empty.into_any_element();
+                };
+                div()
+                    .w_full()
+                    .h_full()
+                    .min_w(measured.extent.minimum().width)
+                    .min_h(measured.extent.minimum().height)
+                    .when_some(measured.extent.height_limit(), |frame, height| {
+                        frame.h(height).max_h(height)
+                    })
+                    .child(group.entity.clone())
+                    .into_any_element()
+            }
+            PaneRef::Tiles { .. } => Empty.into_any_element(),
+        }
+    }
+}
--- /dev/null
+++ b/crates/base/src/dock/geometry.rs
@@ -0,0 +1,145 @@
+use gpui::{Axis, Pixels, Size, px, size};
+
+use super::{NodeId, PaneNode, PaneRef, PanelId};
+
+/// Application-supplied geometry for a separate dock panel.
+/// Both dimensions include the panel header.
+#[derive(Clone, Copy, Debug, PartialEq)]
+pub struct PanelExtent {
+    minimum: Size<Pixels>,
+    preferred: Size<Pixels>,
+    height_limit: Option<Pixels>,
+}
+
+impl PanelExtent {
+    pub fn new(minimum: Size<Pixels>, preferred: Size<Pixels>) -> Self {
+        let minimum = size(minimum.width.max(px(1.)), minimum.height.max(px(1.)));
+        Self {
+            minimum,
+            preferred: size(
+                preferred.width.max(minimum.width),
+                preferred.height.max(minimum.height),
+            ),
+            height_limit: None,
+        }
+    }
+
+    pub fn collapsed(mut self, header_height: Pixels) -> Self {
+        let height = header_height.max(px(1.));
+        self.minimum.height = height;
+        self.preferred.height = height;
+        self.height_limit = Some(height);
+        self
+    }
+
+    pub fn minimum(&self) -> Size<Pixels> {
+        self.minimum
+    }
+
+    pub fn preferred(&self) -> Size<Pixels> {
+        self.preferred
+    }
+
+    pub fn height_limit(&self) -> Option<Pixels> {
+        self.height_limit
+    }
+}
+
+pub(crate) struct MeasuredNode {
+    pub(crate) id: NodeId,
+    pub(crate) extent: PanelExtent,
+    pub(crate) children: Vec<MeasuredNode>,
+}
+
+impl MeasuredNode {
+    pub(crate) fn find(&self, id: NodeId) -> Option<&Self> {
+        if self.id == id {
+            return Some(self);
+        }
+        self.children.iter().find_map(|child| child.find(id))
+    }
+}
+
+/// `None` from `panel` means hidden or absent, not a zero-size live panel.
+/// Call with `honor_sizes=false` only for an explicit presentation change.
+pub(crate) fn measure_node(
+    node: &PaneNode,
+    panel: &impl Fn(PanelId) -> Option<PanelExtent>,
+    honor_sizes: bool,
+) -> Option<MeasuredNode> {
+    match node.kind() {
+        PaneRef::Tabs { panels, .. } => {
+            let extent = panels.iter().find_map(|id| panel(*id))?;
+            Some(MeasuredNode {
+                id: node.id(),
+                extent,
+                children: vec![],
+            })
+        }
+        PaneRef::Tiles { .. } => None,
+        PaneRef::Split {
+            axis,
+            children,
+            sizes,
+        } => {
+            let mut measured = Vec::new();
+            for (index, child) in children.iter().enumerate() {
+                let Some(mut child) = measure_node(child, panel, honor_sizes) else {
+                    continue;
+                };
+                if honor_sizes {
+                    if let Some(Some(saved)) = sizes.get(index) {
+                        match axis {
+                            Axis::Horizontal => {
+                                child.extent.preferred.width =
+                                    (*saved).max(child.extent.minimum.width);
+                            }
+                            Axis::Vertical => {
+                                child.extent.preferred.height = (*saved)
+                                    .max(child.extent.minimum.height)
+                                    .min(child.extent.height_limit.unwrap_or(Pixels::MAX));
+                            }
+                        }
+                    }
+                }
+                measured.push(child);
+            }
+            if measured.is_empty() {
+                return None;
+            }
+            let mut minimum = size(px(0.), px(0.));
+            let mut preferred = minimum;
+            let mut all_height_limited = true;
+            let mut height_limit = px(0.);
+            for child in &measured {
+                let extent = child.extent;
+                match axis {
+                    Axis::Horizontal => {
+                        minimum.width += extent.minimum.width;
+                        minimum.height = minimum.height.max(extent.minimum.height);
+                        preferred.width += extent.preferred.width;
+                        preferred.height = preferred.height.max(extent.preferred.height);
+                        height_limit = height_limit.max(extent.height_limit.unwrap_or(px(0.)));
+                    }
+                    Axis::Vertical => {
+                        minimum.width = minimum.width.max(extent.minimum.width);
+                        minimum.height += extent.minimum.height;
+                        preferred.width = preferred.width.max(extent.preferred.width);
+                        preferred.height += extent.preferred.height;
+                        height_limit += extent.height_limit.unwrap_or(px(0.));
+                    }
+                }
+                all_height_limited &= extent.height_limit.is_some();
+            }
+            Some(MeasuredNode {
+                id: node.id(),
+                extent: PanelExtent {
+                    minimum,
+                    preferred,
+                    height_limit: all_height_limited.then_some(height_limit),
+                },
+                children: measured,
+            })
+        }
+    }
+}
--- a/crates/ui/src/dock/mod.rs
+++ b/crates/ui/src/dock/mod.rs
@@ -33,6 +33,7 @@
 /// alongside [`Panel`]. Exported under this name because `Panel` in this
 /// module is the presentation half that extends it.
 pub use gpui_base::dock::Panel as BasePanel;
+pub use gpui_base::dock::PanelExtent;
 /// The object-safe counterpart of [`BasePanel`], for the same reason.
 pub use gpui_base::dock::PanelView as BasePanelView;
 /// Everything [`gpui_base::dock`] exports, so a consumer never has to depend
--- a/crates/ui/src/dock/panel.rs
+++ b/crates/ui/src/dock/panel.rs
@@ -243,6 +243,10 @@
 }

 impl gpui_base::dock::PanelView for PanelHandle {
+    fn dock_extent(&self, cx: &App) -> Option<gpui_base::dock::PanelExtent> {
+        self.0.dock_extent(cx)
+    }
+
     fn panel_name(&self, cx: &App) -> &'static str {
         self.0.panel_name(cx)
     }
```

- [ ] **Step 2: Check and apply the patch.** If a hunk conflicts with plan 01, reconcile the documented additive changes against that plan; never discard its policy or transaction checks.

```sh
rtk proxy git apply --check /tmp/system-pulse-dock-geometry.patch
rtk proxy git apply /tmp/system-pulse-dock-geometry.patch
```

- [ ] **Step 3: Run the targeted geometry tests and both dock suites.**

```sh
rtk cargo test -p gpui-base --lib dock::geometry_tests
rtk cargo test -p gpui-base --lib dock::
rtk cargo test -p gpui-component --lib dock::
```

Expected: all six geometry tests pass; dock policy, existing dock behavior, and façade export coverage remain green. These commands also type-check the real GPUI APIs that the isolated planning harness cannot check.

- [ ] **Step 4: Format and lint the modified packages.**

```sh
rtk cargo fmt -p gpui-base -p gpui-component
rtk cargo clippy -p gpui-base -p gpui-component --all-targets -- -D warnings
rtk git diff --check
```

Expected: checks pass. Inspect formatting changes and exclude unrelated changes before staging.

- [ ] **Step 5: Commit the geometry change and tests.**

```sh
rtk git add crates/base/src/dock/geometry.rs crates/base/src/dock/geometry_tests.rs crates/base/src/dock/mod.rs crates/base/src/dock/panel.rs crates/base/src/dock/dock_area.rs crates/ui/src/dock/mod.rs crates/ui/src/dock/panel.rs
rtk git commit -m "feat(dock): support separate-panel geometry and collapse extents"
```

## Native acceptance remains in plan 04

The six tests prove geometry arithmetic and state preferences. They do not prove actual GPUI prepaint, divider behavior, or nested scrolling. Plan 04 must run the native scenarios from the approved spec: collapse/expand after resizing; a tall sibling beside a collapsed header; overflow in both axes; keyboard focus reveal; and restoration with mixed collapse states. Do not mark WV-02, WV-06, or WV-11 complete on the strength of these unit tests alone.

## Planning verification

The implementation diff passed `git apply --check` after the complete plan-01 patch on the pinned snapshot. The six combined framework files, new geometry module, and test/helper snippets passed rustfmt parsing and formatting checks. The six arithmetic tests passed in an isolated harness using the original PaneNode source and lightweight stand-ins for GPUI geometry types. That harness verifies the measurement logic; it is **not** a GPUI compilation or native runtime check. Full crate and native commands above are required during execution.
