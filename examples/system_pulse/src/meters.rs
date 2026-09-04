use gpui::*;
use gpui_component::ActiveTheme;
use system_pulse_model::{Meter, ReadingStatus, Sample};

pub(crate) fn value(sample: Option<&Sample>) -> String {
    match sample {
        None => "Waiting for fixture".into(),
        Some(s) if s.status == ReadingStatus::Unavailable => "Unavailable".into(),
        Some(s) => format!(
            "{} {}{}",
            s.text,
            s.unit,
            if s.status == ReadingStatus::Stale {
                " · Stale"
            } else {
                ""
            }
        ),
    }
}

pub(crate) fn meter(kind: Meter, samples: Vec<Sample>, cx: &App) -> AnyElement {
    if kind == Meter::Number {
        return div().child(value(samples.last())).into_any_element();
    }
    let color = cx.theme().primary;
    let height = if kind == Meter::Sparkline {
        rems(2.25)
    } else {
        rems(6.)
    };
    canvas(
        |_, _, _| {},
        move |bounds, _, window, _| {
            let latest = samples.last().and_then(Sample::chart_value);
            let mut path = PathBuilder::stroke(px(2.));
            match kind {
                Meter::Bar => {
                    if let Some(v) = latest {
                        let y = bounds.top() + bounds.size.height / 2.;
                        path.move_to(point(bounds.left(), y));
                        path.line_to(point(
                            bounds.left() + bounds.size.width * (v.clamp(0., 100.) as f32 / 100.),
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
                                + std::f32::consts::TAU * v.clamp(0., 100.) as f32 / 100.
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
                            let x = index as f32 / samples.len().saturating_sub(1).max(1) as f32;
                            let p = bounds.origin
                                + point(
                                    bounds.size.width * x,
                                    bounds.size.height * (1. - v.clamp(0., 100.) as f32 / 100.),
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
    .into_any_element()
}

#[cfg(test)]
mod tests {
    use super::*;
    #[::core::prelude::v1::test]
    fn compact_status_does_not_turn_unavailable_into_zero() {
        assert_eq!(
            value(Some(&crate::fixture::sample("cpu", "overall", 8))),
            "Unavailable"
        );
        assert!(value(Some(&crate::fixture::sample("cpu", "overall", 9))).ends_with("Stale"));
        assert_eq!(value(None), "Waiting for fixture");
    }
}
