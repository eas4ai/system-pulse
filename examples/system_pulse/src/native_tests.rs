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
        let view = cx.new(|cx| WorkspaceView::new_fixture(window, cx));
        workspace = Some(view.clone());
        gpui_component::Root::new(view, window, cx)
    });
    let view = workspace.unwrap();
    draw(cx);
    (view, cx)
}
fn draw(cx: &mut VisualTestContext) {
    for _ in 0..3 {
        cx.update(|window, cx| {
            window.simulate_next_frame(cx);
            window.draw(cx).clear(cx);
        });
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
    assert_eq!(cx.read(|cx| processes.read(cx).selected_index()), Some(499));
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

#[gpui::test]
fn accepting_recovered_layout_preserves_keyboard_reachability(cx: &mut TestAppContext) {
    let (view, cx) = harness(cx);
    command(&view, Command::SavePreset, cx);
    let mut invalid = default_dock();
    let second = invalid.center.children[1].children[0].clone();
    invalid.center.children[0].children.push(second);
    let raw = serde_json::json!({ "dock": invalid }).to_string();
    cx.update(|window, cx| view.update(cx, |this, cx| this.restore(&raw, window, cx)));
    draw(cx);
    command(&view, Command::PanelCollapse("cpu".into()), cx);
    command(&view, Command::Save, cx);
    command(&view, Command::RecallPreset, cx);
    let recover = cx.debug_bounds("workspace:recover").unwrap();
    cx.simulate_click(recover.center(), Modifiers::none());
    draw(cx);
    assert!(cx.debug_bounds("workspace:recover").is_none());
    assert!(cx.read(|cx| view.read(cx).shared.borrow().session.rejected.is_none()));
    let before = cx.read(|cx| view.read(cx).shared.borrow().scroll.offset());
    native_key("alt-pagedown", cx);
    draw(cx);
    assert!(
        cx.read(|cx| view.read(cx).shared.borrow().scroll.offset())
            .y
            < before.y,
        "recovery must keep workspace shortcuts reachable after its button disappears"
    );
    let focus_before_tab = cx.update(|window, cx| window.focused(cx));
    native_key("tab", cx);
    draw(cx);
    let focus_after_tab = cx.update(|window, cx| window.focused(cx));
    assert!(focus_after_tab.is_some());
    assert_ne!(
        focus_before_tab, focus_after_tab,
        "Tab must move focus after recovery"
    );
    let after_tab = cx.read(|cx| view.read(cx).shared.borrow().scroll.offset());
    native_key("alt-pagedown", cx);
    draw(cx);
    assert!(
        cx.read(|cx| view.read(cx).shared.borrow().scroll.offset())
            .y
            < after_tab.y,
        "Tab must retain the workspace keyboard path after recovery"
    );
}

#[gpui::test]
fn revisiting_offscreen_focus_reveals_both_axes_without_pinning_user_scroll(
    cx: &mut TestAppContext,
) {
    let (view, cx) = harness(cx);
    let dock = cx.read(|cx| view.read(cx).dock.clone());
    let nodes =
        cx.read(|cx| leaf_nodes(dock.read(cx).layout(DockPlacement::Center).unwrap().root()));
    cx.update(|window, cx| {
        dock.update(cx, |dock, cx| {
            dock.try_move_panel(
                nodes[1].1,
                InsertTarget::Split {
                    node: nodes[0].0,
                    placement: Placement::Left,
                    size: Some(px(2400.)),
                },
                window,
                cx,
            )
            .unwrap()
        })
    });
    draw(cx);
    let cpu = panel(&view, "cpu", cx);
    let settings = panel(&view, "settings", cx);
    for _ in 0..3 {
        cx.update(|window, cx| {
            cpu.read(cx).controls["collapse"]
                .handle
                .clone()
                .focus(window, cx)
        });
        draw(cx);
        let viewport = cx.debug_bounds("workspace-viewport").unwrap();
        let target = cx.debug_bounds("cpu:collapse").unwrap();
        assert!(
            target.left() >= viewport.left() && target.right() <= viewport.right(),
            "CPU focus must reveal horizontally: target={target:?}, viewport={viewport:?}"
        );
        assert!(
            target.top() >= viewport.top() && target.bottom() <= viewport.bottom(),
            "CPU focus must reveal vertically: target={target:?}, viewport={viewport:?}"
        );
        command(&view, Command::Scroll(100000., -100000.), cx);
        let away = cx.read(|cx| view.read(cx).shared.borrow().scroll.offset());
        let offscreen = cx.debug_bounds("cpu:collapse").unwrap();
        assert!(
            offscreen.left() >= viewport.right(),
            "test must scroll CPU offscreen horizontally"
        );
        assert!(
            offscreen.bottom() <= viewport.top(),
            "test must scroll CPU offscreen vertically"
        );
        command(&view, Command::Tick, cx);
        assert_eq!(
            cx.read(|cx| view.read(cx).shared.borrow().scroll.offset()),
            away,
            "an unchanged focused control must not pin user scrolling"
        );
        cx.update(|window, cx| {
            settings.read(cx).controls["collapse"]
                .handle
                .clone()
                .focus(window, cx)
        });
        draw(cx);
    }
}

#[gpui::test]
fn live_snapshot_discovery_refreshes_controls_and_keeps_explicit_state(cx: &mut TestAppContext) {
    let (view, cx) = harness(cx);
    let mut snapshot = system_pulse_collectors::Snapshot {
        sequence: 1,
        capture_finished_ns: 20_000_000_000,
        ..Default::default()
    };
    snapshot
        .monitors
        .push(system_pulse_collectors::MonitorDescriptor {
            id: "amdgpu:real-id".into(),
            title: "Actual GPU".into(),
            kind: system_pulse_collectors::MonitorKind::Gpu,
            summary_sensor_id: "amdgpu:real-id/usage".into(),
        });
    snapshot
        .sensors
        .push(system_pulse_collectors::SensorDescriptor {
            id: "amdgpu:real-id/usage".into(),
            monitor_id: "amdgpu:real-id".into(),
            title: "Usage".into(),
            kind: system_pulse_collectors::SensorKind::Percentage,
            unit: system_pulse_collectors::Unit::Percent,
            source: "test".into(),
            scope: "device".into(),
            scale: None,
        });
    snapshot.readings.push(system_pulse_collectors::Reading {
        sensor_id: "amdgpu:real-id/usage".into(),
        value: Some(75.),
        total: None,
        availability: system_pulse_collectors::Availability::Available,
        reason: None,
        observations: vec![],
    });
    cx.update(|window, cx| {
        view.update(cx, |this, cx| {
            this.accept_snapshot(snapshot.clone(), window, cx)
        })
    });
    draw(cx);
    let gpu = panel(&view, "amdgpu:real-id", cx);
    command(&view, Command::PanelCollapse("amdgpu:real-id".into()), cx);
    command(
        &view,
        Command::RowCollapse("amdgpu:real-id".into(), "amdgpu:real-id/usage".into()),
        cx,
    );
    snapshot.sequence = 2;
    snapshot.capture_finished_ns += 1_000_000_000;
    snapshot
        .sensors
        .push(system_pulse_collectors::SensorDescriptor {
            id: "amdgpu:real-id/temp".into(),
            title: "Temperature".into(),
            kind: system_pulse_collectors::SensorKind::Temperature,
            unit: system_pulse_collectors::Unit::Celsius,
            ..snapshot.sensors[0].clone()
        });
    cx.update(|window, cx| view.update(cx, |this, cx| this.accept_snapshot(snapshot, window, cx)));
    draw(cx);
    cx.read(|cx| {
        assert!(
            gpu.read(cx)
                .controls
                .contains_key("row:amdgpu:real-id/temp")
        );
        let data = view.read(cx).shared.borrow();
        assert!(data.session.workspace.panels["amdgpu:real-id"].collapsed);
        assert!(
            data.session.workspace.panels["amdgpu:real-id"].sensors["amdgpu:real-id/usage"]
                .collapsed
        );
        assert!(
            !data.session.workspace.panels["amdgpu:real-id"].sensors["amdgpu:real-id/temp"]
                .collapsed
        );
        assert_eq!(
            data.history
                .samples("amdgpu:real-id", "amdgpu:real-id/usage")
                .unwrap()
                .len(),
            2
        );
    });
}

#[gpui::test]
fn accepted_process_snapshots_preserve_identity_and_clear_removed_selection(
    cx: &mut TestAppContext,
) {
    use system_pulse_collectors::{Availability, ProcessIdentity, ProcessRow, Reading, Snapshot};

    let (view, cx) = harness(cx);
    let row = |pid, start_time_ticks| {
        let reading = Reading {
            sensor_id: "controlled-process-reading".into(),
            value: Some(1.),
            total: None,
            availability: Availability::Available,
            reason: None,
            observations: vec![],
        };
        ProcessRow {
            identity: ProcessIdentity {
                pid,
                start_time_ticks,
            },
            name: "controlled process".into(),
            user: Some("user".into()),
            user_reason: None,
            cpu_percent: reading.clone(),
            memory_bytes: reading.clone(),
            read_bytes_per_second: reading.clone(),
            write_bytes_per_second: reading.clone(),
            threads: reading,
        }
    };
    let first = row(7, 9);
    let survivor = row(8, 10);
    let replacement = row(8, 11);
    let mut snapshot = Snapshot {
        sequence: 1,
        capture_finished_ns: 20_000_000_000,
        processes: vec![first.clone(), survivor.clone()],
        ..Default::default()
    };
    let accept = |snapshot: Snapshot, cx: &mut VisualTestContext| {
        let sequence = snapshot.sequence;
        let expected: Vec<_> = snapshot
            .processes
            .iter()
            .map(|row| row.identity.clone())
            .collect();
        cx.update(|window, cx| {
            view.update(cx, |this, cx| this.accept_snapshot(snapshot, window, cx))
        });
        cx.read(|cx| {
            let data = view.read(cx).shared.borrow();
            assert_eq!(data.snapshot.as_ref().unwrap().sequence, sequence);
            assert_eq!(
                data.snapshot
                    .as_ref()
                    .unwrap()
                    .processes
                    .iter()
                    .map(|row| row.identity.clone())
                    .collect::<Vec<_>>(),
                expected,
            );
            assert_eq!(
                data.processes
                    .iter()
                    .map(|row| row.identity.clone())
                    .collect::<Vec<_>>(),
                expected
            );
        });
    };
    accept(snapshot.clone(), cx);
    draw(cx);
    let processes = panel(&view, "processes", cx);
    cx.update(|window, cx| {
        processes.read(cx).controls["table"]
            .handle
            .clone()
            .focus(window, cx)
    });
    native_key("home", cx);
    draw(cx);
    assert_eq!(
        cx.read(|cx| processes.read(cx).selected.clone()),
        Some(first.identity.clone())
    );

    snapshot.sequence += 1;
    snapshot.capture_finished_ns += 1_000_000_000;
    snapshot.processes.reverse();
    accept(snapshot.clone(), cx);
    // Inspect the actual model immediately after production acceptance, without
    // another key that could replace or clear a stale selection.
    assert_eq!(
        cx.read(|cx| processes.read(cx).selected.clone()),
        Some(first.identity.clone())
    );
    assert_eq!(cx.read(|cx| processes.read(cx).selected_index()), Some(1));

    snapshot.sequence += 1;
    snapshot.capture_finished_ns += 1_000_000_000;
    snapshot.processes = vec![survivor.clone()];
    accept(snapshot.clone(), cx);
    assert_eq!(cx.read(|cx| processes.read(cx).selected.clone()), None);

    draw(cx);
    native_key("home", cx);
    draw(cx);
    assert_eq!(
        cx.read(|cx| processes.read(cx).selected.clone()),
        Some(survivor.identity)
    );
    snapshot.sequence += 1;
    snapshot.capture_finished_ns += 1_000_000_000;
    snapshot.processes = vec![replacement, first];
    accept(snapshot, cx);
    assert_eq!(cx.read(|cx| processes.read(cx).selected.clone()), None);
}

#[gpui::test]
fn real_process_keyboard_bounds_follow_all_rows_and_identity(cx: &mut TestAppContext) {
    let (view, cx) = harness(cx);
    let rows: Vec<_> = (0..1205)
        .map(|index| crate::live::ProcessView {
            identity: system_pulse_collectors::ProcessIdentity {
                pid: index + 1,
                start_time_ticks: 55,
            },
            cells: vec![
                (index + 1).to_string(),
                "host process".into(),
                "200 %".into(),
                "4 KiB".into(),
                "Unavailable · Permission denied".into(),
                "2 KiB/s".into(),
                "4 count".into(),
                "user".into(),
            ],
        })
        .collect();
    cx.update(|_, cx| {
        view.update(cx, |this, cx| {
            this.shared.borrow_mut().processes = rows;
            cx.notify();
        })
    });
    let processes = panel(&view, "processes", cx);
    cx.update(|window, cx| {
        processes.read(cx).controls["table"]
            .handle
            .clone()
            .focus(window, cx)
    });
    draw(cx);
    native_key("end", cx);
    draw(cx);
    assert_eq!(
        cx.read(|cx| processes.read(cx).selected_index()),
        Some(1204)
    );
    assert!(cx.debug_bounds("process-row:1204").is_some());
    cx.update(|_, cx| {
        view.update(cx, |this, cx| {
            this.shared.borrow_mut().processes.reverse();
            cx.notify();
        })
    });
    assert_eq!(cx.read(|cx| processes.read(cx).selected_index()), Some(0));
    native_key("down", cx);
    draw(cx);
    assert_eq!(cx.read(|cx| processes.read(cx).selected_index()), Some(1));
    cx.update(|_, cx| {
        view.update(cx, |this, cx| {
            this.shared.borrow_mut().processes.clear();
            cx.notify();
        })
    });
    draw(cx);
    native_key("end", cx);
    draw(cx);
    assert_eq!(cx.read(|cx| processes.read(cx).selected_index()), None);
}

#[gpui::test]
fn process_accessibility_ids_follow_pid_and_start_time_through_reordering_and_reuse(
    cx: &mut TestAppContext,
) {
    let (_, cx) = harness(cx);
    cx.update(|window, cx| {
        for (index, start) in [(0, 91), (1204, 91), (0, 92)] {
            let process = crate::live::ProcessView {
                identity: system_pulse_collectors::ProcessIdentity {
                    pid: 53,
                    start_time_ticks: start,
                },
                cells: vec![
                    "53".into(),
                    "process".into(),
                    "42.0 %".into(),
                    "4 KiB".into(),
                    "1 KiB/s".into(),
                    "2 KiB/s".into(),
                    "2 count".into(),
                    "user".into(),
                ],
            };
            let row =
                crate::panel::process_row(&process, index, true, &crate::live::PROCESS_WIDTHS, cx);
            let mut node = gpui::accesskit::Node::new(gpui::Role::Row);
            row.render(window, cx)
                .into_element()
                .write_a11y_info(&mut node);
            assert_eq!(
                node.author_id(),
                Some(format!("process:53:{start}").as_str())
            );
            assert_eq!(node.row_index(), Some(index + 2));
            let cell = crate::panel::process_cell(&process, 2, 200.);
            let mut node = gpui::accesskit::Node::new(gpui::Role::Cell);
            cell.render(window, cx)
                .into_element()
                .write_a11y_info(&mut node);
            assert_eq!(
                node.author_id(),
                Some(format!("process:53:{start}:cell:2").as_str())
            );
            assert_eq!(node.label(), Some("42.0 %"));
        }
    });
}

#[gpui::test]
fn process_navigation_burst_repaints_once_after_all_movements(cx: &mut TestAppContext) {
    let (view, cx) = harness(cx);
    let processes = panel(&view, "processes", cx);
    cx.update(|window, cx| {
        processes.read(cx).controls["table"]
            .handle
            .clone()
            .focus(window, cx);
    });
    draw(cx);
    assert_eq!(cx.update(|window, cx| window.simulate_next_frame(cx)), 0);
    assert!(cx.debug_bounds("process-row:0").is_some());

    native_key("end", cx);
    for _ in 0..80 {
        native_key("up", cx);
    }
    for _ in 0..3 {
        native_key("down", cx);
    }
    native_key("right", cx);
    native_key("left", cx);
    assert_eq!(cx.read(|cx| processes.read(cx).selected_index()), Some(422));
    assert!(
        cx.debug_bounds("process-row:0").is_some(),
        "queued navigation must not redraw before the next frame"
    );
    assert_eq!(cx.update(|window, cx| window.simulate_next_frame(cx)), 1);
    draw(cx);
    assert!(cx.debug_bounds("process-row:422").is_some());
    assert_eq!(cx.update(|window, cx| window.simulate_next_frame(cx)), 0);

    for (key, expected) in [
        ("home", 0),
        ("up", 0),
        ("down", 1),
        ("end", 499),
        ("down", 499),
        ("up", 498),
    ] {
        native_key(key, cx);
        assert_eq!(
            cx.read(|cx| processes.read(cx).selected_index()),
            Some(expected)
        );
    }
    assert_eq!(cx.read(|cx| processes.read(cx).selected_index()), Some(498));
    assert_eq!(cx.update(|window, cx| window.simulate_next_frame(cx)), 1);
    draw(cx);
    assert!(cx.debug_bounds("process-row:498").is_some());
    assert_eq!(cx.update(|window, cx| window.simulate_next_frame(cx)), 0);
}

fn pending_reveal_snapshot() -> system_pulse_collectors::Snapshot {
    use system_pulse_collectors::{Availability, ProcessIdentity, ProcessRow, Reading, Snapshot};
    let reading = Reading {
        sensor_id: "controlled-process-reading".into(),
        value: Some(1.),
        total: None,
        availability: Availability::Available,
        reason: None,
        observations: vec![],
    };
    Snapshot {
        sequence: 1,
        capture_finished_ns: 20_000_000_000,
        processes: (0..1300)
            .map(|index| ProcessRow {
                identity: ProcessIdentity {
                    pid: index + 1,
                    start_time_ticks: 1,
                },
                name: format!("controlled process {index}"),
                user: Some("user".into()),
                user_reason: None,
                cpu_percent: reading.clone(),
                memory_bytes: reading.clone(),
                read_bytes_per_second: reading.clone(),
                write_bytes_per_second: reading.clone(),
                threads: reading.clone(),
            })
            .collect(),
        ..Default::default()
    }
}

fn accept_pending_reveal_snapshot(
    view: &Entity<WorkspaceView>,
    snapshot: &mut system_pulse_collectors::Snapshot,
    cx: &mut VisualTestContext,
) {
    snapshot.sequence += 1;
    snapshot.capture_finished_ns += 1_000_000_000;
    cx.update(|window, cx| {
        view.update(cx, |this, cx| {
            this.accept_snapshot(snapshot.clone(), window, cx)
        })
    });
    cx.read(|cx| {
        let data = view.read(cx).shared.borrow();
        assert_eq!(data.snapshot.as_ref().unwrap().sequence, snapshot.sequence);
        assert_eq!(
            data.processes
                .iter()
                .map(|row| &row.identity)
                .collect::<Vec<_>>(),
            snapshot
                .processes
                .iter()
                .map(|row| &row.identity)
                .collect::<Vec<_>>()
        );
    });
}

fn assert_selected_process_in_viewport(
    processes: &Entity<MonitorPanel>,
    identity: &system_pulse_collectors::ProcessIdentity,
    index: usize,
    selector: &'static str,
    cx: &mut VisualTestContext,
) {
    assert_eq!(
        cx.read(|cx| processes.read(cx).selected.clone()).as_ref(),
        Some(identity)
    );
    assert_eq!(
        cx.read(|cx| processes.read(cx).selected_index()),
        Some(index)
    );
    let row = cx.debug_bounds(selector).unwrap_or_else(|| {
        panic!("selected process {identity:?} at index {index} must be instantiated after pending reveal")
    });
    let viewport = cx.debug_bounds("process-table").unwrap();
    // The rendered table has a one-pixel border and one h_7 header; its
    // process rows also use h_7. Exclude both from the vertical row viewport.
    assert!(
        row.top() >= viewport.top() + px(1.) + row.size.height
            && row.bottom() <= viewport.bottom() - px(1.),
        "selected process row {row:?} must be inside viewport {viewport:?}"
    );
}

fn process_pending_reveal_snapshot_interleaving(cx: &mut TestAppContext, restore_order: bool) {
    let (view, cx) = harness(cx);
    let mut snapshot = pending_reveal_snapshot();
    let original = snapshot.processes.clone();
    let selected_a = original[1221].identity.clone();
    let selected_b = original[1219].identity.clone();
    accept_pending_reveal_snapshot(&view, &mut snapshot, cx);
    let processes = panel(&view, "processes", cx);
    cx.update(|window, cx| {
        processes.read(cx).controls["table"]
            .handle
            .clone()
            .focus(window, cx);
    });
    draw(cx);
    native_key("end", cx);
    // Approach A from below so it starts at the top of the virtual viewport,
    // matching the retained failure's instantiated span of 1221–1229.
    draw(cx);
    for _ in 0..78 {
        native_key("up", cx);
    }
    draw(cx);
    assert_selected_process_in_viewport(&processes, &selected_a, 1221, "process-row:1221", cx);
    assert!(cx.debug_bounds("process-row:1219").is_none());
    let row = cx.debug_bounds("process-row:1221").unwrap();
    let table = cx.debug_bounds("process-table").unwrap();
    assert_eq!(row.top(), table.top() + px(1.) + row.size.height);
    assert_eq!(cx.update(|window, cx| window.simulate_next_frame(cx)), 0);

    let mut inserted = original[..2].to_vec();
    for row in &mut inserted {
        row.identity.pid += 10_000;
    }
    snapshot.processes.splice(0..0, inserted);
    accept_pending_reveal_snapshot(&view, &mut snapshot, cx);
    // Accept first, then draw that publication so key dispatch itself cannot
    // flush a dirty snapshot between the two coalesced movements.
    draw(cx);
    assert_eq!(
        cx.read(|cx| processes.read(cx).selected_index()),
        Some(1223)
    );
    native_key("up", cx);
    native_key("up", cx);
    assert_eq!(
        cx.read(|cx| processes.read(cx).selected.clone()),
        Some(selected_b.clone())
    );
    assert_eq!(
        cx.read(|cx| processes.read(cx).selected_index()),
        Some(1221)
    );
    if restore_order {
        snapshot.processes = original;
    }
    accept_pending_reveal_snapshot(&view, &mut snapshot, cx);
    let expected_index = if restore_order { 1219 } else { 1221 };
    assert_eq!(
        cx.read(|cx| processes.read(cx).selected_index()),
        Some(expected_index)
    );
    assert_eq!(cx.update(|window, cx| window.simulate_next_frame(cx)), 1);
    draw(cx);
    let selector = if restore_order {
        "process-row:1219"
    } else {
        "process-row:1221"
    };
    assert_selected_process_in_viewport(&processes, &selected_b, expected_index, selector, cx);
    assert_eq!(cx.update(|window, cx| window.simulate_next_frame(cx)), 0);
}

#[gpui::test]
fn process_pending_reveal_follows_identity_after_snapshot_reordering(cx: &mut TestAppContext) {
    process_pending_reveal_snapshot_interleaving(cx, true);
}

#[gpui::test]
fn process_pending_reveal_preserves_unchanged_snapshot_order(cx: &mut TestAppContext) {
    process_pending_reveal_snapshot_interleaving(cx, false);
}

#[gpui::test]
fn process_pending_reveal_is_consumed_before_manual_scroll_and_passive_snapshots(
    cx: &mut TestAppContext,
) {
    let (view, cx) = harness(cx);
    let mut snapshot = pending_reveal_snapshot();
    accept_pending_reveal_snapshot(&view, &mut snapshot, cx);
    let processes = panel(&view, "processes", cx);
    cx.update(|window, cx| {
        processes.read(cx).controls["table"]
            .handle
            .clone()
            .focus(window, cx);
    });
    draw(cx);
    native_key("end", cx);
    draw(cx);
    let selected = snapshot.processes[1299].identity.clone();
    assert_selected_process_in_viewport(&processes, &selected, 1299, "process-row:1299", cx);
    let table = cx.debug_bounds("process-table").unwrap();
    cx.simulate_event(ScrollWheelEvent {
        position: table.origin + point(px(30.), px(60.)),
        delta: ScrollDelta::Pixels(point(px(0.), px(400.))),
        ..Default::default()
    });
    draw(cx);
    assert!(
        cx.debug_bounds("process-row:1299").is_none(),
        "manual scrolling must leave selection offscreen"
    );
    let anchor = cx
        .debug_bounds("process-row:1280")
        .expect("wheel exposes an earlier row");

    snapshot.processes.rotate_right(1);
    accept_pending_reveal_snapshot(&view, &mut snapshot, cx);
    draw(cx);
    assert_eq!(
        cx.read(|cx| processes.read(cx).selected.clone()),
        Some(selected.clone())
    );
    assert_eq!(cx.read(|cx| processes.read(cx).selected_index()), Some(0));
    assert!(
        cx.debug_bounds("process-row:0").is_none(),
        "passive snapshots must not reveal the selected identity"
    );
    assert_eq!(cx.debug_bounds("process-row:1280"), Some(anchor));
    native_key("right", cx);
    draw(cx);
    assert_eq!(
        cx.debug_bounds("process-row:1280").unwrap().top(),
        anchor.top()
    );
    assert!(
        cx.debug_bounds("process-row:0").is_none(),
        "horizontal navigation must not create a vertical reveal"
    );
}

#[gpui::test]
fn process_pending_reveal_does_not_scroll_to_a_reused_pid(cx: &mut TestAppContext) {
    let (view, cx) = harness(cx);
    let mut snapshot = pending_reveal_snapshot();
    accept_pending_reveal_snapshot(&view, &mut snapshot, cx);
    let processes = panel(&view, "processes", cx);
    cx.update(|window, cx| {
        processes.read(cx).controls["table"]
            .handle
            .clone()
            .focus(window, cx);
    });
    draw(cx);
    native_key("home", cx);
    draw(cx);
    let initial = cx.debug_bounds("process-row:0").unwrap();
    native_key("end", cx);
    assert_eq!(
        cx.read(|cx| processes.read(cx).selected_index()),
        Some(1299)
    );
    snapshot.processes[1299].identity.start_time_ticks += 1;
    accept_pending_reveal_snapshot(&view, &mut snapshot, cx);
    assert_eq!(cx.read(|cx| processes.read(cx).selected.clone()), None);
    assert_eq!(cx.update(|window, cx| window.simulate_next_frame(cx)), 1);
    draw(cx);
    assert_eq!(
        cx.debug_bounds("process-row:0"),
        Some(initial),
        "vanished selection must not scroll to its replacement"
    );
    assert!(cx.debug_bounds("process-row:1299").is_none());
    snapshot.processes[1299].identity.start_time_ticks -= 1;
    accept_pending_reveal_snapshot(&view, &mut snapshot, cx);
    draw(cx);
    assert_eq!(cx.read(|cx| processes.read(cx).selected.clone()), None);
    assert_eq!(cx.debug_bounds("process-row:0"), Some(initial));
    native_key("down", cx);
    draw(cx);
    assert_selected_process_in_viewport(
        &processes,
        &snapshot.processes[0].identity,
        0,
        "process-row:0",
        cx,
    );
}

#[gpui::test]
fn process_horizontal_burst_accumulates_and_repaints_once(cx: &mut TestAppContext) {
    let (view, cx) = harness(cx);
    cx.update(|_, cx| {
        view.update(cx, |this, cx| {
            this.shared.borrow_mut().process_widths = [1000.; 8];
            cx.notify();
        });
    });
    let processes = panel(&view, "processes", cx);
    cx.update(|window, cx| {
        processes.read(cx).controls["table"]
            .handle
            .clone()
            .focus(window, cx);
    });
    draw(cx);
    let original = cx.debug_bounds("process-row:0").unwrap();
    for key in ["right", "right", "right", "left"] {
        native_key(key, cx);
    }
    assert_eq!(cx.update(|window, cx| window.simulate_next_frame(cx)), 1);
    draw(cx);
    assert_eq!(
        cx.debug_bounds("process-row:0").unwrap().left(),
        original.left() - px(480.)
    );
    for _ in 0..5 {
        native_key("left", cx);
    }
    assert_eq!(cx.update(|window, cx| window.simulate_next_frame(cx)), 1);
    draw(cx);
    assert_eq!(
        cx.debug_bounds("process-row:0").unwrap().left(),
        original.left()
    );
    assert_eq!(cx.update(|window, cx| window.simulate_next_frame(cx)), 0);
}

#[gpui::test]
fn outer_navigation_burst_accumulates_both_axes_and_repaints_once(cx: &mut TestAppContext) {
    let (view, cx) = harness(cx);
    let dock = cx.read(|cx| view.read(cx).dock.clone());
    let nodes =
        cx.read(|cx| leaf_nodes(dock.read(cx).layout(DockPlacement::Center).unwrap().root()));
    cx.update(|window, cx| {
        dock.update(cx, |dock, cx| {
            dock.try_move_panel(
                nodes[1].1,
                InsertTarget::Split {
                    node: nodes[0].0,
                    placement: Placement::Left,
                    size: Some(px(2400.)),
                },
                window,
                cx,
            )
            .unwrap();
        });
    });
    let processes = panel(&view, "processes", cx);
    cx.update(|window, cx| {
        processes.read(cx).controls["table"]
            .handle
            .clone()
            .focus(window, cx);
    });
    draw(cx);
    native_key("home", cx);
    draw(cx);
    let selected = cx
        .read(|cx| processes.read(cx).selected.clone())
        .expect("Home must establish a selected process identity before outer navigation");
    let scroll = cx.read(|cx| view.read(cx).shared.borrow().scroll.clone());
    assert!(scroll.max_offset().x > px(600.));
    assert!(scroll.max_offset().y > px(600.));
    let notifications = std::rc::Rc::new(std::cell::Cell::new(0));
    let observed = notifications.clone();
    let _subscription =
        cx.update(|_, cx| cx.observe(&view, move |_, _| observed.set(observed.get() + 1)));
    for _ in 0..2 {
        notifications.set(0);
        let mut expected = scroll.offset();
        for (key, dx, dy) in [
            ("alt-pageup", 0., 300.),
            ("alt-pageup", 0., 300.),
            ("alt-pagedown", 0., -300.),
            ("alt-right", -300., 0.),
            ("alt-right", -300., 0.),
            ("alt-left", 300., 0.),
        ] {
            expected.x = (expected.x + px(dx)).clamp(-scroll.max_offset().x, px(0.));
            expected.y = (expected.y + px(dy)).clamp(-scroll.max_offset().y, px(0.));
            native_key(key, cx);
            assert_eq!(
                cx.read(|cx| processes.read(cx).selected.clone()),
                Some(selected.clone()),
                "{key} must preserve the selected process identity"
            );
            assert_eq!(
                scroll.offset(),
                expected,
                "every key mutates the offset immediately"
            );
        }
        assert_eq!(
            notifications.get(),
            0,
            "queued Alt navigation must not dirty the view"
        );
        assert_eq!(cx.update(|window, cx| window.simulate_next_frame(cx)), 1);
        assert_eq!(
            cx.read(|cx| processes.read(cx).selected.clone()),
            Some(selected.clone()),
            "frame delivery must preserve the selected process identity"
        );
        assert_eq!(notifications.get(), 1);
        draw(cx);
        assert_eq!(
            cx.read(|cx| processes.read(cx).selected.clone()),
            Some(selected.clone()),
            "rendering outer movement must preserve the selected process identity"
        );
        assert_eq!(scroll.offset(), expected);
        assert_eq!(cx.update(|window, cx| window.simulate_next_frame(cx)), 0);
    }
}
