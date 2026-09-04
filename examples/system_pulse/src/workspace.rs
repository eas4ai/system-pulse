use crate::{
    fixture::{self, Monitor},
    panel::{self, MonitorPanel, WorkspaceSkin},
    storage::{self, Storage},
};
use gpui::*;
use gpui_base::{Button, Scrollbar, ScrollbarMode, dock::*};
use gpui_component::ActiveTheme;
use std::{
    cell::RefCell,
    collections::{BTreeMap, BTreeSet},
    path::PathBuf,
    rc::Rc,
    time::Duration,
};
use system_pulse_model::{ExpandedSize, HistoryStore, Meter, Session, Workspace};

pub(crate) type Shared = Rc<RefCell<Data>>;
pub(crate) struct Data {
    pub(crate) session: Session,
    pub(crate) history: HistoryStore,
    pub(crate) catalog: Vec<Monitor>,
    pub(crate) owner: Option<WeakEntity<WorkspaceView>>,
    pub(crate) views: BTreeMap<String, WeakEntity<MonitorPanel>>,
    pub(crate) bounds: BTreeMap<String, Bounds<Pixels>>,
    pub(crate) scroll: ScrollHandle,
}

#[derive(Clone)]
pub(crate) enum Command {
    PanelCollapse(String),
    PanelVisible(String),
    RowCollapse(String, String),
    SensorVisible(String, String),
    Meter(String, String),
    Tick,
    Save,
    SavePreset,
    RecallPreset,
    Recover,
    ReverseDiscovery,
    ToggleGpu,
    Scroll(f32, f32),
}

pub(crate) fn default_dock() -> DockAreaState {
    let children = fixture::catalog()
        .into_iter()
        .map(|monitor| {
            let mut leaf = PanelState::new("SystemPulseMonitor");
            leaf.info = PanelInfo::panel(serde_json::json!({"monitor_id": monitor.id}));
            PanelState {
                panel_name: "TabPanel".into(),
                children: vec![leaf],
                info: PanelInfo::tabs(0),
            }
        })
        .collect::<Vec<_>>();
    DockAreaState {
        version: Some(1),
        center: PanelState {
            panel_name: "StackPanel".into(),
            info: PanelInfo::stack(vec![px(280.); children.len()], Axis::Vertical),
            children,
        },
        left_dock: None,
        right_dock: None,
        bottom_dock: None,
    }
}

pub(crate) fn validate_dock(value: &serde_json::Value) -> Result<(), String> {
    let state: DockAreaState = serde_json::from_value(value.clone()).map_err(|e| e.to_string())?;
    PanelPolicy::Separate
        .validate_state(&state)
        .map_err(|e| e.to_string())?;
    if state.left_dock.is_some() || state.right_dock.is_some() || state.bottom_dock.is_some() {
        return Err("The fixture workspace supports center splits only".into());
    }
    fn leaves(node: &PanelState, seen: &mut BTreeSet<String>) -> Result<(), String> {
        let expected = match &node.info {
            PanelInfo::Stack { .. } => "StackPanel",
            PanelInfo::Tabs { .. } => "TabPanel",
            PanelInfo::Panel(_) => "SystemPulseMonitor",
            PanelInfo::Tiles { .. } => return Err("Tile layouts are unsupported".into()),
        };
        if node.panel_name != expected {
            return Err(format!("Layout kind/name mismatch: {}", node.panel_name));
        }
        if let PanelInfo::Panel(value) = &node.info {
            let id = value["monitor_id"]
                .as_str()
                .ok_or("Missing monitor identity")?;
            if node.panel_name != "SystemPulseMonitor"
                || !fixture::catalog().iter().any(|m| m.id == id)
            {
                return Err(format!("Unknown fixture monitor: {id}"));
            }
            if !seen.insert(id.to_owned()) {
                return Err(format!("Duplicate monitor: {id}"));
            }
        }
        for child in &node.children {
            leaves(child, seen)?;
        }
        Ok(())
    }
    leaves(&state.center, &mut BTreeSet::new())
}

fn ensure_enabled_regions(
    shared: &Shared,
    dock: &Entity<DockArea>,
    window: &mut Window,
    cx: &mut App,
) {
    fn collect(node: &PanelState, ids: &mut BTreeSet<String>) {
        if let PanelInfo::Panel(value) = &node.info {
            if let Some(id) = value["monitor_id"].as_str() {
                ids.insert(id.to_owned());
            }
        }
        for child in &node.children {
            collect(child, ids);
        }
    }
    let mut present = BTreeSet::new();
    collect(&dock.read(cx).dump(cx).center, &mut present);
    let missing: Vec<_> = {
        let data = shared.borrow();
        data.catalog
            .iter()
            .filter(|m| data.session.workspace.panels[m.id].visible && !present.contains(m.id))
            .cloned()
            .collect()
    };
    for monitor in missing {
        let entity = cx.new(|cx| MonitorPanel::new(monitor.clone(), shared.clone(), cx));
        shared
            .borrow_mut()
            .views
            .insert(monitor.id.into(), entity.downgrade());
        dock.update(cx, |dock, cx| {
            dock.add_panel(entity, DockPlacement::Center, Some(px(280.)), window, cx)
        });
    }
    dock.update(cx, |dock, cx| dock.refresh_geometry(window, cx));
}

// Divider events can precede prepaint. ResizableState's resolved split sizes are
// authoritative on those axes; cached bounds supply only unconstrained axes.
fn capture_preferences(shared: &Shared, dock: &DockAreaState) {
    fn collect(node: &PanelState, width: Option<f32>, height: Option<f32>, data: &mut Data) {
        if let PanelInfo::Panel(value) = &node.info {
            let Some(id) = value["monitor_id"].as_str() else {
                return;
            };
            if !data.catalog.iter().any(|monitor| monitor.id == id) {
                return;
            }
            let Some(panel) = data.session.workspace.panels.get_mut(id) else {
                return;
            };
            if panel.collapsed || !panel.visible {
                return;
            }
            let measured = data.bounds.get(id).map(|bounds| bounds.size);
            let width = width.or_else(|| measured.map(|size| size.width.as_f32()));
            let height = height.or_else(|| measured.map(|size| size.height.as_f32()));
            if let (Some(width), Some(height)) = (width, height) {
                if width.is_finite() && height.is_finite() && width >= 320. && height >= 220. {
                    panel.expanded_size = ExpandedSize {
                        width: width.min(system_pulse_model::MAX_EXPANDED_DIMENSION),
                        height: height.min(system_pulse_model::MAX_EXPANDED_DIMENSION),
                    };
                }
            }
        }
        for (ix, child) in node.children.iter().enumerate() {
            let (width, height) = match &node.info {
                PanelInfo::Stack { sizes, axis } => {
                    let allocation = sizes
                        .get(ix)
                        .map(|size| size.as_f32())
                        .filter(|size| *size > 0.);
                    if *axis == 0 {
                        (allocation.or(width), height)
                    } else {
                        (width, allocation.or(height))
                    }
                }
                _ => (width, height),
            };
            collect(child, width, height, data);
        }
    }
    collect(&dock.center, None, None, &mut shared.borrow_mut());
}

pub struct WorkspaceView {
    pub(crate) shared: Shared,
    pub(crate) dock: Entity<DockArea>,
    notice: String,
    directory: Option<PathBuf>,
    read_blocked: bool,
    storage: Storage,
    revision: u64,
    tick: u64,
    preset: Option<String>,
    timer: Option<Task<()>>,
    save_task: Option<Task<()>>,
    focus: FocusHandle,
}

impl Command {
    fn control_id(&self) -> String {
        match self {
            Self::PanelVisible(id) => format!("workspace:visible:{id}"),
            Self::Tick => "workspace:tick".into(),
            Self::Save => "workspace:save".into(),
            Self::SavePreset => "workspace:save-preset".into(),
            Self::RecallPreset => "workspace:recall-preset".into(),
            Self::Recover => "workspace:recover".into(),
            Self::ReverseDiscovery => "workspace:reverse-discovery".into(),
            Self::ToggleGpu => "workspace:toggle-gpu".into(),
            _ => unreachable!("only workspace commands appear in the toolbar"),
        }
    }
}

impl WorkspaceView {
    pub fn new(live: bool, window: &mut Window, cx: &mut Context<Self>) -> Self {
        let mut workspace =
            Workspace::new(serde_json::to_value(default_dock()).expect("static dock serializes"));
        fixture::discover(&mut workspace, &fixture::catalog());
        workspace.panel_mut("cpu").sensor_mut("overall").meter = Meter::Line;
        let mut session = Session {
            workspace: workspace.clone(),
            rejected: None,
        };
        let mut notice = String::new();
        let mut read_blocked = false;
        let directory = if live {
            match storage::directory() {
                Ok(path) => Some(path),
                Err(e) => {
                    notice = e;
                    read_blocked = true;
                    None
                }
            }
        } else {
            None
        };
        let mut preset = None;
        if let Some(dir) = &directory {
            match storage::read(&dir.join("workspace.json")) {
                Ok(Some(raw)) => session = Session::restore(&raw, workspace, validate_dock),
                Ok(None) => {}
                Err(e) => {
                    notice = e;
                    read_blocked = true;
                }
            }
            match storage::read(&dir.join("preset.json")) {
                Ok(raw) => preset = raw,
                Err(e) => {
                    notice = e;
                    read_blocked = true;
                }
            }
        }
        fixture::discover(&mut session.workspace, &fixture::catalog());
        let shared = Rc::new(RefCell::new(Data {
            session,
            history: HistoryStore::new(120).expect("valid fixture capacity"),
            catalog: fixture::catalog(),
            owner: Some(cx.weak_entity()),
            views: BTreeMap::new(),
            bounds: BTreeMap::new(),
            scroll: ScrollHandle::default(),
        }));
        let dock = cx.new(|cx| {
            DockArea::new("system-pulse", Some(1), window, cx)
                .with_renderer(Rc::new(WorkspaceSkin(shared.clone())))
        });
        panel::register(shared.clone(), cx);
        let state = serde_json::from_value(shared.borrow().session.workspace.dock.clone())
            .expect("validated/default dock");
        dock.update(cx, |dock, cx| {
            dock.set_panel_policy(PanelPolicy::Separate, window, cx)
                .expect("empty dock accepts policy");
            dock.load(state, window, cx)
                .expect("validated/default dock loads");
            dock.refresh_geometry(window, cx);
        });
        ensure_enabled_regions(&shared, &dock, window, cx);
        cx.subscribe_in(&dock, window, |this, _, event, _, cx| {
            if matches!(event, DockEvent::LayoutChanged) {
                this.record(cx);
                this.queue_save(cx);
                cx.notify();
            }
        })
        .detach();
        let mut view = Self {
            shared,
            dock,
            notice,
            directory,
            read_blocked,
            storage: Storage::default(),
            revision: 0,
            tick: 0,
            preset,
            timer: None,
            save_task: None,
            focus: cx.focus_handle(),
        };
        view.advance(cx);
        if live {
            view.timer = Some(cx.spawn_in(window, async move |weak, window| {
                loop {
                    window
                        .background_executor()
                        .timer(Duration::from_secs(1))
                        .await;
                    if weak
                        .update_in(window, |this, _, cx| this.advance(cx))
                        .is_err()
                    {
                        break;
                    }
                }
            }));
            // The final native window closes before App quits. Retain this view
            // until the App-level callback snapshots it; a weak entity callback
            // can otherwise disappear with the window before writing state.
            let owner = cx.entity();
            App::on_app_quit(cx, move |cx| {
                let (path, storage, json, preset) = owner.update(cx, |this, cx| {
                    this.record(cx);
                    let data = this.shared.borrow();
                    let json = if this.read_blocked {
                        None
                    } else {
                        validate_dock(&data.session.workspace.dock)
                            .and_then(|_| data.session.autosave_json())
                            .ok()
                    };
                    (
                        this.directory.clone(),
                        this.storage.clone(),
                        json,
                        this.preset.clone(),
                    )
                });
                cx.background_executor().spawn(async move {
                    if let (Some(path), Some(json)) = (path, json) {
                        if let Err(error) =
                            storage.write(&path.join("workspace.json"), u64::MAX, &json)
                        {
                            eprintln!("{error}");
                        }
                        if let Some(preset) = preset {
                            if let Err(error) =
                                storage.write(&path.join("preset.json"), u64::MAX, &preset)
                            {
                                eprintln!("{error}");
                            }
                        }
                    }
                })
            })
            .detach();
        }
        view
    }

    fn capture_sizes(&mut self, cx: &App) {
        capture_preferences(&self.shared, &self.dock.read(cx).dump(cx));
    }

    pub(crate) fn record(&mut self, cx: &App) {
        self.capture_sizes(cx);
        let state = self.dock.read(cx).dump(cx);
        self.shared.borrow_mut().session.workspace.dock =
            serde_json::to_value(state).expect("dock serializes");
    }

    fn notify_panels(&self, cx: &mut Context<Self>) {
        let views: Vec<_> = self.shared.borrow().views.values().cloned().collect();
        for view in views {
            let _ = view.update(cx, |panel, cx| {
                if let Some(group) = &panel.group {
                    let _ = group.update(cx, |_, cx| cx.notify());
                }
                cx.notify();
            });
        }
        cx.notify();
    }

    pub(crate) fn advance(&mut self, cx: &mut Context<Self>) {
        self.tick += 1;
        if let Err(e) = fixture::advance(&mut self.shared.borrow_mut().history, self.tick) {
            self.notice = e;
        }
        self.notify_panels(cx);
    }

    fn queue_save(&mut self, cx: &mut Context<Self>) {
        if self.read_blocked {
            return;
        }
        let Some(dir) = &self.directory else { return };
        let data = self.shared.borrow();
        let result =
            validate_dock(&data.session.workspace.dock).and_then(|_| data.session.autosave_json());
        drop(data);
        let json = match result {
            Ok(json) => json,
            Err(e) => {
                self.notice = e;
                cx.notify();
                return;
            }
        };
        self.revision += 1;
        let revision = self.revision;
        let path = dir.join("workspace.json");
        let storage = self.storage.clone();
        self.save_task = Some(cx.spawn(async move |weak, cx| {
            cx.background_executor()
                .timer(Duration::from_millis(250))
                .await;
            let result = smol::unblock(move || storage.write(&path, revision, &json)).await;
            if let Err(error) = result {
                let _ = weak.update(cx, |this, cx| {
                    this.notice = error;
                    cx.notify();
                });
            }
        }));
    }

    pub(crate) fn restore(&mut self, raw: &str, window: &mut Window, cx: &mut Context<Self>) {
        let mut fallback =
            Workspace::new(serde_json::to_value(default_dock()).expect("default serializes"));
        fixture::discover(&mut fallback, &fixture::catalog());
        let mut session = Session::restore(raw, fallback, validate_dock);
        fixture::discover(&mut session.workspace, &fixture::catalog());
        if let Some(rejected) = self.shared.borrow().session.rejected.clone() {
            session.rejected = Some(rejected);
        }
        self.shared.borrow_mut().session = session;
        let state = serde_json::from_value(self.shared.borrow().session.workspace.dock.clone())
            .expect("validated/default dock");
        self.shared.borrow_mut().bounds.clear();
        self.dock.update(cx, |dock, cx| {
            dock.load(state, window, cx)
                .expect("adapter-validated dock");
            dock.refresh_geometry(window, cx);
        });
        ensure_enabled_regions(&self.shared, &self.dock, window, cx);
        self.notify_panels(cx);
    }

    pub(crate) fn command(
        &mut self,
        command: Command,
        window: &mut Window,
        cx: &mut Context<Self>,
    ) {
        match command {
            Command::Tick => {
                self.advance(cx);
                return;
            }
            Command::Scroll(dx, dy) => {
                let scroll = &self.shared.borrow().scroll;
                let max = scroll.max_offset();
                let old = scroll.offset();
                scroll.set_offset(point(
                    (old.x + px(dx)).clamp(-max.x, px(0.)),
                    (old.y + px(dy)).clamp(-max.y, px(0.)),
                ));
                cx.notify();
                return;
            }
            Command::PanelCollapse(id) => {
                self.capture_sizes(cx);
                let view = self.shared.borrow().views.get(&id).cloned();
                if let Some(view) = view {
                    let _ =
                        view.update(cx, |p, cx| p.controls["collapse"].handle.focus(window, cx));
                }
                let mut data = self.shared.borrow_mut();
                let panel = data.session.workspace.panel_mut(&id);
                panel.collapsed = !panel.collapsed;
                drop(data);
                self.dock
                    .update(cx, |dock, cx| dock.refresh_geometry(window, cx));
            }
            Command::PanelVisible(id) => {
                self.capture_sizes(cx);
                let mut data = self.shared.borrow_mut();
                let panel = data.session.workspace.panel_mut(&id);
                panel.visible = !panel.visible;
                let visible = panel.visible;
                let old = data.views.get(&id).and_then(WeakEntity::upgrade);
                drop(data);
                if visible {
                    if let Some(monitor) = fixture::catalog().into_iter().find(|m| m.id == id) {
                        let panel = old.unwrap_or_else(|| {
                            cx.new(|cx| MonitorPanel::new(monitor, self.shared.clone(), cx))
                        });
                        self.shared.borrow_mut().views.insert(id, panel.downgrade());
                        self.dock.update(cx, |dock, cx| {
                            dock.add_panel(panel, DockPlacement::Center, Some(px(280.)), window, cx)
                        });
                    }
                } else if let Some(panel) = old {
                    self.focus.focus(window, cx);
                    self.dock
                        .update(cx, |dock, cx| dock.remove_panel(panel, window, cx));
                }
                self.dock
                    .update(cx, |dock, cx| dock.refresh_geometry(window, cx));
            }
            Command::RowCollapse(id, sensor) => {
                let view = self.shared.borrow().views.get(&id).cloned();
                if let Some(view) = view {
                    let _ = view.update(cx, |p, cx| {
                        p.controls[&format!("row:{sensor}")]
                            .handle
                            .focus(window, cx)
                    });
                }
                let mut data = self.shared.borrow_mut();
                let row = data.session.workspace.panel_mut(&id).sensor_mut(&sensor);
                row.collapsed = !row.collapsed;
            }
            Command::SensorVisible(id, sensor) => {
                let mut data = self.shared.borrow_mut();
                let row = data.session.workspace.panel_mut(&id).sensor_mut(&sensor);
                row.visible = !row.visible;
            }
            Command::Meter(id, sensor) => {
                let mut data = self.shared.borrow_mut();
                let row = data.session.workspace.panel_mut(&id).sensor_mut(&sensor);
                row.meter = match row.meter {
                    Meter::Number => Meter::Line,
                    Meter::Line => Meter::Bar,
                    Meter::Bar => Meter::Sparkline,
                    Meter::Sparkline => Meter::Radial,
                    Meter::Radial => Meter::Number,
                };
            }
            Command::SavePreset => {
                if self.read_blocked {
                    self.notice = "Saved state could not be read; correct the read error and restart before saving".into();
                    cx.notify();
                    return;
                }
                self.record(cx);
                match self.shared.borrow().session.autosave_json() {
                    Ok(json) => {
                        self.preset = Some(json.clone());
                        if let Some(dir) = &self.directory {
                            self.revision += 1;
                            let path = dir.join("preset.json");
                            let storage = self.storage.clone();
                            let revision = self.revision;
                            cx.spawn(async move |weak, cx| {
                                if let Err(e) =
                                    smol::unblock(move || storage.write(&path, revision, &json))
                                        .await
                                {
                                    let _ = weak.update(cx, |this, cx| {
                                        this.notice = e;
                                        cx.notify();
                                    });
                                }
                            })
                            .detach();
                        }
                    }
                    Err(e) => self.notice = e,
                }
            }
            Command::RecallPreset => {
                if let Some(raw) = self.preset.clone() {
                    self.restore(&raw, window, cx);
                } else {
                    self.notice = "Save the fixture preset before recalling it".into();
                }
            }
            Command::Recover => {
                if self.read_blocked {
                    self.notice = "Correct the configuration-directory read error and restart; the original file remains untouched".into();
                    cx.notify();
                    return;
                }
                let rejected = self
                    .shared
                    .borrow()
                    .session
                    .rejected
                    .as_ref()
                    .map(|r| r.original.clone());
                if let (Some(raw), Some(dir)) = (rejected, &self.directory) {
                    self.revision += 1;
                    if let Err(e) = self.storage.write(
                        &dir.join("workspace.rejected.json"),
                        self.revision,
                        &raw,
                    ) {
                        self.notice = e;
                        cx.notify();
                        return;
                    }
                }
                // The recovery button disappears after acceptance. Keep the
                // keyboard dispatch path in the retained workspace before removal.
                self.focus.focus(window, cx);
                self.shared.borrow_mut().session.accept_recovery();
                self.notice.clear();
            }
            Command::ReverseDiscovery => {
                self.shared.borrow_mut().catalog.reverse();
            }
            Command::ToggleGpu => {
                self.capture_sizes(cx);
                let mut data = self.shared.borrow_mut();
                if data.catalog.iter().any(|m| m.id == "gpu:fixture-a") {
                    data.catalog.retain(|m| m.id != "gpu:fixture-a");
                } else {
                    data.catalog.push(
                        fixture::catalog()
                            .into_iter()
                            .find(|m| m.id == "gpu:fixture-a")
                            .expect("fixture exists"),
                    );
                }
                drop(data);
                self.dock
                    .update(cx, |dock, cx| dock.refresh_geometry(window, cx));
            }
            Command::Save => {}
        }
        self.record(cx);
        self.queue_save(cx);
        self.notify_panels(cx);
    }
}

impl Render for WorkspaceView {
    fn render(&mut self, _: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        let data = self.shared.borrow();
        let mut commands = data
            .catalog
            .iter()
            .map(|m| {
                let visible = data.session.workspace.panels[m.id].visible;
                (
                    format!("{} {}", if visible { "Hide" } else { "Show" }, m.title),
                    Command::PanelVisible(m.id.into()),
                )
            })
            .collect::<Vec<_>>();
        commands.extend([
            ("Advance fixture".into(), Command::Tick),
            ("Save".into(), Command::Save),
            ("Save preset".into(), Command::SavePreset),
            ("Recall preset".into(), Command::RecallPreset),
            ("Reverse discovery".into(), Command::ReverseDiscovery),
            ("Connect/disconnect GPU A".into(), Command::ToggleGpu),
        ]);
        let mut message = self.notice.clone();
        if let Some(rejected) = &data.session.rejected {
            message = format!(
                "Saved layout rejected: {}. Original input retained; autosave blocked. {}",
                rejected.error, self.notice
            );
            commands.push(("Accept recovered layout".into(), Command::Recover));
        }
        let scroll = data.scroll.clone();
        drop(data);
        let extent = self.dock.read(cx).content_extent(cx);
        let toolbar = div()
            .flex()
            .flex_wrap()
            .gap_1()
            .children(commands.into_iter().map(|(label, command)| {
                let selector = command.control_id();
                Button::new(SharedString::from(command.control_id()))
                    .debug_selector(move || selector.clone().into())
                    .accessibility_label(label.clone())
                    .child(label)
                    .px_2()
                    .h_7()
                    .text_sm()
                    .border_1()
                    .rounded(cx.theme().radius)
                    .border_color(cx.theme().border)
                    .focus_visible(|style| style.border_color(cx.theme().ring))
                    .on_click(cx.listener(move |this, _, window, cx| {
                        this.command(command.clone(), window, cx)
                    }))
            }));
        div().size_full().flex().flex_col().gap_2().p_2().bg(cx.theme().background)
            .text_color(cx.theme().foreground).track_focus(&self.focus).tab_group()
            .on_key_down(cx.listener(|this, event: &KeyDownEvent, window, cx| {
                if event.keystroke.modifiers.alt {
                    let command = match event.keystroke.key.as_str() {
                        "pageup" => Command::Scroll(0., 300.), "pagedown" => Command::Scroll(0., -300.),
                        "left" => Command::Scroll(300., 0.), "right" => Command::Scroll(-300., 0.), _ => return,
                    };
                    this.command(command, window, cx); cx.stop_propagation();
                }
            }))
            .child("Fixture mode · simulated readings · 1 s cadence · normalized demonstration meters")
            .child("Alt+PageUp/PageDown: workspace · Alt+Left/Right: horizontal · table arrows/Home/End · Tab: next control")
            .child(toolbar).child(message)
            .child(div().flex_1().min_h_0().min_w_0().relative()
                .child(div().id("workspace-scroll").size_full().overflow_scroll().track_scroll(&scroll)
                    .debug_selector(|| "workspace-viewport".into())
                    .child(div().w(extent.width).h(extent.height).min_w_full().child(self.dock.clone())))
                .child(Scrollbar::new(&scroll).mode(ScrollbarMode::Always)))
    }
}
