use std::{cell::Cell, rc::Rc};

use gpui::{
    AppContext as _, Axis, Context, Entity, InteractiveElement as _, IntoElement, Modifiers,
    MouseButton, ParentElement as _, Render, Styled as _, TestAppContext, VisualTestContext,
    Window, div, point, prelude::FluentBuilder, px,
};

use super::{ResizablePanelGroup, ResizableState, resizable_panel};

struct Harness {
    state: Entity<ResizableState>,
    axis: Axis,
    middle_visible: bool,
    middle_collapsed: bool,
    resize_callbacks: Rc<Cell<usize>>,
    group_visible: bool,
}

impl Render for Harness {
    fn render(&mut self, _: &mut Window, _: &mut Context<Self>) -> impl IntoElement {
        let horizontal = self.axis == Axis::Horizontal;
        let preferred = if horizontal { 420. } else { 280. };
        div()
            .w(px(1200.))
            .h(px(596.))
            .when(self.group_visible, |this| {
                this.child(
                    ResizablePanelGroup::new("constraints")
                        .axis(self.axis)
                        .preserve_constraints()
                        .with_state(&self.state)
                        .on_resize({
                            let calls = self.resize_callbacks.clone();
                            move |_, _, _| calls.set(calls.get() + 1)
                        })
                        .children((0..3).map(|ix| {
                            let collapsed = ix == 1 && self.middle_collapsed;
                            resizable_panel()
                                .visible(ix != 1 || self.middle_visible)
                                .size(px(if collapsed { 36. } else { preferred }))
                                .size_range(
                                    px(if collapsed { 36. } else { 220. })..px(if collapsed {
                                        36.
                                    } else {
                                        10000.
                                    }),
                                )
                                .when(ix != 2, |panel| panel.flex_none())
                                .child(
                                    div()
                                        .size_full()
                                        .debug_selector(move || format!("constraint-{ix}").into()),
                                )
                        })),
                )
            })
    }
}

fn harness(
    cx: &mut TestAppContext,
    axis: Axis,
    middle_visible: bool,
    middle_collapsed: bool,
) -> (
    &mut VisualTestContext,
    Entity<Harness>,
    Entity<ResizableState>,
) {
    let state = cx.update(|cx| cx.new(|_| ResizableState::default()));
    let (view, cx) = cx.add_window_view({
        let state = state.clone();
        move |_, _| Harness {
            state,
            axis,
            middle_visible,
            middle_collapsed,
            resize_callbacks: Rc::new(Cell::new(0)),
            group_visible: true,
        }
    });
    draw(cx);
    (cx, view, state)
}

fn draw(cx: &mut VisualTestContext) {
    for _ in 0..3 {
        cx.update(|window, cx| window.draw(cx).clear(cx));
    }
}

#[gpui::test]
fn container_growth_preserves_fixed_width_and_caches_flexible_width(cx: &mut TestAppContext) {
    let (cx, _, state) = harness(cx, Axis::Horizontal, false, false);
    assert_eq!(
        cx.debug_bounds("constraint-0").unwrap().size.width,
        px(420.)
    );
    assert_eq!(
        cx.debug_bounds("constraint-2").unwrap().size.width,
        px(780.)
    );
    state.read_with(cx, |state, _| {
        assert_eq!(state.sizes(), &vec![px(420.), px(0.), px(780.)]);
    });
}

#[gpui::test]
fn shrinking_before_collapsed_slot_redirects_space_to_expanded_sibling(cx: &mut TestAppContext) {
    let (cx, _, state) = harness(cx, Axis::Vertical, true, true);
    cx.update(|window, cx| {
        state.update(cx, |state, cx| state.resize_panel(0, px(240.), window, cx))
    });
    // Check the resize result before prepaint can mask a cache/render disagreement.
    state.read_with(cx, |state, _| {
        assert_eq!(state.sizes(), &vec![px(240.), px(36.), px(320.)])
    });
    draw(cx);
    assert_eq!(
        cx.debug_bounds("constraint-1").unwrap().size.height,
        px(36.)
    );
    assert_eq!(
        cx.debug_bounds("constraint-2").unwrap().size.height,
        px(320.)
    );
}

#[gpui::test]
fn divider_after_hidden_slot_resizes_previous_visible_panel(cx: &mut TestAppContext) {
    let (cx, view, state) = harness(cx, Axis::Horizontal, true, false);
    // Hide a previously measured slot, so it has stale bounds and size metadata.
    cx.update(|_, cx| {
        view.update(cx, |view, cx| {
            view.middle_visible = false;
            cx.notify();
        })
    });
    draw(cx);
    let boundary = cx.debug_bounds("constraint-2").unwrap().left();
    cx.simulate_mouse_down(
        point(boundary - px(2.), px(50.)),
        MouseButton::Left,
        Modifiers::default(),
    );
    cx.simulate_mouse_move(
        point(boundary + px(10.), px(50.)),
        Some(MouseButton::Left),
        Modifiers::default(),
    );
    cx.simulate_mouse_move(
        point(px(480.), px(50.)),
        Some(MouseButton::Left),
        Modifiers::default(),
    );
    cx.simulate_mouse_up(
        point(px(480.), px(50.)),
        MouseButton::Left,
        Modifiers::default(),
    );
    draw(cx);
    state.read_with(cx, |state, _| {
        assert_eq!(state.sizes(), &vec![px(480.), px(0.), px(720.)])
    });
    assert_eq!(
        cx.debug_bounds("constraint-0").unwrap().size.width,
        px(480.)
    );
    assert_eq!(
        cx.debug_bounds("constraint-2").unwrap().size.width,
        px(720.)
    );
}

struct SavedWidthsHarness {
    state: Entity<ResizableState>,
}
impl Render for SavedWidthsHarness {
    fn render(&mut self, _: &mut Window, _: &mut Context<Self>) -> impl IntoElement {
        div().w(px(1200.)).h(px(100.)).child(
            ResizablePanelGroup::new("saved-widths")
                .preserve_constraints()
                .with_state(&self.state)
                .children((0..2).map(|ix| {
                    resizable_panel()
                        .size(px(420.))
                        .size_range(px(320.)..px(10000.))
                        .when(ix == 0, |panel| panel.flex_none())
                        .child(
                            div()
                                .size_full()
                                .debug_selector(move || format!("saved-width-{ix}").into()),
                        )
                })),
        )
    }
}

#[gpui::test]
fn saved_widths_do_not_proportionally_scale_fixed_panes(cx: &mut TestAppContext) {
    let state = cx.update(|cx| {
        let state = cx.new(|_| ResizableState::default());
        state.update(cx, |state, cx| {
            state.sync_panels_count(Axis::Horizontal, 2, cx);
            state.adopt_sizes(&[Some(px(420.)), Some(px(420.))], cx);
        });
        state
    });
    let (_, cx) = cx.add_window_view({
        let state = state.clone();
        move |_, _| SavedWidthsHarness { state }
    });
    draw(cx);
    assert_eq!(
        cx.debug_bounds("saved-width-0").unwrap().size.width,
        px(420.)
    );
    assert_eq!(
        cx.debug_bounds("saved-width-1").unwrap().size.width,
        px(780.)
    );
    state.read_with(cx, |state, _| {
        assert_eq!(state.sizes(), &vec![px(420.), px(780.)])
    });
}

fn assert_hiding_drag_source_cancels(
    cx: &mut TestAppContext,
    restore_before_release: bool,
    omit_group: bool,
) {
    let (cx, view, state) = harness(cx, Axis::Horizontal, true, false);
    let events = Rc::new(Cell::new(0));
    let _subscription = cx.update(|_, cx| {
        let events = events.clone();
        cx.subscribe(&state, move |_, _, _| events.set(events.get() + 1))
    });
    let boundary = cx.debug_bounds("constraint-2").unwrap().left();
    cx.simulate_mouse_down(
        point(boundary - px(2.), px(50.)),
        MouseButton::Left,
        Modifiers::default(),
    );
    cx.simulate_mouse_move(
        point(boundary + px(10.), px(50.)),
        Some(MouseButton::Left),
        Modifiers::default(),
    );
    state.read_with(cx, |state, _| assert_eq!(state.resizing_panel_ix, Some(1)));
    cx.update(|_, cx| {
        if omit_group {
            state.update(cx, |state, cx| {
                // Refreshing an unrelated slot must preserve the active source.
                state.adopt_sizes(&[Some(px(0.)), None, None], cx);
                assert_eq!(state.resizing_panel_ix, Some(1));
                state.adopt_sizes(&[Some(px(0.)); 3], cx);
            });
            view.update(cx, |view, cx| {
                view.group_visible = false;
                cx.notify();
            });
        } else {
            view.update(cx, |view, cx| {
                view.middle_visible = false;
                cx.notify();
            });
        }
    });
    draw(cx);
    if omit_group {
        cx.update(|_, cx| {
            state.update(cx, |state, cx| {
                state.adopt_sizes(&[Some(px(420.)), Some(px(420.)), Some(px(360.))], cx)
            });
            view.update(cx, |view, cx| {
                view.group_visible = true;
                cx.notify();
            });
        });
        draw(cx);
    }
    if restore_before_release {
        cx.update(|_, cx| {
            view.update(cx, |view, cx| {
                view.middle_visible = true;
                cx.notify();
            })
        });
        draw(cx);
    }
    let restored = state.read_with(cx, |state, _| state.sizes().clone());
    cx.simulate_mouse_move(
        point(boundary + px(60.), px(50.)),
        Some(MouseButton::Left),
        Modifiers::default(),
    );
    cx.simulate_mouse_up(
        point(boundary + px(60.), px(50.)),
        MouseButton::Left,
        Modifiers::default(),
    );
    draw(cx);
    state.read_with(cx, |state, _| assert_eq!(state.sizes(), &restored));
    assert_eq!(events.get(), 0, "a canceled drag must not emit Resized");
    view.read_with(cx, |view, _| assert_eq!(view.resize_callbacks.get(), 0));
    state.read_with(cx, |state, _| assert_eq!(state.resizing_panel_ix, None));
}

#[gpui::test]
fn hiding_active_drag_source_does_not_report_a_completed_resize(cx: &mut TestAppContext) {
    assert_hiding_drag_source_cancels(cx, false, false);
}

#[gpui::test]
fn restoring_hidden_drag_source_does_not_resume_the_canceled_drag(cx: &mut TestAppContext) {
    assert_hiding_drag_source_cancels(cx, true, false);
}

#[gpui::test]
fn refreshing_hidden_source_cancels_drag_even_when_group_is_omitted(cx: &mut TestAppContext) {
    assert_hiding_drag_source_cancels(cx, true, true);
}
