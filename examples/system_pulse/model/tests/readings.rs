use serde_json::json;
use system_pulse_model::{HistoryStore, Meter, ReadingStatus, Sample, Workspace};

fn current(at_ms: u64, value: f64) -> Sample {
    Sample {
        at_ms,
        value: Some(value),
        text: format!("{value}"),
        unit: "%".into(),
        status: ReadingStatus::Current,
    }
}

#[test]
fn collapse_hide_and_meter_changes_preserve_live_bounded_history() {
    let mut workspace = Workspace::new(json!({}));
    let mut history = HistoryStore::new(3).unwrap();
    for tick in 1..=5 {
        let panel = workspace.panel_mut("cpu");
        panel.collapsed = tick >= 2;
        panel.sensor_mut("overall").collapsed = true;
        panel.sensor_mut("overall").visible = false;
        panel.sensor_mut("overall").meter = Meter::Bar;
        history
            .push("cpu", "overall", current(tick * 1000, tick as f64))
            .unwrap();
    }
    let samples = history.samples("cpu", "overall").unwrap();
    assert_eq!(
        samples.iter().map(|s| s.at_ms).collect::<Vec<_>>(),
        vec![3000, 4000, 5000]
    );
    assert_eq!(history.latest("cpu", "overall").unwrap().text, "5");
    workspace.panel_mut("cpu").collapsed = false;
    assert_eq!(history.samples("cpu", "overall").unwrap().len(), 3);
    assert!(workspace.panels["cpu"].sensors["overall"].collapsed);
}

#[test]
fn unavailable_and_stale_are_explicit_history_gaps() {
    let mut history = HistoryStore::new(4).unwrap();
    history.push("gpu:A", "util", current(1000, 34.0)).unwrap();
    let stale = Sample {
        at_ms: 2000,
        status: ReadingStatus::Stale,
        ..current(2000, 34.0)
    };
    history.push("gpu:A", "util", stale).unwrap();
    assert_eq!(history.latest("gpu:A", "util").unwrap().text, "34");
    assert_eq!(history.latest("gpu:A", "util").unwrap().chart_value(), None);
    history
        .push(
            "gpu:A",
            "util",
            Sample {
                at_ms: 3000,
                value: None,
                text: "Unavailable".into(),
                unit: "%".into(),
                status: ReadingStatus::Unavailable,
            },
        )
        .unwrap();
    assert_eq!(
        history
            .samples("gpu:A", "util")
            .unwrap()
            .iter()
            .map(Sample::chart_value)
            .collect::<Vec<_>>(),
        vec![Some(34.0), None, None]
    );
}

#[test]
fn fixture_serialization_retains_values_units_timestamps_and_status() {
    let sample: Sample = serde_json::from_str(
        r#"{
        "at_ms": 500, "value": 12.5, "text": "12.5", "unit": "MiB/s", "status": "current"
    }"#,
    )
    .unwrap();
    assert_eq!(sample.at_ms, 500);
    assert_eq!(sample.unit, "MiB/s");
    assert_eq!(sample.chart_value(), Some(12.5));
    assert_eq!(
        serde_json::from_str::<Sample>(&serde_json::to_string(&sample).unwrap()).unwrap(),
        sample
    );
}

#[test]
fn invalid_and_out_of_order_samples_do_not_mutate_history() {
    assert!(HistoryStore::new(0).is_err());
    assert!(HistoryStore::new(3601).is_err());
    let mut history = HistoryStore::new(2).unwrap();
    history.push("cpu", "overall", current(2000, 4.0)).unwrap();
    for invalid in [
        current(1000, 2.0),
        current(2000, 5.0),
        current(3000, f64::NAN),
        Sample {
            status: ReadingStatus::Unavailable,
            ..current(3000, 6.0)
        },
    ] {
        assert!(history.push("cpu", "overall", invalid).is_err());
    }
    assert_eq!(history.samples("cpu", "overall").unwrap().len(), 1);
    assert_eq!(history.latest("cpu", "overall").unwrap().value, Some(4.0));
    assert!(history.push("", "overall", current(3000, 2.0)).is_err());
}
