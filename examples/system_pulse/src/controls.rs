use crate::workspace::{Command, Shared};
use gpui::{prelude::FluentBuilder, *};
use gpui_base::{Button, ElementExt};
use gpui_component::{ActiveTheme, tooltip::Tooltip};
use std::{cell::Cell, rc::Rc};

#[derive(Clone)]
pub(crate) struct FocusEntry {
    pub(crate) handle: FocusHandle,
    was_focused: Rc<Cell<bool>>,
    reveal_state: Rc<Cell<Option<RevealState>>>,
}
impl FocusEntry {
    pub(crate) fn new(cx: &mut App) -> Self {
        Self::from_handle(cx.focus_handle().tab_stop(true))
    }
    pub(crate) fn from_handle(handle: FocusHandle) -> Self {
        Self {
            handle,
            was_focused: Rc::new(Cell::new(false)),
            reveal_state: Rc::new(Cell::new(None)),
        }
    }
    pub(crate) fn entered(&self, window: &Window) -> bool {
        let focused = self.handle.is_focused(window);
        let previous = self.was_focused.replace(focused);
        focused && !previous
    }
}

#[derive(Clone, Copy)]
struct RevealState {
    visible: bool,
    inner_offset: Option<Point<Pixels>>,
    outer_offset: Point<Pixels>,
}

fn contained(bounds: Bounds<Pixels>, viewport: Bounds<Pixels>) -> bool {
    bounds.left() >= viewport.left()
        && bounds.right() <= viewport.right()
        && bounds.top() >= viewport.top()
        && bounds.bottom() <= viewport.bottom()
}

impl FocusEntry {
    fn reveal_control(
        &self,
        mut bounds: Bounds<Pixels>,
        inner: Option<&ScrollHandle>,
        outer: &ScrollHandle,
        window: &mut Window,
    ) {
        let entered = self.entered(window);
        if !self.handle.is_focused(window) {
            self.reveal_state.set(None);
            return;
        }
        let inner_offset = inner.map(ScrollHandle::offset);
        let outer_offset = outer.offset();
        let visible = contained(bounds, outer.bounds())
            && inner.is_none_or(|scroll| contained(bounds, scroll.bounds()));
        // A live reading can resize its adjacent disclosure after focus. Follow
        // that layout change only while the previously visible control's scroll
        // offsets stay unchanged; deliberate scrolling must remain independent.
        let layout_clipped = !visible
            && self.reveal_state.get().is_some_and(|previous| {
                previous.visible
                    && previous.inner_offset == inner_offset
                    && previous.outer_offset == outer_offset
            });
        let mut outer_shift = point(px(0.), px(0.));
        if entered || layout_clipped {
            if let Some(inner) = inner {
                bounds.origin += reveal(bounds, inner);
            }
            outer_shift = reveal(bounds, outer);
            bounds.origin += outer_shift;
            window.refresh();
        }
        self.reveal_state.set(Some(RevealState {
            visible: contained(bounds, outer.bounds())
                && inner.is_none_or(|scroll| {
                    let mut viewport = scroll.bounds();
                    viewport.origin += outer_shift;
                    contained(bounds, viewport)
                }),
            inner_offset: inner.map(ScrollHandle::offset),
            outer_offset: outer.offset(),
        }));
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
    let disclosure = matches!(&command, Command::RowCollapse(_, _));
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
        Command::RowCollapse(id, sensor)
            if id == "cpu:host" && crate::dashboard::core_number(sensor).is_some() =>
        {
            format!(
                "{} {}",
                if expanded == Some(true) { "▾" } else { "▸" },
                crate::dashboard::core_number(sensor).expect("matched core")
            )
        }
        Command::RowCollapse(_, _) => format!(
            "{} {}",
            if expanded == Some(true) { "▾" } else { "▸" },
            label
                .split_once(' ')
                .map_or(label.as_str(), |(_, rest)| rest)
        ),
        Command::Meter(_, _) => label.split_whitespace().nth(1).unwrap_or("Meter").into(),
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
        .when(disclosure, |button| {
            button.flex_1().min_w_0().overflow_hidden().justify_start()
        })
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
        .on_prepaint(move |bounds, window, _| {
            // The measurement canvas sits inside the one-pixel control border.
            focus.reveal_control(bounds.dilate(px(1.)), inner.as_ref(), &outer, window);
        })
        .when_some(expanded, |control, expanded| {
            control.aria_expanded(expanded)
        })
        .child(
            div()
                .min_w_0()
                .overflow_hidden()
                .text_ellipsis()
                .child(visible),
        );
    control
}
