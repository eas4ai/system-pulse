use crate::{
    native_tests::{draw, native_key},
    screens::{ApplicationView, ScreenView},
};
use gpui_kit::{AppContext, Entity, Modifiers, TestAppContext, VisualTestContext};
use system_pulse_model::Screen;

#[path = "screen_fixture.rs"]
mod fixture;

fn accept(
    view: &Entity<ScreenView>,
    snapshot: system_pulse_collectors::Snapshot,
    cx: &mut VisualTestContext,
) {
    let sequence = snapshot.sequence;
    cx.update(|window, cx| {
        let owner = view.read(cx).shared.borrow().owner.clone().unwrap();
        owner
            .update(cx, |owner, cx| owner.accept_snapshot(snapshot, window, cx))
            .unwrap();
    });
    draw(cx);
    cx.read(|cx| {
        assert_eq!(
            view.read(cx)
                .shared
                .borrow()
                .snapshot
                .as_ref()
                .unwrap()
                .sequence,
            sequence
        )
    });
}

fn command(
    view: &Entity<ScreenView>,
    command: crate::workspace::Command,
    cx: &mut VisualTestContext,
) {
    cx.update(|window, cx| {
        let owner = view.read(cx).shared.borrow().owner.clone().unwrap();
        owner
            .update(cx, |owner, cx| owner.command(command, window, cx))
            .unwrap();
    });
    draw(cx);
}

fn populated(cx: &mut TestAppContext) -> (Entity<ScreenView>, &mut VisualTestContext) {
    let (view, cx) = harness(cx);
    for sequence in 1..=5 {
        accept(&view, fixture::snapshot(sequence), cx);
    }
    (view, cx)
}

fn harness(cx: &mut TestAppContext) -> (Entity<ScreenView>, &mut VisualTestContext) {
    cx.update(gpui_kit::component::init);
    let mut screens = None;
    let (_, cx) = cx.add_window_view(|window, cx| {
        let view = cx.new(|cx| ApplicationView::new_fixture(window, cx));
        screens = Some(view.read(cx).screens.clone());
        gpui_kit::component::Root::new(view, window, cx)
    });
    draw(cx);
    (screens.unwrap(), cx)
}

fn active(view: &Entity<ScreenView>, cx: &VisualTestContext) -> Screen {
    cx.read(|cx| {
        view.read(cx)
            .shared
            .borrow()
            .session
            .workspace
            .screens
            .active
    })
}

#[gpui_kit::test]
fn every_tab_is_clickable_and_preserves_the_legacy_layout(cx: &mut TestAppContext) {
    let (view, cx) = harness(cx);
    let before = cx.read(|cx| view.read(cx).shared.borrow().session.workspace.dock.clone());
    for (screen, selector) in Screen::ALL.into_iter().zip([
        "screen-tab:summary",
        "screen-tab:cpu",
        "screen-tab:memory",
        "screen-tab:gpu",
        "screen-tab:disks",
        "screen-tab:network",
        "screen-tab:energy",
        "screen-tab:thermals",
        "screen-tab:processes",
        "screen-tab:settings",
    ]) {
        let bounds = cx
            .debug_bounds(selector)
            .expect("tab is in production root");
        cx.simulate_click(bounds.center(), Modifiers::default());
        draw(cx);
        assert_eq!(active(&view, cx), screen);
        cx.read(|cx| assert_eq!(view.read(cx).shared.borrow().session.workspace.dock, before));
    }
}

#[gpui_kit::test]
fn arrows_home_end_and_control_tab_switch_screens(cx: &mut TestAppContext) {
    let (view, cx) = harness(cx);
    cx.update(|window, cx| {
        view.read(cx).focus[&Screen::Summary]
            .handle
            .clone()
            .focus(window, cx)
    });
    native_key("right", cx);
    draw(cx);
    assert_eq!(active(&view, cx), Screen::Cpu);
    native_key("end", cx);
    draw(cx);
    assert_eq!(active(&view, cx), Screen::Settings);
    native_key("ctrl-tab", cx);
    draw(cx);
    assert_eq!(active(&view, cx), Screen::Summary);
    native_key("ctrl-shift-tab", cx);
    draw(cx);
    assert_eq!(active(&view, cx), Screen::Settings);
    native_key("home", cx);
    draw(cx);
    assert_eq!(active(&view, cx), Screen::Summary);
}

#[gpui_kit::test]
fn keyboard_switching_works_immediately_after_application_creation(cx: &mut TestAppContext) {
    let (view, cx) = harness(cx);
    assert_eq!(active(&view, cx), Screen::Summary);
    native_key("ctrl-tab", cx);
    draw(cx);
    assert_eq!(active(&view, cx), Screen::Cpu);
}

#[gpui_kit::test]
fn keyboard_switching_survives_builtin_preset_from_settings(cx: &mut TestAppContext) {
    let (view, cx) = harness(cx);
    let settings = cx.debug_bounds("screen-tab:settings").unwrap();
    cx.simulate_click(settings.center(), Modifiers::default());
    draw(cx);
    assert_eq!(active(&view, cx), Screen::Settings);
    let setting = cx.debug_bounds("settings-dark").unwrap();
    cx.simulate_click(setting.center(), Modifiers::default());
    draw(cx);
    command(
        &view,
        crate::workspace::Command::Preset(crate::workspace::presets::PresetCommand::Builtin(
            system_pulse_model::BuiltinPreset::Default,
        )),
        cx,
    );
    assert_eq!(active(&view, cx), Screen::Summary);
    native_key("ctrl-tab", cx);
    draw(cx);
    assert_eq!(active(&view, cx), Screen::Cpu);
}

#[gpui_kit::test]
fn keyboard_switching_survives_accepting_recovered_settings(cx: &mut TestAppContext) {
    let (view, cx) = harness(cx);
    cx.update(|window, cx| {
        let owner = view.read(cx).shared.borrow().owner.clone().unwrap();
        owner
            .update(cx, |owner, cx| {
                owner.restore("invalid saved workspace", window, cx)
            })
            .unwrap();
    });
    draw(cx);
    cx.read(|cx| assert!(view.read(cx).shared.borrow().session.rejected.is_some()));
    let recovery = cx.debug_bounds("accept-screen-recovery").unwrap();
    cx.simulate_click(recovery.center(), Modifiers::default());
    draw(cx);
    assert!(cx.debug_bounds("accept-screen-recovery").is_none());
    cx.read(|cx| assert!(view.read(cx).shared.borrow().session.rejected.is_none()));
    assert_eq!(active(&view, cx), Screen::Summary);
    // The focused recovery button has disappeared. Do not click a new focus target.
    native_key("ctrl-tab", cx);
    draw(cx);
    assert_eq!(active(&view, cx), Screen::Cpu);
}

#[gpui_kit::test]
fn collapsed_hidden_legacy_process_panel_cannot_hide_the_process_screen(cx: &mut TestAppContext) {
    let (view, cx) = harness(cx);
    cx.update(|window, cx| {
        view.update(cx, |view, cx| {
            let shared = view.shared.clone();
            let mut data = shared.borrow_mut();
            let state = data.session.workspace.panel_mut("processes");
            state.visible = false;
            state.collapsed = true;
            drop(data);
            view.select(Screen::Processes, window, cx);
        })
    });
    draw(cx);
    assert!(cx.debug_bounds("process-table").is_some());
    assert_eq!(active(&view, cx), Screen::Processes);
}

#[gpui_kit::test]
fn tab_switching_preserves_process_identity_selection(cx: &mut TestAppContext) {
    let (view, cx) = harness(cx);
    let identity = cx.read(|cx| view.read(cx).shared.borrow().processes[0].identity.clone());
    cx.update(|window, cx| {
        view.update(cx, |view, cx| {
            view.processes
                .update(cx, |panel, _| panel.selected = Some(identity.clone()));
            view.select(Screen::Memory, window, cx);
        })
    });
    draw(cx);
    cx.update(|window, cx| view.update(cx, |view, cx| view.select(Screen::Processes, window, cx)));
    draw(cx);
    cx.read(|cx| {
        assert_eq!(
            view.read(cx).processes.read(cx).selected.as_ref(),
            Some(&identity)
        )
    });
    assert!(cx.debug_bounds("process-details").is_some());
}

#[gpui_kit::test]
fn all_ten_screens_render_populated_collector_data(cx: &mut TestAppContext) {
    let (view, cx) = populated(cx);
    for (screen, selector) in [
        (Screen::Summary, "history:cpu:host/usage"),
        (Screen::Cpu, "history:cpu:host/core-0-usage"),
        (Screen::Memory, "history:memory:host/used"),
        (Screen::Gpu, "history:gpu:pci:0000:01:00.0/usage"),
        (Screen::Disks, "device-history:disks"),
        (Screen::Network, "device-history:network"),
        (Screen::Energy, "history:cpu:host/power"),
        (Screen::Thermals, "history:cpu:host/temperature"),
        (Screen::Processes, "process-table"),
        (Screen::Settings, "settings-dark"),
    ] {
        command(&view, crate::workspace::Command::Screen(screen), cx);
        let bounds = cx
            .debug_bounds(selector)
            .unwrap_or_else(|| panic!("missing populated {screen:?} content: {selector}"));
        assert!(bounds.size.width > gpui_kit::px(0.) && bounds.size.height > gpui_kit::px(0.));
        assert_eq!(active(&view, cx), screen);
    }
    cx.read(|cx| {
        let data = view.read(cx).shared.borrow();
        assert_eq!(data.processes.len(), 2);
        assert_eq!(data.processes[0].identity.pid, 401);
        assert_eq!(crate::screen_data::cpu_cores(&data).len(), 4);
        for monitor in &data.snapshot.as_ref().unwrap().monitors {
            assert!(
                data.history
                    .latest(&monitor.id, &monitor.summary_sensor_id)
                    .unwrap()
                    .chart_value()
                    .is_some(),
                "missing current summary for {}",
                monitor.id
            );
        }
    });
}

#[gpui_kit::test]
fn energy_primary_and_sensor_grid_render_zero_values_and_capture_gaps(cx: &mut TestAppContext) {
    let (view, cx) = populated(cx);
    command(
        &view,
        crate::workspace::Command::ScreenDevice(Screen::Energy, "cpu:host/power".into()),
        cx,
    );
    command(&view, crate::workspace::Command::Screen(Screen::Energy), cx);
    let primary = cx.debug_bounds("selected-channel-history").unwrap();
    let grid = cx.debug_bounds("history:cpu:host/power").unwrap();
    assert_eq!(primary.size.height, gpui_kit::px(260.));
    assert_eq!(grid.size.height, gpui_kit::px(95.));
    assert!(grid.origin.y > primary.origin.y);
    assert!(
        cx.debug_bounds("history:gpu:pci:0000:02:00.0/power")
            .is_some()
    );
    cx.read(|cx| {
        let data = view.read(cx).shared.borrow();
        let selected = crate::screen_data::selected_channel(&data, Screen::Energy).unwrap();
        let rows = crate::screen_data::by_quantity(
            &data,
            system_pulse_model::Quantity::Power,
            system_pulse_model::PhysicalUnit::Watts,
        );
        assert!(
            rows.iter().any(|row| row.sensor == selected.sensor),
            "the primary channel must also exercise the grid path"
        );
        let values: Vec<_> = selected
            .samples(&data)
            .iter()
            .map(|sample| sample.chart_value())
            .collect();
        assert_eq!(
            values,
            vec![Some(43.), Some(44.), None, Some(42.), Some(43.)]
        );
        let zero = rows
            .iter()
            .find(|row| row.monitor == fixture::GPU_B)
            .unwrap();
        assert_eq!(zero.measured(&data), Some(0.));
        assert!(zero.value(&data).starts_with('0'));
        assert!(selected.value(&data).contains("43"));
    });
}

#[gpui_kit::test]
fn selected_gpu_survives_reordering_restore_and_disconnect_without_switching(
    cx: &mut TestAppContext,
) {
    use crate::workspace::Command;
    let (view, cx) = populated(cx);
    command(
        &view,
        Command::ScreenDevice(Screen::Gpu, fixture::GPU_B.into()),
        cx,
    );
    command(&view, Command::Screen(Screen::Gpu), cx);
    assert!(
        cx.debug_bounds("history:gpu:pci:0000:02:00.0/usage")
            .is_some()
    );
    let mut reordered = fixture::snapshot(6);
    reordered.monitors.reverse();
    reordered.sensors.reverse();
    accept(&view, reordered, cx);
    command(&view, Command::Screen(Screen::Memory), cx);
    command(&view, Command::Screen(Screen::Gpu), cx);
    cx.read(|cx| {
        let data = view.read(cx).shared.borrow();
        let choices = crate::screen_data::devices(&data, Screen::Gpu);
        assert_eq!(choices.len(), 2);
        assert_ne!(choices[0].id, choices[1].id);
        assert_ne!(choices[0].label, choices[1].label);
        for choice in &choices {
            assert!(choice.label.contains(&choice.id));
        }
        assert_eq!(
            crate::screen_data::selected_device(&data, Screen::Gpu).as_deref(),
            Some(fixture::GPU_B)
        );
        let json = data.session.autosave_json().unwrap();
        let restored: system_pulse_model::Workspace = serde_json::from_str(&json).unwrap();
        assert_eq!(restored.screens.devices[&Screen::Gpu], fixture::GPU_B);
    });
    let mut disconnected = fixture::snapshot(7);
    disconnected
        .monitors
        .retain(|monitor| monitor.id != fixture::GPU_B);
    disconnected
        .sensors
        .retain(|sensor| sensor.monitor_id != fixture::GPU_B);
    disconnected
        .readings
        .retain(|reading| !reading.sensor_id.starts_with(fixture::GPU_B));
    accept(&view, disconnected, cx);
    cx.read(|cx| {
        let data = view.read(cx).shared.borrow();
        assert_eq!(
            crate::screen_data::selected_device(&data, Screen::Gpu).as_deref(),
            Some(fixture::GPU_B)
        );
        assert!(
            crate::screen_data::devices(&data, Screen::Gpu)
                .iter()
                .all(|device| device.id != fixture::GPU_B)
        );
        assert!(
            data.history
                .latest(fixture::GPU_B, &format!("{}/usage", fixture::GPU_B))
                .is_none()
        );
        assert!(
            data.history
                .latest(fixture::GPU_A, &format!("{}/usage", fixture::GPU_A))
                .unwrap()
                .chart_value()
                .is_some()
        );
    });
    assert!(
        cx.debug_bounds("history:gpu:pci:0000:01:00.0/usage")
            .is_none(),
        "disconnect must not display the other GPU's history"
    );
    accept(&view, fixture::snapshot(8), cx);
    assert!(
        cx.debug_bounds("history:gpu:pci:0000:02:00.0/usage")
            .is_some()
    );
}

#[gpui_kit::test]
fn hidden_sensors_stay_hidden_after_new_snapshots_and_tab_switches(cx: &mut TestAppContext) {
    use crate::workspace::Command;
    let (view, cx) = populated(cx);
    command(
        &view,
        Command::SensorVisible("cpu:host".into(), "cpu:host/core-0-usage".into()),
        cx,
    );
    command(
        &view,
        Command::SensorVisible("cpu:host".into(), "cpu:host/power".into()),
        cx,
    );
    accept(&view, fixture::snapshot(6), cx);
    command(&view, Command::Screen(Screen::Cpu), cx);
    assert!(cx.debug_bounds("history:cpu:host/core-0-usage").is_none());
    assert!(cx.debug_bounds("history:cpu:host/core-1-usage").is_some());
    command(&view, Command::Screen(Screen::Energy), cx);
    assert!(cx.debug_bounds("history:cpu:host/power").is_none());
    assert!(
        cx.debug_bounds("history:gpu:pci:0000:01:00.0/power")
            .is_some()
    );
    cx.read(|cx| {
        let data = view.read(cx).shared.borrow();
        assert!(
            data.history
                .latest("cpu:host", "cpu:host/power")
                .unwrap()
                .chart_value()
                .is_some(),
            "hiding presentation must preserve collection"
        );
        assert!(
            crate::screen_data::devices(&data, Screen::Energy)
                .iter()
                .all(|device| device.id != "cpu:host/power")
        );
        assert_eq!(crate::screen_data::cpu_cores(&data).len(), 3);
    });
}

#[gpui_kit::test]
fn hiding_used_memory_preserves_other_memory_readings(cx: &mut TestAppContext) {
    use crate::workspace::Command;
    let (view, cx) = populated(cx);
    command(&view, Command::Screen(Screen::Memory), cx);
    assert!(cx.debug_bounds("history:memory:host/used").is_some());
    command(
        &view,
        Command::SensorVisible("memory:host".into(), "memory:host/used".into()),
        cx,
    );
    accept(&view, fixture::snapshot(6), cx);
    assert!(cx.debug_bounds("history:memory:host/used").is_none());
    assert!(cx.debug_bounds("level:memory:host/used").is_none());
    assert!(cx.debug_bounds("screen-stat:memory:host/used").is_none());
    for selector in [
        "screen-stat:memory:host/available",
        "screen-stat:memory:host/cache",
        "screen-stat:memory:host/swap",
    ] {
        let bounds = cx
            .debug_bounds(selector)
            .unwrap_or_else(|| panic!("hiding Used also hid {selector}"));
        assert!(bounds.size.width > gpui_kit::px(0.) && bounds.size.height > gpui_kit::px(0.));
    }
    cx.read(|cx| {
        let data = view.read(cx).shared.borrow();
        let available = crate::screen_data::find(&data, "memory:host", "available").unwrap();
        assert_eq!(available.measured(&data), Some(20. * 1024_f64.powi(3)));
        let swap = crate::screen_data::find(&data, "memory:host", "swap").unwrap();
        assert_eq!(swap.measured(&data), Some(0.));
        assert!(
            data.history
                .latest("memory:host", "memory:host/used")
                .unwrap()
                .chart_value()
                .is_some()
        );
    });
}

#[gpui_kit::test]
fn unavailable_selected_thermal_sensor_keeps_other_charts_and_hottest_reading(
    cx: &mut TestAppContext,
) {
    use crate::workspace::Command;
    let (view, cx) = populated(cx);
    let selected_id = format!("{}/temperature", fixture::GPU_B);
    command(
        &view,
        Command::ScreenDevice(Screen::Thermals, selected_id.clone()),
        cx,
    );
    command(&view, Command::Screen(Screen::Thermals), cx);
    assert!(cx.debug_bounds("selected-channel-history").is_some());
    cx.read(|cx| {
        let data = view.read(cx).shared.borrow();
        let selected = crate::screen_data::selected_channel(&data, Screen::Thermals).unwrap();
        assert_eq!(selected.measured(&data), Some(46.));
    });

    let assert_other_temperatures = |expected_hottest: f64, cx: &mut VisualTestContext| {
        assert!(cx.debug_bounds("selected-channel-history").is_none());
        assert!(
            cx.debug_bounds("history:gpu:pci:0000:02:00.0/temperature")
                .is_none()
        );
        assert!(cx.debug_bounds("history:cpu:host/temperature").is_some());
        assert!(
            cx.debug_bounds("history:gpu:pci:0000:01:00.0/temperature")
                .is_some()
        );
        let indicator = cx.debug_bounds("thermal-hottest").unwrap();
        assert!(indicator.size.width > gpui_kit::px(0.));
        assert!(indicator.size.height > gpui_kit::px(0.));
        cx.read(|cx| {
            let data = view.read(cx).shared.borrow();
            assert_eq!(
                crate::screen_data::selected_device(&data, Screen::Thermals).as_deref(),
                Some(selected_id.as_str())
            );
            assert!(crate::screen_data::selected_channel(&data, Screen::Thermals).is_none());
            let temperatures = crate::screen_data::by_quantity(
                &data,
                system_pulse_model::Quantity::Temperature,
                system_pulse_model::PhysicalUnit::Celsius,
            );
            let hottest = crate::screen_data::highest_current(&data, &temperatures).unwrap();
            assert_eq!(hottest.sensor, "cpu:host/temperature");
            assert_eq!(hottest.measured(&data), Some(expected_hottest));
        });
    };

    command(
        &view,
        Command::SensorVisible(fixture::GPU_B.into(), selected_id.clone()),
        cx,
    );
    accept(&view, fixture::snapshot(6), cx);
    assert_other_temperatures(63., cx);

    command(
        &view,
        Command::SensorVisible(fixture::GPU_B.into(), selected_id.clone()),
        cx,
    );
    assert!(cx.debug_bounds("selected-channel-history").is_some());
    let mut disconnected = fixture::snapshot(7);
    disconnected
        .sensors
        .retain(|sensor| sensor.id != selected_id);
    disconnected
        .readings
        .retain(|reading| reading.sensor_id != selected_id);
    accept(&view, disconnected, cx);
    assert_other_temperatures(64., cx);
}
