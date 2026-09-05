use gpui::*;
use gpui_component::ActiveTheme;
use system_pulse_model::{Meter, ReadingStatus, Sample};

pub(crate) fn value(sample: Option<&Sample>) -> String {
    match sample {
        None => "Waiting for host snapshot".into(),
        Some(s) => {
            let status = match s.status {
                ReadingStatus::Current => "",
                ReadingStatus::Stale => "Stale",
                ReadingStatus::Unavailable => "Unavailable",
                ReadingStatus::WarmingUp => "Warming up",
                ReadingStatus::Failed => "Failed",
            };
            let mut text = if s.value.is_some() {
                format!("{} {}", s.text, s.unit).trim().to_owned()
            } else {
                status.into()
            };
            if s.value.is_none() && !s.unit.is_empty() {
                text.push_str(&format!(" · {}", s.unit));
            }
            if s.value.is_some() && !status.is_empty() {
                text.push_str(&format!(" · {status}"));
            }
            if let Some(reason) = &s.reason {
                text.push_str(&format!(" · {reason}"));
            }
            text
        }
    }
}

pub(crate) fn meter(
    kind: Meter,
    samples: Vec<Sample>,
    unit: system_pulse_model::PhysicalUnit,
    cx: &App,
) -> AnyElement {
    if kind == Meter::Number {
        return div().child(value(samples.last())).into_any_element();
    }
    let color = cx.theme().primary;
    let height = if kind == Meter::Sparkline {
        rems(2.25)
    } else {
        rems(6.)
    };
    let mut range = system_pulse_model::chart_range(&samples);
    let capacity = samples
        .last()
        .is_some_and(|s| s.quantity == system_pulse_model::Quantity::Capacity);
    if capacity {
        if let Some(total) = samples
            .last()
            .and_then(|s| s.total)
            .filter(|total| *total > 0.)
        {
            range = (0., total);
        }
    }
    let scale_label = if samples
        .last()
        .is_some_and(|s| s.quantity == system_pulse_model::Quantity::Temperature)
    {
        format!("Observed range: {:.1}–{:.1} °C", range.0, range.1)
    } else {
        if capacity
            && samples
                .last()
                .and_then(|s| s.total)
                .filter(|total| *total > 0.)
                .is_none()
        {
            "No positive capacity scale".into()
        } else {
            format!("Scale: {:.1}–{:.1} {}", range.0, range.1, unit.symbol())
        }
    };
    let chart = canvas(
        |_, _, _| {},
        move |bounds, _, window, _| {
            let latest = samples.last().and_then(Sample::chart_value);
            let mut path = PathBuilder::stroke(px(2.));
            match kind {
                Meter::Bar => {
                    if let Some(v) = latest.filter(|_| {
                        !capacity
                            || samples
                                .last()
                                .and_then(|s| s.total)
                                .filter(|total| *total > 0.)
                                .is_some()
                    }) {
                        let y = bounds.top() + bounds.size.height / 2.;
                        path.move_to(point(bounds.left(), y));
                        path.line_to(point(
                            bounds.left()
                                + bounds.size.width
                                    * samples
                                        .last()
                                        .and_then(Sample::capacity_ratio)
                                        .unwrap_or((v - range.0) / (range.1 - range.0))
                                        .clamp(0., 1.) as f32,
                            y,
                        ));
                    }
                }
                Meter::Radial => {
                    if let Some(v) = latest {
                        let radius = bounds.size.height / 2. - px(4.);
                        let center =
                            bounds.origin + point(bounds.size.width / 2., bounds.size.height / 2.);
                        for step in 0..=60 {
                            let angle = -std::f32::consts::PI / 2.
                                + std::f32::consts::TAU
                                    * ((v - range.0) / (range.1 - range.0)) as f32
                                    * step as f32
                                    / 60.;
                            let p = center + point(radius * angle.cos(), radius * angle.sin());
                            if step == 0 {
                                path.move_to(p);
                            } else {
                                path.line_to(p);
                            }
                        }
                    }
                }
                Meter::Line | Meter::Sparkline => {
                    let mut connected = false;
                    for (index, sample) in samples.iter().enumerate() {
                        if let Some(v) = sample.chart_value() {
                            let x = system_pulse_model::chart_x(&samples, index);
                            let p = bounds.origin
                                + point(
                                    bounds.size.width * x,
                                    bounds.size.height
                                        * (1. - ((v - range.0) / (range.1 - range.0)) as f32),
                                );
                            if connected {
                                path.line_to(p);
                            } else {
                                path.move_to(p);
                            }
                            connected = true;
                        } else {
                            connected = false;
                        }
                    }
                }
                Meter::Number => {}
            }
            if let Ok(path) = path.build() {
                window.paint_path(path, color);
            }
        },
    )
    .w_full()
    .h(height)
    .into_any_element();
    div()
        .flex()
        .flex_col()
        .child(scale_label)
        .child(chart)
        .into_any_element()
}

#[cfg(test)]
mod tests {
    use super::*;
    #[::core::prelude::v1::test]
    fn compact_status_does_not_turn_unavailable_into_zero() {
        assert_eq!(
            value(Some(&crate::fixture::sample("cpu", "overall", 8))),
            "Unavailable · %"
        );
        let mut unitless = crate::fixture::sample("cpu", "overall", 8);
        unitless.unit.clear();
        assert_eq!(value(Some(&unitless)), "Unavailable");
        assert!(value(Some(&crate::fixture::sample("cpu", "overall", 9))).ends_with("Stale"));
        assert_eq!(value(None), "Waiting for host snapshot");
    }
}

pub(crate) fn summary(
    monitor: &system_pulse_model::MonitorDescriptor,
    history: &system_pulse_model::HistoryStore,
) -> String {
    let summary = if monitor.summary.is_empty() {
        if monitor.id == "settings" {
            String::new()
        } else {
            "Unavailable · device absent".into()
        }
    } else if let Some(sample) = history.latest(&monitor.id, &monitor.summary) {
        value(Some(sample))
    } else {
        "Unavailable · waiting for device reading".into()
    };
    if summary.is_empty() {
        monitor.title.clone()
    } else {
        format!("{} · {summary}", monitor.title)
    }
}
pub(crate) fn sensor_label(
    monitor: &system_pulse_model::MonitorDescriptor,
    sensor: &system_pulse_model::SensorDescriptor,
    sample: &Sample,
) -> String {
    format!(
        "{} · {} · {}",
        monitor.title,
        sensor.title,
        value(Some(sample))
    )
}

pub(crate) fn metric_label(id: String, text: String) -> Stateful<Div> {
    div()
        .id(SharedString::from(id.clone()))
        .accessibility_id(id)
        .role(Role::Label)
        .aria_label(text.clone())
        .aria_value(text.clone())
        .child(text)
}
#[cfg(test)]
mod accessibility_tests {
    use super::*;
    #[::core::prelude::v1::test]
    fn metric_labels_supply_platform_text_value_and_stable_author_identity() {
        let label = metric_label("cpu:host:value:usage".into(), "CPU · Usage · 42.0 %".into());
        let mut node = gpui::accesskit::Node::new(Role::Label);
        label.write_a11y_info(&mut node);
        assert_eq!(node.value(), Some("CPU · Usage · 42.0 %"));
        assert_eq!(node.author_id(), Some("cpu:host:value:usage"));
    }
}
