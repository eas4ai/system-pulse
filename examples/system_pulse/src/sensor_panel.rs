//! Dense sensor rows and contiguous physical CPU core tiles.
use super::*;
use system_pulse_model::{Meter, ReadingStatus, Sample, SensorDescriptor, SensorState};

impl MonitorPanel {
    pub(super) fn sensor_rows(&mut self, cx: &mut Context<Self>) -> AnyElement {
        let data = self.shared.borrow();
        let panel = &data.session.workspace.panels[&self.monitor.id];
        // Availability filters presentation only. Keep collection and the user's
        // visibility, order, collapse and meter preferences intact for recovery.
        let display_sample = |sensor: &str| {
            data.history
                .latest(&self.monitor.id, sensor)
                .filter(|sample| sample.status != ReadingStatus::Unavailable)
        };
        let mut rows = Vec::new();
        if let Some(hero) = crate::dashboard::hero(&self.monitor, &data.history, cx) {
            rows.push(hero);
        }
        if self.monitor.id == "memory:host" {
            rows.push(crate::dashboard::memory_composition(&data.history, cx));
        }
        let mut cores = Vec::new();
        for (sensor, state) in panel.visible_sensors() {
            let Some(descriptor) = self.monitor.sensors.iter().find(|s| s.id == sensor) else {
                continue;
            };
            let Some(sample) = display_sample(sensor) else {
                continue;
            };
            let actual_meter = descriptor.quantity.compatible(state.meter);
            let samples = if !state.collapsed && actual_meter != Meter::Number {
                data.history
                    .samples(&self.monitor.id, sensor)
                    .map(|s| s.iter().cloned().collect())
                    .unwrap_or_default()
            } else {
                Vec::new()
            };
            let core = (self.monitor.id == "cpu:host")
                .then(|| crate::dashboard::core_number(sensor))
                .flatten();
            let row = self.sensor_row(descriptor, state, sample, samples, core, cx);
            if core.is_some() {
                cores.push(row);
            } else {
                flush_cores(&mut rows, &mut cores);
                rows.push(row);
            }
        }
        flush_cores(&mut rows, &mut cores);
        for descriptor in &self.monitor.sensors {
            if display_sample(&descriptor.id).is_none() {
                continue;
            }
            if panel
                .sensors
                .get(&descriptor.id)
                .is_some_and(|s| !s.visible)
            {
                rows.push(self.control(
                    &format!("visible:{}", descriptor.id),
                    format!("Show {}", descriptor.title),
                    None,
                    Command::SensorVisible(self.monitor.id.clone(), descriptor.id.clone()),
                    true,
                    cx,
                ));
            }
        }
        div()
            .size_full()
            .relative()
            .child(
                crate::workspace::scroll_viewport(
                    "sensor-scroll",
                    format!("{}:viewport", self.monitor.id),
                )
                .size_full()
                .overflow_y_scroll()
                .track_scroll(&self.body_scroll)
                .child(div().flex().flex_col().children(rows)),
            )
            .child(ScrollableMask::new(Axis::Vertical, &self.body_scroll))
            .child(Scrollbar::vertical(&self.body_scroll).mode(ScrollbarMode::Always))
            .into_any_element()
    }

    fn sensor_row(
        &self,
        descriptor: &SensorDescriptor,
        state: &SensorState,
        sample: &Sample,
        samples: Vec<Sample>,
        core: Option<u32>,
        cx: &App,
    ) -> AnyElement {
        let id = self.monitor.id.clone();
        let sensor = descriptor.id.clone();
        let actual_meter = descriptor.quantity.compatible(state.meter);
        let selector = format!("{id}:meter-body:{sensor}");
        let current = meters::sensor_label(&self.monitor, descriptor, sample);
        let tooltip = current.clone();
        let value_selector = format!("{id}:value:{sensor}");
        let value = meters::metric_text(
            format!("{id}:value:{sensor}"),
            current,
            meters::value(Some(sample)),
        )
        .font_family(cx.theme().mono_font_family.clone())
        .text_sm()
        .min_w_0()
        .overflow_hidden()
        .text_ellipsis()
        .debug_selector(move || value_selector.clone().into())
        .tooltip(move |window, cx| {
            gpui_component::tooltip::Tooltip::new(tooltip.clone()).build(window, cx)
        })
        .when(
            core.is_some() && !state.collapsed && actual_meter == Meter::Number,
            |value| {
                let selector = selector.clone();
                value.debug_selector(move || selector.clone().into())
            },
        );
        let disclosure = self.control(
            &format!("row:{sensor}"),
            format!(
                "{} {}",
                if state.collapsed {
                    "Expand"
                } else {
                    "Collapse"
                },
                descriptor.title
            ),
            Some(!state.collapsed),
            Command::RowCollapse(id.clone(), sensor.clone()),
            true,
            cx,
        );
        let options =
            crate::panel_context::sensor_button(id.clone(), sensor.clone(), self.shared.clone());
        let mut row = div()
            .id(SharedString::from(format!("sensor-row:{id}:{sensor}")))
            .flex()
            .flex_col()
            .gap_1()
            .px_2()
            .py_1()
            .border_b_1()
            .border_color(cx.theme().border);
        if let Some(core) = core {
            row = row
                .w(px(112.))
                .flex_none()
                .rounded_sm()
                .border_1()
                .debug_selector(move || format!("cpu:core:{core}").into())
                .child(
                    div()
                        .flex()
                        .items_center()
                        .gap_1()
                        .child(disclosure)
                        .child(options),
                )
                .child(value)
                .when(!state.collapsed && actual_meter == Meter::Number, |row| {
                    row.child(div().h_1().w_full().bg(cx.theme().muted).when_some(
                        sample.chart_value(),
                        |bar, value| {
                            bar.child(
                                div()
                                    .h_full()
                                    .w(relative((value / 100.).clamp(0., 1.) as f32))
                                    .bg(cx.theme().primary),
                            )
                        },
                    ))
                });
        } else {
            row = row.child(
                div()
                    .flex()
                    .items_center()
                    .gap_1()
                    .child(disclosure)
                    .child(value)
                    .child(self.control(
                        &format!("meter:{sensor}"),
                        if state.meter == actual_meter {
                            format!("Meter: {actual_meter:?}")
                        } else {
                            format!(
                                "Meter: {actual_meter:?} · saved {:?} incompatible",
                                state.meter
                            )
                        },
                        None,
                        Command::Meter(id.clone(), sensor.clone()),
                        true,
                        cx,
                    ))
                    .child(options)
                    .child(self.control(
                        &format!("visible:{sensor}"),
                        format!("Hide {}", descriptor.title),
                        None,
                        Command::SensorVisible(id.clone(), sensor.clone()),
                        true,
                        cx,
                    )),
            );
        }
        row.when(
            !state.collapsed && (actual_meter != Meter::Number || core.is_none()),
            |row| {
                row.child(div().debug_selector(move || selector.clone().into()).child(
                    if actual_meter == Meter::Number {
                        div()
                            .px_2()
                            .py_2()
                            .text_lg()
                            .font_family(cx.theme().mono_font_family.clone())
                            .child(meters::value(Some(sample)))
                            .into_any_element()
                    } else {
                        meters::meter(actual_meter, samples, descriptor.unit, cx)
                    },
                ))
            },
        )
        .context_menu({
            let shared = self.shared.clone();
            move |menu, _, _| crate::panel_context::sensors(menu, &id, &sensor, &shared)
        })
        .into_any_element()
    }
}

fn flush_cores(rows: &mut Vec<AnyElement>, cores: &mut Vec<AnyElement>) {
    if !cores.is_empty() {
        rows.push(
            div()
                .px_3()
                .pt_2()
                .text_sm()
                .child("Logical processors")
                .into_any_element(),
        );
        rows.push(
            div()
                .flex()
                .flex_wrap()
                .gap_2()
                .p_2()
                .children(std::mem::take(cores))
                .into_any_element(),
        );
    }
}
