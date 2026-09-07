use serde_json::json;
use system_pulse_model::{Screen, Session, Workspace};

#[test]
fn legacy_workspace_opens_summary_and_keeps_preferences() {
    let raw = json!({"dock": {}, "interval_ms": 2000,
        "panels": {"cpu:host": {"collapsed": true, "sensors": {}}}})
    .to_string();
    let session = Session::restore(&raw, Workspace::new(json!({})), |_| Ok(()));
    assert!(session.rejected.is_none());
    assert_eq!(session.workspace.screens.active, Screen::Summary);
    assert_eq!(session.workspace.interval_ms, 2000);
    assert!(session.workspace.panels["cpu:host"].collapsed);
}

#[test]
fn all_screens_and_device_choices_round_trip() {
    for screen in Screen::ALL {
        let mut workspace = Workspace::new(json!({"legacy": "kept"}));
        workspace.screens.active = screen;
        workspace
            .screens
            .devices
            .insert(Screen::Gpu, "amdgpu:stable".into());
        let raw = serde_json::to_string(&workspace).unwrap();
        let restored = Session::restore(&raw, Workspace::new(json!({})), |_| Ok(()));
        assert!(restored.rejected.is_none());
        assert_eq!(restored.workspace, workspace);
    }
}

#[test]
fn invalid_navigation_retains_original_and_blocks_autosave() {
    for screens in [
        json!({"active": "unknown"}),
        json!({"devices": {"summary": "cpu:host"}}),
        json!({"devices": {"gpu": "  "}}),
    ] {
        let raw = json!({"dock": {}, "screens": screens}).to_string();
        let session = Session::restore(&raw, Workspace::new(json!({})), |_| Ok(()));
        assert_eq!(session.rejected.as_ref().unwrap().original, raw);
        assert!(session.autosave_json().is_err());
    }
}

#[test]
fn tab_navigation_wraps_without_an_unreachable_screen() {
    let mut screen = Screen::Summary;
    for expected in Screen::ALL
        .into_iter()
        .cycle()
        .skip(1)
        .take(Screen::ALL.len())
    {
        screen = screen.adjacent(true);
        assert_eq!(screen, expected);
    }
    assert_eq!(Screen::Summary.adjacent(false), Screen::Settings);
}
