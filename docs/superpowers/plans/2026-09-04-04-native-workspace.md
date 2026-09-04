# Native Workspace Interaction Proof Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a native, visibly labelled fixture application proving WV-01 through WV-12 with separate dock regions, scrolling, persistent collapse, truthful compact readings, and keyboard controls.

**Architecture:** The `system-pulse` example consumes `system-pulse-model`, the separate-panel policy, and the dock geometry extension from plans 01–03. The app owns identity, presentation, fixtures, and storage; `DockArea` owns geometry and drag operations. A single fixture timer supplies compact summaries and bounded chart history whether panels are expanded, collapsed, hidden, or offscreen.

**Tech Stack:** Rust 2024, the pinned GPUI fork, gpui-base, gpui-component Root/theme, serde_json, smol, standard-library filesystem operations.

---

Execute inside the isolated fork checkout established by the [overview](2026-09-04-workspace-visibility.md), after plans 01–03. Source baseline: `ba3433f0740ee5ba2b1db459af49229caf0c1bcc`. Planning reference checkout: `/tmp/task-manager-plan-n5l92za_`; do not edit that reference checkout. This document is a plan, not evidence that the following code compiled or native interactions passed.

The default fixture arrangement is an eight-panel vertical stress-test stack. This intentionally exercises overflow immediately; it is not the production first-launch arrangement in the product design. Edge dragging establishes horizontal arrangements during acceptance.

Source contracts checked: `examples/hello_world/src/main.rs:25` initializes `gpui_component` and wraps the view in `Root`; `crates/base/src/dock/registry.rs:88` rebuilds registered panel handles; `dock/tab_group.rs:795` supplies drag payloads and renderer context; `base/button.rs:93` supplies owned focus and Enter/Space activation; `base/scrollable_mask.rs:56` implements vertical wheel chaining; `base/virtual_list.rs:140` supplies range-based row rendering; `base/scrollbar.rs:67` exposes viewport/offset contracts. MCP transport was unavailable during this pass; these were read directly.

Dependencies added by earlier plans, not existing baseline methods: `PanelPolicy::Separate`, `PanelPolicy::validate_state`, `DockArea::set_panel_policy`, `try_set_center`, `add_panel_split_view`, `PanelExtent`, `Panel::dock_extent`, `DockArea::content_extent`, and `DockArea::refresh_geometry`. Use exactly those earlier implementations; do not create substitutes in the app.

File responsibilities:

All `src/*` and `README.md` paths below are relative to `examples/system_pulse/`; shell commands run from the fork workspace root.

| File | Responsibility |
| --- | --- |
| `examples/system_pulse/Cargo.toml`, `src/main.rs`, `src/lib.rs` | Native launch and module boundary |
| `src/fixture.rs` | Stable fixture catalogue, summaries, one deterministic tick |
| `src/storage.rs` | Platform path, bounded reads, ordered atomic writes |
| `src/controls.rs` | Accessible buttons, focus reveal, scroll arithmetic |
| `src/meters.rs` | Compact values and bounded gap-preserving fixture meters |
| `src/panel.rs` | Panel body, independent sensor rows, header and dock skin |
| `src/workspace.rs` | Dock lifecycle, commands, restore, autosave, fixture timer |
| `src/native_tests.rs` | Native geometry, keyboard and restoration evidence |
| `README.md` | Launch and manual interaction acceptance procedure |

## Task 1: Establish the executable and deterministic fixture catalogue

**Files:** Create the manifest, `src/main.rs`, `src/lib.rs`, and `src/fixture.rs`; modify the root workspace member list.

- [ ] Add `"examples/system_pulse"` to `[workspace].members`. The model member is added by plan 02; do not add it twice. Create this complete manifest:

```toml
[package]
name = "system-pulse"
version = "0.1.0"
edition.workspace = true
license = "GPL-3.0-or-later"
publish = false

[dependencies]
gpui.workspace = true
gpui_platform.workspace = true
gpui-base.workspace = true
gpui-component.workspace = true
serde_json.workspace = true
smol.workspace = true
system-pulse-model = { path = "model" }

[dev-dependencies]
gpui = { workspace = true, features = ["test-support"] }

[lints]
workspace = true
```

- [ ] Create `src/fixture.rs` with the following implementation and test. These are simulated identities, not guessed hardware identities. `summary` is fixed independently of sensor visibility.

```rust
use system_pulse_model::{HistoryStore, ReadingStatus, Sample, Workspace};

#[derive(Clone)]
pub struct Monitor {
    pub id: &'static str,
    pub title: &'static str,
    pub summary: &'static str,
    pub sensors: Vec<(&'static str, &'static str)>,
}

pub fn catalog() -> Vec<Monitor> {
    vec![
        Monitor {
            id: "cpu",
            title: "CPU",
            summary: "overall",
            sensors: vec![
                ("overall", "Overall utilization"),
                ("core0", "Core 0 utilization"),
            ],
        },
        Monitor {
            id: "gpu:fixture-a",
            title: "GPU A",
            summary: "utilization",
            sensors: vec![("utilization", "Utilization")],
        },
        Monitor {
            id: "gpu:fixture-b",
            title: "GPU B",
            summary: "utilization",
            sensors: vec![("utilization", "Utilization")],
        },
        Monitor {
            id: "memory",
            title: "Memory",
            summary: "capacity",
            sensors: vec![("capacity", "RAM used / total")],
        },
        Monitor {
            id: "volume:fixture-home",
            title: "Home volume",
            summary: "capacity",
            sensors: vec![("capacity", "Capacity used / total")],
        },
        Monitor {
            id: "interface:fixture-lan",
            title: "LAN",
            summary: "traffic",
            sensors: vec![("traffic", "RX / TX throughput")],
        },
        Monitor {
            id: "processes",
            title: "Processes",
            summary: "count",
            sensors: vec![],
        },
        Monitor {
            id: "settings",
            title: "Settings",
            summary: "",
            sensors: vec![],
        },
    ]
}

pub fn discover(workspace: &mut Workspace, monitors: &[Monitor]) {
    for monitor in monitors {
        let panel = workspace.panel_mut(monitor.id);
        for (id, _) in &monitor.sensors {
            panel.sensor_mut(id);
        }
    }
}

pub fn sample(monitor: &str, sensor: &str, tick: u64) -> Sample {
    let value = ((tick * 7 + sensor.len() as u64 * 3) % 80 + 10) as f64;
    let status = match tick % 12 {
        8 => ReadingStatus::Unavailable,
        9 => ReadingStatus::Stale,
        _ => ReadingStatus::Current,
    };
    let (text, unit) = match monitor {
        "memory" => (format!("{:.1} / 32", value / 4.), "GiB"),
        "volume:fixture-home" => (format!("{:.0} / 1000", value * 10.), "GiB"),
        "interface:fixture-lan" => (format!("RX {:.1} · TX {:.1}", value, value / 4.), "MiB/s"),
        "processes" => ("500".to_owned(), "processes"),
        _ => (format!("{value:.0}"), "%"),
    };
    Sample {
        at_ms: tick * 1000,
        value: if status == ReadingStatus::Unavailable {
            None
        } else {
            Some(value)
        },
        text: if status == ReadingStatus::Unavailable {
            "Unavailable".into()
        } else {
            text
        },
        unit: unit.into(),
        status,
    }
}

pub fn advance(history: &mut HistoryStore, tick: u64) -> Result<(), String> {
    for monitor in catalog() {
        let mut ids: Vec<_> = monitor.sensors.iter().map(|(id, _)| *id).collect();
        if !monitor.summary.is_empty() && !ids.contains(&monitor.summary) {
            ids.push(monitor.summary);
        }
        for sensor in ids {
            history.push(monitor.id, sensor, sample(monitor.id, sensor, tick))?;
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn fixtures_continue_through_gaps_and_keep_stable_identity() {
        let mut history = HistoryStore::new(12).unwrap();
        for tick in 1..=14 {
            advance(&mut history, tick).unwrap();
        }
        let cpu = history.samples("cpu", "overall").unwrap();
        assert_eq!(cpu.len(), 12);
        assert_eq!(cpu.front().unwrap().at_ms, 3000);
        assert_eq!(cpu.back().unwrap().at_ms, 14000);
        assert_eq!(cpu.iter().filter(|s| s.chart_value().is_none()).count(), 2);
        assert!(history.latest("gpu:fixture-a", "utilization").is_some());
        assert!(history.latest("gpu:fixture-b", "utilization").is_some());
    }
}
```

- [ ] Create `src/main.rs`:

```rust
use gpui::*;
use gpui_component::{ActiveTheme, Root};
use system_pulse::workspace::WorkspaceView;

fn main() {
    gpui_platform::application().run(|cx| {
        gpui_component::init(cx);
        cx.spawn(async move |cx| {
            let opened = cx.open_window(
                WindowOptions {
                    window_min_size: Some(size(px(960.), px(640.))),
                    ..WindowOptions::default()
                },
                |window, cx| {
                    window.set_window_title("System Pulse — Fixture mode");
                    let view = cx.new(|cx| WorkspaceView::new(true, window, cx));
                    cx.new(|cx| Root::new(view, window, cx).bg(cx.theme().background))
                },
            );
            if let Err(error) = opened {
                eprintln!("Open System Pulse: {error}");
            }
        })
        .detach();
    });
}
```

- [ ] Create `src/lib.rs` declaring the files implemented in the following tasks:

```rust
pub mod controls;
pub mod fixture;
pub mod meters;
#[cfg(test)]
mod native_tests;
pub mod panel;
pub mod storage;
pub mod workspace;
```

The executable first compiles after Task 5 installs all declared modules; do not use temporary empty modules or claim this task builds alone. Run the fixture test with the full package at Task 5. Commit this cohesive tranche with Task 5 after its verification, not before.

## Task 2: Implement bounded storage and focus-safe controls

**Files:** Create `src/storage.rs` and `src/controls.rs`.

- [ ] Create `src/storage.rs`. Reads are bounded to 1 MiB; absent files differ from unreadable files. All writes pass through one cloneable lock, with a revision check that prevents an older queued write replacing a newer snapshot. A rejected input is protected by the model's autosave gate in Task 5.

```rust
use std::{
    collections::BTreeMap,
    fs,
    io::{Read, Write},
    path::{Path, PathBuf},
    sync::{Arc, Mutex},
};

#[derive(Clone, Default)]
pub struct Storage(Arc<Mutex<BTreeMap<PathBuf, u64>>>);

pub fn directory() -> Result<PathBuf, String> {
    if let Some(path) = std::env::var_os("SYSTEM_PULSE_STATE_DIR") {
        return Ok(path.into());
    }
    #[cfg(target_os = "windows")]
    let base = std::env::var_os("APPDATA").map(PathBuf::from);
    #[cfg(target_os = "macos")]
    let base =
        std::env::var_os("HOME").map(|p| PathBuf::from(p).join("Library/Application Support"));
    #[cfg(not(any(target_os = "windows", target_os = "macos")))]
    let base = std::env::var_os("XDG_CONFIG_HOME")
        .map(PathBuf::from)
        .or_else(|| std::env::var_os("HOME").map(|p| PathBuf::from(p).join(".config")));
    base.map(|p| p.join("system-pulse-fixture"))
        .ok_or_else(|| "No platform configuration directory is available".into())
}

pub fn read(path: &Path) -> Result<Option<String>, String> {
    let file = match fs::File::open(path) {
        Ok(file) => file,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(e) => return Err(format!("Read {}: {e}", path.display())),
    };
    let mut bytes = Vec::new();
    file.take(1_048_577)
        .read_to_end(&mut bytes)
        .map_err(|e| e.to_string())?;
    if bytes.len() > 1_048_576 {
        return Err("Saved state exceeds 1 MiB".into());
    }
    String::from_utf8(bytes)
        .map(Some)
        .map_err(|e| format!("State is not UTF-8: {e}"))
}

impl Storage {
    pub fn write(&self, path: &Path, revision: u64, data: &str) -> Result<(), String> {
        let mut versions = self.0.lock().map_err(|_| "Storage lock poisoned")?;
        if versions.get(path).is_some_and(|saved| *saved > revision) {
            return Ok(());
        }
        let parent = path.parent().ok_or("State path has no parent")?;
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
        let temp = path.with_extension(format!("{}.tmp", std::process::id()));
        let result = (|| -> std::io::Result<()> {
            let mut file = fs::File::create(&temp)?;
            file.write_all(data.as_bytes())?;
            file.sync_all()?;
            fs::rename(&temp, path)?;
            Ok(())
        })();
        if let Err(error) = result {
            let _ = fs::remove_file(&temp);
            return Err(format!("Save {}: {error}", path.display()));
        }
        versions.insert(path.to_owned(), revision);
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn older_work_cannot_replace_a_newer_atomic_snapshot() {
        let dir = std::env::temp_dir().join(format!("system-pulse-storage-{}", std::process::id()));
        let path = dir.join("state.json");
        let storage = Storage::default();
        storage.write(&path, 2, "new").unwrap();
        storage.write(&path, 1, "old").unwrap();
        assert_eq!(read(&path).unwrap().as_deref(), Some("new"));
        fs::remove_file(path).unwrap();
        fs::remove_dir(dir).unwrap();
    }
}
```

- [ ] Create `src/controls.rs`. A focused control is revealed only on a focus transition, so scrolling with the pointer can still move an already-focused control offscreen. Reveal the inner viewport first, then the workspace with the adjusted target position. The names and `aria_expanded` state live on the actual button.

```rust
use crate::workspace::{Command, Shared};
use gpui::*;
use gpui_base::{Button, ElementExt};
use std::{cell::Cell, rc::Rc};

#[derive(Clone)]
pub struct FocusEntry {
    pub handle: FocusHandle,
    was_focused: Rc<Cell<bool>>,
}
impl FocusEntry {
    pub fn new(cx: &mut App) -> Self {
        Self {
            handle: cx.focus_handle(),
            was_focused: Rc::new(Cell::new(false)),
        }
    }
    pub fn entered(&self, window: &Window) -> bool {
        let focused = self.handle.is_focused(window);
        let previous = self.was_focused.replace(focused);
        focused && !previous
    }
}

pub fn reveal(bounds: Bounds<Pixels>, scroll: &ScrollHandle) -> Point<Pixels> {
    let viewport = scroll.bounds();
    let mut shift = point(px(0.), px(0.));
    if bounds.left() < viewport.left() {
        shift.x = viewport.left() - bounds.left();
    } else if bounds.right() > viewport.right() {
        shift.x = viewport.right() - bounds.right();
    }
    if bounds.top() < viewport.top() {
        shift.y = viewport.top() - bounds.top();
    } else if bounds.bottom() > viewport.bottom() {
        shift.y = viewport.bottom() - bounds.bottom();
    }
    let old = scroll.offset();
    let max = scroll.max_offset();
    let next = point(
        (old.x + shift.x).clamp(-max.x, px(0.)),
        (old.y + shift.y).clamp(-max.y, px(0.)),
    );
    scroll.set_offset(next);
    next - old
}

pub fn button(
    id: String,
    label: String,
    expanded: Option<bool>,
    focus: &FocusEntry,
    shared: &Shared,
    command: Command,
    inner: Option<ScrollHandle>,
) -> impl IntoElement {
    let target = shared.borrow().owner.clone();
    let outer = shared.borrow().scroll.clone();
    let focus = focus.clone();
    let mut control = Button::new(SharedString::from(id.clone()))
        .accessibility_label(label.clone())
        .track_focus(&focus.handle)
        .px_2()
        .h(px(28.))
        .border_1()
        .rounded_sm()
        .on_mouse_down(MouseButton::Left, |_, _, cx| cx.stop_propagation())
        .on_click(move |_, window, cx| {
            cx.stop_propagation();
            if let Some(owner) = &target {
                let _ = owner.update(cx, |view, cx| view.command(command.clone(), window, cx));
            }
        })
        .debug_selector(move || id.clone().into())
        .on_prepaint(move |mut bounds, window, cx| {
            if focus.entered(window) {
                if let Some(inner) = &inner {
                    bounds.origin += reveal(bounds, inner);
                }
                reveal(bounds, &outer);
                window.refresh();
            }
            let _ = cx;
        })
        .child(label);
    if let Some(expanded) = expanded {
        control = control.aria_expanded(expanded);
    }
    control
}
```

## Task 3: Draw truthful compact values and detailed fixture meters

**Files:** Create `src/meters.rs`.

- [ ] Install this complete renderer. A stale value remains text with its status; stale/unavailable samples break chart paths. All fixture numeric chart values are normalized demonstration values, visibly described by the application banner; these are not production capacity scales.

```rust
use gpui::*;
use gpui_component::ActiveTheme;
use system_pulse_model::{Meter, ReadingStatus, Sample};

pub fn value(sample: Option<&Sample>) -> String {
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

pub fn meter(kind: Meter, samples: Vec<Sample>, cx: &App) -> AnyElement {
    if kind == Meter::Number {
        return div().child(value(samples.last())).into_any_element();
    }
    let color = cx.theme().primary;
    let height = if kind == Meter::Sparkline { 36. } else { 96. };
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
                                + std::f32::consts::TAU * v as f32 / 100. * step as f32 / 60.;
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
    .h(px(height))
    .into_any_element()
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn compact_status_does_not_turn_unavailable_into_zero() {
        assert_eq!(
            value(Some(&crate::fixture::sample("cpu", "overall", 8))),
            "Unavailable"
        );
        assert!(value(Some(&crate::fixture::sample("cpu", "overall", 9))).ends_with("Stale"));
        assert_eq!(value(None), "Waiting for fixture");
    }
}
```

## Task 4: Implement the separate-region skin and independent sensor bodies

**Files:** Create `src/panel.rs`.

- [ ] Create the following file. Header drag handling is attached only to the title/summary area; buttons are siblings. The renderer preserves the framework's drop handler on the content frame. Compact panels do not instantiate their body. Process rows use a bounded viewport and virtual range callback; their keyboard focus is one table stop with Up/Down/Home/End navigation, so Tab leaves the table.

```rust
use crate::{
    controls::{self, FocusEntry},
    fixture::Monitor,
    meters,
    workspace::{Command, Shared},
};
use gpui::*;
use gpui_base::{
    ElementExt, ScrollableMask, Scrollbar, ScrollbarMode, Table, TableCell, TableRow,
    VirtualListScrollHandle, dock::*, v_virtual_list,
};
use gpui_component::ActiveTheme;
use std::{collections::BTreeMap, rc::Rc, sync::Arc};

pub struct MonitorPanel {
    pub monitor: Monitor,
    pub shared: Shared,
    pub group: Option<WeakEntity<TabGroup>>,
    pub focus: FocusHandle,
    pub controls: BTreeMap<String, FocusEntry>,
    body_scroll: ScrollHandle,
    table_scroll: VirtualListScrollHandle,
    pub(crate) selected: usize,
}

impl MonitorPanel {
    pub fn new(monitor: Monitor, shared: Shared, cx: &mut Context<Self>) -> Self {
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
    ) -> AnyElement {
        controls::button(
            format!("{}:{key}", self.monitor.id),
            label,
            expanded,
            &self.controls[key],
            &self.shared,
            command,
            body.then(|| self.body_scroll.clone()),
        )
        .into_any_element()
    }

    pub fn header(
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
            if collapsed && !summary.is_empty() {
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
            ))
            .child(
                div()
                    .id("drag-title")
                    .flex_1()
                    .min_w(px(0.))
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
                        ))
                        .child(div().flex_1().child(current))
                        .child(self.control(
                            &format!("visible:{sensor}"),
                            format!("Hide {label}"),
                            None,
                            Command::SensorVisible(id.clone(), sensor.clone()),
                            true,
                        )),
                )
                .child(self.control(
                    &format!("meter:{sensor}"),
                    format!("Meter: {:?}", state.meter),
                    None,
                    Command::Meter(id, sensor),
                    true,
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

    fn process_table(&mut self, cx: &mut Context<Self>) -> AnyElement {
        let handle = self.controls["table"].handle.clone();
        let sizes = Rc::new(vec![size(px(600.), px(28.)); 500]);
        let list = v_virtual_list(cx.entity(), "process-rows", sizes, |this, range, _, _| {
            range
                .map(|index| {
                    TableRow::new(("process", index), index + 1)
                        .flex()
                        .h(px(28.))
                        .aria_selected(index == this.selected)
                        .debug_selector(move || format!("process-row:{index}").into())
                        .child(
                            TableCell::new(("pid", index), 1)
                                .w(px(90.))
                                .child(format!("{}", 1000 + index)),
                        )
                        .child(
                            TableCell::new(("name", index), 2)
                                .w(px(320.))
                                .child(format!("fixture-process-{index}")),
                        )
                        .child(
                            TableCell::new(("cpu", index), 3)
                                .w(px(100.))
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
                    this.table_scroll.base_handle().bounds(),
                    &this.shared.borrow().scroll,
                );
                window.refresh();
                cx.stop_propagation();
                cx.notify();
            }))
            .on_prepaint(move |bounds, window, _| {
                if focus.entered(window) {
                    controls::reveal(bounds, &outer);
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
    fn render(&mut self, _: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        if self.shared.borrow().session.workspace.panels[self.monitor.id].collapsed {
            return Empty.into_any_element();
        }
        let content = match self.monitor.id {
            "processes" => self.process_table(cx),
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
pub struct WorkspaceSkin(pub Shared);
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
            .border_1()
            .border_color(cx.theme().border)
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

pub fn register(shared: Shared, cx: &mut App) {
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
```

`PanelExtent` and `refresh_geometry` come from plan 03. Do not replace collapse with `visible(false)`: hidden monitors are removed explicitly by the app and reinserted as separate regions, while collapsed monitors remain in their logical regions.

## Task 5: Integrate dock lifecycle, fixture cadence, state and one preset slot

**Files:** Create `src/workspace.rs` and the tests from Task 6 before running the package checks.

- [ ] Create this complete application controller. The one-slot preset exists to prove round-trip presentation behavior, not to implement full preset management. Rejected input keeps autosave disabled. Explicit recovery first archives rejected bytes before permitting a default-layout save.

```rust
use crate::{
    fixture::{self, Monitor},
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
use system_pulse_model::{ExpandedSize, HistoryStore, Meter, Session, Workspace};

pub type Shared = Rc<RefCell<Data>>;
pub struct Data {
    pub session: Session,
    pub history: HistoryStore,
    pub catalog: Vec<Monitor>,
    pub owner: Option<WeakEntity<WorkspaceView>>,
    pub views: BTreeMap<String, WeakEntity<MonitorPanel>>,
    pub bounds: BTreeMap<String, Bounds<Pixels>>,
    pub scroll: ScrollHandle,
}

#[derive(Clone)]
pub enum Command {
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

pub fn default_dock() -> DockAreaState {
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

pub fn validate_dock(value: &serde_json::Value) -> Result<(), String> {
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

pub struct WorkspaceView {
    pub shared: Shared,
    pub dock: Entity<DockArea>,
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
                Err(e) => notice = e,
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
            let shared = view.shared.clone();
            let dock = view.dock.clone();
            let storage = view.storage.clone();
            let path = view.directory.clone();
            let blocked = view.read_blocked;
            cx.on_app_quit(move |_, cx| {
                let mut data = shared.borrow_mut();
                data.session.workspace.dock =
                    serde_json::to_value(dock.read(cx).dump(cx)).expect("dock serializes");
                let json = validate_dock(&data.session.workspace.dock)
                    .and_then(|_| data.session.autosave_json());
                let storage = storage.clone();
                let path = path.clone();
                cx.background_executor().spawn(async move {
                    if !blocked {
                        if let (Some(path), Ok(json)) = (path, json) {
                            if let Err(e) =
                                storage.write(&path.join("workspace.json"), u64::MAX, &json)
                            {
                                eprintln!("{e}");
                            }
                        }
                    }
                })
            })
            .detach();
        }
        view
    }

    fn capture_sizes(&mut self) {
        let mut data = self.shared.borrow_mut();
        let bounds = data.bounds.clone();
        for (id, bounds) in bounds {
            let panel = data.session.workspace.panel_mut(&id);
            if !panel.collapsed
                && panel.visible
                && bounds.size.width >= px(320.)
                && bounds.size.height >= px(220.)
            {
                panel.expanded_size = ExpandedSize {
                    width: bounds.size.width.as_f32(),
                    height: bounds.size.height.as_f32(),
                };
            }
        }
    }

    pub fn record(&mut self, cx: &App) {
        self.capture_sizes();
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

    pub fn advance(&mut self, cx: &mut Context<Self>) {
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

    pub fn restore(&mut self, raw: &str, window: &mut Window, cx: &mut Context<Self>) {
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

    pub fn command(&mut self, command: Command, window: &mut Window, cx: &mut Context<Self>) {
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
                self.capture_sizes();
                let view = self.shared.borrow().views.get(&id).cloned();
                if let Some(view) = view {
                    let _ = view.update(cx, |p, _| p.controls["collapse"].handle.focus(window));
                }
                let mut data = self.shared.borrow_mut();
                let panel = data.session.workspace.panel_mut(&id);
                panel.collapsed = !panel.collapsed;
                drop(data);
                self.dock
                    .update(cx, |dock, cx| dock.refresh_geometry(window, cx));
            }
            Command::PanelVisible(id) => {
                self.capture_sizes();
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
                    self.focus.focus(window);
                    self.dock
                        .update(cx, |dock, cx| dock.remove_panel(panel, window, cx));
                }
                self.dock
                    .update(cx, |dock, cx| dock.refresh_geometry(window, cx));
            }
            Command::RowCollapse(id, sensor) => {
                let view = self.shared.borrow().views.get(&id).cloned();
                if let Some(view) = view {
                    let _ = view.update(cx, |p, _| {
                        p.controls[&format!("row:{sensor}")].handle.focus(window)
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
                        return;
                    }
                }
                self.shared.borrow_mut().session.accept_recovery();
                self.notice.clear();
            }
            Command::ReverseDiscovery => {
                self.shared.borrow_mut().catalog.reverse();
            }
            Command::ToggleGpu => {
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
                "Saved layout rejected: {}. Original input retained; autosave blocked.",
                rejected.error
            );
            commands.push(("Recover default layout".into(), Command::Recover));
        }
        let scroll = data.scroll.clone();
        drop(data);
        let extent = self.dock.read(cx).content_extent(cx);
        let toolbar =
            div()
                .flex()
                .flex_wrap()
                .gap_1()
                .children(
                    commands
                        .into_iter()
                        .enumerate()
                        .map(|(index, (label, command))| {
                            Button::new(("workspace-command", index))
                                .accessibility_label(label.clone())
                                .child(label)
                                .px_2()
                                .h(px(28.))
                                .border_1()
                                .rounded_sm()
                                .on_click(cx.listener(move |this, _, window, cx| {
                                    this.command(command.clone(), window, cx)
                                }))
                        }),
                );
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
            .child(div().flex_1().min_h(px(0.)).min_w(px(0.)).relative()
                .child(div().id("workspace-scroll").size_full().overflow_scroll().track_scroll(&scroll)
                    .debug_selector(|| "workspace-viewport".into())
                    .child(div().w(extent.width).h(extent.height).min_w_full().child(self.dock.clone())))
                .child(Scrollbar::new(&scroll).mode(ScrollbarMode::Always)))
    }
}
```

- [ ] Add the native tests from Task 6, then run `rtk cargo test -p system-pulse --lib`. Expect the fixture/status/storage tests and native tests to pass. If a signature differs after rebasing the pinned fork, inspect that source and update this app and tests together; do not bypass a failing acceptance assertion.
- [ ] Run `rtk cargo check -p system-pulse --all-targets` and `rtk cargo clippy -p system-pulse --all-targets -- -D warnings`. Resolve compiler/lint failures, including unused imports, before committing. Run `rtk cargo fmt --all --check`; format changed Rust files if required and repeat the check.
- [ ] Commit the executable and modules together after verification: `rtk git add Cargo.toml examples/system_pulse` then `rtk git commit -m "feat: add native fixture workspace with persistent collapse"`.

## Task 6: Prove geometry, state restoration and keyboard behavior natively

**Files:** Create `src/native_tests.rs`.

- [ ] Write these tests before completing Task 5. Run `rtk cargo test -p system-pulse --lib` once the declarations exist and before the controller implementation to record the expected missing-implementation failure. After installing Tasks 1–5, rerun that exact command and retain its output. These are intended native checks; they have not run during planning.

```rust
use crate::{
    panel::MonitorPanel,
    workspace::{Command, WorkspaceView, default_dock},
};
use gpui::*;
use gpui_base::{Placement, dock::*};

fn harness(cx: &mut TestAppContext) -> (Entity<WorkspaceView>, &mut VisualTestContext) {
    cx.update(gpui_component::init);
    let (view, cx) = cx.add_window_view(|window, cx| WorkspaceView::new(false, window, cx));
    draw(cx);
    (view, cx)
}
fn draw(cx: &mut VisualTestContext) {
    for _ in 0..3 {
        cx.update(|window, cx| window.draw(cx).clear(cx));
    }
}
fn command(view: &Entity<WorkspaceView>, cmd: Command, cx: &mut VisualTestContext) {
    cx.update(|window, cx| view.update(cx, |this, cx| this.command(cmd, window, cx)));
    draw(cx);
}
fn panel(view: &Entity<WorkspaceView>, id: &str, cx: &VisualTestContext) -> Entity<MonitorPanel> {
    cx.read(|cx| view.read(cx).shared.borrow().views[id].upgrade().unwrap())
}
fn leaf_nodes(node: &PaneNode) -> Vec<(NodeId, PanelId)> {
    match node.kind() {
        PaneRef::Tabs { panels, .. } => {
            assert_eq!(panels.len(), 1, "every region has exactly one monitor");
            vec![(node.id(), panels[0])]
        }
        PaneRef::Split { children, .. } => children.iter().flat_map(leaf_nodes).collect(),
        PaneRef::Tiles { .. } => panic!("fixture never installs tile layout"),
    }
}

#[gpui::test]
fn collapse_keeps_a_header_and_continuous_history(cx: &mut TestAppContext) {
    let (view, cx) = harness(cx);
    let before = cx.debug_bounds("panel:cpu").unwrap().size;
    command(
        &view,
        Command::RowCollapse("cpu".into(), "overall".into()),
        cx,
    );
    command(&view, Command::PanelCollapse("cpu".into()), cx);
    assert_eq!(cx.debug_bounds("panel:cpu").unwrap().size.height, px(36.));
    for _ in 0..9 {
        command(&view, Command::Tick, cx);
    }
    cx.read(|cx| {
        let shared = &view.read(cx).shared;
        let data = shared.borrow();
        let history = data.history.samples("cpu", "overall").unwrap();
        assert_eq!(history.len(), 10);
        assert_eq!(history.back().unwrap().at_ms, 10000);
        assert_eq!(
            history.iter().filter(|s| s.chart_value().is_none()).count(),
            2
        );
    });
    command(&view, Command::PanelCollapse("cpu".into()), cx);
    assert_eq!(
        cx.debug_bounds("panel:cpu").unwrap().size.height,
        before.height
    );
    assert!(cx.debug_bounds("cpu:meter-body:overall").is_none());
    command(&view, Command::Meter("cpu".into(), "overall".into()), cx);
    command(
        &view,
        Command::SensorVisible("cpu".into(), "overall".into()),
        cx,
    );
    command(
        &view,
        Command::SensorVisible("cpu".into(), "overall".into()),
        cx,
    );
    command(&view, Command::PanelVisible("cpu".into()), cx);
    command(&view, Command::PanelVisible("cpu".into()), cx);
    cx.read(|cx| {
        let data = view.read(cx).shared.borrow();
        let row = &data.session.workspace.panels["cpu"].sensors["overall"];
        assert!(row.collapsed);
        assert_eq!(row.meter, system_pulse_model::Meter::Bar);
        assert_eq!(data.history.samples("cpu", "overall").unwrap().len(), 10);
    });
}

#[gpui::test]
fn enter_and_space_toggle_without_moving_the_panel(cx: &mut TestAppContext) {
    let (view, cx) = harness(cx);
    let cpu = panel(&view, "cpu", cx);
    let before = cx.read(|cx| {
        let dock = &view.read(cx).dock;
        leaf_nodes(dock.read(cx).layout(DockPlacement::Center).unwrap().root())
    });
    cx.update(|window, cx| cpu.read(cx).controls["collapse"].handle.focus(window));
    cx.simulate_keystrokes("enter");
    draw(cx);
    assert_eq!(cx.debug_bounds("panel:cpu").unwrap().size.height, px(36.));
    cx.simulate_keystrokes("space");
    draw(cx);
    assert!(cx.debug_bounds("panel:cpu").unwrap().size.height >= px(220.));
    let after = cx.read(|cx| {
        leaf_nodes(
            view.read(cx)
                .dock
                .read(cx)
                .layout(DockPlacement::Center)
                .unwrap()
                .root(),
        )
    });
    assert_eq!(before, after);
    cx.update(|window, cx| {
        cpu.read(cx).controls["meter:overall"].handle.focus(window);
        view.update(cx, |this, cx| {
            this.command(Command::PanelCollapse("cpu".into()), window, cx)
        });
        assert!(cpu.read(cx).controls["collapse"].handle.is_focused(window));
    });
}

#[gpui::test]
fn workspace_and_long_table_are_independently_reachable(cx: &mut TestAppContext) {
    let (view, cx) = harness(cx);
    let viewport = cx.debug_bounds("workspace-viewport").unwrap();
    let extent = cx.read(|cx| view.read(cx).dock.read(cx).content_extent(cx));
    assert!(extent.height > viewport.size.height);
    command(&view, Command::Scroll(0., -100000.), cx);
    let settings = panel(&view, "settings", cx);
    cx.update(|window, cx| settings.read(cx).controls["collapse"].handle.focus(window));
    draw(cx);
    let target = cx.debug_bounds("settings:collapse").unwrap();
    assert!(target.top() >= viewport.top() && target.bottom() <= viewport.bottom());
    let processes = panel(&view, "processes", cx);
    cx.update(|window, cx| processes.read(cx).controls["table"].handle.focus(window));
    draw(cx);
    cx.simulate_keystrokes("end");
    draw(cx);
    assert_eq!(cx.read(|cx| processes.read(cx).selected), 499);
    assert!(cx.debug_bounds("process-row:499").is_some());
    assert!(
        cx.debug_bounds("process-row:0").is_none(),
        "rows are virtualized"
    );
    let before = cx.read(|cx| view.read(cx).shared.borrow().scroll.offset());
    command(&view, Command::Scroll(0., 300.), cx);
    let after = cx.read(|cx| view.read(cx).shared.borrow().scroll.offset());
    assert!(
        after.y > before.y,
        "workspace remains reachable while table retains focus"
    );
    cx.update(|window, cx| window.focus_next(cx));
    cx.update(|window, cx| {
        assert!(
            !processes.read(cx).controls["table"]
                .handle
                .is_focused(window)
        )
    });
}

#[gpui::test]
fn restore_preserves_identity_and_rejection_is_not_bypassed_by_preset(cx: &mut TestAppContext) {
    let (view, cx) = harness(cx);
    command(&view, Command::PanelCollapse("gpu:fixture-a".into()), cx);
    command(
        &view,
        Command::RowCollapse("cpu".into(), "overall".into()),
        cx,
    );
    command(&view, Command::SavePreset, cx);
    command(&view, Command::ReverseDiscovery, cx);
    command(&view, Command::ToggleGpu, cx);
    command(&view, Command::RecallPreset, cx);
    command(&view, Command::ToggleGpu, cx);
    assert_eq!(
        cx.debug_bounds("panel:gpu:fixture-a").unwrap().size.height,
        px(36.)
    );
    cx.read(|cx| {
        assert!(
            view.read(cx).shared.borrow().session.workspace.panels["cpu"].sensors["overall"]
                .collapsed
        )
    });
    let mut invalid = default_dock();
    let second = invalid.center.children[1].children[0].clone();
    invalid.center.children[0].children.push(second);
    let mut state = system_pulse_model::Workspace::new(serde_json::to_value(invalid).unwrap());
    crate::fixture::discover(&mut state, &crate::fixture::catalog());
    let raw = serde_json::to_string(&state).unwrap();
    cx.update(|window, cx| view.update(cx, |this, cx| this.restore(&raw, window, cx)));
    draw(cx);
    command(&view, Command::RecallPreset, cx);
    cx.read(|cx| {
        let data = view.read(cx).shared.borrow();
        assert_eq!(data.session.rejected.as_ref().unwrap().original, raw);
        assert!(data.session.autosave_json().is_err());
        leaf_nodes(
            view.read(cx)
                .dock
                .read(cx)
                .layout(DockPlacement::Center)
                .unwrap()
                .root(),
        );
    });
    command(&view, Command::Recover, cx);
    cx.read(|cx| {
        assert!(
            view.read(cx)
                .shared
                .borrow()
                .session
                .autosave_json()
                .is_ok()
        )
    });
}

#[gpui::test]
fn edge_move_is_accepted_and_merge_is_rejected_atomically(cx: &mut TestAppContext) {
    let (view, cx) = harness(cx);
    let dock = cx.read(|cx| view.read(cx).dock.clone());
    let nodes =
        cx.read(|cx| leaf_nodes(dock.read(cx).layout(DockPlacement::Center).unwrap().root()));
    let before = cx.read(|cx| dock.read(cx).dump(cx));
    cx.update(|window, cx| {
        dock.update(cx, |dock, cx| {
            assert!(
                dock.try_move_panel(
                    nodes[0].1,
                    InsertTarget::Tabs {
                        node: nodes[1].0,
                        ix: None,
                        activate: true
                    },
                    window,
                    cx
                )
                .is_err()
            );
        })
    });
    assert_eq!(cx.read(|cx| dock.read(cx).dump(cx)), before);
    cx.update(|window, cx| {
        dock.update(cx, |dock, cx| {
            dock.try_move_panel(
                nodes[0].1,
                InsertTarget::Split {
                    node: nodes[1].0,
                    placement: Placement::Right,
                    size: Some(px(420.)),
                },
                window,
                cx,
            )
            .unwrap();
        })
    });
    draw(cx);
    let after =
        cx.read(|cx| leaf_nodes(dock.read(cx).layout(DockPlacement::Center).unwrap().root()));
    assert_eq!(after.len(), nodes.len());
    assert_ne!(cx.read(|cx| dock.read(cx).dump(cx)), before);
}

#[gpui::test]
fn older_partial_layout_gets_regions_for_default_enabled_monitors(cx: &mut TestAppContext) {
    let (view, cx) = harness(cx);
    let mut dock = default_dock();
    dock.center.children.truncate(1);
    dock.center.info = PanelInfo::stack(vec![px(280.)], Axis::Vertical);
    let raw = serde_json::json!({ "dock": dock }).to_string();
    cx.update(|window, cx| view.update(cx, |this, cx| this.restore(&raw, window, cx)));
    draw(cx);
    cx.read(|cx| {
        let app = view.read(cx);
        let data = app.shared.borrow();
        assert!(data.session.rejected.is_none());
        let nodes = leaf_nodes(
            app.dock
                .read(cx)
                .layout(DockPlacement::Center)
                .unwrap()
                .root(),
        );
        assert_eq!(nodes.len(), data.catalog.len());
        assert!(
            data.session
                .workspace
                .panels
                .values()
                .all(|panel| panel.visible && !panel.collapsed)
        );
    });
}
```

- [ ] Run `rtk cargo test -p system-pulse --lib`. All named tests must run, including `#[gpui::test]` cases; a display/harness failure is an unavailable check, not a pass. Run the focused framework geometry and policy commands from plans 01 and 03 after this app integrates them.
- [ ] Run `rtk cargo check -p system-pulse --all-targets`, `rtk cargo clippy -p system-pulse --all-targets -- -D warnings`, and `rtk cargo fmt --all --check` after any test-driven corrections. Record executed checks only.

## Task 7: Exercise native pointer and accessibility behavior

**Files:** Create `examples/system_pulse/README.md` with the following content. The native manual checks complement tests; do not substitute screenshots for interactions.

- [ ] Install the README:

```markdown
# System Pulse fixture workspace

This native interaction proof uses deterministic simulated readings. It does not inspect or control real processes and does not run operating-system collectors.

From the fork workspace root:

    rtk cargo run -p system-pulse
    rtk cargo test -p system-pulse --lib

State is stored under `system-pulse-fixture` in the platform configuration directory. `SYSTEM_PULSE_STATE_DIR` selects an isolated directory for interaction checks. One preset slot is provided to verify save/recall behavior. Full preset management is outside this proof.

Default panels and rows are expanded. A panel title is the drag handle. The buttons beside it expand/collapse and hide the panel. The toolbar re-enables hidden panels. Row controls independently fold the meter, hide the sensor, and change meter type. Compact summaries keep updating every second, including simulated unavailable/stale states.

Alt+PageUp/PageDown scrolls the workspace vertically; Alt+Left/Right scrolls horizontally. The table uses Up/Down/Home/End; Tab leaves it. Scrollbars provide an independent pointer route to the workspace even when the pointer is over the table.

## Native acceptance record

Record platform, checkout commit, command, result, and artifact path for each scenario below. Initially every scenario is unverified.

1. At the minimum 960×640 window, scroll to all eight panels with the wheel and workspace scrollbar. Resize the window smaller/larger within the supported limit; no panel visibility or collapse state changes.
2. Drag CPU by its title to the right and below GPU A. Both edge placements work. Attempt center and header drops: source identity and position remain intact, and no tab strip or tab group appears. Drag each exposed divider and verify measured regions resize. Record CPU's resized width and height, collapse it, then expand it and compare against the recorded dimensions. Repeat with collapsed CPU beside a taller expanded neighbor: CPU remains header-only, the neighbor keeps its useful body, and expansion restores CPU's preference. Place enough panels side by side to exceed the viewport width and reach every panel using both the horizontal scrollbar and Alt+Left/Right. Close/re-add a monitor and verify it appears as its own region.
3. Collapse CPU's overall row, collapse CPU, then expand CPU. The overall row remains compact in its original position. Change its meter while compact, hide/show it, and expand it. The selected meter returns with continuous bounded history.
4. Keep CPU collapsed through a complete 12-tick fixture cycle. Its summary updates and explicitly says Unavailable/Stale at the defined ticks. Settings collapse keeps only its title and controls. GPU A and B retain independent state despite discovery-order reversal.
5. Scroll within the long process table to row 499, then reach Settings with the workspace scrollbar and keyboard shortcuts. Wheel over the table scrolls its rows; at its vertical edge the ancestor remains scrollable. Tab out of the table and navigate to a panel above the viewport; focus is revealed without losing the selected process row.
6. Focus every expansion control and activate Enter and Space. Inspect the accessibility tree: each is a button with a descriptive name and expanded state. Activating header buttons never starts a drag. Collapse a panel while a descendant has focus using the native test command path; focus lands on its expansion button.
7. Save a preset with mixed panel/row collapse, change both, and recall. Restart the app and compare placement, expanded preferences, and collapse states. Disconnect/reconnect GPU A and reverse discovery; state remains associated with fixture A, never fixture B.
8. Close the app. Preserve a copy of workspace.json, insert a second child into a tabs group, and restart. A valid default opens with an error; original workspace.json bytes remain unchanged after normal interactions. Explicit recovery writes workspace.rejected.json before saving the valid default. Verify a normal preset recall cannot bypass the recovery gate.

Linux is the primary interaction-proof platform. On macOS, follow the fork's `docs/ACCESSIBILITY-UI-TESTING.md` to run a signed .app before accessibility inspection; a bare cargo-run process is insufficient evidence there. Record any platform unavailable to the executor. Do not infer cross-platform acceptance from Linux results.
```

- [ ] Run the README scenarios against the native window, including actual pointer edge drops, rejected center/header drops, divider movement, nested wheel scrolling, and accessibility inspection. Capture one expanded, one mixed-collapse, and one recovered-layout screenshot as supplementary artifacts; record the commands/actions and expected-versus-observed result beside each.
- [ ] Check every WV requirement against its evidence before committing completion. WV-01 has policy tests and native edge/merge interactions; WV-02/04 have extent/virtual-table/focus tests plus pointer scroll and resize; WV-05–09 have model tests, fixture continuity and native collapse tests; WV-10 has keyboard/focus tests plus native accessibility inspection; WV-11/12 have model round-trips, app restore tests, filesystem checks and recovery interaction.
- [ ] Commit test and acceptance documentation only after recording results: `rtk git add examples/system_pulse` then `rtk git commit -m "test: verify native workspace visibility interactions"`.

## Delivery gate

No production collector, process-operation, GPU accuracy, rendering-frame-rate, or cross-platform-runtime claim follows from this fixture proof. Native acceptance remains open until the commands and interaction checks above run on the implementation checkout. Keep unmet checks in the evidence record and resolve them before claiming WV acceptance.

Planning verification actually performed: all nine embedded Rust blocks parsed and formatted with `rustfmt --edition 2024`. The exact fixture and storage modules were extracted into `/tmp/system-pulse-native-pure-elgujmqf`, linked to the model verification crate, and both tests passed; Clippy with `--all-targets -- -D warnings` also passed there. The GPUI modules and native tests were not compiled or run. Those checks depend on executing the framework plans in the implementation checkout.
