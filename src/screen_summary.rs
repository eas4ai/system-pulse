use crate::{
    screen_charts::segmented_meter,
    screen_data::{self as data, Channel},
    screen_pages::chart,
    screen_style::{accent, heading, palette, section},
    workspace::Data,
};
use gpui_kit::component::{ActiveTheme, tooltip::Tooltip};
use gpui_kit::{prelude::FluentBuilder, *};
use system_pulse_model::{PhysicalUnit, Quantity, Screen};

fn mini_level(
    label: &str,
    channel: Option<&Channel>,
    state: &Data,
    screen: Screen,
    cx: &App,
) -> AnyElement {
    let color = accent(screen, cx);
    div()
        .id(SharedString::from(format!("summary-meter:{label}")))
        .flex()
        .flex_col()
        .gap_2()
        .items_center()
        .flex_1()
        .min_w_0()
        .tooltip({
            let detail = channel
                .map(|channel| {
                    format!(
                        "{} · {}{}",
                        channel.device,
                        channel.label,
                        if matches!(channel.quantity, Quantity::Percentage | Quantity::Capacity) {
                            ""
                        } else {
                            " · level follows the observed chart range"
                        }
                    )
                })
                .unwrap_or_else(|| "No available sensor".into());
            move |window, cx| Tooltip::new(detail.clone()).build(window, cx)
        })
        .child(
            div()
                .text_size(px(11.))
                .font_weight(FontWeight::SEMIBOLD)
                .text_color(color)
                .child(label.to_owned()),
        )
        .child(
            segmented_meter(
                format!("summary-level:{label}"),
                channel.and_then(|channel| data::current_ratio(channel, state)),
                color,
                true,
                cx,
            )
            .h(px(150.)),
        )
        .child(
            div()
                .text_size(px(11.))
                .font_family(cx.theme().mono_font_family.clone())
                .text_color(color)
                .text_center()
                .child(
                    channel
                        .map(|channel| channel.value(state))
                        .unwrap_or_else(|| "—".into()),
                ),
        )
        .into_any_element()
}

fn subsystem(
    title: &str,
    screen: Screen,
    channel: Option<Channel>,
    state: &Data,
    width: f32,
    cx: &App,
) -> AnyElement {
    let color = accent(screen, cx);
    let label = channel
        .as_ref()
        .map(|channel| channel.value(state))
        .unwrap_or_else(|| "Unavailable".into());
    let detail = channel
        .as_ref()
        .map(|channel| channel.device.clone())
        .unwrap_or_else(|| "No available sensor".into());
    let ratio = channel
        .as_ref()
        .and_then(|channel| data::current_ratio(channel, state));
    section(cx)
        .gap_2()
        .p_2()
        .w(px(width))
        .flex_none()
        .border_color(color.opacity(0.4))
        .bg(color.opacity(0.055))
        .child(
            div()
                .flex()
                .items_center()
                .justify_between()
                .gap_2()
                .child(heading(title.to_owned(), 19., cx))
                .child(
                    crate::meters::metric_label(format!("summary-value:{}", screen.id()), label)
                        .font_family(cx.theme().mono_font_family.clone())
                        .text_size(px(16.))
                        .text_color(color),
                ),
        )
        .child(
            div()
                .text_size(px(11.))
                .text_color(palette(cx).muted)
                .overflow_hidden()
                .text_ellipsis()
                .child(detail),
        )
        .child(segmented_meter(
            format!("summary-strip:{}", screen.id()),
            ratio,
            color,
            false,
            cx,
        ))
        .into_any_element()
}

pub(crate) fn render(state: &Data, width: f32, cx: &App) -> AnyElement {
    let cpu = data::find(state, "cpu:host", "usage");
    let clock = data::highest_current(
        state,
        &data::monitor_channels(state, "cpu:host")
            .into_iter()
            .filter(|channel| {
                channel.quantity == Quantity::Frequency && channel.unit == PhysicalUnit::Hertz
            })
            .collect::<Vec<_>>(),
    );
    let temperature = data::highest_current(
        state,
        &data::by_quantity(state, Quantity::Temperature, PhysicalUnit::Celsius),
    );
    let gpu =
        data::selected_device(state, Screen::Gpu).and_then(|id| data::find(state, &id, "usage"));
    let levels = section(cx)
        .gap_2()
        .w(px(205.))
        .flex_none()
        .child(div().flex().gap_2().children([
            mini_level("CPU", cpu.as_ref(), state, Screen::Cpu, cx),
            mini_level("Clock", clock.as_ref(), state, Screen::Thermals, cx),
            mini_level("Temp", temperature.as_ref(), state, Screen::Energy, cx),
            mini_level("GPU", gpu.as_ref(), state, Screen::Gpu, cx),
        ]));
    let top_width = if width >= 1100. {
        (width - 229.) * 0.52
    } else {
        width - 217.
    };
    let cpu_color = accent(Screen::Cpu, cx);
    let overview = section(cx)
        .gap_2()
        .w(px(top_width))
        .flex_none()
        .child(
            div()
                .flex()
                .items_center()
                .justify_between()
                .child(heading("CPU overview", 20., cx))
                .child(
                    crate::meters::metric_label(
                        "summary-cpu".into(),
                        cpu.as_ref()
                            .map(|channel| channel.value(state))
                            .unwrap_or_else(|| "Waiting".into()),
                    )
                    .text_size(px(24.))
                    .font_family(cx.theme().mono_font_family.clone())
                    .text_color(cpu_color),
                ),
        )
        .when_some(cpu, |view, cpu| {
            view.child(chart(&cpu, state, cpu_color, 150., cx))
        })
        .child(
            div()
                .text_size(px(12.))
                .text_color(palette(cx).muted)
                .child(format!(
                    "{} logical processor charts",
                    data::cpu_cores(state).len()
                )),
        );
    let process_width = if width >= 1100. {
        width - 229. - top_width
    } else {
        width
    };
    let mut top_processes: Vec<_> = state.processes.iter().collect();
    top_processes.sort_by(|a, b| {
        b.numeric[0]
            .unwrap_or(-1.)
            .total_cmp(&a.numeric[0].unwrap_or(-1.))
            .then_with(|| a.identity.cmp(&b.identity))
    });
    let processes =
        section(cx)
            .gap_2()
            .w(px(process_width))
            .flex_none()
            .child(
                div()
                    .flex()
                    .items_center()
                    .justify_between()
                    .gap_2()
                    .child(heading("Top CPU processes", 18., cx))
                    .child(
                        div()
                            .text_size(px(11.))
                            .text_color(palette(cx).muted)
                            .child(format!("{} total", state.processes.len())),
                    ),
            )
            .child(
                div()
                    .flex()
                    .px_1()
                    .gap_2()
                    .text_size(px(11.))
                    .text_color(palette(cx).muted)
                    .child(
                        div()
                            .w(px(68.))
                            .flex_none()
                            .whitespace_nowrap()
                            .child("PID"),
                    )
                    .child(div().flex_1().child("Name"))
                    .child(div().w(px(62.)).text_right().child("CPU")),
            )
            .child(
                div().flex().flex_col().children(
                    top_processes
                        .into_iter()
                        .take(8)
                        .enumerate()
                        .map(|(index, row)| {
                            let cpu = row.cells.get(2).cloned().unwrap_or_default();
                            div()
                                .flex()
                                .items_center()
                                .gap_2()
                                .px_1()
                                .h(px(23.))
                                .text_size(px(12.))
                                .when(index % 2 == 0, |view| view.bg(cpu_color.opacity(0.075)))
                                .child(
                                    div()
                                        .w(px(68.))
                                        .flex_none()
                                        .whitespace_nowrap()
                                        .font_family(cx.theme().mono_font_family.clone())
                                        .child(row.identity.pid.to_string()),
                                )
                                .child(
                                    div()
                                        .flex_1()
                                        .min_w_0()
                                        .overflow_hidden()
                                        .text_ellipsis()
                                        .child(row.cells.get(1).cloned().unwrap_or_default()),
                                )
                                .child(
                                    div()
                                        .w(px(80.))
                                        .flex_none()
                                        .overflow_hidden()
                                        .text_ellipsis()
                                        .text_right()
                                        .text_color(cpu_color)
                                        .child(cpu),
                                )
                        }),
                ),
            );
    let memory = data::find(state, "memory:host", "used");
    let memory_color = accent(Screen::Memory, cx);
    let memory_section = section(cx)
        .gap_2()
        .child(
            div()
                .flex()
                .items_center()
                .justify_between()
                .gap_2()
                .child(heading("Memory utilization", 23., cx))
                .child(
                    crate::meters::metric_label(
                        "summary-memory".into(),
                        memory
                            .as_ref()
                            .map(|channel| channel.value(state))
                            .unwrap_or_else(|| "Waiting".into()),
                    )
                    .text_size(px(19.))
                    .text_color(memory_color)
                    .font_family(cx.theme().mono_font_family.clone()),
                ),
        )
        .when_some(memory, |view, memory| {
            view.child(
                div()
                    .flex()
                    .gap_3()
                    .child(
                        segmented_meter(
                            "summary-memory-level",
                            data::current_ratio(&memory, state),
                            memory_color,
                            true,
                            cx,
                        )
                        .h(px(105.))
                        .gap(px(1.)),
                    )
                    .child(div().flex_1().min_w_0().child(chart(
                        &memory,
                        state,
                        memory_color,
                        105.,
                        cx,
                    ))),
            )
        })
        .child(
            div().flex().flex_wrap().gap_3().children(
                ["available", "cache", "swap"]
                    .into_iter()
                    .filter_map(|suffix| {
                        let channel = data::find(state, "memory:host", suffix)?;
                        Some(
                            div()
                                .flex_1()
                                .min_w_0()
                                .flex()
                                .gap_2()
                                .text_size(px(12.))
                                .child(
                                    div()
                                        .text_color(palette(cx).muted)
                                        .child(channel.label.clone()),
                                )
                                .child(crate::meters::metric_label(
                                    format!("summary-memory:{suffix}"),
                                    channel.value(state),
                                )),
                        )
                    }),
            ),
        );
    let tile_width = (width - 24.) / 3.;
    let disk = data::selected_device(state, Screen::Disks)
        .and_then(|id| data::find(state, &id, "capacity"));
    let network =
        data::selected_device(state, Screen::Network).and_then(|id| data::find(state, &id, "rx"));
    let power = data::selected_channel(state, Screen::Energy);
    let gpu =
        data::selected_device(state, Screen::Gpu).and_then(|id| data::find(state, &id, "usage"));
    div()
        .flex()
        .flex_col()
        .gap_3()
        .child(
            div()
                .flex()
                .flex_wrap()
                .gap_3()
                .child(levels)
                .child(overview)
                .child(processes),
        )
        .child(memory_section)
        .child(div().flex().flex_wrap().gap_3().children([
            subsystem("Disks", Screen::Disks, disk, state, tile_width, cx),
            subsystem("Network", Screen::Network, network, state, tile_width, cx),
            subsystem("Energy", Screen::Energy, power, state, tile_width, cx),
            subsystem("GPU", Screen::Gpu, gpu, state, tile_width, cx),
            subsystem(
                "Thermals",
                Screen::Thermals,
                temperature,
                state,
                tile_width,
                cx,
            ),
        ]))
        .into_any_element()
}
