#[cfg(test)]
use crate::fixture;
use crate::{
    live::{self, LiveState},
    panel::{self, MonitorPanel, WorkspaceSkin},
    storage::{self, Storage},
};
use gpui::*;
use gpui_base::{Button, ElementExt, Scrollbar, ScrollbarMode, dock::*};
use gpui_component::ActiveTheme;
use std::{
    cell::RefCell,
    collections::{BTreeMap, BTreeSet},
    path::PathBuf,
    rc::Rc,
    time::Duration,
};
use system_pulse_collectors::{SamplingService, Snapshot};
use system_pulse_model::{
    ExpandedSize, HistoryStore, MonitorDescriptor as Monitor, Session, Workspace,
};

pub(crate) type Shared = Rc<RefCell<Data>>;
pub(crate) struct Data {
    pub(crate) session: Session,
    pub(crate) history: HistoryStore,
    pub(crate) catalog: Vec<Monitor>,
    pub(crate) owner: Option<WeakEntity<WorkspaceView>>,
    pub(crate) views: BTreeMap<String, WeakEntity<MonitorPanel>>,
    pub(crate) bounds: BTreeMap<String, Bounds<Pixels>>,
    pub(crate) scroll: ScrollHandle,
    pub(crate) processes: Vec<crate::live::ProcessView>,
    pub(crate) process_widths: [f32; 8],
    pub(crate) allow_process_actions: bool,
    pub(crate) snapshot: Option<std::sync::Arc<Snapshot>>,
    pub(crate) live: LiveState,
}

#[derive(Clone)]
pub(crate) enum Command {
    PanelCollapse(String),
    PanelVisible(String),
    RowCollapse(String, String),
    SensorVisible(String, String),
    Meter(String, String),
    #[cfg(test)]
    Tick,
    Save,
    SavePreset,
    RecallPreset,
    Recover,
    #[cfg(test)]
    ReverseDiscovery,
    #[cfg(test)]
    ToggleGpu,
    Interval(u64),
    Scroll(f32, f32),
}

#[cfg(test)]
pub(crate) fn default_dock() -> DockAreaState {
    default_dock_for(&fixture::catalog())
}

fn default_dock_for(monitors: &[Monitor]) -> DockAreaState {
    let children = monitors
        .iter()
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

#[cfg(test)]
pub(crate) fn validate_dock(value: &serde_json::Value) -> Result<(), String> {
    validate_dock_mode(value, false)
}

fn validate_dock_mode(value: &serde_json::Value, allow_fixture: bool) -> Result<(), String> {
    let state: DockAreaState = serde_json::from_value(value.clone()).map_err(|e| e.to_string())?;
    PanelPolicy::Separate
        .validate_state(&state)
        .map_err(|e| e.to_string())?;
    if state.left_dock.is_some() || state.right_dock.is_some() || state.bottom_dock.is_some() {
        return Err("The workspace supports center splits only".into());
    }
    fn leaves(
        node: &PanelState,
        seen: &mut BTreeSet<String>,
        allow_fixture: bool,
    ) -> Result<(), String> {
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
                || id.trim().is_empty()
                || (!allow_fixture && live::is_fixture_id(id))
            {
                return Err(format!("Unsupported simulated monitor identity: {id}"));
            }
            if !seen.insert(id.to_owned()) {
                return Err(format!("Duplicate monitor: {id}"));
            }
        }
        for child in &node.children {
            leaves(child, seen, allow_fixture)?;
        }
        Ok(())
    }
    leaves(&state.center, &mut BTreeSet::new(), allow_fixture)
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
            .filter(|m| data.session.workspace.panels[&m.id].visible && !present.contains(&m.id))
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
    #[cfg(test)]
    tick: u64,
    fixture_mode: bool,
    service: Option<SamplingService>,
    accepted_clock: Option<(std::time::Instant, u64)>,
    accepted_unix_ns: u64,
    accepted_model_timing: Option<(u64, u64)>,
    diagnostic_revision: u64,
    diagnostics: Option<crate::diagnostics::Writer>,
    preset: Option<String>,
    timer: Option<Task<()>>,
    save_task: Option<Task<()>>,
    focus: FocusHandle,
    visibility_scroll: ScrollHandle,
    keyboard_repaint_pending: bool,
    visibility_controls: BTreeMap<String, crate::controls::FocusEntry>,
}

impl Command {
    fn control_id(&self) -> String {
        match self {
            Self::PanelVisible(id) => format!("workspace:visible:{id}"),
            #[cfg(test)]
            Self::Tick => "workspace:tick".into(),
            Self::Save => "workspace:save".into(),
            Self::SavePreset => "workspace:save-preset".into(),
            Self::RecallPreset => "workspace:recall-preset".into(),
            Self::Interval(ms) => format!("workspace:interval:{ms}"),
            Self::Recover => "workspace:recover".into(),
            #[cfg(test)]
            Self::ReverseDiscovery => "workspace:reverse-discovery".into(),
            #[cfg(test)]
            Self::ToggleGpu => "workspace:toggle-gpu".into(),
            _ => unreachable!("only workspace commands appear in the toolbar"),
        }
    }
}

impl WorkspaceView {
    pub fn new(window: &mut Window, cx: &mut Context<Self>) -> Self {
        Self::construct(false, window, cx)
    }

    #[cfg(test)]
    pub(crate) fn new_fixture(window: &mut Window, cx: &mut Context<Self>) -> Self {
        Self::construct(true, window, cx)
    }

    fn construct(fixture_mode: bool, window: &mut Window, cx: &mut Context<Self>) -> Self {
        let live = !fixture_mode;
        let initial = initial_catalog(fixture_mode);
        let mut workspace = Workspace::new(
            serde_json::to_value(default_dock_for(&initial)).expect("default dock serializes"),
        );
        live::discover(&mut workspace, &initial);
        #[cfg(test)]
        if fixture_mode {
            workspace.panel_mut("cpu").sensor_mut("overall").meter =
                system_pulse_model::Meter::Line;
        }
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
                Ok(Some(raw)) => session = restore_session(&raw, workspace, fixture_mode),
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
        let catalog = if fixture_mode {
            initial
        } else {
            live::catalog(&session.workspace)
        };
        live::discover(&mut session.workspace, &catalog);
        let interval = Duration::from_millis(session.workspace.interval_ms);
        let service = if live {
            match SamplingService::start(interval) {
                Ok(service) => Some(service),
                Err(e) => {
                    notice = e;
                    None
                }
            }
        } else {
            None
        };
        let diagnostics = if live {
            crate::diagnostics::Writer::from_env().unwrap_or_else(|e| {
                notice = e;
                None
            })
        } else {
            None
        };
        let shared = Rc::new(RefCell::new(Data {
            session,
            history: HistoryStore::new(120).expect("valid history capacity"),
            catalog,
            processes: Vec::new(),
            process_widths: live::PROCESS_WIDTHS,
            allow_process_actions: live && !fixture_mode,
            snapshot: None,
            live: LiveState::default(),
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
            #[cfg(test)]
            tick: 0,
            fixture_mode,
            service,
            accepted_clock: None,
            accepted_unix_ns: 0,
            accepted_model_timing: None,
            diagnostic_revision: 0,
            diagnostics,
            preset,
            timer: None,
            save_task: None,
            focus: cx.focus_handle(),
            visibility_scroll: ScrollHandle::default(),
            keyboard_repaint_pending: false,
            visibility_controls: BTreeMap::new(),
        };
        #[cfg(test)]
        if fixture_mode {
            view.advance(cx);
        }
        if live {
            view.timer = Some(cx.spawn_in(window, async move |weak, window| {
                loop {
                    window
                        .background_executor()
                        .timer(Duration::from_millis(100))
                        .await;
                    if weak
                        .update_in(window, |this, window, cx| this.deliver(window, cx))
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
                        validate_dock_mode(&data.session.workspace.dock, this.fixture_mode)
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

    fn deliver(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        if let Some(writer) = &self.diagnostics {
            if let Some(error) = writer.take_error() {
                self.notice = error;
                cx.notify();
            }
        }
        if let Some(snapshot) = self.service.as_ref().and_then(SamplingService::take_latest) {
            self.accept_snapshot(snapshot, window, cx);
        } else if let Some((accepted, collector_ms)) = self.accepted_clock {
            let now = collector_ms.saturating_add(accepted.elapsed().as_millis() as u64);
            let mut data = self.shared.borrow_mut();
            let threshold = data.session.workspace.interval_ms * 2;
            if data.history.mark_stale(now, threshold) {
                if let Some(snapshot) = &data.snapshot {
                    data.processes = live::process_views(snapshot, now, threshold);
                    data.process_widths = live::process_widths(&data.processes);
                }
                drop(data);
                self.publish_diagnostics(now);
                self.notify_panels(cx);
            }
        }
    }

    pub(crate) fn accept_snapshot(
        &mut self,
        snapshot: Snapshot,
        window: &mut Window,
        cx: &mut Context<Self>,
    ) {
        let model_started = self
            .diagnostics
            .as_ref()
            .and_then(|writer| writer.timestamp());
        let unix_ns = live::unix_ns();
        let now_ms = live::collector_now_ms(&snapshot, unix_ns);
        let mut data = self.shared.borrow_mut();
        let old_catalog = data.catalog.clone();
        let interval = data.session.workspace.interval_ms;
        let Data {
            session,
            history,
            live,
            ..
        } = &mut *data;
        if let Err(error) =
            live.accept(&snapshot, &mut session.workspace, history, now_ms, interval)
        {
            self.notice = error;
            cx.notify();
            return;
        }
        data.catalog = live::catalog(&data.session.workspace);
        data.processes = live::process_views(&snapshot, now_ms, interval * 2);
        data.process_widths = live::process_widths(&data.processes);
        let snapshot = std::sync::Arc::new(snapshot);
        data.snapshot = Some(snapshot);
        let changed = old_catalog != data.catalog;
        let updates: Vec<_> = data
            .catalog
            .iter()
            .filter_map(|monitor| {
                data.views
                    .get(&monitor.id)
                    .map(|view| (view.clone(), monitor.clone()))
            })
            .collect();
        let identities: Vec<_> = data.processes.iter().map(|p| p.identity.clone()).collect();
        self.accepted_unix_ns = unix_ns;
        drop(data);
        self.accepted_model_timing = model_started.zip(
            self.diagnostics
                .as_ref()
                .and_then(|writer| writer.timestamp()),
        );
        self.publish_diagnostics(now_ms);
        for (view, monitor) in updates {
            let _ = view.update(cx, |panel, cx| {
                panel.refresh(monitor, cx);
                live::reconcile_selection(&mut panel.selected, &identities);
            });
        }
        if changed {
            self.capture_sizes(cx);
            ensure_enabled_regions(&self.shared, &self.dock, window, cx);
            self.record(cx);
            self.queue_save(cx);
        }
        self.accepted_clock = Some((std::time::Instant::now(), now_ms));
        self.notify_panels(cx);
    }

    fn publish_diagnostics(&mut self, rendered_at_collector_ms: u64) {
        let Some(writer) = &self.diagnostics else {
            return;
        };
        let data = self.shared.borrow();
        let Some(snapshot) = data.snapshot.clone() else {
            return;
        };
        self.diagnostic_revision += 1;
        let construction_started = writer.timestamp();
        let record = crate::diagnostics::Record::new(
            snapshot,
            self.accepted_unix_ns,
            self.diagnostic_revision,
            rendered_at_collector_ms,
            &data,
        );
        if construction_started.is_some() {
            writer.submit_timed(record, self.accepted_model_timing, construction_started);
        } else {
            writer.submit(record);
        }
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

    #[cfg(test)]
    pub(crate) fn advance(&mut self, cx: &mut Context<Self>) {
        self.tick += 1;
        if let Err(e) = fixture::advance(&mut self.shared.borrow_mut().history, self.tick) {
            self.notice = e;
        }
        self.shared.borrow_mut().processes = fixture::processes();
        self.notify_panels(cx);
    }

    fn queue_save(&mut self, cx: &mut Context<Self>) {
        if self.read_blocked {
            return;
        }
        let Some(dir) = &self.directory else { return };
        let data = self.shared.borrow();
        let result = validate_dock_mode(&data.session.workspace.dock, self.fixture_mode)
            .and_then(|_| data.session.autosave_json());
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
        let catalog = self.shared.borrow().catalog.clone();
        let mut fallback = Workspace::new(
            serde_json::to_value(default_dock_for(&catalog)).expect("default serializes"),
        );
        live::discover(&mut fallback, &catalog);
        let mut session = restore_session(raw, fallback, self.fixture_mode);
        live::discover(&mut session.workspace, &catalog);
        if let Some(rejected) = self.shared.borrow().session.rejected.clone() {
            session.rejected = Some(rejected);
        }
        let interval = Duration::from_millis(session.workspace.interval_ms);
        if let Some(service) = &self.service {
            if let Err(e) = service.set_interval(interval) {
                self.notice = e;
            }
        }
        if !self.fixture_mode {
            self.shared.borrow_mut().catalog = live::catalog(&session.workspace);
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

    fn request_keyboard_repaint(&mut self, window: &mut Window, cx: &Context<Self>) {
        if self.keyboard_repaint_pending {
            return;
        }
        self.keyboard_repaint_pending = true;
        // Keep queued Alt navigation from forcing a redraw for every key.
        cx.on_next_frame(window, |this, _, cx| {
            this.keyboard_repaint_pending = false;
            cx.notify();
        });
    }

    pub(crate) fn command(
        &mut self,
        command: Command,
        window: &mut Window,
        cx: &mut Context<Self>,
    ) {
        match command {
            #[cfg(test)]
            Command::Tick => {
                self.advance(cx);
                return;
            }
            Command::Scroll(dx, dy) => {
                let scroll = self.shared.borrow().scroll.clone();
                let max = scroll.max_offset();
                let old = scroll.offset();
                scroll.set_offset(point(
                    (old.x + px(dx)).clamp(-max.x, px(0.)),
                    (old.y + px(dy)).clamp(-max.y, px(0.)),
                ));
                self.request_keyboard_repaint(window, cx);
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
                    let monitor = self
                        .shared
                        .borrow()
                        .catalog
                        .iter()
                        .find(|m| m.id == id)
                        .cloned();
                    if let Some(monitor) = monitor {
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
                let quantity = data
                    .catalog
                    .iter()
                    .find(|m| m.id == id)
                    .and_then(|m| m.sensors.iter().find(|s| s.id == sensor))
                    .map(|s| s.quantity)
                    .unwrap_or(system_pulse_model::Quantity::Scalar);
                let row = data.session.workspace.panel_mut(&id).sensor_mut(&sensor);
                row.meter = quantity.next_meter(row.meter);
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
                    self.notice = "Save a preset before recalling it".into();
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
            #[cfg(test)]
            Command::ReverseDiscovery => {
                self.shared.borrow_mut().catalog.reverse();
            }
            #[cfg(test)]
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
            Command::Interval(ms) => {
                if let Some(service) = &self.service {
                    if let Err(error) = service.set_interval(Duration::from_millis(ms)) {
                        self.notice = error;
                        return;
                    }
                }
                if [500, 1000, 2000, 5000].contains(&ms) {
                    self.shared.borrow_mut().session.workspace.interval_ms = ms;
                }
            }
            Command::Save => {}
        }
        self.record(cx);
        self.queue_save(cx);
        self.notify_panels(cx);
    }
}

/// Keep scroll clipping bounds in the native accessibility ancestry.
pub(crate) fn scroll_viewport(id: &'static str, native_id: String) -> Stateful<Div> {
    div()
        .id(id)
        .role(Role::ScrollView)
        .accessibility_id(native_id)
}

#[cfg(test)]
mod viewport_accessibility_tests {
    use super::*;

    #[::core::prelude::v1::test]
    fn scroll_viewports_expose_stable_native_geometry_nodes() {
        for (internal, native) in [
            ("workspace-scroll", "workspace:viewport"),
            ("process-table-viewport", "processes:viewport"),
            ("sensor-scroll", "cpu:host:viewport"),
            ("process-row-clip", "processes:rows-viewport"),
        ] {
            let element = scroll_viewport(internal, native.into());
            assert_eq!(element.a11y_role(), Some(Role::ScrollView));
            let mut node = gpui::accesskit::Node::new(Role::ScrollView);
            element.write_a11y_info(&mut node);
            assert_eq!(node.author_id(), Some(native));
        }
    }
}

impl Render for WorkspaceView {
    fn render(&mut self, _: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        let data = self.shared.borrow();
        let monitor_commands = data
            .catalog
            .iter()
            .map(|m| {
                let visible = data.session.workspace.panels[&m.id].visible;
                (
                    format!("{} {}", if visible { "Hide" } else { "Show" }, m.title),
                    Command::PanelVisible(m.id.clone()),
                )
            })
            .collect::<Vec<_>>();
        let mut commands = vec![
            ("Save".into(), Command::Save),
            ("Save preset".into(), Command::SavePreset),
            ("Recall preset".into(), Command::RecallPreset),
        ];
        let selected_interval = data.session.workspace.interval_ms;
        commands.extend([500, 1000, 2000, 5000].map(|ms| {
            (
                format!(
                    "{}{} s",
                    if ms == selected_interval { "✓ " } else { "" },
                    ms as f64 / 1000.
                ),
                Command::Interval(ms),
            )
        }));
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
        let toolbar = div().flex().flex_wrap().gap_1().children(
            commands
                .into_iter()
                .map(|(label, command)| command_button(label, command, cx)),
        );
        let visibility_scroll = self.visibility_scroll.clone();
        let visibility =
            div()
                .flex()
                .flex_wrap()
                .gap_1()
                .children(monitor_commands.into_iter().map(|(label, command)| {
                    let entry = self
                        .visibility_controls
                        .entry(command.control_id())
                        .or_insert_with(|| crate::controls::FocusEntry::new(cx))
                        .clone();
                    let scroll = visibility_scroll.clone();
                    command_button(label, command, cx)
                        .track_focus(&entry.handle)
                        .on_prepaint(move |bounds, window, _| {
                            if entry.entered(window) {
                                crate::controls::reveal(bounds.dilate(px(1.)), &scroll);
                                window.refresh();
                            }
                        })
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
            .child("System Pulse · live host readings")
            .child("Alt+PageUp/PageDown: workspace · Alt+Left/Right: horizontal · table arrows/Home/End · Tab: next control")
            .child(toolbar)
            .child(div().h(px(96.)).flex_none().relative()
                .child(div().id("visibility-controls").size_full().overflow_y_scroll().track_scroll(&self.visibility_scroll).child(visibility))
                .child(Scrollbar::vertical(&self.visibility_scroll).mode(ScrollbarMode::Always)))
            .child(message)
            .child(div().flex_1().min_h_0().min_w_0().relative()
                .child(scroll_viewport("workspace-scroll", "workspace:viewport".into()).size_full().overflow_scroll().track_scroll(&scroll)
                    .debug_selector(|| "workspace-viewport".into())
                    .child(div().w(extent.width).h(extent.height).min_w_full().child(self.dock.clone())))
                .child(Scrollbar::new(&scroll).mode(ScrollbarMode::Always)))
    }
}

fn initial_catalog(fixture_mode: bool) -> Vec<Monitor> {
    #[cfg(test)]
    if fixture_mode {
        return fixture::catalog();
    }
    let _ = fixture_mode;
    live::presentations()
}

fn restore_session(raw: &str, fallback: Workspace, allow_fixture: bool) -> Session {
    let mut session = Session::restore(raw, fallback.clone(), |value| {
        validate_dock_mode(value, allow_fixture)
    });
    if !allow_fixture
        && session.rejected.is_none()
        && (session
            .workspace
            .panels
            .keys()
            .any(|id| live::is_fixture_id(id))
            || session
                .workspace
                .monitors
                .keys()
                .any(|id| live::is_fixture_id(id)))
    {
        session = Session {
            workspace: fallback,
            rejected: Some(system_pulse_model::RejectedInput {
                original: raw.into(),
                error: "Saved workspace contains simulated device identities".into(),
            }),
        };
    }
    // Saved dock leaves may precede persisted presentation metadata.
    fn collect(value: &serde_json::Value, ids: &mut Vec<String>) {
        if let Some(id) = value.get("monitor_id").and_then(serde_json::Value::as_str) {
            ids.push(id.into());
        }
        match value {
            serde_json::Value::Object(map) => {
                for value in map.values() {
                    collect(value, ids);
                }
            }
            serde_json::Value::Array(values) => {
                for value in values {
                    collect(value, ids);
                }
            }
            _ => {}
        }
    }
    let mut ids = Vec::new();
    collect(&session.workspace.dock, &mut ids);
    for id in ids {
        session.workspace.panel_mut(&id);
    }
    session
}

#[cfg(test)]
mod live_tests {
    use super::*;
    #[::core::prelude::v1::test]
    fn live_restore_rejects_copied_fixture_workspace_and_preserves_original() {
        let mut copied = Workspace::new(serde_json::to_value(default_dock()).unwrap());
        fixture::discover(&mut copied, &fixture::catalog());
        let raw = serde_json::to_string(&copied).unwrap();
        let fallback =
            Workspace::new(serde_json::to_value(default_dock_for(&live::presentations())).unwrap());
        let restored = restore_session(&raw, fallback.clone(), false);
        assert_eq!(restored.rejected.as_ref().unwrap().original, raw);
        assert!(restored.autosave_json().is_err());
        assert_eq!(restored.workspace.dock, fallback.dock);
        assert!(
            restored
                .workspace
                .panels
                .keys()
                .all(|id| !live::is_fixture_id(id))
        );
        let mut panels_only = fallback.clone();
        panels_only.panel_mut("gpu:fixture-a");
        assert!(
            restore_session(
                &serde_json::to_string(&panels_only).unwrap(),
                fallback,
                false
            )
            .rejected
            .is_some()
        );
    }
    #[::core::prelude::v1::test]
    fn absent_real_identity_is_valid_before_discovery() {
        let missing = Monitor {
            id: "nvidia:GPU-absent".into(),
            title: "Saved GPU".into(),
            summary: "usage".into(),
            sensors: vec![],
        };
        let dock = serde_json::to_value(default_dock_for(&[missing])).unwrap();
        assert!(validate_dock(&dock).is_ok());
        let workspace = Workspace::new(dock);
        let restored = restore_session(
            &serde_json::to_string(&workspace).unwrap(),
            workspace,
            false,
        );
        assert!(restored.rejected.is_none());
        assert!(restored.workspace.panels.contains_key("nvidia:GPU-absent"));
        assert!(
            live::catalog(&restored.workspace)
                .iter()
                .any(|m| m.id == "nvidia:GPU-absent")
        );
    }
}

fn command_button(label: String, command: Command, cx: &Context<WorkspaceView>) -> Button {
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
        .on_click(cx.listener(move |this, _, window, cx| this.command(command.clone(), window, cx)))
}

#[cfg(test)]
mod diagnostic_delivery_tests {
    use super::{Duration, Snapshot, WorkspaceView};
    use gpui::{AppContext, Element, Role, TestAppContext};

    #[gpui::test]
    fn elapsed_delivery_refreshes_diagnostics_without_refreshing_the_snapshot(
        cx: &mut TestAppContext,
    ) {
        cx.update(gpui_component::init);
        let mut view = None;
        let (_, cx) = cx.add_window_view(|window, cx| {
            let workspace = cx.new(|cx| WorkspaceView::new_fixture(window, cx));
            view = Some(workspace.clone());
            gpui_component::Root::new(workspace, window, cx)
        });
        let view = view.unwrap();
        let dir = std::env::temp_dir().join(format!("pulse-stale-delivery-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join("latest.json");
        let reading = system_pulse_collectors::Reading {
            sensor_id: "cpu:host/usage".into(),
            value: Some(42.),
            total: None,
            availability: system_pulse_collectors::Availability::Available,
            reason: None,
            observations: vec![],
        };
        let snapshot = Snapshot {
            sequence: 43,
            capture_started_ns: 19_900_000_000,
            capture_finished_ns: 20_000_000_000,
            monitors: vec![system_pulse_collectors::MonitorDescriptor {
                id: "cpu:host".into(),
                title: "CPU".into(),
                kind: system_pulse_collectors::MonitorKind::Cpu,
                summary_sensor_id: "cpu:host/usage".into(),
            }],
            sensors: vec![system_pulse_collectors::SensorDescriptor {
                id: "cpu:host/usage".into(),
                monitor_id: "cpu:host".into(),
                title: "Usage".into(),
                kind: system_pulse_collectors::SensorKind::Percentage,
                unit: system_pulse_collectors::Unit::Percent,
                source: "controlled test".into(),
                scope: "host".into(),
                scale: None,
            }],
            readings: vec![
                reading.clone(),
                system_pulse_collectors::Reading {
                    sensor_id: "cpu:host/processes".into(),
                    value: Some(1.),
                    ..reading.clone()
                },
            ],
            processes: vec![system_pulse_collectors::ProcessRow {
                identity: system_pulse_collectors::ProcessIdentity {
                    pid: 7,
                    start_time_ticks: 9,
                },
                name: "controlled process".into(),
                user: Some("user".into()),
                user_reason: None,
                cpu_percent: reading.clone(),
                memory_bytes: reading.clone(),
                read_bytes_per_second: reading.clone(),
                write_bytes_per_second: reading.clone(),
                threads: reading,
            }],
            ..Snapshot::default()
        };
        cx.update(|window, cx| {
            view.update(cx, |this, cx| {
                this.diagnostics =
                    Some(crate::diagnostics::Writer::start_with_trace(path.clone(), true).unwrap());
                this.accept_snapshot(snapshot, window, cx);
            })
        });
        let deadline = std::time::Instant::now() + Duration::from_secs(2);
        let before: serde_json::Value = loop {
            if let Ok(raw) = std::fs::read_to_string(&path) {
                if let Ok(record) = serde_json::from_str::<serde_json::Value>(&raw) {
                    if record["snapshot"]["sequence"] == 43 {
                        break record;
                    }
                }
            }
            assert!(
                std::time::Instant::now() < deadline,
                "initial diagnostic write did not finish"
            );
            std::thread::sleep(Duration::from_millis(5));
        };
        let initial_history_len = cx.read(|cx| {
            view.read(cx)
                .shared
                .borrow()
                .history
                .samples("cpu:host", "cpu:host/usage")
                .unwrap()
                .len()
        });
        cx.update(|window, cx| {
            view.update(cx, |this, cx| {
                this.accepted_clock = Some((
                    std::time::Instant::now() - Duration::from_millis(3000),
                    20_000,
                ));
                this.deliver(window, cx);
                let revision = this.diagnostic_revision;
                this.deliver(window, cx);
                assert_eq!(
                    this.diagnostic_revision, revision,
                    "unchanged stale state must not publish again"
                );
            })
        });
        let writer = cx.update(|_, cx| view.update(cx, |this, _| this.diagnostics.take()));
        drop(writer); // Flush the bounded worker's final record, without another collection.
        let after: serde_json::Value =
            serde_json::from_str(&std::fs::read_to_string(&path).unwrap()).unwrap();
        let mapping = |record: &serde_json::Value, id: &str| {
            record["rendered"]
                .as_array()
                .unwrap()
                .iter()
                .find(|r| r["element_id"] == id)
                .unwrap()
                .clone()
        };
        let id = "cpu:host:value:cpu:host/usage";
        assert_eq!(mapping(&before, id)["sample"]["status"], "current");
        cx.read(|cx| {
            let data = view.read(cx).shared.borrow();
            let monitor = data.catalog.iter().find(|m| m.id == "cpu:host").unwrap();
            let sample = data.history.latest("cpu:host", "cpu:host/usage").unwrap();
            assert_eq!(sample.status, system_pulse_model::ReadingStatus::Stale);
            assert_eq!(
                data.history
                    .samples("cpu:host", "cpu:host/usage")
                    .unwrap()
                    .len(),
                initial_history_len
            );
            let label = crate::meters::sensor_label(monitor, &monitor.sensors[0], sample);
            let mut node = gpui::accesskit::Node::new(Role::Label);
            crate::meters::metric_label(id.into(), label.clone()).write_a11y_info(&mut node);
            assert_eq!(node.value(), Some(label.as_str()));
            assert_eq!(mapping(&after, id)["label"], label);
            assert_eq!(mapping(&after, id)["sample"]["status"], "stale");
            assert_eq!(
                mapping(&after, "cpu:host:summary")["label"],
                crate::meters::summary(monitor, &data.history)
            );
            assert_eq!(
                mapping(&after, "process:7:9:cell:2")["label"],
                data.processes[0].cells[2]
            );
            assert!(data.processes[0].cells[2].contains("Stale"));
        });
        assert_eq!(
            after["render_revision"].as_u64().unwrap(),
            before["render_revision"].as_u64().unwrap() + 1
        );
        assert_eq!(before["rendered_at_collector_ms"], 20_000);
        assert!(after["rendered_at_collector_ms"].as_u64().unwrap() >= 23_000);
        assert_eq!(
            mapping(&after, id)["sample"]["at_ms"],
            mapping(&before, id)["sample"]["at_ms"]
        );
        assert_eq!(after["snapshot"], before["snapshot"]);
        assert_eq!(after["accepted_unix_ns"], before["accepted_unix_ns"]);
        assert_eq!(after["application_pid"], before["application_pid"]);
        let timing_path = path.with_extension("publication-timing.json");
        assert!(timing_path.is_file(), "opt-in publication timings missing");
        let timing: serde_json::Value =
            serde_json::from_slice(&std::fs::read(&timing_path).unwrap()).unwrap();
        let records = timing["history"]["records"].as_array().unwrap();
        assert_eq!(records.len(), 2);
        for record in records {
            assert_eq!(record["sequence"], 43);
            assert_eq!(record["accepted_unix_ns"], before["accepted_unix_ns"]);
            let stages = &record["stages"];
            let values: Vec<_> = [
                "acceptance_started_ns",
                "model_completed_ns",
                "construction_started_ns",
                "construction_completed_ns",
                "submission_started_ns",
                "submission_completed_ns",
                "dequeue_ns",
            ]
            .iter()
            .map(|key| stages[key].as_u64().unwrap())
            .collect();
            assert!(values.windows(2).all(|pair| pair[0] <= pair[1]));
        }
        assert_eq!(
            records[0]["stages"]["acceptance_started_ns"],
            records[1]["stages"]["acceptance_started_ns"]
        );
        assert_eq!(
            records[0]["stages"]["model_completed_ns"],
            records[1]["stages"]["model_completed_ns"]
        );
        std::fs::remove_file(timing_path).unwrap();
        std::fs::remove_file(path).unwrap();
        std::fs::remove_dir(dir).unwrap();
    }
}

#[cfg(test)]
mod preset_bound_tests {
    use super::{Command, WorkspaceView};
    use gpui::{AppContext, TestAppContext};

    #[gpui::test]
    fn oversized_preset_keeps_the_previous_slot_and_reports_the_save_error(
        cx: &mut TestAppContext,
    ) {
        cx.update(gpui_component::init);
        let mut view = None;
        let (_, cx) = cx.add_window_view(|window, cx| {
            let workspace = cx.new(|cx| WorkspaceView::new_fixture(window, cx));
            view = Some(workspace.clone());
            gpui_component::Root::new(workspace, window, cx)
        });
        let view = view.unwrap();
        cx.update(|window, cx| {
            view.update(cx, |this, cx| {
                let previous = this.shared.borrow().session.autosave_json().unwrap();
                this.preset = Some(previous.clone());
                this.shared
                    .borrow_mut()
                    .session
                    .workspace
                    .monitors
                    .values_mut()
                    .next()
                    .unwrap()
                    .title = "x".repeat(system_pulse_model::MAX_CONFIGURATION_BYTES + 1);
                this.command(Command::SavePreset, window, cx);
                assert!(
                    this.preset.as_deref() == Some(previous.as_str()),
                    "rejected serialization must preserve the previous preset slot"
                );
                assert!(this.notice.contains("16 MiB"));
            })
        });
    }
}
