use crate::{
    screen_charts::{ChartSeries, history_chart, segmented_meter},
    screen_data::{self as data, Channel},
    screen_style::{accent, empty, heading, palette, section},
    workspace::Data,
};
use gpui_kit::component::{ActiveTheme, tooltip::Tooltip};
use gpui_kit::{prelude::FluentBuilder, *};
use system_pulse_model::{PhysicalUnit, Quantity, Screen};

pub(crate) fn metric(
    id: String,
    label: String,
    value: String,
    color: Hsla,
    cx: &App,
) -> AnyElement {
    div()
        .id(SharedString::from(id.clone()))
        .role(Role::Group)
        .aria_label(label.clone())
        .flex()
        .flex_col()
        .gap_1()
        .min_w(px(135.))
        .flex_1()
        .child(
            div()
                .text_size(px(12.))
                .text_color(palette(cx).muted)
                .child(label),
        )
        .child(
            crate::meters::metric_label(id, value)
                .text_size(px(19.))
                .font_family(cx.theme().mono_font_family.clone())
                .text_color(color),
        )
        .into_any_element()
}

fn stat(channel: &Channel, state: &Data, cx: &App) -> AnyElement {
    let detail = format!(
        "{}\n{}",
        crate::meters::value(channel.latest(state)),
        channel.scope
    );
    let id = format!("screen-stat:{}", channel.sensor);
    div()
        .id(SharedString::from(id.clone()))
        .debug_selector(move || id.clone())
        .min_w(px(155.))
        .flex_1()
        .tooltip(move |window, cx| Tooltip::new(detail.clone()).build(window, cx))
        .child(metric(
            format!("screen-stat-value:{}", channel.sensor),
            channel.label.clone(),
            channel.value(state),
            palette(cx).text,
            cx,
        ))
        .into_any_element()
}

pub(crate) fn series(channel: &Channel, state: &Data, color: Hsla) -> ChartSeries {
    ChartSeries {
        label: channel.label.clone(),
        samples: channel.samples(state),
        color,
    }
}

pub(crate) fn chart(
    channel: &Channel,
    state: &Data,
    color: Hsla,
    height: f32,
    cx: &App,
) -> AnyElement {
    let range = match channel.quantity {
        Quantity::Percentage => Some((0., 100.)),
        Quantity::Capacity => channel
            .latest(state)
            .and_then(|sample| sample.total)
            .filter(|total| *total > 0.)
            .map(|total| (0., total)),
        _ => None,
    };
    history_chart(
        format!("history:{}", channel.sensor),
        vec![series(channel, state, color)],
        height,
        range,
        cx,
    )
}

pub(crate) fn hero_meter(channel: &Channel, state: &Data, screen: Screen, cx: &App) -> AnyElement {
    let color = accent(screen, cx);
    let value = channel.value(state);
    let ratio = data::current_ratio(channel, state);
    let scale_note = if matches!(channel.quantity, Quantity::Percentage | Quantity::Capacity) {
        channel.label.clone()
    } else {
        format!("{} · meter follows the observed chart range", channel.label)
    };
    div()
        .flex()
        .flex_col()
        .gap_2()
        .child(
            div()
                .flex()
                .items_center()
                .gap_4()
                .child(div().flex_1().min_w_0().child(segmented_meter(
                    format!("level:{}", channel.sensor),
                    ratio,
                    color,
                    false,
                    cx,
                )))
                .child(
                    crate::meters::metric_label(format!("hero:{}", channel.sensor), value)
                        .text_size(px(if channel.quantity == Quantity::Capacity {
                            22.
                        } else {
                            30.
                        }))
                        .font_family(cx.theme().mono_font_family.clone())
                        .text_color(color),
                ),
        )
        .child(
            div()
                .text_size(px(12.))
                .text_color(palette(cx).muted)
                .child(scale_note),
        )
        .into_any_element()
}

pub(crate) fn render(screen: Screen, state: &Data, width: f32, cx: &App) -> AnyElement {
    match screen {
        Screen::Cpu => cpu(state, width, cx),
        Screen::Memory => memory(state, cx),
        Screen::Gpu => gpu(state, width, cx),
        Screen::Disks | Screen::Network => device(screen, state, cx),
        Screen::Energy | Screen::Thermals => environmental(screen, state, width, cx),
        _ => Empty.into_any_element(),
    }
}

fn cpu(state: &Data, width: f32, cx: &App) -> AnyElement {
    let color = accent(Screen::Cpu, cx);
    let cores = data::cpu_cores(state);
    let overall = data::find(state, "cpu:host", "usage");
    let columns = ((width + 8.) / 148.).floor().clamp(1., 10.) as usize;
    let cell_width = (width - (columns - 1) as f32 * 8.) / columns as f32;
    let grid = div()
        .flex()
        .flex_wrap()
        .gap(px(8.))
        .children(cores.iter().map(|core| {
            let index = crate::dashboard::core_number(&core.sensor).unwrap_or(0);
            let clock = data::find(state, "cpu:host", &format!("core-{index}-frequency"));
            div()
                .w(px(cell_width))
                .flex_none()
                .min_w_0()
                .border_1()
                .border_color(color.opacity(0.55))
                .rounded(px(4.))
                .bg(color.opacity(0.025))
                .overflow_hidden()
                .child(
                    div()
                        .flex()
                        .items_center()
                        .justify_between()
                        .px_2()
                        .pt_1()
                        .gap_1()
                        .text_size(px(11.))
                        .child(format!("CPU {index}"))
                        .child(
                            crate::meters::metric_label(
                                format!("core-value:{index}"),
                                core.value(state),
                            )
                            .font_family(cx.theme().mono_font_family.clone())
                            .text_color(color),
                        ),
                )
                .child(chart(core, state, color, 85., cx))
                .when_some(clock, |view, clock| {
                    view.child(
                        div()
                            .px_2()
                            .pb_1()
                            .text_size(px(10.))
                            .text_color(palette(cx).muted)
                            .child(clock.value(state)),
                    )
                })
        }));
    let stats: Vec<_> = data::monitor_channels(state, "cpu:host")
        .into_iter()
        .filter(|channel| !channel.sensor.contains("/core-"))
        .collect();
    div()
        .flex()
        .flex_col()
        .gap_4()
        .when_some(overall, |view, overall| {
            view.child(hero_meter(&overall, state, Screen::Cpu, cx))
        })
        .child(div().text_sm().text_color(palette(cx).muted).child(format!(
            "Utilization by logical processor · {} charts",
            cores.len()
        )))
        .when(cores.is_empty(), |view| {
            view.child(empty(
                "No processor readings yet",
                "Processor charts appear when the host reports its first interval.",
                cx,
            ))
        })
        .child(grid)
        .child(
            div()
                .flex()
                .flex_wrap()
                .gap_4()
                .children(stats.iter().map(|channel| stat(channel, state, cx))),
        )
        .into_any_element()
}

fn memory(state: &Data, cx: &App) -> AnyElement {
    let used = data::find(state, "memory:host", "used");
    let rows = data::monitor_channels(state, "memory:host");
    if rows.is_empty() {
        return empty(
            "Memory readings unavailable",
            "Memory charts will appear when the host provides a reading.",
            cx,
        );
    }
    let color = accent(Screen::Memory, cx);
    div()
        .flex()
        .flex_col()
        .gap_4()
        .when(used.is_none(), |view| view.child(empty("RAM usage hidden or unavailable",
            "Other available memory readings are shown below. Sensor visibility is in Settings.", cx)))
        .when_some(used, |view, used| view.child(hero_meter(&used, state, Screen::Memory, cx))
            .child(section(cx).child(heading("Memory utilization", 19., cx))
                .child(chart(&used, state, color, 350., cx))))
        .when_some(
            crate::dashboard::memory_segments(&state.history),
            |view, parts| {
                view.child(
                    div()
                        .flex()
                        .flex_col()
                        .gap_2()
                        .child(
                            div()
                                .text_sm()
                                .text_color(palette(cx).muted)
                                .child("Physical memory composition"),
                        )
                        .child(
                            div().flex().gap_4().children(
                                ["Other", "Cache", "Buffers", "Free"]
                                    .into_iter()
                                    .enumerate()
                                    .map(|(index, label)| {
                                        div()
                                            .flex()
                                            .items_center()
                                            .gap_1()
                                            .text_size(px(12.))
                                            .child(
                                                div()
                                                    .size(px(8.))
                                                    .bg(color
                                                        .opacity([0.95, 0.65, 0.4, 0.16][index])),
                                            )
                                            .child(label)
                                    }),
                            ),
                        )
                        .child(
                            div()
                                .h(px(26.))
                                .w_full()
                                .flex()
                                .rounded(px(4.))
                                .overflow_hidden()
                                .children(parts.into_iter().enumerate().map(|(index, part)| {
                                    div()
                                        .h_full()
                                        .w(relative(part as f32))
                                        .flex_none()
                                        .bg(color.opacity([0.95, 0.65, 0.4, 0.16][index]))
                                })),
                        ),
                )
            },
        )
        .child(
            div()
                .flex()
                .flex_wrap()
                .gap_4()
                .children(rows.iter().map(|channel| stat(channel, state, cx))),
        )
        .into_any_element()
}

fn gpu(state: &Data, width: f32, cx: &App) -> AnyElement {
    let Some(id) = data::selected_device(state, Screen::Gpu) else {
        return empty(
            "No GPU readings available",
            "Supported GPUs appear here when their native provider reports them.",
            cx,
        );
    };
    let rows = data::gpu_channels(state, &id);
    if rows.is_empty() {
        return empty(
            "GPU unavailable",
            "The selected GPU has no available readings. Choose an available device above.",
            cx,
        );
    }
    let color = accent(Screen::Gpu, cx);
    let usage = rows
        .iter()
        .find(|channel| {
            channel.quantity == Quantity::Percentage && channel.sensor.ends_with("/usage")
        })
        .or_else(|| {
            rows.iter()
                .find(|channel| channel.quantity == Quantity::Percentage)
        });
    let capacity = rows
        .iter()
        .find(|channel| channel.quantity == Quantity::Capacity);
    let others: Vec<_> = rows
        .iter()
        .filter(|channel| {
            usage.is_none_or(|usage| usage.sensor != channel.sensor)
                && capacity.is_none_or(|capacity| capacity.sensor != channel.sensor)
        })
        .collect();
    let cell_width = if width >= 1100. {
        (width - 24.) / 3.
    } else {
        (width - 12.) / 2.
    };
    div()
        .flex()
        .flex_col()
        .gap_4()
        .when_some(usage, |view, usage| {
            view.child(hero_meter(usage, state, Screen::Gpu, cx)).child(
                section(cx)
                    .child(heading("GPU utilization", 19., cx))
                    .child(chart(usage, state, color, 260., cx)),
            )
        })
        .when_some(capacity, |view, capacity| {
            view.child(
                section(cx)
                    .id(SharedString::from(format!(
                        "gpu-capacity:{}",
                        capacity.sensor
                    )))
                    .role(Role::Group)
                    .aria_label(capacity.label.clone())
                    .child(hero_meter(capacity, state, Screen::Gpu, cx)),
            )
        })
        .child(
            div()
                .flex()
                .flex_wrap()
                .gap_3()
                .children(others.into_iter().map(|channel| {
                    section(cx)
                        .w(px(cell_width))
                        .flex_none()
                        .child(stat(channel, state, cx))
                        .child(chart(channel, state, color, 80., cx))
                })),
        )
        .into_any_element()
}

fn device(screen: Screen, state: &Data, cx: &App) -> AnyElement {
    let Some(id) = data::selected_device(state, screen) else {
        return empty(
            &format!("No {} readings available", screen.title().to_lowercase()),
            "Discovered devices will appear in the selector above.",
            cx,
        );
    };
    let rows = data::monitor_channels(state, &id);
    if rows.is_empty() {
        return empty(
            "Selected device unavailable",
            "Its saved identity is preserved. Choose an available device above.",
            cx,
        );
    }
    let color = accent(screen, cx);
    let rate_rows: Vec<_> = rows
        .iter()
        .filter(|channel| channel.unit == PhysicalUnit::BytesPerSecond)
        .collect();
    let capacity = rows.iter().find(|channel| {
        channel.quantity == Quantity::Capacity
            && channel
                .latest(state)
                .is_some_and(|sample| sample.total.is_some())
    });
    let primary = if screen == Screen::Disks {
        capacity
    } else {
        rate_rows.first().copied()
    };
    let secondary_color = accent(Screen::Thermals, cx);
    div().flex().flex_col().gap_4()
        .when_some(primary, |view, primary| view.child(hero_meter(primary, state, screen, cx)))
        .child(section(cx).child(heading(if screen == Screen::Disks { "Disk transfer rate" } else { "Network throughput" }, 19., cx))
            .child(div().flex().flex_wrap().gap_4().children(rate_rows.iter().enumerate().map(|(index, channel)| {
                metric(format!("rate:{}", channel.sensor), channel.label.clone(), channel.value(state),
                    if index == 0 { color } else { secondary_color }, cx)
            })))
            .child(history_chart(format!("device-history:{}", screen.id()), rate_rows.iter().enumerate()
                .map(|(index, channel)| series(channel, state, if index == 0 { color } else { secondary_color })).collect(),
                345., None, cx)))
        .child(div().flex().flex_wrap().gap_4().children(rows.iter().map(|channel| stat(channel, state, cx))))
        .when(screen == Screen::Disks, |view| view.child(div().text_size(px(12.)).text_color(palette(cx).muted)
            .child("Capacity describes this filesystem. Transfer rates describe its backing block device.")))
        .into_any_element()
}

fn environmental(screen: Screen, state: &Data, width: f32, cx: &App) -> AnyElement {
    let (quantity, unit) = if screen == Screen::Energy {
        (Quantity::Power, PhysicalUnit::Watts)
    } else {
        (Quantity::Temperature, PhysicalUnit::Celsius)
    };
    let rows = data::environmental_channels(state, quantity, unit);
    let selected = data::selected_channel(state, screen);
    if rows.is_empty() {
        return empty(
            if screen == Screen::Energy {
                "No power measurement available"
            } else {
                "No temperature measurement available"
            },
            "This screen uses measured sensor data. Choose an available sensor when one is reported.",
            cx,
        );
    }
    let hottest = (screen == Screen::Thermals)
        .then(|| data::highest_current(state, &rows))
        .flatten();
    let color = accent(screen, cx);
    let grid_width = if width >= 1100. {
        (width - 24.) / 3.
    } else {
        (width - 12.) / 2.
    };
    div()
        .flex()
        .flex_col()
        .gap_4()
        .when_some(hottest, |view, hottest| {
            view.child(
                div()
                    .flex()
                    .flex_wrap()
                    .items_center()
                    .gap_2()
                    .child(div().text_sm().text_color(palette(cx).muted).child(format!(
                        "Hottest current sensor · {} · {}",
                        hottest.device, hottest.label
                    )))
                    .child(
                        crate::meters::metric_label("thermal-hottest".into(), hottest.value(state))
                            .debug_selector(|| "thermal-hottest".into())
                            .text_color(color)
                            .font_family(cx.theme().mono_font_family.clone()),
                    ),
            )
        })
        .when(selected.is_none(), |view| {
            view.child(empty(
                "Selected sensor unavailable",
                "Its saved identity is preserved. Choose an available sensor above.",
                cx,
            ))
        })
        .when_some(selected, |view, selected| {
            view.child(hero_meter(&selected, state, screen, cx)).child(
                section(cx)
                    .child(heading(selected.label.clone(), 20., cx))
                    .child(
                        div()
                            .text_sm()
                            .text_color(palette(cx).muted)
                            .child(selected.device.clone()),
                    )
                    .child(
                        div()
                            .id("selected-channel-history")
                            .debug_selector(|| "selected-channel-history".into())
                            .child(chart(&selected, state, color, 260., cx)),
                    )
                    .when(!selected.scope.is_empty(), |view| {
                        view.child(
                            div()
                                .text_size(px(12.))
                                .text_color(palette(cx).muted)
                                .child(selected.scope.clone()),
                        )
                    }),
            )
        })
        .child(heading(
            if screen == Screen::Thermals {
                "Temperature sensors"
            } else {
                "Measured power channels"
            },
            24.,
            cx,
        ))
        .child(
            div()
                .flex()
                .flex_wrap()
                .gap_3()
                .children(rows.iter().map(|channel| {
                    section(cx)
                        .w(px(grid_width))
                        .flex_none()
                        .border_color(color.opacity(0.4))
                        .child(
                            div()
                                .text_size(px(12.))
                                .text_color(palette(cx).muted)
                                .child(channel.device.clone()),
                        )
                        .child(stat(channel, state, cx))
                        .when_some(
                            channel
                                .latest(state)
                                .and_then(|sample| sample.reason.clone()),
                            |view, reason| {
                                let id = format!("sensor-availability:{}", channel.sensor);
                                view.child(
                                    div()
                                        .debug_selector(move || id.clone())
                                        .text_sm()
                                        .text_color(palette(cx).muted)
                                        .child(reason),
                                )
                            },
                        )
                        .child(chart(channel, state, color, 95., cx))
                })),
        )
        .into_any_element()
}
