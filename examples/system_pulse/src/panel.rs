use crate::{
    controls::{self, FocusEntry},
    live, meters,
    workspace::{Command, Shared},
};
use gpui::{prelude::FluentBuilder, *};
use gpui_base::{
    ElementExt, ScrollableMask, Scrollbar, ScrollbarMode, Table, TableCell, TableRow,
    VirtualListScrollHandle, dock::*, v_virtual_list,
};
use gpui_component::ActiveTheme;
use std::{collections::BTreeMap, rc::Rc, sync::Arc};
use system_pulse_collectors::ProcessIdentity;
use system_pulse_model::MonitorDescriptor as Monitor;

pub(crate) struct MonitorPanel {
    pub(crate) monitor: Monitor,
    pub(crate) shared: Shared,
    pub(crate) group: Option<WeakEntity<TabGroup>>,
    pub(crate) focus: FocusHandle,
    pub(crate) controls: BTreeMap<String, FocusEntry>,
    body_scroll: ScrollHandle,
    table_scroll: VirtualListScrollHandle,
    pub(crate) selected: Option<ProcessIdentity>,
    table_horizontal: ScrollHandle,
    keyboard_repaint_pending: bool,
}

impl MonitorPanel {
    pub(crate) fn new(monitor: Monitor, shared: Shared, cx: &mut Context<Self>) -> Self {
        let mut controls = BTreeMap::new();
        for key in ["collapse", "close", "table"] {
            controls.insert(key.into(), FocusEntry::new(cx));
        }
        for sensor in &monitor.sensors {
            let id = &sensor.id;
            for verb in ["row", "visible", "meter"] {
                controls.insert(format!("{verb}:{id}"), FocusEntry::new(cx));
            }
        }
        Self {
            monitor,
            shared,
            group: None,
            focus: cx.focus_handle(),
            controls,
            body_scroll: ScrollHandle::default(),
            table_scroll: VirtualListScrollHandle::new(),
            selected: None,
            table_horizontal: ScrollHandle::default(),
            keyboard_repaint_pending: false,
        }
    }

    pub(crate) fn refresh(&mut self, monitor: Monitor, cx: &mut Context<Self>) {
        for sensor in &monitor.sensors {
            for verb in ["row", "visible", "meter"] {
                self.controls
                    .entry(format!("{verb}:{}", sensor.id))
                    .or_insert_with(|| FocusEntry::new(cx));
            }
        }
        self.monitor = monitor;
    }
    pub(crate) fn selected_index(&self) -> Option<usize> {
        self.selected.as_ref().and_then(|selected| {
            self.shared
                .borrow()
                .processes
                .iter()
                .position(|row| &row.identity == selected)
        })
    }

    fn control(
        &self,
        key: &str,
        label: String,
        expanded: Option<bool>,
        command: Command,
        body: bool,
        cx: &App,
    ) -> AnyElement {
        controls::button(
            label,
            expanded,
            &self.controls[key],
            &self.shared,
            command,
            body.then(|| self.body_scroll.clone()),
            cx,
        )
        .into_any_element()
    }

    pub(crate) fn header(
        &mut self,
        group: &TabGroupContext,
        _: &mut Window,
        cx: &mut Context<Self>,
    ) -> AnyElement {
        let data = self.shared.borrow();
        let collapsed = data.session.workspace.panels[&self.monitor.id].collapsed;
        let title = meters::summary(&self.monitor, &data.history);
        drop(data);
        let drag = group
            .is_draggable()
            .then(|| group.drag_panel(0, cx))
            .flatten();
        let preview = title.clone();
        div()
            .flex()
            .items_center()
            .gap_1()
            .h(px(36.))
            .flex_none()
            .bg(cx.theme().muted)
            .border_b_1()
            .border_color(cx.theme().border)
            .child(self.control(
                "collapse",
                format!(
                    "{} {}",
                    if collapsed { "Expand" } else { "Collapse" },
                    self.monitor.title
                ),
                Some(!collapsed),
                Command::PanelCollapse(self.monitor.id.clone()),
                false,
                cx,
            ))
            .child(
                meters::metric_label(format!("{}:summary", self.monitor.id), title)
                    .flex_1()
                    .min_w_0()
                    .overflow_hidden()
                    .when_some(drag, |el, drag| {
                        el.on_drag(drag, move |drag, offset, _, cx| {
                            cx.stop_propagation();
                            drag.set_drag_offset(offset);
                            cx.new(|_| DragPreview(preview.clone()))
                        })
                    }),
            )
            .child(self.control(
                "close",
                format!("Hide {}", self.monitor.title),
                None,
                Command::PanelVisible(self.monitor.id.clone()),
                false,
                cx,
            ))
            .into_any_element()
    }

    fn sensor_rows(&mut self, cx: &mut Context<Self>) -> AnyElement {
        let data = self.shared.borrow();
        let panel = data.session.workspace.panels[&self.monitor.id].clone();
        let mut rows = Vec::new();
        for (sensor, state) in panel.visible_sensors() {
            let Some(descriptor) = self.monitor.sensors.iter().find(|s| s.id == sensor) else {
                continue;
            };
            let label = &descriptor.title;
            let absent = live::missing(
                descriptor.quantity,
                descriptor.unit,
                "Sensor or device absent",
                0,
            );
            let current = meters::sensor_label(
                &self.monitor,
                descriptor,
                data.history
                    .latest(&self.monitor.id, sensor)
                    .unwrap_or(&absent),
            );
            let actual_meter = descriptor.quantity.compatible(state.meter);
            let samples = if state.collapsed {
                Vec::new()
            } else if actual_meter == system_pulse_model::Meter::Number {
                data.history
                    .latest(&self.monitor.id, sensor)
                    .cloned()
                    .into_iter()
                    .collect()
            } else {
                data.history
                    .samples(&self.monitor.id, sensor)
                    .map(|s| s.iter().cloned().collect())
                    .unwrap_or_default()
            };
            let id = self.monitor.id.to_owned();
            let sensor = sensor.to_owned();
            let selector = format!("{}:meter-body:{sensor}", self.monitor.id);
            let row = div()
                .flex()
                .flex_col()
                .gap_1()
                .p_2()
                .child(
                    div()
                        .flex()
                        .items_center()
                        .gap_1()
                        .child(self.control(
                            &format!("row:{sensor}"),
                            format!(
                                "{} {label}",
                                if state.collapsed {
                                    "Expand"
                                } else {
                                    "Collapse"
                                }
                            ),
                            Some(!state.collapsed),
                            Command::RowCollapse(id.clone(), sensor.clone()),
                            true,
                            cx,
                        ))
                        .child(
                            meters::metric_label(
                                format!("{}:value:{sensor}", self.monitor.id),
                                current,
                            )
                            .flex_1(),
                        )
                        .child(self.control(
                            &format!("visible:{sensor}"),
                            format!("Hide {label}"),
                            None,
                            Command::SensorVisible(id.clone(), sensor.clone()),
                            true,
                            cx,
                        )),
                )
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
                    Command::Meter(id, sensor),
                    true,
                    cx,
                ))
                .when(!state.collapsed, |row| {
                    row.child(
                        div()
                            .debug_selector(move || selector.clone().into())
                            .child(meters::meter(actual_meter, samples, descriptor.unit, cx)),
                    )
                });
            rows.push(row.into_any_element());
        }
        for descriptor in &self.monitor.sensors {
            let sensor = &descriptor.id;
            let label = &descriptor.title;
            if panel.sensors.get(sensor).is_some_and(|s| !s.visible) {
                rows.push(self.control(
                    &format!("visible:{sensor}"),
                    format!("Show {label}"),
                    None,
                    Command::SensorVisible(self.monitor.id.clone(), sensor.clone()),
                    true,
                    cx,
                ));
            }
        }
        drop(data);
        div()
            .size_full()
            .relative()
            .child(
                div()
                    .id("sensor-scroll")
                    .size_full()
                    .overflow_y_scroll()
                    .track_scroll(&self.body_scroll)
                    .child(div().flex().flex_col().children(rows)),
            )
            .child(ScrollableMask::new(Axis::Vertical, &self.body_scroll))
            .child(Scrollbar::vertical(&self.body_scroll).mode(ScrollbarMode::Always))
            .into_any_element()
    }

    fn request_keyboard_repaint(&mut self, window: &mut Window, cx: &Context<Self>) {
        if self.keyboard_repaint_pending {
            return;
        }
        self.keyboard_repaint_pending = true;
        // Dirtying this event makes GPUI redraw before the next queued key,
        // which can starve live snapshot delivery during ordinary key repeat.
        cx.on_next_frame(window, |this, window, cx| {
            this.keyboard_repaint_pending = false;
            window.refresh();
            cx.notify();
        });
    }

    fn process_table(&mut self, window: &Window, cx: &mut Context<Self>) -> AnyElement {
        let handle = self.controls["table"].handle.clone();
        let ring = cx.theme().ring;
        let count = self.shared.borrow().processes.len();
        let widths = self.shared.borrow().process_widths;
        let width: f32 = widths.iter().sum();
        let sizes = Rc::new(vec![size(px(width), window.rem_size() * 1.75); count]);
        let list = v_virtual_list(cx.entity(), "process-rows", sizes, |this, range, _, cx| {
            let data = this.shared.borrow();
            range
                .filter_map(|index| {
                    let process = data.processes.get(index)?;
                    Some(process_row(
                        process,
                        index,
                        this.selected.as_ref() == Some(&process.identity),
                        &data.process_widths,
                        cx,
                    ))
                })
                .collect()
        })
        .track_scroll(&self.table_scroll);
        let outer = self.shared.borrow().scroll.clone();
        let focus = self.controls["table"].clone();
        let horizontal = self.table_horizontal.clone();
        div().id("process-table-viewport").size_full().relative().track_focus(&handle)
            .border_1().border_color(cx.theme().border).focus_visible(move |style| style.border_color(ring))
            .debug_selector(|| "process-table".into())
            .on_key_down(cx.listener(|this, event: &KeyDownEvent, window, cx| {
                if event.keystroke.modifiers.alt { return; }
                if matches!(event.keystroke.key.as_str(), "left" | "right") {
                    let old = this.table_horizontal.offset();
                    let delta = if event.keystroke.key == "left" { 240. } else { -240. };
                    this.table_horizontal.set_offset(point((old.x + px(delta)).clamp(-this.table_horizontal.max_offset().x, px(0.)), old.y));
                    this.request_keyboard_repaint(window, cx); cx.stop_propagation(); return;
                }
                let count = this.shared.borrow().processes.len();
                if count == 0 { return; }
                let current = this.selected_index();
                let next = match event.keystroke.key.as_str() {
                    "up" => current.unwrap_or(0).saturating_sub(1),
                    "down" => current.map_or(0, |i| (i + 1).min(count - 1)),
                    "home" => 0, "end" => count - 1, _ => return,
                };
                this.selected = Some(this.shared.borrow().processes[next].identity.clone());
                this.table_scroll.scroll_to_item(next, ScrollStrategy::Top);
                controls::reveal(this.table_scroll.base_handle().bounds().dilate(px(1.)), &this.shared.borrow().scroll);
                this.request_keyboard_repaint(window, cx); cx.stop_propagation();
            }))
            .on_prepaint(move |bounds, window, _| {
                if focus.entered(window) { controls::reveal(bounds.dilate(px(1.)), &outer); window.refresh(); }
            })
            .child(div().id("process-horizontal").size_full().overflow_x_scroll().track_scroll(&horizontal)
                .child(Table::new("process-table").row_count(count + 1).column_count(8)
                    .accessibility_label(format!("{count} readable process rows; arrows navigate and scroll columns; Tab leaves table"))
                    .w(px(width)).h_full().flex().flex_col()
                    .child(TableRow::new("process-columns", 1).flex().h_7().flex_none()
                        .children(live::PROCESS_COLUMNS.iter().enumerate().map(|(column, title)| {
                            TableCell::new(("process-heading", column), column + 1).role(Role::ColumnHeader)
                                .aria_label((*title).to_owned()).w(px(widths[column])).flex_none().child(*title)
                        })))
                    .child(div().flex_1().min_h_0().child(list))))
            .child(ScrollableMask::new(Axis::Vertical, self.table_scroll.base_handle()))
            .child(Scrollbar::vertical(&self.table_scroll).mode(ScrollbarMode::Always))
            .child(Scrollbar::horizontal(&horizontal).mode(ScrollbarMode::Always))
            .into_any_element()
    }
}

pub(crate) fn process_cell(process: &live::ProcessView, column: usize, width: f32) -> TableCell {
    let cell_id = format!(
        "process:{}:{}:cell:{column}",
        process.identity.pid, process.identity.start_time_ticks
    );
    TableCell::new(SharedString::from(cell_id.clone()), column + 1)
        .accessibility_id(cell_id)
        .aria_label(process.cells[column].clone())
        .w(px(width))
        .flex_none()
        .overflow_hidden()
        .child(process.cells[column].clone())
}

pub(crate) fn process_row(
    process: &live::ProcessView,
    index: usize,
    selected: bool,
    widths: &[f32; 8],
    cx: &App,
) -> TableRow {
    let stable_id = format!(
        "process:{}:{}",
        process.identity.pid, process.identity.start_time_ticks
    );
    TableRow::new(SharedString::from(stable_id.clone()), index + 2)
        .accessibility_id(stable_id)
        .flex()
        .h_7()
        .aria_selected(selected)
        .when(selected, |row| row.bg(cx.theme().muted))
        .debug_selector(move || format!("process-row:{index}").into())
        .children(
            process
                .cells
                .iter()
                .enumerate()
                .map(|(column, _)| process_cell(process, column, widths[column])),
        )
}

impl Panel for MonitorPanel {
    fn panel_name(&self) -> &'static str {
        "SystemPulseMonitor"
    }
    fn visible(&self, _: &App) -> bool {
        let data = self.shared.borrow();
        data.session
            .workspace
            .panels
            .get(&self.monitor.id)
            .is_some_and(|s| s.visible)
            && data.catalog.iter().any(|m| m.id == self.monitor.id)
    }
    fn zoomable(&self, _: &App) -> bool {
        false
    }
    fn dock_extent(&self, _: &App) -> Option<PanelExtent> {
        let data = self.shared.borrow();
        let p = &data.session.workspace.panels[&self.monitor.id];
        let extent = PanelExtent::new(
            size(px(320.), px(220.)),
            size(px(p.expanded_size.width), px(p.expanded_size.height)),
        );
        Some(if p.collapsed {
            extent.collapsed(px(36.))
        } else {
            extent
        })
    }
    fn on_added_to(&mut self, group: WeakEntity<TabGroup>, _: &mut Window, _: &mut Context<Self>) {
        self.group = Some(group);
    }
    fn dump(&self, _: &App) -> PanelState {
        let mut state = PanelState::new("SystemPulseMonitor");
        state.info = PanelInfo::panel(serde_json::json!({ "monitor_id": self.monitor.id }));
        state
    }
}
impl EventEmitter<PanelEvent> for MonitorPanel {}
impl Focusable for MonitorPanel {
    fn focus_handle(&self, _: &App) -> FocusHandle {
        self.focus.clone()
    }
}
impl Render for MonitorPanel {
    fn render(&mut self, window: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        if self.shared.borrow().session.workspace.panels[&self.monitor.id].collapsed {
            return Empty.into_any_element();
        }
        let content = match self.monitor.id.as_str() {
            "processes" => self.process_table(window, cx),
            "settings" => div().p_3().child("Choose the global sampling interval and panel visibility above. Sensor meters use physical units. CPU process percentages use one core and may exceed 100%.").into_any_element(),
            _ => self.sensor_rows(cx),
        };
        div()
            .size_full()
            .track_focus(&self.focus)
            .child(content)
            .into_any_element()
    }
}

struct DragPreview(String);
impl Render for DragPreview {
    fn render(&mut self, _: &mut Window, _: &mut Context<Self>) -> impl IntoElement {
        div().p_2().child(self.0.clone())
    }
}

#[derive(Clone)]
pub(crate) struct WorkspaceSkin(pub(crate) Shared);
impl TabGroupRenderer for WorkspaceSkin {
    fn frame(&self, group: &TabGroupContext, _: &mut Window, cx: &mut App) -> Stateful<Div> {
        let id = group
            .active_panel()
            .and_then(|p| p.view().downcast::<MonitorPanel>().ok())
            .map(|p| p.read(cx).monitor.id.to_owned());
        let shared = self.0.clone();
        let selector = id.clone().unwrap_or_else(|| "empty".into());
        div()
            .id(("monitor-region", group.node().as_u64()))
            .role(Role::Group)
            .aria_label(selector.clone())
            .debug_selector(move || format!("panel:{selector}").into())
            .bg(cx.theme().background)
            .on_prepaint(move |bounds, _, _| {
                if let Some(id) = &id {
                    shared.borrow_mut().bounds.insert(id.clone(), bounds);
                }
            })
    }
    fn render_tab_bar(
        &self,
        group: &TabGroupContext,
        window: &mut Window,
        cx: &mut App,
    ) -> AnyElement {
        match group
            .active_panel()
            .and_then(|p| p.view().downcast::<MonitorPanel>().ok())
        {
            Some(panel) => panel.update(cx, |panel, cx| panel.header(group, window, cx)),
            None => Empty.into_any_element(),
        }
    }
    fn render_active_panel(
        &self,
        panel: AnyView,
        _: &TabGroupContext,
        _: &mut Window,
        _: &mut App,
    ) -> AnyElement {
        div().size_full().child(panel).into_any_element()
    }
}
impl TilesRenderer for WorkspaceSkin {
    fn render_drag_bar(&self, _: &TileContext, _: &mut Window, _: &mut App) -> AnyElement {
        Empty.into_any_element()
    }
}
impl DockAreaRenderer for WorkspaceSkin {
    fn tab_group_renderer(&self) -> Rc<dyn TabGroupRenderer> {
        Rc::new(self.clone())
    }
    fn tiles_renderer(&self) -> Rc<dyn TilesRenderer> {
        Rc::new(self.clone())
    }
}

pub(crate) fn register(shared: Shared, cx: &mut App) {
    register_panel(cx, "SystemPulseMonitor", move |context, _, cx| {
        let id = match &context.state().info {
            PanelInfo::Panel(v) => v["monitor_id"].as_str().unwrap_or(""),
            _ => "",
        };
        let monitor = {
            let data = shared.borrow();
            data.catalog
                .iter()
                .find(|m| m.id == id)
                .or_else(|| data.session.workspace.monitors.get(id))
                .cloned()
        }
        .expect("restored catalog contains every validated dock identity");
        let entity = cx.new(|cx| MonitorPanel::new(monitor.clone(), shared.clone(), cx));
        shared
            .borrow_mut()
            .views
            .insert(monitor.id.into(), entity.downgrade());
        Arc::new(entity) as Arc<dyn PanelView>
    });
}
