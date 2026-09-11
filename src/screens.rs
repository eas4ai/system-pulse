//! Fixed reference-based screens over the existing live workspace controller.
use crate::{
    controls::FocusEntry,
    panel::MonitorPanel,
    screen_data,
    screen_style::{self, palette},
    workspace::{Command, Shared, WorkspaceView},
};
use gpui_kit::base::{ElementExt, Scrollbar, ScrollbarMode, Tab, Tabs};
use gpui_kit::component::{
    ActiveTheme, Disableable, Sizable,
    button::Button,
    menu::{DropdownMenu, PopupMenuItem},
};
use gpui_kit::{prelude::FluentBuilder, *};
use std::collections::BTreeMap;
use system_pulse_model::Screen;

pub struct ApplicationView {
    // Own the sampler, persistence tasks and the legacy layout compatibility state.
    _workspace: Entity<WorkspaceView>,
    pub(crate) screens: Entity<ScreenView>,
}

impl ApplicationView {
    pub fn new(window: &mut Window, cx: &mut Context<Self>) -> Self {
        let workspace = cx.new(|cx| WorkspaceView::new(window, cx));
        Self::from_workspace(workspace, window, cx)
    }

    /// Preserve monitoring and saved preferences after the native window closes.
    pub(crate) fn detach_window(&mut self, cx: &mut Context<Self>) {
        self._workspace
            .update(cx, |workspace, cx| workspace.detach_window(cx));
    }

    /// Recreate controls against the new native window, retaining sampled history.
    pub(crate) fn attach_window(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        self._workspace
            .update(cx, |workspace, cx| workspace.attach_window(window, cx));
        let shared = self._workspace.read(cx).shared.clone();
        self.screens = cx.new(|cx| ScreenView::new(shared, window, cx));
        self._workspace.update(cx, |workspace, _| {
            workspace.screen_view = Some(self.screens.downgrade())
        });
        cx.notify();
    }

    pub(crate) fn cpu_samples(&self, cx: &App) -> Vec<system_pulse_model::Sample> {
        self._workspace
            .read(cx)
            .shared
            .borrow()
            .history
            .samples("cpu:host", "cpu:host/usage")
            .map(|samples| samples.iter().cloned().collect())
            .unwrap_or_default()
    }

    fn from_workspace(
        workspace: Entity<WorkspaceView>,
        window: &mut Window,
        cx: &mut Context<Self>,
    ) -> Self {
        let shared = workspace.read(cx).shared.clone();
        let screens = cx.new(|cx| ScreenView::new(shared, window, cx));
        workspace.update(cx, |workspace, _| {
            workspace.screen_view = Some(screens.downgrade())
        });
        Self {
            _workspace: workspace,
            screens,
        }
    }

    #[cfg(test)]
    pub(crate) fn new_fixture(window: &mut Window, cx: &mut Context<Self>) -> Self {
        let workspace = cx.new(|cx| WorkspaceView::new_fixture(window, cx));
        Self::from_workspace(workspace, window, cx)
    }
}

impl Render for ApplicationView {
    fn render(&mut self, _: &mut Window, _: &mut Context<Self>) -> impl IntoElement {
        div().size_full().child(self.screens.clone())
    }
}

pub(crate) struct ScreenView {
    pub(crate) shared: Shared,
    pub(crate) processes: Entity<MonitorPanel>,
    settings: Entity<crate::settings::SettingsPanel>,
    pub(crate) focus: BTreeMap<Screen, FocusEntry>,
    scrolls: BTreeMap<Screen, ScrollHandle>,
    tab_scroll: ScrollHandle,
    rendered_screen: Screen,
}

impl ScreenView {
    fn new(shared: Shared, window: &mut Window, cx: &mut Context<Self>) -> Self {
        let monitor = crate::live::presentations()
            .into_iter()
            .find(|monitor| monitor.id == "processes")
            .expect("process presentation exists");
        let processes = cx.new(|cx| MonitorPanel::new_standalone(monitor, shared.clone(), cx));
        let settings = cx.new(|cx| crate::settings::SettingsPanel::new(shared.clone(), cx));
        let active = shared.borrow().session.workspace.screens.active;
        let focus: BTreeMap<_, _> = Screen::ALL
            .into_iter()
            .map(|screen| (screen, FocusEntry::new(cx)))
            .collect();
        focus[&active].handle.focus(window, cx);
        Self {
            shared,
            processes,
            settings,
            focus,
            rendered_screen: active,
            scrolls: Screen::ALL
                .into_iter()
                .map(|screen| (screen, ScrollHandle::default()))
                .collect(),
            tab_scroll: ScrollHandle::default(),
        }
    }

    pub(crate) fn refresh(&mut self, cx: &mut Context<Self>) {
        let identities = self.shared.borrow().process_identities();
        let active = self.shared.borrow().session.workspace.screens.active;
        self.processes.update(cx, |panel, cx| {
            crate::live::reconcile_selection(&mut panel.selected, &identities);
            if active == Screen::Processes {
                cx.notify();
            }
        });
        if active == Screen::Settings {
            self.settings
                .update(cx, |settings, cx| settings.refresh(cx));
        }
        cx.notify();
    }

    pub(crate) fn select(&mut self, screen: Screen, window: &mut Window, cx: &mut Context<Self>) {
        let owner = self.shared.borrow().owner.clone();
        if let Some(owner) = owner {
            let _ = owner.update(cx, |owner, cx| {
                owner.command(Command::Screen(screen), window, cx)
            });
        }
        cx.notify();
    }

    fn navigation(&mut self, cx: &mut Context<Self>) -> AnyElement {
        let active = self.shared.borrow().session.workspace.screens.active;
        let colors = palette(cx);
        let tabs = Screen::ALL.into_iter().enumerate().map(|(index, screen)| {
            let focused = self.focus[&screen].clone();
            let scroll = self.tab_scroll.clone();
            let color = screen_style::accent(screen, cx);
            Tab::new(SharedString::from(format!("screen-tab:{}", screen.id())))
                .accessibility_id(format!("screen-tab:{}", screen.id()))
                .accessibility_label(screen.title())
                .selected(screen == active)
                .set_position(index + 1, Screen::ALL.len())
                .track_focus(&focused.handle)
                .h(px(40.))
                .px_3()
                .flex_none()
                .text_sm()
                .border_b_2()
                .border_color(if screen == active {
                    color
                } else {
                    colors.border
                })
                .bg(if screen == active {
                    colors.selected
                } else {
                    colors.surface
                })
                .text_color(if screen == active {
                    colors.text
                } else {
                    colors.muted
                })
                .hover(move |style| style.bg(colors.raised).text_color(colors.text))
                .focus_visible(move |style| style.bg(colors.selected).border_color(color))
                .debug_selector(move || format!("screen-tab:{}", screen.id()).into())
                .child(screen.title())
                .on_click(cx.listener(move |this, _, window, cx| {
                    this.focus[&screen].handle.focus(window, cx);
                    this.select(screen, window, cx);
                }))
                .on_key_down(cx.listener(move |this, event: &KeyDownEvent, window, cx| {
                    if event.keystroke.modifiers.control
                        || event.keystroke.modifiers.alt
                        || event.keystroke.modifiers.platform
                    {
                        return;
                    }
                    let next = match event.keystroke.key.as_str() {
                        "left" => screen.adjacent(false),
                        "right" => screen.adjacent(true),
                        "home" => Screen::Summary,
                        "end" => Screen::Settings,
                        "enter" | "space" => screen,
                        _ => return,
                    };
                    this.focus[&next].handle.focus(window, cx);
                    this.select(next, window, cx);
                    cx.stop_propagation();
                }))
                .on_prepaint(move |bounds, window, _| {
                    if focused.entered(window) {
                        crate::controls::reveal(bounds, &scroll);
                        window.refresh();
                    }
                })
        });
        div()
            .h(px(40.))
            .flex_none()
            .bg(colors.surface)
            .child(
                Tabs::new("screen-tabs")
                    .accessibility_id("screen-tabs")
                    .aria_label("System monitor screens")
                    .flex()
                    .h_full()
                    .overflow_x_scroll()
                    .track_scroll(&self.tab_scroll)
                    .children(tabs),
            )
            .into_any_element()
    }

    fn device_picker(&self, screen: Screen) -> AnyElement {
        let data = self.shared.borrow();
        let choices = screen_data::devices(&data, screen);
        let selected = screen_data::selected_device(&data, screen);
        let label = choices
            .iter()
            .find(|choice| Some(&choice.id) == selected.as_ref())
            .map(|choice| choice.label.clone())
            .unwrap_or_else(|| {
                if matches!(screen, Screen::Energy | Screen::Thermals) {
                    return if choices.is_empty() {
                        "No available sensors"
                    } else {
                        "Choose a sensor"
                    }
                    .into();
                }
                selected
                    .clone()
                    .map(|id| format!("Unavailable · {id}"))
                    .unwrap_or_else(|| "No available devices".into())
            });
        let owner = data.owner.clone();
        drop(data);
        Button::new(SharedString::from(format!("screen-device:{}", screen.id())))
            .accessibility_id(format!("screen-device:{}", screen.id()))
            .accessibility_label(format!("{} device: {label}", screen.title()))
            .small()
            .max_w(px(640.))
            .label(label)
            .disabled(choices.is_empty())
            .dropdown_menu(move |mut menu, _, _| {
                menu = menu.scrollable(true).max_h(px(320.));
                for choice in &choices {
                    let id = choice.id.clone();
                    let owner = owner.clone();
                    menu = menu.item(
                        PopupMenuItem::new(choice.label.clone())
                            .checked(selected.as_ref() == Some(&id))
                            .on_click(move |_, window, cx| {
                                if let Some(owner) = &owner {
                                    let _ = owner.update(cx, |owner, cx| {
                                        owner.command(
                                            Command::ScreenDevice(screen, id.clone()),
                                            window,
                                            cx,
                                        );
                                    });
                                }
                            }),
                    );
                }
                menu
            })
            .into_any_element()
    }

    fn notice(&self, cx: &App) -> Option<String> {
        self.shared
            .borrow()
            .owner
            .as_ref()
            .and_then(|owner| owner.upgrade())
            .map(|owner| owner.read(cx).screen_notice())
            .filter(|notice| !notice.is_empty())
    }
}

impl Render for ScreenView {
    fn render(&mut self, window: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        let colors = palette(cx);
        let active = self.shared.borrow().session.workspace.screens.active;
        if self.rendered_screen != active {
            // Preset restoration can remove the input that currently owns focus.
            // Move it into the newly visible screen once, without stealing it on ticks.
            self.rendered_screen = active;
            self.focus[&active].handle.focus(window, cx);
        }

        let navigation = self.navigation(cx);
        let picker = active
            .has_device_selection()
            .then(|| self.device_picker(active));
        let notice = self.notice(cx);
        if active == Screen::Summary {
            // Summary displays the top CPU rows as well as the process count.
            self.shared.borrow_mut().prepare_processes();
        }
        let data = self.shared.borrow();
        let width = (window.viewport_size().width.as_f32() - 32.).max(320.);
        let interval = data.session.workspace.interval_ms as f64 / 1000.;
        let current = data
            .history
            .latest("cpu:host", "cpu:host/usage")
            .is_some_and(|sample| sample.status == system_pulse_model::ReadingStatus::Current);
        let status = if data.snapshot.is_none() {
            "Waiting for system data"
        } else if current {
            "Live system data"
        } else {
            "Readings warming up or delayed"
        };
        let status_text = format!(
            "{status} · {} readable processes · {interval} s update",
            data.process_count()
        );
        let page = match active {
            Screen::Summary => crate::screen_summary::render(&data, width, cx),
            Screen::Processes => self.processes.clone().into_any_element(),
            Screen::Settings => self.settings.clone().into_any_element(),
            _ => crate::screen_pages::render(active, &data, width, cx),
        };
        let rejected = data.session.rejected.is_some();
        let owner = data.owner.clone();
        drop(data);
        let header = div()
            .flex()
            .flex_wrap()
            .items_center()
            .justify_between()
            .gap_2()
            .px_4()
            .py_3()
            .flex_none()
            .child(screen_style::heading(active.title(), 32., cx))
            .when_some(picker, |view, picker| view.child(picker));
        #[cfg(target_os = "windows")]
        let temperatures_enabled = owner
            .as_ref()
            .and_then(|owner| owner.upgrade())
            .is_some_and(|owner| owner.read(cx).cpu_temperatures_enabled());
        #[cfg(target_os = "windows")]
        let header = header.when(active == Screen::Thermals, |view| {
            view.child(
                div()
                    .flex()
                    .gap_2()
                    .child(
                        Button::new("enable-cpu-temperatures")
                            .label("Enable CPU temperatures…")
                            .disabled(temperatures_enabled)
                            .on_click(cx.listener(|this, _, window, cx| {
                                let owner = this.shared.borrow().owner.clone();
                                if let Some(owner) = owner {
                                    let _ = owner.update(cx, |owner, cx| {
                                        owner.command(Command::EnableCpuTemperatures, window, cx)
                                    });
                                }
                            })),
                    )
                    .child(
                        Button::new("disable-cpu-temperatures")
                            .label("Disable CPU temperatures")
                            .disabled(!temperatures_enabled)
                            .on_click(cx.listener(|this, _, window, cx| {
                                let owner = this.shared.borrow().owner.clone();
                                if let Some(owner) = owner {
                                    let _ = owner.update(cx, |owner, cx| {
                                        owner.command(Command::DisableCpuTemperatures, window, cx)
                                    });
                                }
                            })),
                    ),
            )
        });
        let scroll = self.scrolls[&active].clone();
        let content = if matches!(active, Screen::Processes | Screen::Settings) {
            div()
                .size_full()
                .px_4()
                .pb_3()
                .child(page)
                .into_any_element()
        } else {
            div()
                .size_full()
                .relative()
                .child(
                    crate::workspace::scroll_viewport(
                        "screen-scroll",
                        format!("screen:{}:viewport", active.id()),
                    )
                    .size_full()
                    .overflow_y_scroll()
                    .track_scroll(&scroll)
                    .child(div().px_4().pb_4().child(page)),
                )
                .child(Scrollbar::vertical(&scroll).mode(ScrollbarMode::Always))
                .into_any_element()
        };
        div()
            .id("system-pulse-screens")
            .size_full()
            .flex()
            .flex_col()
            .font_family(cx.theme().font_family.clone())
            .text_size(px(14.))
            .bg(colors.background)
            .text_color(colors.text)
            .on_key_down(cx.listener(|this, event: &KeyDownEvent, window, cx| {
                let key = event.keystroke.key.as_str();
                if event.keystroke.modifiers.control && matches!(key, "tab" | "pageup" | "pagedown")
                {
                    let active = this.shared.borrow().session.workspace.screens.active;
                    let next = active.adjacent(key != "pageup" && !event.keystroke.modifiers.shift);
                    this.focus[&next].handle.focus(window, cx);
                    this.select(next, window, cx);
                    cx.stop_propagation();
                }
            }))
            .child(
                div()
                    .flex()
                    .items_center()
                    .justify_between()
                    .h(px(38.))
                    .px_4()
                    .flex_none()
                    .bg(colors.surface)
                    .border_b_1()
                    .border_color(colors.border)
                    .child(
                        div()
                            .font_weight(FontWeight::SEMIBOLD)
                            .child("System Pulse"),
                    )
                    .child(
                        div()
                            .text_xs()
                            .text_color(colors.muted)
                            .child("Ctrl+Tab to switch screens"),
                    ),
            )
            .child(navigation)
            .child(header)
            .when_some(notice, |view, notice| {
                view.child(div().px_4().pb_2().text_sm().child(notice))
            })
            .when(rejected, |view| {
                view.child(
                    Button::new("accept-screen-recovery")
                        .accessibility_id("accept-screen-recovery")
                        .debug_selector(|| "accept-screen-recovery".into())
                        .label("Accept recovered settings")
                        .on_click(cx.listener(move |this, _, window, cx| {
                            if let Some(owner) = &owner {
                                let _ = owner.update(cx, |owner, cx| {
                                    owner.command(Command::Recover, window, cx)
                                });
                            }
                            this.focus[&active].handle.focus(window, cx);
                        })),
                )
            })
            .child(
                div()
                    .id(SharedString::from(format!("screen:{}", active.id())))
                    .role(Role::TabPanel)
                    .aria_label(active.title())
                    .accessibility_id(format!("screen:{}", active.id()))
                    .flex_1()
                    .min_h_0()
                    .min_w_0()
                    .child(content),
            )
            .child(
                div()
                    .flex()
                    .items_center()
                    .gap_2()
                    .h(px(27.))
                    .px_4()
                    .flex_none()
                    .border_t_1()
                    .border_color(colors.border)
                    .bg(colors.surface)
                    .child(div().size(px(6.)).rounded_full().bg(if current {
                        screen_style::accent(Screen::Cpu, cx)
                    } else {
                        colors.muted
                    }))
                    .child(
                        div()
                            .id("screen-status")
                            .role(Role::Status)
                            .aria_label(status_text.clone())
                            .text_xs()
                            .text_color(colors.muted)
                            .child(status_text),
                    ),
            )
    }
}
