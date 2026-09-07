//! Docked appearance and sampling controls.
use crate::controls::{self, FocusEntry};
use crate::workspace::{Command, Shared};
use gpui_kit::base::{Button, ElementExt, Scrollbar, ScrollbarMode};
use gpui_kit::component::{ActiveTheme, Theme, ThemeMode};
use gpui_kit::*;
use std::collections::BTreeMap;
use system_pulse_model::{Appearance, ColorTheme, NumericFont, UiFont};

pub(crate) fn apply(appearance: Appearance, window: &mut Window, cx: &mut App) {
    Theme::change(
        match appearance.theme {
            ColorTheme::Dark => ThemeMode::Dark,
            ColorTheme::Light => ThemeMode::Light,
        },
        Some(window),
        cx,
    );
    let theme = Theme::global_mut(cx);
    theme.font_family = appearance.ui_font.family().into();
    theme.mono_font_family = appearance.numeric_font.family().into();
    Theme::sync_base(cx);
    window.refresh();
}

pub(crate) struct SettingsPanel {
    shared: Shared,
    scroll: ScrollHandle,
    controls: BTreeMap<&'static str, FocusEntry>,
    pub(crate) presets: Option<Entity<crate::workspace::presets::PresetManager>>,
}
impl SettingsPanel {
    pub(crate) fn new(shared: Shared, cx: &mut App) -> Self {
        let controls = [
            "settings-dark",
            "settings-light",
            "settings-inter",
            "settings-plex-sans",
            "settings-jetbrains",
            "settings-plex-mono",
            "settings-500",
            "settings-1000",
            "settings-2000",
            "settings-5000",
        ]
        .into_iter()
        .map(|id| (id, FocusEntry::new(cx)))
        .collect();
        Self {
            shared,
            scroll: ScrollHandle::default(),
            controls,
            presets: None,
        }
    }

    pub(crate) fn refresh(&mut self, cx: &mut Context<Self>) {
        if let Some(presets) = &self.presets {
            presets.update(cx, |_, cx| cx.notify());
        }
        cx.notify();
    }

    fn choice(
        &self,
        id: &'static str,
        label: impl Into<SharedString>,
        selected: bool,
        command: Command,
        cx: &App,
    ) -> Button {
        let target = self.shared.borrow().owner.clone();
        let outer = self.shared.borrow().scroll.clone();
        let inner = self.scroll.clone();
        let focus = self.controls[id].clone();
        let label = label.into();
        let ring = cx.theme().ring;
        Button::new(id)
            .accessibility_label(label.clone())
            .track_focus(&focus.handle)
            .aria_toggled(if selected {
                gpui_kit::accesskit::Toggled::True
            } else {
                gpui_kit::accesskit::Toggled::False
            })
            .h_7()
            .px_2()
            .border_1()
            .rounded(cx.theme().radius)
            .border_color(cx.theme().border)
            .bg(if selected {
                cx.theme().primary
            } else {
                cx.theme().background
            })
            .text_color(if selected {
                cx.theme().primary_foreground
            } else {
                cx.theme().foreground
            })
            .focus_visible(move |style| style.border_color(ring))
            .debug_selector(move || id.into())
            .on_click(move |_, window, cx| {
                if let Some(owner) = &target {
                    let _ =
                        owner.update(cx, |owner, cx| owner.command(command.clone(), window, cx));
                }
            })
            .on_prepaint(move |mut bounds, window, _| {
                if focus.entered(window) {
                    bounds = bounds.dilate(px(1.));
                    bounds.origin += controls::reveal(bounds, &inner);
                    controls::reveal(bounds, &outer);
                    window.refresh();
                }
            })
            .child(label)
    }
}

impl Render for SettingsPanel {
    fn render(&mut self, _: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        if self.presets.is_none() {
            self.presets = Some(cx.new(|_| {
                crate::workspace::presets::PresetManager::new(
                    self.shared.clone(),
                    self.scroll.clone(),
                )
            }));
        }
        let appearance = self.shared.borrow().session.workspace.appearance;
        let interval = self.shared.borrow().session.workspace.interval_ms;
        let content = div().flex().flex_col().gap_4().p_3()
            .child(div().text_lg().child("Appearance"))
            .child(div().flex().flex_col().gap_1().child("Theme")
                .child(div().flex().flex_wrap().gap_1().children([
                    ("settings-dark", "Dark", ColorTheme::Dark), ("settings-light", "Light", ColorTheme::Light)
                ].into_iter().map(|(id, label, theme)| self.choice(id, label, appearance.theme == theme,
                    Command::Appearance(Appearance { theme, ..appearance }), cx)))))
            .child(div().flex().flex_col().gap_1().child("Interface font")
                .child(div().flex().flex_wrap().gap_1().children([
                    ("settings-inter", UiFont::Inter), ("settings-plex-sans", UiFont::IbmPlexSans)
                ].into_iter().map(|(id, ui_font)| self.choice(id, ui_font.label(), appearance.ui_font == ui_font,
                    Command::Appearance(Appearance { ui_font, ..appearance }), cx)))))
            .child(div().flex().flex_col().gap_1().child("Numeric font")
                .child(div().flex().flex_wrap().gap_1().children([
                    ("settings-jetbrains", NumericFont::JetbrainsMono), ("settings-plex-mono", NumericFont::IbmPlexMono)
                ].into_iter().map(|(id, numeric_font)| self.choice(id, numeric_font.family(), appearance.numeric_font == numeric_font,
                    Command::Appearance(Appearance { numeric_font, ..appearance }), cx)))))
            .child(div().p_2().bg(cx.theme().muted).flex().flex_col().gap_1()
                .child("The quick brown fox jumps over the lazy dog.")
                .child(div().font_family(appearance.numeric_font.family()).child("0123456789 · 64.2 % · 8.5 GiB")))
            .child(div().text_lg().child("Sampling"))
            .child(div().flex().flex_wrap().gap_1().children([
                ("settings-500", 500, "0.5 s"), ("settings-1000", 1000, "1 s"),
                ("settings-2000", 2000, "2 s"), ("settings-5000", 5000, "5 s")
            ].into_iter().map(|(id, ms, label)| self.choice(id, label, interval == ms, Command::Interval(ms), cx))))
            .child(div().text_sm().text_color(cx.theme().muted_foreground)
                .child("Changes apply immediately and save automatically. Process CPU uses one core and may exceed 100%."));
        let content = content.child(self.presets.as_ref().unwrap().clone());
        div()
            .size_full()
            .relative()
            .child(
                div()
                    .id("settings-scroll")
                    .size_full()
                    .overflow_y_scroll()
                    .track_scroll(&self.scroll)
                    .child(content),
            )
            .child(Scrollbar::vertical(&self.scroll).mode(ScrollbarMode::Always))
    }
}

#[cfg(test)]
mod tests {
    use super::{Appearance, ColorTheme, NumericFont, UiFont};
    use crate::native_tests::{draw, harness, panel};
    use crate::workspace::Command;
    use gpui_kit::component::{ActiveTheme, ThemeMode};
    use gpui_kit::{Modifiers, TestAppContext};

    #[gpui_kit::test]
    fn docked_choices_apply_immediately_restore_and_reveal_keyboard_focus(cx: &mut TestAppContext) {
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
        for id in [
            "settings-light",
            "settings-plex-sans",
            "settings-plex-mono",
            "settings-5000",
        ] {
            cx.update(|window, cx| {
                settings.read(cx).controls[id]
                    .handle
                    .clone()
                    .focus(window, cx)
            });
            draw(cx);
            let bounds = cx.debug_bounds(id).unwrap();
            let viewport = cx.read(|cx| settings.read(cx).scroll.bounds());
            assert!(
                bounds.top() >= viewport.top() && bounds.bottom() <= viewport.bottom(),
                "{id} must be visible after keyboard focus"
            );
            cx.simulate_click(bounds.center(), Modifiers::none());
            draw(cx);
        }
        let expected = Appearance {
            theme: ColorTheme::Light,
            ui_font: UiFont::IbmPlexSans,
            numeric_font: NumericFont::IbmPlexMono,
        };
        cx.read(|cx| {
            let data = view.read(cx).shared.borrow();
            assert_eq!(data.session.workspace.appearance, expected);
            assert_eq!(data.session.workspace.interval_ms, 5000);
            assert_eq!(cx.theme().mode, ThemeMode::Light);
            assert_eq!(cx.theme().font_family.as_ref(), "IBM Plex Sans");
            assert_eq!(cx.theme().mono_font_family.as_ref(), "IBM Plex Mono");
        });
        let raw = cx.read(|cx| {
            view.read(cx)
                .shared
                .borrow()
                .session
                .autosave_json()
                .unwrap()
        });
        cx.update(|window, cx| {
            view.update(cx, |view, cx| {
                view.command(Command::Appearance(Appearance::default()), window, cx)
            })
        });
        assert_eq!(cx.read(|cx| cx.theme().mode), ThemeMode::Dark);
        cx.update(|window, cx| view.update(cx, |view, cx| view.restore(&raw, window, cx)));
        draw(cx);
        assert_eq!(
            cx.read(|cx| view.read(cx).shared.borrow().session.workspace.appearance),
            expected
        );
        assert_eq!(cx.read(|cx| cx.theme().mode), ThemeMode::Light);
        assert_eq!(
            cx.read(|cx| cx.theme().mono_font_family.to_string()),
            "IBM Plex Mono"
        );
    }
}
