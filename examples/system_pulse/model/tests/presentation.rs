use serde_json::json;
use system_pulse_model::{ExpandedSize, Meter, Workspace};

#[test]
fn defaults_expand_panels_and_rows() {
    let mut workspace = Workspace::new(json!({"kind": "split"}));
    let panel = workspace.panel_mut("gpu:pci:0000:03:00.0");
    assert!(panel.visible);
    assert!(!panel.collapsed);
    let sensor = panel.sensor_mut("utilization");
    assert!(sensor.visible);
    assert!(!sensor.collapsed);
    assert_eq!(sensor.meter, Meter::Number);
}

#[test]
fn panel_row_meter_and_visibility_are_independent() {
    let mut workspace = Workspace::new(json!({}));
    let panel = workspace.panel_mut("cpu");
    panel.expanded_size = ExpandedSize {
        width: 600.0,
        height: 320.0,
    };
    panel.sensor_mut("overall").collapsed = true;
    panel.sensor_mut("temperature");
    panel.collapsed = true;
    panel.visible = false;
    panel.sensor_mut("overall").meter = Meter::Bar;
    panel.sensor_mut("overall").visible = false;
    panel.visible = true;
    panel.collapsed = false;
    panel.sensor_mut("overall").visible = true;
    assert!(panel.sensors["overall"].collapsed);
    assert!(!panel.sensors["temperature"].collapsed);
    assert_eq!(panel.sensors["overall"].meter, Meter::Bar);
    assert_eq!(panel.expanded_size.width, 600.0);
    assert_eq!(panel.expanded_size.height, 320.0);
    assert_eq!(
        panel
            .visible_sensors()
            .iter()
            .map(|(id, _)| *id)
            .collect::<Vec<_>>(),
        vec!["overall", "temperature"]
    );
}

#[test]
fn discovery_order_and_missing_devices_do_not_reassign_choices() {
    let mut workspace = Workspace::new(json!({}));
    workspace.panel_mut("gpu:uuid:A").collapsed = true;
    workspace
        .panel_mut("gpu:uuid:A")
        .sensor_mut("temperature")
        .collapsed = true;
    workspace.panel_mut("gpu:uuid:B");
    // A is absent from this discovery pass. Presence is collector data, not saved visibility.
    for id in ["gpu:uuid:B", "cpu"] {
        workspace.panel_mut(id);
    }
    assert!(workspace.panels["gpu:uuid:A"].collapsed);
    assert!(!workspace.panels["gpu:uuid:B"].collapsed);
    assert!(
        workspace
            .panel_mut("gpu:uuid:A")
            .sensor_mut("temperature")
            .collapsed
    );
}

#[test]
fn saved_order_survives_hiding_and_has_a_stable_tie_breaker() {
    let mut workspace = Workspace::new(json!({}));
    let panel = workspace.panel_mut("cpu");
    panel.sensor_mut("a").order = 2;
    panel.sensor_mut("b").order = 0;
    panel.sensor_mut("c").order = 0;
    panel.sensor_mut("b").visible = false;
    assert_eq!(
        panel
            .visible_sensors()
            .iter()
            .map(|(id, _)| *id)
            .collect::<Vec<_>>(),
        vec!["c", "a"]
    );
    panel.sensor_mut("b").visible = true;
    assert_eq!(
        panel
            .visible_sensors()
            .iter()
            .map(|(id, _)| *id)
            .collect::<Vec<_>>(),
        vec!["b", "c", "a"]
    );
}

#[test]
fn older_fields_default_to_expanded_and_dimensions_are_validated() {
    let mut workspace: Workspace = serde_json::from_value(json!({
        "dock": {}, "panels": { "cpu": { "sensors": { "overall": {} } } }
    }))
    .unwrap();
    assert!(!workspace.panels["cpu"].collapsed);
    assert!(!workspace.panels["cpu"].sensors["overall"].collapsed);
    assert!(workspace.validate().is_ok());
    workspace.panel_mut("cpu").expanded_size.width = f32::NAN;
    assert!(workspace.validate().is_err());
    workspace.panel_mut("cpu").expanded_size.width = 0.0;
    assert!(workspace.validate().is_err());
}

#[test]
fn sensor_order_overflow_compacts_existing_rows_before_appending() {
    let mut workspace = Workspace::new(json!({}));
    let panel = workspace.panel_mut("cpu");
    panel.sensor_mut("z");
    panel.sensor_mut("z").collapsed = true;
    panel.sensor_mut("a");
    panel.sensor_mut("z").order = u32::MAX;
    panel.sensor_mut("a").order = u32::MAX - 1;
    panel.sensor_mut("a").visible = false;
    panel.sensor_mut("a").meter = Meter::Bar;

    panel.sensor_mut("new");

    assert_eq!(panel.sensors["a"].order, 0);
    assert_eq!(panel.sensors["z"].order, 1);
    assert_eq!(panel.sensors["new"].order, 2);
    assert!(!panel.sensors["a"].visible);
    assert_eq!(panel.sensors["a"].meter, Meter::Bar);
    assert!(panel.sensors["z"].collapsed);
}

#[test]
fn expanded_dimensions_accept_limit_and_reject_values_above_it() {
    let mut workspace = Workspace::new(json!({}));
    workspace.panel_mut("cpu").expanded_size = ExpandedSize {
        width: 16_384.0,
        height: 16_384.0,
    };
    assert!(workspace.validate().is_ok());
    workspace.panel_mut("cpu").expanded_size.width = 16_384.1;
    assert!(workspace.validate().is_err());
}
