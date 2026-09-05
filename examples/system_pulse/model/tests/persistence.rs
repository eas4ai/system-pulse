use serde_json::{Value, json};
use system_pulse_model::{Meter, Session, Workspace};

// This small test protocol exercises the injected adapter, not GPUI's JSON schema.
fn validate_dock(value: &Value) -> Result<(), String> {
    if value.get("kind").and_then(Value::as_str) == Some("split") {
        Ok(())
    } else {
        Err("A split layout is required; tab groups are incompatible".into())
    }
}

fn fallback() -> Workspace {
    Workspace::new(json!({"kind": "split", "panels": ["cpu"]}))
}

#[test]
fn layout_and_preset_roundtrips_keep_both_collapse_levels_and_geometry() {
    let mut workspace = fallback();
    workspace.dock = json!({"kind": "split", "axis": "vertical", "panels": ["cpu", "gpu:A"]});
    let panel = workspace.panel_mut("gpu:A");
    panel.collapsed = true;
    panel.expanded_size.width = 650.0;
    let sensor = panel.sensor_mut("utilization");
    sensor.collapsed = true;
    sensor.visible = false;
    sensor.meter = Meter::Line;
    sensor.order = 4;
    let preset = serde_json::to_string(&workspace).unwrap();
    let mut session = Session::restore(&preset, fallback(), validate_dock);
    assert!(session.rejected.is_none());
    assert_eq!(session.workspace, workspace);
    // Recall restores the same snapshot without modifying current readings.
    session.workspace.panel_mut("gpu:A").collapsed = false;
    session = Session::restore(&preset, fallback(), validate_dock);
    assert_eq!(session.workspace, workspace);
    assert_eq!(
        serde_json::from_str::<Workspace>(&session.autosave_json().unwrap()).unwrap(),
        workspace
    );
}

#[test]
fn incompatible_layout_retains_exact_input_and_blocks_autosave_until_recovery() {
    let original =
        " {\n \"dock\": {\"kind\":\"tabs\",\"panels\":[\"cpu\",\"gpu:A\"]}, \"panels\": {} } ";
    let mut session = Session::restore(original, fallback(), validate_dock);
    assert_eq!(session.workspace, fallback());
    assert_eq!(session.rejected.as_ref().unwrap().original, original);
    assert!(
        session
            .rejected
            .as_ref()
            .unwrap()
            .error
            .contains("tab groups")
    );
    session.workspace.panel_mut("cpu").collapsed = true;
    assert!(session.autosave_json().is_err());
    assert_eq!(session.rejected.as_ref().unwrap().original, original);
    session.accept_recovery();
    assert!(session.rejected.is_none());
    assert!(session.autosave_json().is_ok());
}

#[test]
fn malformed_json_future_schema_and_invalid_dimensions_are_retained() {
    for original in [
        "not json".to_string(),
        json!({"schema_version": 42, "dock": {"kind":"split"}}).to_string(),
        json!({"dock":{"kind":"split"}, "panels":{"cpu":{"expanded_size":{"width":-1,"height":280}}}}).to_string(),
    ] {
        let session = Session::restore(&original, fallback(), validate_dock);
        assert_eq!(session.workspace, fallback());
        assert_eq!(session.rejected.as_ref().unwrap().original, original);
        assert!(session.autosave_json().is_err());
    }
}

#[test]
fn autosave_revalidates_presentation_and_legacy_defaults_remain_expanded() {
    let mut session = Session::restore(
        r#"{"dock":{"kind":"split"},"panels":{"cpu":{"sensors":{"overall":{}}}}}"#,
        fallback(),
        validate_dock,
    );
    assert!(session.rejected.is_none());
    assert!(!session.workspace.panels["cpu"].collapsed);
    assert!(!session.workspace.panels["cpu"].sensors["overall"].collapsed);
    session.workspace.panel_mut("cpu").expanded_size.height = 0.0;
    assert!(session.autosave_json().is_err());
}

#[test]
fn interval_and_absent_device_descriptors_roundtrip() {
    let mut workspace = system_pulse_model::Workspace::new(serde_json::json!({}));
    workspace.interval_ms = 5000;
    workspace.monitors.insert(
        "amdgpu:stable".into(),
        system_pulse_model::MonitorDescriptor {
            id: "amdgpu:stable".into(),
            title: "GPU stable".into(),
            summary: "usage".into(),
            sensors: vec![],
        },
    );
    let restored: system_pulse_model::Workspace =
        serde_json::from_str(&serde_json::to_string(&workspace).unwrap()).unwrap();
    assert_eq!(restored.interval_ms, 5000);
    assert_eq!(restored.monitors["amdgpu:stable"].title, "GPU stable");
    workspace.interval_ms = 7;
    assert!(workspace.validate().is_err());
}
