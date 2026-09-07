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
use gpui_component::{ActiveTheme, menu::ContextMenuExt};
use std::{collections::BTreeMap, rc::Rc, sync::Arc};

#[path = "process_panel.rs"]
mod process_panel;
#[path = "sensor_panel.rs"]
mod sensor_panel;
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
    process_reveal_pending: bool,
    process_state: process_panel::ProcessPanelState,
    pub(crate) settings: Option<Entity<crate::settings::SettingsPanel>>,
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
            process_reveal_pending: false,
            process_state: process_panel::ProcessPanelState::default(),
            settings: None,
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
        let context_shared = self.shared.clone();
        let context_id = self.monitor.id.clone();
        div()
            .id(SharedString::from(format!(
                "monitor-header:{}",
                self.monitor.id
            )))
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
                    .font_family(cx.theme().mono_font_family.clone())
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
            .child(crate::panel_context::monitor_button(
                self.monitor.id.clone(),
                self.shared.clone(),
            ))
            .child(self.control(
                "close",
                format!("Hide {}", self.monitor.title),
                None,
                Command::PanelVisible(self.monitor.id.clone()),
                false,
                cx,
            ))
            .context_menu(move |menu, _, _| {
                crate::panel_context::monitor(menu, &context_id, &context_shared)
            })
            .into_any_element()
    }
}

pub(crate) fn process_cell(process: &live::ProcessView, column: usize, width: f32) -> TableCell {
    let cell_id = format!(
        "process:{}:{}:cell:{column}",
        process.identity.pid, process.identity.start_time_ticks
    );
    let tooltip = process.cells[column].clone();
    let numeric = column == 0 || (2..7).contains(&column);
    TableCell::new(SharedString::from(cell_id.clone()), column + 1)
        .accessibility_id(cell_id.clone())
        .aria_label(process.cells[column].clone())
        .w(px(width))
        .flex_none()
        .px_2()
        .flex()
        .items_center()
        .overflow_hidden()
        .tooltip(move |window, cx| {
            gpui_component::tooltip::Tooltip::new(tooltip.clone()).build(window, cx)
        })
        .child(
            div()
                .w_full()
                .overflow_hidden()
                .text_ellipsis()
                .when(numeric, |cell| cell.text_right())
                .debug_selector(move || format!("{cell_id}:text").into())
                .child(process.cells[column].clone()),
        )
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
        .children(process.cells.iter().enumerate().map(|(column, _)| {
            process_cell(process, column, widths[column])
                .when(column == 0 || (2..7).contains(&column), |cell| {
                    cell.font_family(cx.theme().mono_font_family.clone())
                })
        }))
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
            "settings" => {
                let settings = self.settings.get_or_insert_with(|| {
                    cx.new(|cx| crate::settings::SettingsPanel::new(self.shared.clone(), cx))
                });
                settings.clone().into_any_element()
            }
            _ => self.sensor_rows(cx),
        };
        div()
            .size_full()
            .track_focus(&self.focus)
            .font_family(cx.theme().font_family.clone())
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
