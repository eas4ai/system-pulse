use crate::{
    panel::MonitorPanel,
    workspace::{Command, WorkspaceView, default_dock},
};
use gpui::{
    AppContext, Axis, Element, Entity, IntoElement, KeyDownEvent, KeyUpEvent, Keystroke, Modifiers,
    MouseButton, RenderOnce, ScrollDelta, ScrollWheelEvent, TestAppContext, VisualTestContext,
    point, px,
};
use gpui_base::{Placement, dock::*};

fn harness(cx: &mut TestAppContext) -> (Entity<WorkspaceView>, &mut VisualTestContext) {
    cx.update(gpui_component::init);
    let mut workspace = None;
    let (_, cx) = cx.add_window_view(|window, cx| {
        let view = cx.new(|cx| WorkspaceView::new(false, window, cx));
        workspace = Some(view.clone());
        gpui_component::Root::new(view, window, cx)
    });
    let view = workspace.unwrap();
    draw(cx);
    (view, cx)
}
fn draw(cx: &mut VisualTestContext) {
    for _ in 0..3 {
        cx.update(|window, cx| window.draw(cx).clear(cx));
    }
}
fn command(view: &Entity<WorkspaceView>, cmd: Command, cx: &mut VisualTestContext) {
    cx.update(|window, cx| view.update(cx, |this, cx| this.command(cmd, window, cx)));
    draw(cx);
}
fn panel(view: &Entity<WorkspaceView>, id: &str, cx: &VisualTestContext) -> Entity<MonitorPanel> {
    cx.read(|cx| view.read(cx).shared.borrow().views[id].upgrade().unwrap())
}
fn leaf_nodes(node: &PaneNode) -> Vec<(NodeId, PanelId)> {
    match node.kind() {
        PaneRef::Tabs { panels, .. } => {
            assert_eq!(panels.len(), 1, "every region has exactly one monitor");
            vec![(node.id(), panels[0])]
        }
        PaneRef::Split { children, .. } => children.iter().flat_map(leaf_nodes).collect(),
        PaneRef::Tiles { .. } => panic!("fixture never installs tile layout"),
    }
}

#[gpui::test]
fn collapse_keeps_a_header_and_continuous_history(cx: &mut TestAppContext) {
    let (view, cx) = harness(cx);
    let before = cx.debug_bounds("panel:cpu").unwrap().size;
    command(
        &view,
        Command::RowCollapse("cpu".into(), "overall".into()),
        cx,
    );
    command(&view, Command::PanelCollapse("cpu".into()), cx);
    assert_eq!(cx.debug_bounds("panel:cpu").unwrap().size.height, px(36.));
    for _ in 0..9 {
        command(&view, Command::Tick, cx);
    }
    cx.read(|cx| {
        let shared = &view.read(cx).shared;
        let data = shared.borrow();
        let history = data.history.samples("cpu", "overall").unwrap();
        assert_eq!(history.len(), 10);
        assert_eq!(history.back().unwrap().at_ms, 10000);
        assert_eq!(
            history.iter().filter(|s| s.chart_value().is_none()).count(),
            2
        );
    });
    command(&view, Command::PanelCollapse("cpu".into()), cx);
    assert_eq!(
        cx.debug_bounds("panel:cpu").unwrap().size.height,
        before.height
    );
    assert!(cx.debug_bounds("cpu:meter-body:overall").is_none());
    command(&view, Command::Meter("cpu".into(), "overall".into()), cx);
    command(
        &view,
        Command::SensorVisible("cpu".into(), "overall".into()),
        cx,
    );
    command(
        &view,
        Command::SensorVisible("cpu".into(), "overall".into()),
        cx,
    );
    command(&view, Command::PanelVisible("cpu".into()), cx);
    command(&view, Command::PanelVisible("cpu".into()), cx);
    cx.read(|cx| {
        let data = view.read(cx).shared.borrow();
        let row = &data.session.workspace.panels["cpu"].sensors["overall"];
        assert!(row.collapsed);
        assert_eq!(row.meter, system_pulse_model::Meter::Bar);
        assert_eq!(data.history.samples("cpu", "overall").unwrap().len(), 10);
    });
}

#[gpui::test]
fn enter_and_space_toggle_without_moving_the_panel(cx: &mut TestAppContext) {
    let (view, cx) = harness(cx);
    let cpu = panel(&view, "cpu", cx);
    let before = cx.read(|cx| {
        let dock = &view.read(cx).dock;
        leaf_nodes(dock.read(cx).layout(DockPlacement::Center).unwrap().root())
    });
    cx.update(|window, cx| {
        cpu.read(cx).controls["collapse"]
            .handle
            .clone()
            .focus(window, cx)
    });
    draw(cx);
    native_key("enter", cx);
    draw(cx);
    assert_eq!(cx.debug_bounds("panel:cpu").unwrap().size.height, px(36.));
    native_key("space", cx);
    draw(cx);
    assert!(cx.debug_bounds("panel:cpu").unwrap().size.height >= px(220.));
    let after = cx.read(|cx| {
        leaf_nodes(
            view.read(cx)
                .dock
                .read(cx)
                .layout(DockPlacement::Center)
                .unwrap()
                .root(),
        )
    });
    assert_eq!(before, after);
    cx.update(|window, cx| {
        cpu.read(cx).controls["meter:overall"]
            .handle
            .clone()
            .focus(window, cx);
        view.update(cx, |this, cx| {
            this.command(Command::PanelCollapse("cpu".into()), window, cx)
        });
        assert!(cpu.read(cx).controls["collapse"].handle.is_focused(window));
    });
}

#[gpui::test]
fn workspace_and_long_table_are_independently_reachable(cx: &mut TestAppContext) {
    let (view, cx) = harness(cx);
    let viewport = cx.debug_bounds("workspace-viewport").unwrap();
    let extent = cx.read(|cx| view.read(cx).dock.read(cx).content_extent(cx));
    assert!(extent.height > viewport.size.height);
    command(&view, Command::Scroll(0., -100000.), cx);
    let settings = panel(&view, "settings", cx);
    cx.update(|window, cx| {
        settings.read(cx).controls["collapse"]
            .handle
            .clone()
            .focus(window, cx)
    });
    draw(cx);
    let target = cx.debug_bounds("settings:collapse").unwrap();
    assert!(target.top() >= viewport.top() && target.bottom() <= viewport.bottom());
    let processes = panel(&view, "processes", cx);
    cx.update(|window, cx| {
        processes.read(cx).controls["table"]
            .handle
            .clone()
            .focus(window, cx)
    });
    draw(cx);
    cx.simulate_keystrokes("end");
    draw(cx);
    assert_eq!(cx.read(|cx| processes.read(cx).selected), 499);
    assert!(cx.debug_bounds("process-row:499").is_some());
    assert!(
        cx.debug_bounds("process-row:0").is_none(),
        "rows are virtualized"
    );
    let before = cx.read(|cx| view.read(cx).shared.borrow().scroll.offset());
    command(&view, Command::Scroll(0., 300.), cx);
    let after = cx.read(|cx| view.read(cx).shared.borrow().scroll.offset());
    assert!(
        after.y > before.y,
        "workspace remains reachable while table retains focus"
    );
    cx.update(|window, cx| window.focus_next(cx));
    cx.update(|window, cx| {
        assert!(
            !processes.read(cx).controls["table"]
                .handle
                .is_focused(window)
        )
    });
}

#[gpui::test]
fn restore_preserves_identity_and_rejection_is_not_bypassed_by_preset(cx: &mut TestAppContext) {
    let (view, cx) = harness(cx);
    command(&view, Command::PanelCollapse("gpu:fixture-a".into()), cx);
    command(
        &view,
        Command::RowCollapse("cpu".into(), "overall".into()),
        cx,
    );
    command(&view, Command::SavePreset, cx);
    command(&view, Command::ReverseDiscovery, cx);
    command(&view, Command::ToggleGpu, cx);
    command(&view, Command::RecallPreset, cx);
    command(&view, Command::ToggleGpu, cx);
    assert_eq!(
        cx.debug_bounds("panel:gpu:fixture-a").unwrap().size.height,
        px(36.)
    );
    cx.read(|cx| {
        assert!(
            view.read(cx).shared.borrow().session.workspace.panels["cpu"].sensors["overall"]
                .collapsed
        )
    });
    let mut invalid = default_dock();
    let second = invalid.center.children[1].children[0].clone();
    invalid.center.children[0].children.push(second);
    let mut state = system_pulse_model::Workspace::new(serde_json::to_value(invalid).unwrap());
    crate::fixture::discover(&mut state, &crate::fixture::catalog());
    let raw = serde_json::to_string(&state).unwrap();
    cx.update(|window, cx| view.update(cx, |this, cx| this.restore(&raw, window, cx)));
    draw(cx);
    command(&view, Command::RecallPreset, cx);
    cx.read(|cx| {
        let data = view.read(cx).shared.borrow();
        assert_eq!(data.session.rejected.as_ref().unwrap().original, raw);
        assert!(data.session.autosave_json().is_err());
        leaf_nodes(
            view.read(cx)
                .dock
                .read(cx)
                .layout(DockPlacement::Center)
                .unwrap()
                .root(),
        );
    });
    command(&view, Command::Recover, cx);
    cx.read(|cx| {
        assert!(
            view.read(cx)
                .shared
                .borrow()
                .session
                .autosave_json()
                .is_ok()
        )
    });
}

#[gpui::test]
fn edge_move_is_accepted_and_merge_is_rejected_atomically(cx: &mut TestAppContext) {
    let (view, cx) = harness(cx);
    let dock = cx.read(|cx| view.read(cx).dock.clone());
    let nodes =
        cx.read(|cx| leaf_nodes(dock.read(cx).layout(DockPlacement::Center).unwrap().root()));
    let before = cx.read(|cx| dock.read(cx).dump(cx));
    cx.update(|window, cx| {
        dock.update(cx, |dock, cx| {
            assert!(
                dock.try_move_panel(
                    nodes[0].1,
                    InsertTarget::Tabs {
                        node: nodes[1].0,
                        ix: None,
                        activate: true
                    },
                    window,
                    cx
                )
                .is_err()
            );
        })
    });
    assert_eq!(cx.read(|cx| dock.read(cx).dump(cx)), before);
    cx.update(|window, cx| {
        dock.update(cx, |dock, cx| {
            dock.try_move_panel(
                nodes[0].1,
                InsertTarget::Split {
                    node: nodes[1].0,
                    placement: Placement::Right,
                    size: Some(px(420.)),
                },
                window,
                cx,
            )
            .unwrap();
        })
    });
    draw(cx);
    let after =
        cx.read(|cx| leaf_nodes(dock.read(cx).layout(DockPlacement::Center).unwrap().root()));
    assert_eq!(after.len(), nodes.len());
    assert_ne!(cx.read(|cx| dock.read(cx).dump(cx)), before);
}

#[gpui::test]
fn older_partial_layout_gets_regions_for_default_enabled_monitors(cx: &mut TestAppContext) {
    let (view, cx) = harness(cx);
    let mut dock = default_dock();
    dock.center.children.truncate(1);
    dock.center.info = PanelInfo::stack(vec![px(280.)], Axis::Vertical);
    let raw = serde_json::json!({ "dock": dock }).to_string();
    cx.update(|window, cx| view.update(cx, |this, cx| this.restore(&raw, window, cx)));
    draw(cx);
    cx.read(|cx| {
        let app = view.read(cx);
        let data = app.shared.borrow();
        assert!(data.session.rejected.is_none());
        let nodes = leaf_nodes(
            app.dock
                .read(cx)
                .layout(DockPlacement::Center)
                .unwrap()
                .root(),
        );
        assert_eq!(nodes.len(), data.catalog.len());
        assert!(
            data.session
                .workspace
                .panels
                .values()
                .all(|panel| panel.visible && !panel.collapsed)
        );
    });
}

#[gpui::test]
fn tab_enters_and_leaves_the_retained_process_table(cx: &mut TestAppContext) {
    let (view, cx) = harness(cx);
    let processes = panel(&view, "processes", cx);
    cx.update(|window, cx| {
        processes.read(cx).controls["close"]
            .handle
            .clone()
            .focus(window, cx)
    });
    draw(cx);
    cx.simulate_keystrokes("tab");
    draw(cx);
    cx.update(|window, cx| {
        assert!(
            processes.read(cx).controls["table"]
                .handle
                .is_focused(window),
            "Tab must enter the process table"
        )
    });
    cx.simulate_keystrokes("tab");
    draw(cx);
    cx.update(|window, cx| {
        assert!(
            !processes.read(cx).controls["table"]
                .handle
                .is_focused(window),
            "Tab must leave the process table"
        )
    });
}

fn native_key(key: &str, cx: &mut VisualTestContext) {
    let keystroke = Keystroke::parse(key).unwrap();
    cx.simulate_event(KeyDownEvent {
        keystroke: keystroke.clone(),
        is_held: false,
        prefer_character_input: false,
    });
    cx.simulate_event(KeyUpEvent { keystroke });
}

#[gpui::test]
fn divider_drag_snapshot_uses_latest_allocation_without_a_fixture_tick(cx: &mut TestAppContext) {
    let (view, cx) = harness(cx);
    let bounds = cx.debug_bounds("panel:cpu").unwrap();
    let start = point(bounds.left() + px(100.), bounds.bottom());
    cx.simulate_mouse_down(start, MouseButton::Left, Modifiers::none());
    cx.simulate_mouse_move(
        start + point(px(0.), px(10.)),
        MouseButton::Left,
        Modifiers::none(),
    );
    cx.simulate_mouse_move(
        start + point(px(0.), px(48.)),
        MouseButton::Left,
        Modifiers::none(),
    );
    cx.simulate_mouse_up(
        start + point(px(0.), px(48.)),
        MouseButton::Left,
        Modifiers::none(),
    );
    let saved = cx.read(|cx| view.read(cx).dock.read(cx).dump(cx));
    let PanelInfo::Stack { sizes, .. } = &saved.center.info else {
        panic!("vertical split")
    };
    assert!(
        sizes[0] > bounds.size.height,
        "native divider drag must resize CPU"
    );
    // Last rendered bounds may still describe the preceding frame at a quit callback.
    cx.update(|_, cx| {
        view.update(cx, |this, cx| {
            this.shared.borrow_mut().bounds.insert("cpu".into(), bounds);
            this.record(cx);
        })
    });
    let raw = cx.read(|cx| {
        let data = view.read(cx).shared.borrow();
        assert_eq!(
            data.session.workspace.panels["cpu"].expanded_size.height,
            sizes[0].as_f32(),
            "snapshot must use authoritative divider allocation"
        );
        data.session.autosave_json().unwrap()
    });
    cx.update(|window, cx| view.update(cx, |this, cx| this.restore(&raw, window, cx)));
    draw(cx);
    assert_eq!(cx.debug_bounds("panel:cpu").unwrap().size.height, sizes[0]);
    let extent = cx.read(|cx| view.read(cx).dock.read(cx).content_extent(cx));
    let scroll = cx.read(|cx| view.read(cx).shared.borrow().scroll.clone());
    assert_eq!(
        scroll.max_offset().y,
        (extent.height - scroll.bounds().size.height).max(px(0.)),
        "outer scroll extent updates without ticking"
    );
}

#[gpui::test]
fn collapsed_panel_beside_tall_neighbor_restores_its_region(cx: &mut TestAppContext) {
    let (view, cx) = harness(cx);
    let dock = cx.read(|cx| view.read(cx).dock.clone());
    let nodes =
        cx.read(|cx| leaf_nodes(dock.read(cx).layout(DockPlacement::Center).unwrap().root()));
    cx.update(|window, cx| {
        dock.update(cx, |dock, cx| {
            dock.try_move_panel(
                nodes[0].1,
                InsertTarget::Split {
                    node: nodes[1].0,
                    placement: Placement::Right,
                    size: Some(px(420.)),
                },
                window,
                cx,
            )
            .unwrap()
        })
    });
    draw(cx);
    let before = cx.debug_bounds("panel:cpu").unwrap();
    let topology =
        cx.read(|cx| leaf_nodes(dock.read(cx).layout(DockPlacement::Center).unwrap().root()));
    command(&view, Command::PanelCollapse("cpu".into()), cx);
    assert_eq!(cx.debug_bounds("panel:cpu").unwrap().size.height, px(36.));
    assert!(cx.debug_bounds("panel:gpu:fixture-a").unwrap().size.height >= px(220.));
    command(&view, Command::PanelCollapse("cpu".into()), cx);
    assert_eq!(cx.debug_bounds("panel:cpu").unwrap().size, before.size);
    assert_eq!(
        cx.read(|cx| leaf_nodes(dock.read(cx).layout(DockPlacement::Center).unwrap().root())),
        topology
    );
}

#[gpui::test]
fn wheel_routes_to_table_and_outer_canvas_independently(cx: &mut TestAppContext) {
    let (view, cx) = harness(cx);
    let processes = panel(&view, "processes", cx);
    cx.update(|window, cx| {
        processes.read(cx).controls["table"]
            .handle
            .clone()
            .focus(window, cx)
    });
    draw(cx);
    let table = cx.debug_bounds("process-table").unwrap();
    let position = table.origin + point(px(30.), px(30.));
    let before = cx.read(|cx| view.read(cx).shared.borrow().scroll.offset());
    cx.simulate_event(ScrollWheelEvent {
        position,
        delta: ScrollDelta::Pixels(point(px(0.), px(-400.))),
        ..Default::default()
    });
    draw(cx);
    assert!(
        cx.debug_bounds("process-row:0").is_none(),
        "wheel must scroll virtual rows"
    );
    assert_eq!(
        cx.read(|cx| view.read(cx).shared.borrow().scroll.offset()),
        before,
        "table consumes wheel while rows remain"
    );
    native_key("alt-pageup", cx);
    draw(cx);
    assert!(
        cx.read(|cx| view.read(cx).shared.borrow().scroll.offset())
            .y
            > before.y,
        "outer keyboard path works while table is focused"
    );
    command(&view, Command::Scroll(0., 100000.), cx);
    let header = cx.debug_bounds("cpu:collapse").unwrap();
    cx.simulate_event(ScrollWheelEvent {
        position: header.origin,
        delta: ScrollDelta::Pixels(point(px(0.), px(-200.))),
        ..Default::default()
    });
    draw(cx);
    assert!(
        cx.read(|cx| view.read(cx).shared.borrow().scroll.offset())
            .y
            < px(0.),
        "wheel outside table scrolls workspace"
    );
}

#[gpui::test]
fn disclosure_buttons_expose_expanded_state_and_click_action(cx: &mut TestAppContext) {
    let (view, cx) = harness(cx);
    let cpu = panel(&view, "cpu", cx);
    for expanded in [true, false] {
        cx.update(|window, cx| {
            let shared = view.read(cx).shared.clone();
            let focus = cpu.read(cx).controls["collapse"].clone();
            let control = crate::controls::button(
                "Collapse CPU".into(),
                Some(expanded),
                &focus,
                &shared,
                Command::PanelCollapse("cpu".into()),
                None,
                cx,
            );
            let mut node = gpui::accesskit::Node::new(gpui::Role::Button);
            control
                .render(window, cx)
                .into_element()
                .write_a11y_info(&mut node);
            assert_eq!(node.role(), gpui::Role::Button);
            assert_eq!(node.is_expanded(), Some(expanded));
            assert!(node.supports_action(gpui::AccessibleAction::Click));
        });
    }
}

#[gpui::test]
fn toolbar_focus_stays_with_monitor_identity_when_discovery_order_reverses(
    cx: &mut TestAppContext,
) {
    let (view, cx) = harness(cx);
    command(&view, Command::PanelVisible("cpu".into()), cx);
    let toolbar = cx.debug_bounds("workspace:visible:cpu").unwrap();
    cx.simulate_click(toolbar.center(), Modifiers::none());
    draw(cx);
    assert!(cx.read(|cx| view.read(cx).shared.borrow().session.workspace.panels["cpu"].visible));
    command(&view, Command::ReverseDiscovery, cx);
    native_key("space", cx);
    draw(cx);
    cx.read(|cx| {
        let data = view.read(cx).shared.borrow();
        assert!(
            !data.session.workspace.panels["cpu"].visible,
            "focused Hide CPU must stay attached to CPU after reverse discovery"
        );
        assert!(data.session.workspace.panels["settings"].visible);
    });
}
