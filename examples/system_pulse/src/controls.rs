use crate::workspace::{Command, Shared};
use gpui::{prelude::FluentBuilder, *};
use gpui_base::{Button, ElementExt};
use gpui_component::{ActiveTheme, tooltip::Tooltip};
use std::{cell::Cell, rc::Rc};

#[derive(Clone)]
pub(crate) struct FocusEntry {
    pub(crate) handle: FocusHandle,
    was_focused: Rc<Cell<bool>>,
}
impl FocusEntry {
    pub(crate) fn new(cx: &mut App) -> Self {
        Self {
            handle: cx.focus_handle().tab_stop(true),
            was_focused: Rc::new(Cell::new(false)),
        }
    }
    pub(crate) fn entered(&self, window: &Window) -> bool {
        let focused = self.handle.is_focused(window);
        let previous = self.was_focused.replace(focused);
        focused && !previous
    }
}

pub(crate) fn reveal(bounds: Bounds<Pixels>, scroll: &ScrollHandle) -> Point<Pixels> {
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

pub(crate) fn button(
    label: String,
    expanded: Option<bool>,
    focus: &FocusEntry,
    shared: &Shared,
    command: Command,
    inner: Option<ScrollHandle>,
    cx: &App,
) -> Button {
    let id = match &command {
        Command::PanelCollapse(id) => format!("{id}:collapse"),
        Command::PanelVisible(id) => format!("{id}:close"),
        Command::RowCollapse(id, sensor) => format!("{id}:row:{sensor}"),
        Command::SensorVisible(id, sensor) => format!("{id}:visible:{sensor}"),
        Command::Meter(id, sensor) => format!("{id}:meter:{sensor}"),
        _ => unreachable!("panel controls only dispatch panel or sensor commands"),
    };
    let target = shared.borrow().owner.clone();
    let outer = shared.borrow().scroll.clone();
    let focus = focus.clone();
    let visible = match &command {
        Command::PanelCollapse(_) => {
            if expanded == Some(true) {
                "▾".into()
            } else {
                "▸".into()
            }
        }
        Command::PanelVisible(_) | Command::SensorVisible(_, _) if label.starts_with("Hide ") => {
            "×".into()
        }
        Command::RowCollapse(_, _) => format!(
            "{} {}",
            if expanded == Some(true) { "▾" } else { "▸" },
            label
                .split_once(' ')
                .map_or(label.as_str(), |(_, rest)| rest)
        ),
        _ => label.clone(),
    };
    let tooltip = label.clone();
    let ring = cx.theme().ring;
    let hover = cx.theme().muted;
    let control = Button::new(SharedString::from(id.clone()))
        .accessibility_label(label.clone())
        .track_focus(&focus.handle)
        .px_2()
        .h_7()
        .flex_none()
        .text_sm()
        .border_1()
        .rounded(cx.theme().radius)
        .border_color(cx.theme().border)
        .focus_visible(move |style| style.border_color(ring).bg(hover))
        .hover(move |style| style.bg(hover))
        .tooltip(move |window, cx| Tooltip::new(tooltip.clone()).build(window, cx))
        .on_mouse_down(MouseButton::Left, |_, _, cx| cx.stop_propagation())
        .on_click(move |_, window, cx| {
            cx.stop_propagation();
            if let Some(owner) = &target {
                let _ = owner.update(cx, |view, cx| view.command(command.clone(), window, cx));
            }
        })
        .debug_selector(move || id.clone().into())
        .on_prepaint(move |mut bounds, window, _| {
            if focus.entered(window) {
                if let Some(inner) = &inner {
                    bounds.origin += reveal(bounds, inner);
                }
                reveal(bounds, &outer);
                window.refresh();
            }
        })
        .when_some(expanded, |control, expanded| {
            control.aria_expanded(expanded)
        })
        .child(visible);
    control
}
