use serde_json::json;
use system_pulse_model::{HistoryStore, Meter, ReadingStatus, Sample, Workspace};

fn current(at_ms: u64, value: f64) -> Sample {
    Sample {
        at_ms,
        value: Some(value),
        text: format!("{value}"),
        unit: "%".into(),
        status: ReadingStatus::Current,
        quantity: Default::default(),
        total: None,
        reason: None,
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
                quantity: Default::default(),
                total: None,
                reason: None,
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

#[test]
fn physical_values_capacity_and_signed_temperature_remain_truthful() {
    use system_pulse_model::{PhysicalUnit, Quantity};
    let rate =
        Sample::measured(1, Quantity::Rate, 4096., None, PhysicalUnit::BytesPerSecond).unwrap();
    assert_eq!(rate.value, Some(4096.));
    assert_eq!(rate.text, "4.0");
    assert_eq!(rate.unit, "KiB/s");
    let capacity = Sample::measured(
        2,
        Quantity::Capacity,
        16. * 1024_f64.powi(3),
        Some(64. * 1024_f64.powi(3)),
        PhysicalUnit::Bytes,
    )
    .unwrap();
    assert_eq!(capacity.capacity_ratio(), Some(0.25));
    assert_eq!(capacity.text, "16.0 / 64.0");
    assert_eq!(capacity.unit, "GiB");
    assert!(Sample::measured(3, Quantity::Temperature, -10., None, PhysicalUnit::Celsius).is_ok());
    assert!(Sample::measured(3, Quantity::Rate, -10., None, PhysicalUnit::BytesPerSecond).is_err());
    assert!(
        Sample::measured(
            3,
            Quantity::Percentage,
            f64::INFINITY,
            None,
            PhysicalUnit::Percent
        )
        .is_err()
    );
    assert_eq!(
        Sample::measured(4, Quantity::Percentage, 150., None, PhysicalUnit::Percent)
            .unwrap()
            .value,
        Some(150.)
    );
}

#[test]
fn meters_follow_physical_compatibility_and_observed_scales() {
    use system_pulse_model::{PhysicalUnit, Quantity, chart_range};
    assert_eq!(Quantity::Capacity.meters(), &[Meter::Number, Meter::Bar]);
    assert_eq!(
        Quantity::Counter.meters(),
        &[Meter::Number, Meter::Sparkline]
    );
    assert_eq!(
        Quantity::Rate.meters(),
        &[Meter::Number, Meter::Sparkline, Meter::Line]
    );
    assert!(!Quantity::Temperature.meters().contains(&Meter::Bar));
    assert!(Quantity::Temperature.meters().contains(&Meter::Radial));
    let sample =
        Sample::measured(1, Quantity::Rate, 4096., None, PhysicalUnit::BytesPerSecond).unwrap();
    let range = chart_range(&[sample]);
    assert!(range.1 >= 4096.);
    let temp =
        Sample::measured(1, Quantity::Temperature, -10., None, PhysicalUnit::Celsius).unwrap();
    let range = chart_range(&[temp]);
    assert!(range.0 < -10. && range.1 > -10.);
}

#[test]
fn absent_series_are_evicted_without_changing_presentation_and_stale_adds_no_points() {
    let mut history = HistoryStore::new(2).unwrap();
    let mut workspace = Workspace::new(json!({}));
    workspace.panel_mut("absent").collapsed = true;
    for n in 1..=100 {
        history
            .push(&format!("device:{n}"), "value", current(n, 1.))
            .unwrap();
        history.retain_keys(&std::collections::BTreeSet::from([(
            format!("device:{n}"),
            "value".into(),
        )]));
        assert_eq!(history.series_count(), 1);
    }
    assert!(workspace.panels["absent"].collapsed);
    assert!(history.mark_stale(110, 5));
    let values = history.samples("device:100", "value").unwrap();
    assert_eq!(values.len(), 1);
    assert_eq!(values.back().unwrap().status, ReadingStatus::Stale);
    assert!(!history.mark_stale(111, 5));
}

#[test]
fn chart_time_spacing_uses_elapsed_capture_time() {
    let samples = vec![current(1000, 1.), current(1500, 2.), current(6000, 3.)];
    assert_eq!(system_pulse_model::chart_x(&samples, 1), 0.1);
    assert_eq!(system_pulse_model::chart_x(&samples, 2), 1.);
}

#[test]
fn zero_sized_capacity_keeps_the_observation_without_inventing_a_ratio() {
    let sample = Sample::measured(
        1,
        system_pulse_model::Quantity::Capacity,
        0.,
        Some(0.),
        system_pulse_model::PhysicalUnit::Bytes,
    )
    .unwrap();
    assert_eq!(sample.value, Some(0.));
    assert_eq!(sample.total, Some(0.));
    assert_eq!(sample.status, ReadingStatus::Current);
    assert_eq!(sample.capacity_ratio(), None);
}
