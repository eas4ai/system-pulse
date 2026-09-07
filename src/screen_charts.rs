use gpui_kit::component::ActiveTheme;
use gpui_kit::prelude::FluentBuilder;
use gpui_kit::*;
use system_pulse_model::{Quantity, Sample};

pub(crate) struct ChartSeries {
    pub label: String,
    pub color: Hsla,
    pub samples: Vec<Sample>,
}

#[derive(Debug, PartialEq)]
struct ChartPoint {
    x: f32,
    y: f32,
}

fn time_domain(series: &[ChartSeries]) -> (u64, u64) {
    let mut times = series
        .iter()
        .flat_map(|series| &series.samples)
        .map(|sample| sample.at_ms);
    let Some(first) = times.next() else {
        return (0, 0);
    };
    times.fold((first, first), |(low, high), time| {
        (low.min(time), high.max(time))
    })
}

fn value_domain(series: &[ChartSeries], requested: Option<(f64, f64)>) -> (f64, f64) {
    if let Some((low, high)) =
        requested.filter(|(low, high)| low.is_finite() && high.is_finite() && low < high)
    {
        return (low, high);
    }
    let temperature = series
        .iter()
        .flat_map(|series| &series.samples)
        .next()
        .is_some_and(|sample| sample.quantity == Quantity::Temperature);
    let mut values = series
        .iter()
        .flat_map(|series| &series.samples)
        .filter_map(chart_value);
    let Some(first) = values.next() else {
        return (0., 1.);
    };
    let (mut low, mut high) = values.fold((first, first), |(low, high), value| {
        (low.min(value), high.max(value))
    });
    if !temperature {
        low = low.min(0.);
        high = high.max(0.);
    }
    if low == high {
        let padding = (low.abs() * 0.05).max(1.);
        if temperature {
            low = (low - padding).max(-f64::MAX);
        }
        high = (high + padding).min(f64::MAX);
    }
    (low, high)
}

fn trace_segments(samples: &[Sample], time: (u64, u64), range: (f64, f64)) -> Vec<Vec<ChartPoint>> {
    let mut segments = Vec::new();
    let mut current = Vec::new();
    let mut previous = None;
    for sample in samples {
        let monotonic = previous.is_none_or(|previous| sample.at_ms > previous);
        previous = Some(previous.map_or(sample.at_ms, |previous: u64| previous.max(sample.at_ms)));
        if let Some(point) = chart_point(sample, time, range).filter(|_| monotonic) {
            current.push(point);
        } else if !current.is_empty() {
            segments.push(std::mem::take(&mut current));
        }
    }
    if !current.is_empty() {
        segments.push(current);
    }
    segments
}

fn latest_point(samples: &[Sample], time: (u64, u64), range: (f64, f64)) -> Option<ChartPoint> {
    let last = samples.last()?;
    if samples[..samples.len() - 1]
        .iter()
        .any(|sample| sample.at_ms >= last.at_ms)
    {
        return None;
    }
    chart_point(last, time, range)
}

fn chart_value(sample: &Sample) -> Option<f64> {
    sample.chart_value().filter(|value| value.is_finite())
}

fn chart_point(sample: &Sample, time: (u64, u64), range: (f64, f64)) -> Option<ChartPoint> {
    let value = chart_value(sample)?;
    let span = time.1.saturating_sub(time.0);
    let x = if span == 0 {
        1.
    } else {
        (sample.at_ms.saturating_sub(time.0) as f64 / span as f64).clamp(0., 1.) as f32
    };
    // Scale before subtracting so even finite extremes cannot overflow the span.
    let scale = range.0.abs().max(range.1.abs()).max(f64::MIN_POSITIVE);
    let ratio = ((value.clamp(range.0, range.1) / scale - range.0 / scale)
        / (range.1 / scale - range.0 / scale))
        .clamp(0., 1.);
    Some(ChartPoint {
        x,
        y: (1. - ratio) as f32,
    })
}

fn meter_ratio(ratio: Option<f64>) -> Option<f64> {
    ratio
        .filter(|ratio| ratio.is_finite())
        .map(|ratio| ratio.clamp(0., 1.))
}

fn range_label(range: (f64, f64), unit: &str) -> String {
    // Sample.value remains physical; Sample.unit already includes its display prefix.
    let divisor = ["B/s", "B", "Hz"]
        .iter()
        .find_map(|suffix| {
            let prefix = unit.strip_suffix(suffix)?;
            Some(match prefix {
                "Ki" => 1024_f64,
                "Mi" => 1024_f64.powi(2),
                "Gi" => 1024_f64.powi(3),
                "Ti" => 1024_f64.powi(4),
                "Pi" => 1024_f64.powi(5),
                "k" => 1e3,
                "M" => 1e6,
                "G" => 1e9,
                "T" => 1e12,
                _ => 1.,
            })
        })
        .unwrap_or(1.);
    format!(
        "Scale: {:.1}–{:.1} {unit}",
        range.0 / divisor,
        range.1 / divisor
    )
}

pub(crate) fn history_chart(
    id: impl Into<SharedString>,
    series: Vec<ChartSeries>,
    height: f32,
    range: Option<(f64, f64)>,
    cx: &App,
) -> AnyElement {
    let id = id.into();
    let time = time_domain(&series);
    let range = value_domain(&series, range);
    let has_points = series
        .iter()
        .flat_map(|series| &series.samples)
        .any(|sample| chart_value(sample).is_some());
    let has_samples = series.iter().any(|series| !series.samples.is_empty());
    let waiting = if has_samples {
        "No current readings"
    } else {
        "Waiting for history"
    };
    let unit = series
        .iter()
        .flat_map(|series| &series.samples)
        .last()
        .map_or("", |sample| sample.unit.as_str());
    let scale_label = range_label(range, unit);
    let elapsed = format!(
        "{:.1} s history",
        time.1.saturating_sub(time.0) as f64 / 1000.
    );
    let values = series
        .iter()
        .map(|series| {
            format!(
                "{}: {}",
                series.label,
                crate::meters::value(series.samples.last())
            )
        })
        .collect::<Vec<_>>()
        .join("; ");
    let label = format!(
        "History chart. {values}. {scale_label}. {elapsed}. {}",
        if has_points { "" } else { waiting }
    );
    let accent = series
        .first()
        .map_or(cx.theme().primary, |series| series.color);
    let dark = cx.theme().is_dark();
    let grid = cx
        .theme()
        .foreground
        .opacity(if dark { 0.09 } else { 0.12 });
    let foreground = cx.theme().foreground;
    let chart = canvas(
        |_, _, _| {},
        move |bounds, _, window, _| {
            if bounds.size.width <= px(12.) || bounds.size.height <= px(12.) {
                return;
            }
            window.with_content_mask(Some(ContentMask { bounds }), |window| {
                let plot = Bounds::new(
                    bounds.origin + point(px(5.), px(5.)),
                    size(bounds.size.width - px(10.), bounds.size.height - px(10.)),
                );
                let position = |point: &ChartPoint| {
                    plot.origin
                        + gpui_kit::point(plot.size.width * point.x, plot.size.height * point.y)
                };
                let mut grid_path = PathBuilder::stroke(px(1.));
                for column in 0..=20 {
                    let x = plot.left() + plot.size.width * column as f32 / 20.;
                    grid_path.move_to(point(x, plot.top()));
                    grid_path.line_to(point(x, plot.bottom()));
                }
                for row in 0..=10 {
                    let y = plot.top() + plot.size.height * row as f32 / 10.;
                    grid_path.move_to(point(plot.left(), y));
                    grid_path.line_to(point(plot.right(), y));
                }
                if let Ok(path) = grid_path.build() {
                    window.paint_path(path, grid);
                }
                for series in &series {
                    for segment in trace_segments(&series.samples, time, range) {
                        let points = segment.iter().map(position).collect::<Vec<_>>();
                        if points.len() > 1 {
                            let mut fill = PathBuilder::fill();
                            fill.move_to(point(points[0].x, plot.bottom()));
                            for point in &points {
                                fill.line_to(*point);
                            }
                            fill.line_to(point(points[points.len() - 1].x, plot.bottom()));
                            fill.close();
                            if let Ok(path) = fill.build() {
                                window.paint_path(
                                    path,
                                    series.color.opacity(if dark { 0.12 } else { 0.08 }),
                                );
                            }
                            for (width, opacity) in [(7., 0.06), (4., 0.15), (1.5, 0.95)] {
                                let mut line = PathBuilder::stroke(px(width));
                                line.add_polygon(&points, false);
                                if let Ok(path) = line.build() {
                                    window.paint_path(path, series.color.opacity(opacity));
                                }
                            }
                        } else {
                            let center = points[0];
                            let mut dot = PathBuilder::fill();
                            dot.add_polygon(
                                &[
                                    center + point(px(-2.), px(0.)),
                                    center + point(px(0.), px(-2.)),
                                    center + point(px(2.), px(0.)),
                                    center + point(px(0.), px(2.)),
                                ],
                                true,
                            );
                            if let Ok(path) = dot.build() {
                                window.paint_path(path, series.color);
                            }
                        }
                    }
                    if let Some(latest) = latest_point(&series.samples, time, range) {
                        let center = position(&latest);
                        let vertices = [
                            center + point(px(-3.), px(0.)),
                            center + point(px(3.), px(-4.)),
                            center + point(px(3.), px(4.)),
                        ];
                        let mut marker = PathBuilder::fill();
                        marker.add_polygon(&vertices, true);
                        if let Ok(path) = marker.build() {
                            window.paint_path(path, foreground);
                        }
                    }
                }
            });
        },
    )
    .w_full()
    .h_full();
    let height = if height.is_finite() {
        height.max(28.)
    } else {
        150.
    };
    div()
        .id(id.clone())
        .accessibility_id(id.to_string())
        .debug_selector(move || id.to_string())
        .role(Role::Image)
        .aria_label(label)
        .w_full()
        .h(px(height))
        .flex()
        .flex_col()
        .gap_1()
        .when(height >= 140., |this| {
            this.child(
                div()
                    .flex()
                    .justify_between()
                    .text_size(px(10.))
                    .text_color(cx.theme().muted_foreground)
                    .child(scale_label)
                    .child(elapsed),
            )
        })
        .child(
            div()
                .relative()
                .flex_1()
                .min_h_0()
                .w_full()
                .border_1()
                .border_color(accent.opacity(0.4))
                .rounded_sm()
                .overflow_hidden()
                .bg(accent.opacity(if dark { 0.035 } else { 0.025 }))
                .child(chart)
                .when(!has_points, |this| {
                    this.child(
                        div()
                            .absolute()
                            .inset_0()
                            .flex()
                            .items_center()
                            .justify_center()
                            .text_size(px(11.))
                            .text_color(cx.theme().muted_foreground)
                            .child(waiting),
                    )
                }),
        )
        .into_any_element()
}

pub(crate) fn segmented_meter(
    id: impl Into<SharedString>,
    ratio: Option<f64>,
    color: Hsla,
    vertical: bool,
    cx: &App,
) -> AnyElement {
    let id = id.into();
    let ratio = meter_ratio(ratio);
    let label = ratio.map_or_else(
        || "Level unavailable".into(),
        |ratio| format!("Level: {:.1}%", ratio * 100.),
    );
    let lit = ratio.map_or(0, |ratio| (ratio * 30.).ceil() as usize);
    let dark = cx.theme().is_dark();
    div()
        .id(id.clone())
        .accessibility_id(id.to_string())
        .debug_selector(move || id.to_string())
        .role(Role::Image)
        .aria_label(label)
        .flex()
        .gap(px(2.))
        .p(px(3.))
        .flex_shrink_0()
        .when(vertical, |this| {
            this.flex_col_reverse().w(px(26.)).h(px(180.))
        })
        .when(!vertical, |this| this.w_full().h(px(28.)))
        .children((0..30).map(|index| {
            let active = index < lit;
            div()
                .flex_1()
                .min_w_0()
                .min_h_0()
                .rounded(px(1.))
                .border_1()
                .border_color(color.opacity(if active { 0.9 } else { 0.1 }))
                .bg(color.opacity(if active {
                    0.78
                } else if dark {
                    0.08
                } else {
                    0.12
                }))
                .when(active, |this| {
                    this.shadow(vec![BoxShadow {
                        color: color.opacity(0.36),
                        offset: point(px(0.), px(0.)),
                        blur_radius: px(6.),
                        spread_radius: px(0.),
                        inset: false,
                    }])
                })
        }))
        .into_any_element()
}

#[cfg(test)]
mod tests {
    use super::*;
    use system_pulse_model::{PhysicalUnit, ReadingStatus};

    fn sample(at_ms: u64, value: f64) -> Sample {
        Sample::measured(
            at_ms,
            Quantity::Percentage,
            value,
            None,
            PhysicalUnit::Percent,
        )
        .unwrap()
    }

    fn series(samples: Vec<Sample>) -> ChartSeries {
        ChartSeries {
            label: "CPU".into(),
            color: hsla(0.3, 0.8, 0.6, 1.),
            samples,
        }
    }

    #[::core::prelude::v1::test]
    fn uneven_timestamps_align_across_series_without_float_clock_loss() {
        let origin = u64::MAX - 1000;
        let series = vec![
            series(vec![
                sample(origin, 0.),
                sample(origin + 100, 50.),
                sample(origin + 1000, 100.),
            ]),
            series(vec![sample(origin + 500, 25.)]),
        ];
        let time = time_domain(&series);
        assert_eq!(time, (origin, origin + 1000));
        let trace = trace_segments(&series[0].samples, time, (0., 100.));
        assert_eq!(trace[0][1], ChartPoint { x: 0.1, y: 0.5 });
        assert_eq!(
            trace_segments(&series[1].samples, time, (0., 100.))[0][0].x,
            0.5
        );
    }

    #[::core::prelude::v1::test]
    fn unavailable_and_nonfinite_samples_break_both_trace_and_area() {
        let mut samples = vec![
            sample(0, 20.),
            sample(100, 40.),
            sample(200, 50.),
            sample(300, 70.),
            sample(400, 80.),
        ];
        samples[1].status = ReadingStatus::Unavailable;
        samples[3].value = Some(f64::NAN);
        let segments = trace_segments(&samples, (0, 400), (0., 100.));
        assert_eq!(
            segments.iter().map(Vec::len).collect::<Vec<_>>(),
            vec![1, 1, 1]
        );
        assert_eq!(segments[1][0].x, 0.5);
    }

    #[::core::prelude::v1::test]
    fn stale_latest_never_gets_current_marker() {
        let mut samples = vec![sample(0, 20.), sample(100, 40.)];
        assert!(latest_point(&samples, (0, 100), (0., 100.)).is_some());
        samples[1].status = ReadingStatus::Stale;
        assert!(latest_point(&samples, (0, 100), (0., 100.)).is_none());
        assert_eq!(trace_segments(&samples, (0, 100), (0., 100.))[0].len(), 1);
    }

    #[::core::prelude::v1::test]
    fn empty_single_and_zero_domains_stay_finite() {
        assert_eq!(value_domain(&[], None), (0., 1.));
        assert!(trace_segments(&[], (0, 0), (0., 1.)).is_empty());
        let series = vec![series(vec![sample(42, 0.)])];
        let range = value_domain(&series, None);
        assert_eq!(range, (0., 1.));
        assert_eq!(
            trace_segments(&series[0].samples, (42, 42), range)[0][0],
            ChartPoint { x: 1., y: 1. }
        );
        assert_eq!(value_domain(&series, Some((f64::NAN, 0.))), range);
    }

    #[::core::prelude::v1::test]
    fn shared_range_covers_every_series_and_keeps_temperature_negative() {
        assert_eq!(
            value_domain(
                &[series(vec![sample(0, 20.)]), series(vec![sample(0, 80.)])],
                None
            ),
            (0., 80.)
        );
        let cold =
            Sample::measured(0, Quantity::Temperature, -5., None, PhysicalUnit::Celsius).unwrap();
        let range = value_domain(&[series(vec![cold])], None);
        assert!(range.0 < -5. && range.1 > -5.);
    }

    #[::core::prelude::v1::test]
    fn ratios_clamp_but_unavailable_and_nonfinite_do_not_light_cells() {
        assert_eq!(meter_ratio(None), None);
        assert_eq!(meter_ratio(Some(f64::NAN)), None);
        assert_eq!(meter_ratio(Some(f64::INFINITY)), None);
        assert_eq!(meter_ratio(Some(-1.)), Some(0.));
        assert_eq!(meter_ratio(Some(0.)), Some(0.));
        assert_eq!(meter_ratio(Some(0.5)), Some(0.5));
        assert_eq!(meter_ratio(Some(2.)), Some(1.));
    }

    #[::core::prelude::v1::test]
    fn range_labels_convert_base_values_without_relabelling_bytes_as_gibibytes() {
        assert_eq!(
            range_label((0., 2. * 1024_f64.powi(3)), "GiB"),
            "Scale: 0.0–2.0 GiB"
        );
        assert_eq!(
            range_label((0., 3. * 1024_f64.powi(2)), "MiB/s"),
            "Scale: 0.0–3.0 MiB/s"
        );
        assert_eq!(range_label((0., 4e9), "GHz"), "Scale: 0.0–4.0 GHz");
        assert_eq!(range_label((-5., 20.), "°C"), "Scale: -5.0–20.0 °C");
    }

    #[::core::prelude::v1::test]
    fn out_of_order_samples_cannot_draw_backwards_or_claim_latest_marker() {
        let samples = vec![sample(100, 10.), sample(300, 30.), sample(200, 20.)];
        let segments = trace_segments(&samples, (100, 300), (0., 100.));
        assert_eq!(segments.len(), 1);
        assert_eq!(segments[0].len(), 2);
        assert!(latest_point(&samples, (100, 300), (0., 100.)).is_none());
    }

    #[::core::prelude::v1::test]
    fn finite_extremes_cannot_overflow_chart_coordinates() {
        let point = chart_point(&sample(100, 0.), (0, 100), (-f64::MAX, f64::MAX)).unwrap();
        assert_eq!(point, ChartPoint { x: 1., y: 0.5 });
        for value in [-f64::MAX, f64::MAX] {
            let extreme =
                Sample::measured(0, Quantity::Temperature, value, None, PhysicalUnit::Celsius)
                    .unwrap();
            let series = vec![series(vec![extreme])];
            let range = value_domain(&series, None);
            assert!(range.0.is_finite() && range.1.is_finite() && range.0 < range.1);
            assert!(
                trace_segments(&series[0].samples, (0, 0), range)[0][0]
                    .y
                    .is_finite()
            );
        }
    }
}
