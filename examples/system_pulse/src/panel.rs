use crate::{
    controls::{self, FocusEntry},
    fixture::Monitor,
    meters,
    workspace::{Command, Shared},
};
use gpui::{prelude::FluentBuilder, *};
use gpui_base::{
    ElementExt, ScrollableMask, Scrollbar, ScrollbarMode, Table, TableCell, TableRow,
    VirtualListScrollHandle, dock::*, v_virtual_list,
};
use gpui_component::ActiveTheme;
use std::{collections::BTreeMap, rc::Rc, sync::Arc};

pub(crate) struct MonitorPanel {
    pub(crate) monitor: Monitor,
    pub(crate) shared: Shared,
    pub(crate) group: Option<WeakEntity<TabGroup>>,
    pub(crate) focus: FocusHandle,
    pub(crate) controls: BTreeMap<String, FocusEntry>,
    body_scroll: ScrollHandle,
    table_scroll: VirtualListScrollHandle,
    pub(crate) selected: usize,
}

impl MonitorPanel {
    pub(crate) fn new(monitor: Monitor, shared: Shared, cx: &mut Context<Self>) -> Self {
        let mut controls = BTreeMap::new();
        for key in ["collapse", "close", "table"] {
            controls.insert(key.into(), FocusEntry::new(cx));
        }
        for (id, _) in &monitor.sensors {
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
            selected: 0,
        }
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
        let collapsed = data.session.workspace.panels[self.monitor.id].collapsed;
        let summary = if self.monitor.summary.is_empty() {
            String::new()
        } else {
            meters::value(data.history.latest(self.monitor.id, self.monitor.summary))
        };
        let title = format!(
            "{}{}",
            self.monitor.title,
            if !summary.is_empty() {
                format!(" · {summary}")
            } else {
                String::new()
            }
        );
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
                Command::PanelCollapse(self.monitor.id.into()),
                false,
                cx,
            ))
            .child(
                div()
                    .id("drag-title")
                    .flex_1()
                    .min_w_0()
                    .overflow_hidden()
                    .child(title)
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
                Command::PanelVisible(self.monitor.id.into()),
                false,
                cx,
            ))
            .into_any_element()
    }

    fn sensor_rows(&mut self, cx: &mut Context<Self>) -> AnyElement {
        let data = self.shared.borrow();
        let panel = data.session.workspace.panels[self.monitor.id].clone();
        let mut rows = Vec::new();
        for (sensor, state) in panel.visible_sensors() {
            let Some((_, label)) = self.monitor.sensors.iter().find(|(id, _)| *id == sensor) else {
                continue;
            };
            let current = meters::value(data.history.latest(self.monitor.id, sensor));
            let samples = data
                .history
                .samples(self.monitor.id, sensor)
                .map(|s| s.iter().cloned().collect())
                .unwrap_or_default();
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
                        .child(div().flex_1().child(current))
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
                    format!("Meter: {:?}", state.meter),
                    None,
                    Command::Meter(id, sensor),
                    true,
                    cx,
                ))
                .when(!state.collapsed, |row| {
                    row.child(
                        div()
                            .debug_selector(move || selector.clone().into())
                            .child(meters::meter(state.meter, samples, cx)),
                    )
                });
            rows.push(row.into_any_element());
        }
        for (sensor, label) in &self.monitor.sensors {
            if panel.sensors.get(*sensor).is_some_and(|s| !s.visible) {
                rows.push(self.control(
                    &format!("visible:{sensor}"),
                    format!("Show {label}"),
                    None,
                    Command::SensorVisible(self.monitor.id.into(), (*sensor).into()),
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

    fn process_table(&mut self, window: &Window, cx: &mut Context<Self>) -> AnyElement {
        let handle = self.controls["table"].handle.clone();
        let ring = cx.theme().ring;
        let sizes = Rc::new(vec![
            size(window.rem_size() * 37.5, window.rem_size() * 1.75);
            500
        ]);
        let list = v_virtual_list(cx.entity(), "process-rows", sizes, |this, range, _, cx| {
            range
                .map(|index| {
                    TableRow::new(("process", index), index + 1)
                        .flex()
                        .h_7()
                        .aria_selected(index == this.selected)
                        .when(index == this.selected, |row| row.bg(cx.theme().muted))
                        .debug_selector(move || format!("process-row:{index}").into())
                        .child(
                            TableCell::new(("pid", index), 1)
                                .w_24()
                                .child(format!("{}", 1000 + index)),
                        )
                        .child(
                            TableCell::new(("name", index), 2)
                                .w_80()
                                .child(format!("fixture-process-{index}")),
                        )
                        .child(
                            TableCell::new(("cpu", index), 3)
                                .w_24()
                                .child(format!("{}%", index % 100)),
                        )
                })
                .collect()
        })
        .track_scroll(&self.table_scroll);
        let outer = self.shared.borrow().scroll.clone();
        let focus = self.controls["table"].clone();
        div()
            .id("process-table-viewport")
            .size_full()
            .relative()
            .track_focus(&handle)
            .border_1()
            .border_color(cx.theme().border)
            .focus_visible(move |style| style.border_color(ring))
            .debug_selector(|| "process-table".into())
            .on_key_down(cx.listener(|this, event: &KeyDownEvent, window, cx| {
                if event.keystroke.modifiers.alt {
                    return;
                }
                let next = match event.keystroke.key.as_str() {
                    "up" => this.selected.saturating_sub(1),
                    "down" => (this.selected + 1).min(499),
                    "home" => 0,
                    "end" => 499,
                    _ => return,
                };
                this.selected = next;
                this.table_scroll.scroll_to_item(next, ScrollStrategy::Top);
                controls::reveal(
                    this.table_scroll.base_handle().bounds().dilate(px(1.)),
                    &this.shared.borrow().scroll,
                );
                window.refresh();
                cx.stop_propagation();
                cx.notify();
            }))
            .on_prepaint(move |bounds, window, _| {
                if focus.entered(window) {
                    // Include the table viewport's one-pixel focus border.
                    controls::reveal(bounds.dilate(px(1.)), &outer);
                    window.refresh();
                }
            })
            .child(
                Table::new("process-table")
                    .row_count(500)
                    .column_count(3)
                    .accessibility_label("Fixture processes; arrows navigate; Tab leaves table")
                    .size_full()
                    .child(list),
            )
            .child(ScrollableMask::new(
                Axis::Vertical,
                self.table_scroll.base_handle(),
            ))
            .child(Scrollbar::new(&self.table_scroll).mode(ScrollbarMode::Always))
            .into_any_element()
    }
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
            .get(self.monitor.id)
            .is_some_and(|s| s.visible)
            && data.catalog.iter().any(|m| m.id == self.monitor.id)
    }
    fn zoomable(&self, _: &App) -> bool {
        false
    }
    fn dock_extent(&self, _: &App) -> Option<PanelExtent> {
        let data = self.shared.borrow();
        let p = &data.session.workspace.panels[self.monitor.id];
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
        if self.shared.borrow().session.workspace.panels[self.monitor.id].collapsed {
            return Empty.into_any_element();
        }
        let content = match self.monitor.id {
            "processes" => self.process_table(window, cx),
            "settings" => div().p_3().child("Fixture controls and the single preset slot are in the workspace toolbar. No operating-system collectors are running.").into_any_element(),
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
        let monitor = crate::fixture::catalog()
            .into_iter()
            .find(|m| m.id == id)
            .expect("native adapter validates every fixture identity before loading");
        let entity = cx.new(|cx| MonitorPanel::new(monitor.clone(), shared.clone(), cx));
        shared
            .borrow_mut()
            .views
            .insert(monitor.id.into(), entity.downgrade());
        Arc::new(entity) as Arc<dyn PanelView>
    });
}
