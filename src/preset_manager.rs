use super::PresetCommand;
use crate::{
    controls::{self, FocusEntry},
    screen_style::{self, heading, palette, section},
    workspace::{Command, Shared},
};
use gpui_kit::base::{Button, ElementExt};
use gpui_kit::component::{
    ActiveTheme,
    input::{Input, InputState},
};
use gpui_kit::*;
use std::collections::BTreeMap;
use system_pulse_model::BuiltinPreset;

#[derive(Clone)]
enum Action {
    Create,
    Rename(String),
    Dispatch(PresetCommand),
    Ask(PresetCommand, String),
    Cancel,
}

pub(crate) struct PresetManager {
    shared: Shared,
    scroll: ScrollHandle,
    input: Option<Entity<InputState>>,
    input_focus: Option<FocusEntry>,
    confirmation: Option<(PresetCommand, String)>,
    focus_confirmation: bool,
    controls: BTreeMap<String, FocusEntry>,
}
impl PresetManager {
    pub(crate) fn new(shared: Shared, scroll: ScrollHandle) -> Self {
        Self {
            shared,
            scroll,
            input: None,
            input_focus: None,
            confirmation: None,
            focus_confirmation: false,
            controls: BTreeMap::new(),
        }
    }
    fn dispatch(&mut self, action: Action, window: &mut Window, cx: &mut Context<Self>) {
        let name = self
            .input
            .as_ref()
            .map(|input| input.read(cx).value().to_string())
            .unwrap_or_default();
        let command = match action {
            Action::Create => PresetCommand::Create(name),
            Action::Rename(from) => PresetCommand::Rename(from, name),
            Action::Dispatch(command) => command,
            Action::Ask(command, message) => {
                self.confirmation = Some((command, message));
                self.focus_confirmation = true;
                cx.notify();
                return;
            }
            Action::Cancel => {
                self.confirmation = None;
                if let Some(focus) = &self.input_focus {
                    focus.handle.focus(window, cx);
                }
                cx.notify();
                return;
            }
        };
        self.confirmation = None;
        if let Some(focus) = &self.input_focus {
            focus.handle.focus(window, cx);
        }
        let owner = self.shared.borrow().owner.clone();
        // Workspace notifications can refresh this manager; dispatch after its
        // current entity update releases the mutable borrow.
        if let Some(owner) = owner {
            window.defer(cx, move |window, cx| {
                let _ = owner.update(cx, |owner, cx| {
                    owner.command(Command::Preset(command), window, cx)
                });
            });
        }
        cx.notify();
    }
    fn button(
        &mut self,
        id: String,
        label: String,
        action: Action,
        cx: &mut Context<Self>,
    ) -> Button {
        let focus = self
            .controls
            .entry(id.clone())
            .or_insert_with(|| FocusEntry::new(cx))
            .clone();
        let outer = self.shared.borrow().scroll.clone();
        let inner = self.scroll.clone();
        let colors = palette(cx);
        let accent = screen_style::accent(system_pulse_model::Screen::Settings, cx);
        let ring = accent;
        let primary = id == "preset:create" || id.ends_with(":apply");
        let visible_label = if id.ends_with(":apply") {
            "Apply".into()
        } else {
            label.clone()
        };
        Button::new(SharedString::from(id.clone()))
            .accessibility_label(label.clone())
            .track_focus(&focus.handle)
            .h_9()
            .px_3()
            .border_1()
            .rounded(px(6.))
            .border_color(if primary { accent } else { colors.border })
            .bg(if primary {
                colors.selected
            } else {
                colors.raised
            })
            .text_color(if primary { accent } else { colors.text })
            .hover(move |style| style.border_color(accent))
            .focus_visible(move |style| style.border_color(ring))
            .on_click(
                cx.listener(move |this, _, window, cx| this.dispatch(action.clone(), window, cx)),
            )
            .debug_selector(move || id.clone().into())
            .on_prepaint(move |mut bounds, window, _| {
                if focus.entered(window) {
                    bounds = bounds.dilate(px(1.));
                    bounds.origin += controls::reveal(bounds, &inner);
                    controls::reveal(bounds, &outer);
                    window.refresh();
                }
            })
            .child(visible_label)
    }
}
impl Render for PresetManager {
    fn render(&mut self, window: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        if self.input.is_none() {
            let input = cx.new(|cx| {
                InputState::new(window, cx).placeholder("New preset name or rename target…")
            });
            self.input_focus = Some(FocusEntry::from_handle(input.read(cx).focus_handle(cx)));
            self.input = Some(input);
        }
        let input_focus = self.input_focus.as_ref().unwrap().clone();
        let outer = self.shared.borrow().scroll.clone();
        let inner = self.scroll.clone();
        let input = div()
            .on_prepaint(move |mut bounds, window, _| {
                if input_focus.entered(window) {
                    bounds.origin += controls::reveal(bounds, &inner);
                    controls::reveal(bounds, &outer);
                    window.refresh();
                }
            })
            .child(Input::new(self.input.as_ref().unwrap()));
        let (names, error, notice, busy) = {
            let data = self.shared.borrow();
            (
                data.presets.presets.keys().cloned().collect::<Vec<_>>(),
                data.preset_error.clone(),
                data.preset_notice.clone(),
                data.preset_busy,
            )
        };
        // Keep focus entries bounded when presets are renamed or removed.
        let active_ids: std::collections::BTreeSet<_> = names
            .iter()
            .flat_map(|name| {
                ["apply", "rename", "overwrite", "delete"]
                    .map(|verb| format!("preset:user:{name}:{verb}"))
            })
            .collect();
        self.controls
            .retain(|id, _| !id.starts_with("preset:user:") || active_ids.contains(id));
        let builtin_buttons: Vec<_> = BuiltinPreset::ALL
            .into_iter()
            .map(|kind| {
                self.button(
                    format!("preset:builtin:{}", kind.name()),
                    format!("Use {}", kind.name()),
                    Action::Dispatch(PresetCommand::Builtin(kind)),
                    cx,
                )
            })
            .collect();
        let save = self.button(
            "preset:create".into(),
            "Save current workspace".into(),
            Action::Create,
            cx,
        );
        let colors = palette(cx);
        let mut user_rows = Vec::new();
        for name in names {
            let actions = [
                (
                    "apply",
                    format!("Use {name}"),
                    Action::Dispatch(PresetCommand::Recall(name.clone())),
                ),
                ("rename", "Rename".into(), Action::Rename(name.clone())),
                (
                    "overwrite",
                    "Overwrite…".into(),
                    Action::Ask(
                        PresetCommand::Overwrite(name.clone()),
                        format!("Replace {name} with the current workspace?"),
                    ),
                ),
                (
                    "delete",
                    "Delete…".into(),
                    Action::Ask(
                        PresetCommand::Delete(name.clone()),
                        format!("Delete preset {name}? Your current workspace stays open."),
                    ),
                ),
            ];
            user_rows.push(
                div()
                    .flex()
                    .flex_wrap()
                    .gap_2()
                    .p_2()
                    .items_center()
                    .rounded(px(6.))
                    .bg(colors.background)
                    .child(div().flex_1().min_w(px(120.)).child(name.clone()))
                    .children(actions.into_iter().map(|(verb, label, action)| {
                        self.button(format!("preset:user:{name}:{verb}"), label, action, cx)
                    })),
            );
        }
        let mut content = section(cx)
            .p_4()
            .gap_3()
            .child(heading("Presets", 22., cx))
            .child(
                div()
                    .text_sm()
                    .text_color(colors.muted)
                    .child("Save your screen, device selections and preferences for later."),
            )
            .child(
                div()
                    .flex()
                    .items_center()
                    .flex_wrap()
                    .gap_2()
                    .child(
                        div()
                            .text_sm()
                            .text_color(colors.muted)
                            .mr_2()
                            .child("Built-in"),
                    )
                    .children(builtin_buttons),
            )
            .child(
                div()
                    .flex()
                    .flex_wrap()
                    .items_center()
                    .gap_2()
                    .child(input.flex_1().min_w(px(220.)))
                    .child(save),
            )
            .child(div().text_xs().text_color(colors.muted).child(
                "To rename a preset, enter its new name above, then choose Rename beside it.",
            ))
            .children(user_rows);
        if let Some((command, message)) = self.confirmation.clone() {
            let cancel = self.button("preset:cancel".into(), "Cancel".into(), Action::Cancel, cx);
            let confirm = self.button(
                "preset:confirm".into(),
                "Confirm".into(),
                Action::Dispatch(command),
                cx,
            );
            if std::mem::take(&mut self.focus_confirmation) {
                self.controls["preset:cancel"].handle.focus(window, cx);
            }
            content = content.child(
                div()
                    .flex()
                    .flex_col()
                    .gap_1()
                    .p_3()
                    .rounded(px(6.))
                    .border_1()
                    .border_color(colors.border)
                    .bg(colors.raised)
                    .child(message)
                    .child(div().flex().gap_1().child(cancel).child(confirm)),
            );
        }
        if let Some(error) = error {
            content = content.child(div().text_color(cx.theme().danger).child(error));
        }
        if !notice.is_empty() {
            content = content.child(
                div()
                    .id("preset-status")
                    .role(Role::Status)
                    .accessibility_id("preset-status")
                    .aria_label(notice.clone())
                    .child(notice),
            );
        }
        if busy {
            content = content.child("Preset actions will be available after saving finishes.");
        }
        content
    }
}

#[cfg(test)]
mod tests {
    use super::PresetManager;
    use crate::native_tests::{draw, harness, panel};
    use crate::workspace::Command;
    use gpui_kit::{Entity, Modifiers, TestAppContext, VisualTestContext};

    fn click(manager: &Entity<PresetManager>, id: &'static str, cx: &mut VisualTestContext) {
        cx.update(|window, cx| {
            manager.read(cx).controls[id]
                .handle
                .clone()
                .focus(window, cx)
        });
        draw(cx);
        let bounds = cx.debug_bounds(id).unwrap();
        cx.simulate_click(bounds.center(), Modifiers::none());
        draw(cx);
    }
    fn name(manager: &Entity<PresetManager>, value: &str, cx: &mut VisualTestContext) {
        let input = cx.read(|cx| manager.read(cx).input.clone().unwrap());
        cx.update(|window, cx| input.update(cx, |input, cx| input.set_value(value, window, cx)));
        draw(cx);
    }

    #[gpui_kit::test]
    fn named_preset_controls_confirm_cancel_rename_and_recall(cx: &mut TestAppContext) {
        let (view, cx) = harness(cx);
        let monitor = panel(&view, "settings", cx);
        cx.update(|window, cx| {
            monitor.read(cx).controls["close"]
                .handle
                .clone()
                .focus(window, cx)
        });
        draw(cx);
        let settings = cx.read(|cx| monitor.read(cx).settings.clone().unwrap());
        let manager = cx.read(|cx| settings.read(cx).presets.clone().unwrap());
        name(&manager, "Work", cx);
        click(&manager, "preset:create", cx);
        assert_eq!(
            cx.read(|cx| view
                .read(cx)
                .shared
                .borrow()
                .presets
                .get("Work")
                .unwrap()
                .interval_ms),
            1000
        );
        cx.update(|window, cx| {
            view.update(cx, |view, cx| {
                view.command(Command::Interval(2000), window, cx)
            })
        });
        draw(cx);
        click(&manager, "preset:user:Work:overwrite", cx);
        click(&manager, "preset:cancel", cx);
        assert_eq!(
            cx.read(|cx| view
                .read(cx)
                .shared
                .borrow()
                .presets
                .get("Work")
                .unwrap()
                .interval_ms),
            1000
        );
        click(&manager, "preset:user:Work:overwrite", cx);
        click(&manager, "preset:confirm", cx);
        assert_eq!(
            cx.read(|cx| view
                .read(cx)
                .shared
                .borrow()
                .presets
                .get("Work")
                .unwrap()
                .interval_ms),
            2000
        );
        name(&manager, "Coding", cx);
        click(&manager, "preset:user:Work:rename", cx);
        assert!(cx.read(|cx| view.read(cx).shared.borrow().presets.get("Work").is_none()));
        assert!(cx.read(|cx| {
            view.read(cx)
                .shared
                .borrow()
                .presets
                .get("Coding")
                .is_some()
        }));
        cx.update(|window, cx| {
            view.update(cx, |view, cx| {
                view.command(Command::Interval(5000), window, cx)
            })
        });
        draw(cx);
        click(&manager, "preset:user:Coding:apply", cx);
        assert_eq!(
            cx.read(|cx| view.read(cx).shared.borrow().session.workspace.interval_ms),
            2000
        );
        // Recall reconstructs dock views; use the current manager entity.
        let monitor = panel(&view, "settings", cx);
        draw(cx);
        let settings = cx.read(|cx| monitor.read(cx).settings.clone().unwrap());
        let manager = cx.read(|cx| settings.read(cx).presets.clone().unwrap());
        click(&manager, "preset:user:Coding:delete", cx);
        click(&manager, "preset:cancel", cx);
        assert!(cx.read(|cx| {
            view.read(cx)
                .shared
                .borrow()
                .presets
                .get("Coding")
                .is_some()
        }));
        click(&manager, "preset:user:Coding:delete", cx);
        click(&manager, "preset:confirm", cx);
        assert!(cx.read(|cx| view.read(cx).shared.borrow().presets.presets.is_empty()));
    }
}
