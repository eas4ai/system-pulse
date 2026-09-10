//! Process table interaction, keeping canonical snapshots separate from the visible order.
use super::*;
use crate::processes::{self, ProcessSort};
use gpui_kit::component::{
    Disableable, Sizable,
    button::{Button, ButtonVariants},
    input::{Input, InputEvent, InputState},
    menu::{ContextMenuExt, PopupMenuItem},
};
use std::rc::Rc;
use system_pulse_collectors::process_control::{self, ProcessSignal};

#[derive(Default)]
pub(super) struct ProcessPanelState {
    input: Option<Entity<InputState>>,
    subscription: Option<Subscription>,
    query: String,
    sort: ProcessSort,
    confirmation: Option<(ProcessIdentity, String, ProcessSignal)>,
}

// The workspace retains this state while native windows and controls are recreated.
#[derive(Default)]
pub(crate) struct ProcessActionState {
    busy: bool,
    notice: String,
}

impl ProcessActionState {
    fn finish_action(
        &mut self,
        name: &str,
        pid: u32,
        result: Result<process_control::ProcessActionOutcome, String>,
    ) {
        self.busy = false;
        self.notice = match result {
            Ok(process_control::ProcessActionOutcome::SignalSent) => format!(
                "Request sent to {name} (PID {pid}). Waiting for the process list to update."
            ),
            Ok(process_control::ProcessActionOutcome::ExitObserved) => {
                format!("{name} (PID {pid}) has exited.")
            }
            Ok(process_control::ProcessActionOutcome::CloseRequested) => format!(
                "Closure requested for {name} (PID {pid}). Check its window for a response; exit has not been confirmed."
            ),
            Ok(process_control::ProcessActionOutcome::TerminationPending) => format!(
                "Termination requested for {name} (PID {pid}); exit is still pending. Check the process list before trying again."
            ),
            Err(error) => error,
        };
    }
}

impl MonitorPanel {
    fn process_projection(&self) -> Vec<usize> {
        processes::project(
            &self.shared.borrow().processes,
            &self.process_state.query,
            self.process_state.sort,
        )
    }

    fn visible_selected_index(&self, rows: &[usize]) -> Option<usize> {
        let selected = self.selected_index()?;
        rows.iter().position(|&index| index == selected)
    }

    fn prepare_process_action(
        &mut self,
        identity: ProcessIdentity,
        signal: ProcessSignal,
        cx: &mut Context<Self>,
    ) {
        if self.shared.borrow().process_action.busy {
            return;
        }
        let name = self
            .shared
            .borrow()
            .processes
            .iter()
            .find(|row| row.identity == identity)
            .and_then(|row| row.cells.get(1))
            .cloned();
        if let Some(name) = name {
            self.selected = Some(identity.clone());
            self.process_state.confirmation = Some((identity, name, signal));
            self.shared.borrow_mut().process_action.notice.clear();
        } else {
            self.process_state.confirmation = None;
            self.shared.borrow_mut().process_action.notice =
                "This process has exited. Select another process.".into();
        }
        cx.notify();
    }

    fn confirm_process_action(&mut self, cx: &mut Context<Self>) {
        if self.shared.borrow().process_action.busy {
            return;
        }
        let Some((identity, name, signal)) = self.process_state.confirmation.take() else {
            return;
        };
        // Fixtures can never dispatch an OS operation, even when a PID happens to match.
        if !self.shared.borrow().allow_process_actions || self.shared.borrow().snapshot.is_none() {
            self.shared.borrow_mut().process_action.notice =
                "Process actions require a live system snapshot.".into();
            cx.notify();
            return;
        }
        self.shared.borrow_mut().process_action.busy = true;
        self.shared.borrow_mut().process_action.notice =
            format!("Sending request to {name} (PID {})…", identity.pid);
        let shared = self.shared.clone();
        cx.spawn(async move |weak, cx| {
            let pid = identity.pid;
            let result = smol::unblock(move || {
                process_control::send_signal_with_authentication(&identity, signal)
            })
            .await;
            shared
                .borrow_mut()
                .process_action
                .finish_action(&name, pid, result);
            let _ = weak.update(cx, |_, cx| cx.notify());
            // A reopened dashboard owns a new panel. Deliver completion there even
            // when the original panel no longer exists.
            let owner = shared.borrow().owner.clone();
            if let Some(owner) = owner {
                let _ = owner.update(cx, |owner, cx| {
                    if let Some(screen) = &owner.screen_view {
                        let _ = screen.update(cx, |screen, cx| screen.refresh(cx));
                    }
                    cx.notify();
                });
            }
        })
        .detach();
        cx.notify();
    }

    fn process_toolbar(&mut self, window: &mut Window, cx: &mut Context<Self>) -> AnyElement {
        if self.process_state.input.is_none() {
            let input =
                cx.new(|cx| InputState::new(window, cx).placeholder("Search name, PID, or user…"));
            self.process_state.subscription =
                Some(cx.subscribe(&input, |this, input, event, cx| {
                    if matches!(event, InputEvent::Change) {
                        this.process_state.query = input.read(cx).value().to_string();
                        this.table_scroll.scroll_to_item(0, ScrollStrategy::Top);
                        cx.notify();
                    }
                }));
            self.process_state.input = Some(input);
        }
        let mut toolbar = div().flex().flex_col().gap_1().flex_none().child(
            div()
                .flex()
                .items_center()
                .gap_1()
                .child(
                    div()
                        .w(px(280.))
                        .flex_none()
                        .min_w_0()
                        .debug_selector(|| "process-search".into())
                        .child(Input::new(self.process_state.input.as_ref().unwrap()).small()),
                )
                .children(
                    [
                        ("end-task", "End task…", ProcessSignal::Terminate),
                        ("force-quit", "Force quit…", ProcessSignal::Kill),
                    ]
                    .into_iter()
                    .map(|(id, label, signal)| {
                        let disabled =
                            self.selected.is_none() || self.shared.borrow().process_action.busy;
                        Button::new(id)
                            .small()
                            .ghost()
                            .label(label)
                            .disabled(disabled)
                            .a11y_synthetic_children(move |tree| {
                                // Kit 0.6.1 blocks activation but does not publish
                                // its disabled state to the native accessibility node.
                                if disabled {
                                    tree.parent_node().set_disabled();
                                }
                            })
                            .on_click(cx.listener(move |this, _, _, cx| {
                                if let Some(identity) = this.selected.clone() {
                                    this.prepare_process_action(identity, signal, cx);
                                }
                            }))
                    }),
                ),
        );
        if let Some((identity, name, signal)) = &self.process_state.confirmation {
            let force = *signal == ProcessSignal::Kill;
            let prompt = format!(
                "{} {name} (PID {})?{}",
                if force { "Force quit" } else { "End" },
                identity.pid,
                if force {
                    " Unsaved work may be lost."
                } else if cfg!(target_os = "windows") {
                    " Request graceful closure. The application may ask to save work or decline."
                } else {
                    " The process will receive a termination request."
                }
            );
            toolbar = toolbar.child(
                div()
                    .id("process-action-confirmation")
                    .flex()
                    .flex_wrap()
                    .items_center()
                    .gap_2()
                    .p_2()
                    .bg(cx.theme().muted)
                    .role(Role::Group)
                    .accessibility_id("process-action-confirmation")
                    .aria_label(prompt.clone())
                    .child(prompt)
                    .child(
                        Button::new("cancel-process-action")
                            .accessibility_label("Cancel process action")
                            .small()
                            .child(
                                div()
                                    .debug_selector(|| "process-action:cancel".into())
                                    .child("Cancel"),
                            )
                            .on_click(cx.listener(|this, _, window, cx| {
                                this.controls["table"].handle.focus(window, cx);
                                this.process_state.confirmation = None;
                                cx.notify();
                            })),
                    )
                    .child(
                        Button::new("confirm-process-action")
                            .accessibility_label(if force {
                                "Confirm force quit"
                            } else {
                                "Confirm end task"
                            })
                            .small()
                            .danger()
                            .child(
                                div()
                                    .debug_selector(|| "process-action:confirm".into())
                                    .child(if force { "Force quit" } else { "End task" }),
                            )
                            .on_click(cx.listener(|this, _, window, cx| {
                                this.controls["table"].handle.focus(window, cx);
                                this.confirm_process_action(cx);
                            })),
                    ),
            );
        }
        if !self.shared.borrow().process_action.notice.is_empty() {
            toolbar = toolbar.child(
                div()
                    .id("process-action-status")
                    .p_1()
                    .role(Role::Status)
                    .accessibility_id("process-action-status")
                    .aria_label(self.shared.borrow().process_action.notice.clone())
                    .child(self.shared.borrow().process_action.notice.clone()),
            );
        }
        toolbar.into_any_element()
    }

    fn request_keyboard_repaint(&mut self, window: &mut Window, cx: &Context<Self>) {
        if self.keyboard_repaint_pending {
            return;
        }
        self.keyboard_repaint_pending = true;
        // Dirtying this event makes GPUI redraw before the next queued key,
        // which can starve live snapshot delivery during ordinary key repeat.
        cx.on_next_frame(window, |this, window, cx| {
            this.keyboard_repaint_pending = false;
            window.refresh();
            cx.notify();
        });
    }

    fn process_details(&self, cx: &App) -> AnyElement {
        let data = self.shared.borrow();
        let selected = self
            .selected
            .as_ref()
            .and_then(|identity| data.processes.iter().find(|row| &row.identity == identity));
        let Some(row) = selected else {
            return div()
                .id("process-details")
                .accessibility_id("process-details")
                .role(Role::Group)
                .aria_label("Process details")
                .p_3()
                .flex_none()
                .border_t_1()
                .border_color(cx.theme().border)
                .text_sm()
                .text_color(cx.theme().muted_foreground)
                .child("Select a process to inspect its current readings.")
                .into_any_element();
        };
        let name = row.cells.get(1).cloned().unwrap_or_default();
        div()
            .id("process-details")
            .accessibility_id("process-details")
            .debug_selector(|| "process-details".into())
            .role(Role::Group)
            .aria_label(format!("Details for {name}, PID {}", row.identity.pid))
            .flex_none()
            .flex()
            .flex_col()
            .gap_2()
            .p_3()
            .border_t_1()
            .border_color(cx.theme().border)
            .bg(crate::screen_style::palette(cx).surface)
            .child(
                div()
                    .flex()
                    .items_center()
                    .gap_3()
                    .child(crate::screen_style::heading(name, 18., cx))
                    .child(
                        div()
                            .text_sm()
                            .text_color(cx.theme().muted_foreground)
                            .child(format!("PID {}", row.identity.pid)),
                    ),
            )
            .child(
                div().flex().flex_wrap().gap_4().children(
                    processes::VISIBLE_PROCESS_COLUMNS
                        .iter()
                        .copied()
                        .filter(|column| *column >= 2)
                        .map(|column| {
                            div()
                                .flex()
                                .flex_col()
                                .gap_1()
                                .min_w(px(110.))
                                .flex_1()
                                .child(
                                    div()
                                        .text_size(px(11.))
                                        .text_color(cx.theme().muted_foreground)
                                        .child(live::PROCESS_COLUMNS[column]),
                                )
                                .child(
                                    crate::meters::metric_label(
                                        format!("process-detail:{column}"),
                                        row.cells.get(column).cloned().unwrap_or_default(),
                                    )
                                    .text_sm()
                                    .font_family(cx.theme().mono_font_family.clone()),
                                )
                        }),
                ),
            )
            .into_any_element()
    }

    pub(super) fn process_table(
        &mut self,
        window: &mut Window,
        cx: &mut Context<Self>,
    ) -> AnyElement {
        let toolbar = self.process_toolbar(window, cx);
        let rows = Rc::new(self.process_projection());
        // Snapshot delivery may reorder rows after a key but before layout.
        // Consume the intent even when reconciliation cleared the selection.
        let reveal_pending = std::mem::take(&mut self.process_reveal_pending);
        if reveal_pending && let Some(index) = self.visible_selected_index(&rows) {
            self.table_scroll.scroll_to_item(index, ScrollStrategy::Top);
        }
        let reveal_identity = reveal_pending.then(|| self.selected.clone()).flatten();
        let revealing_selected_row = reveal_identity.is_some();
        let handle = self.controls["table"].handle.clone();
        let ring = cx.theme().ring;
        let count = rows.len();
        let widths = self.shared.borrow().process_widths;
        let width: f32 = processes::VISIBLE_PROCESS_COLUMNS
            .iter()
            .map(|&column| widths[column])
            .sum();
        let sizes = Rc::new(vec![size(px(width), window.rem_size() * 1.75); count]);
        let list = v_virtual_list(
            cx.entity(),
            "process-rows",
            sizes,
            move |this, range, _, cx| {
                let data = this.shared.borrow();
                range
                    .filter_map(|index| {
                        let process = data.processes.get(*rows.get(index)?)?;
                        let identity = process.identity.clone();
                        let menu_identity = identity.clone();
                        let entity = cx.entity().downgrade();
                        let reveal = reveal_identity.as_ref() == Some(&identity);
                        let outer = data.scroll.clone();
                        Some(
                            process_row(
                                process,
                                index,
                                this.selected.as_ref() == Some(&process.identity),
                                &data.process_widths,
                                cx,
                            )
                            .on_prepaint(move |mut bounds, window, _| {
                                if reveal {
                                    // A dock region may be taller than the window.
                                    // Reveal the selected row after virtual layout,
                                    // preserving the user's horizontal position.
                                    let viewport = outer.bounds();
                                    bounds.origin.x = viewport.origin.x;
                                    bounds.size.width = viewport.size.width;
                                    let shift = controls::reveal(bounds, &outer);
                                    if shift.y != px(0.) {
                                        window.refresh();
                                    }
                                }
                            })
                            .on_click(cx.listener(move |this, _, window, cx| {
                                this.selected = Some(identity.clone());
                                this.controls["table"].handle.focus(window, cx);
                                cx.notify();
                            }))
                            .context_menu(move |menu, _, _| {
                                let mut menu = menu;
                                for (label, signal) in [
                                    ("End task…", ProcessSignal::Terminate),
                                    ("Force quit…", ProcessSignal::Kill),
                                ] {
                                    let identity = menu_identity.clone();
                                    let entity = entity.clone();
                                    menu = menu.item(PopupMenuItem::new(label).on_click(
                                        move |_, _, cx| {
                                            let _ = entity.update(cx, |this, cx| {
                                                this.prepare_process_action(
                                                    identity.clone(),
                                                    signal,
                                                    cx,
                                                )
                                            });
                                        },
                                    ));
                                }
                                menu
                            }),
                        )
                    })
                    .collect()
            },
        )
        .track_scroll(&self.table_scroll);
        let outer = self.shared.borrow().scroll.clone();
        let focus = self.controls["table"].clone();
        let horizontal = self.table_horizontal.clone();
        let table = crate::workspace::scroll_viewport("process-table-viewport", "processes:viewport".into()).size_full().relative().track_focus(&handle)
            .border_1().border_color(cx.theme().border).focus_visible(move |style| style.border_color(ring))
            .debug_selector(|| "process-table".into())
            .on_key_down(cx.listener(|this, event: &KeyDownEvent, window, cx| {
                if event.keystroke.modifiers.alt { return; }
                if matches!(event.keystroke.key.as_str(), "left" | "right") {
                    let old = this.table_horizontal.offset();
                    let delta = if event.keystroke.key == "left" { 240. } else { -240. };
                    this.table_horizontal.set_offset(point((old.x + px(delta)).clamp(-this.table_horizontal.max_offset().x, px(0.)), old.y));
                    this.request_keyboard_repaint(window, cx); cx.stop_propagation(); return;
                }
                let rows = this.process_projection();
                let count = rows.len();
                if count == 0 { return; }
                let current = this.visible_selected_index(&rows);
                let next = match event.keystroke.key.as_str() {
                    "up" => current.unwrap_or(0).saturating_sub(1),
                    "down" => current.map_or(0, |i| (i + 1).min(count - 1)),
                    "home" => 0, "end" => count - 1, _ => return,
                };
                this.selected = Some(this.shared.borrow().processes[rows[next]].identity.clone());
                this.process_reveal_pending = true;
                this.request_keyboard_repaint(window, cx); cx.stop_propagation();
            }))
            .on_prepaint(move |bounds, window, _| {
                if focus.entered(window) && !revealing_selected_row {
                    // Entering a tall region reveals its leading viewport. A
                    // pending row reveal already chose the keyboard destination.
                    let mut target = bounds.dilate(px(1.));
                    target.size.height = target.size.height.min(outer.bounds().size.height);
                    controls::reveal(target, &outer);
                    window.refresh();
                }
            })
            .child(div().id("process-horizontal").size_full().overflow_x_scroll().track_scroll(&horizontal)
                .child(Table::new("process-table").row_count(count + 1).column_count(processes::VISIBLE_PROCESS_COLUMNS.len())
                    .accessibility_label(format!("{count} readable process rows; arrows navigate and scroll columns; Tab leaves table"))
                    .w_full().min_w(px(width)).h_full().flex().flex_col()
                    .child(TableRow::new("process-columns", 1).flex().h_7().flex_none()
                        .children(processes::VISIBLE_PROCESS_COLUMNS.iter().enumerate().map(|(visible_index, &column)| {
                            let title = live::PROCESS_COLUMNS[column];
                            TableCell::new(("process-heading", column), visible_index + 1).role(Role::ColumnHeader)
                                .aria_label(format!("Sort by {title}")).w(px(widths[column])).flex_none()
                                .when(column == 1, |cell| cell.flex_grow(1.))
                                .child(Button::new(("sort-process", column)).accessibility_label(format!("Sort by {title}")).ghost().small().w_full().px_2().justify_start()
                                    .child(div().w_full().when(column == 0 || (2..7).contains(&column), |label| label.text_right()).debug_selector(move || format!("process-sort:{column}").into()).child(format!("{title}{}", if self.process_state.sort.column == column {
                                        if self.process_state.sort.descending { " ↓" } else { " ↑" }
                                    } else { "" })))
                                    .on_click(cx.listener(move |this, _, _, cx| {
                                        this.process_state.sort.select(column);
                                        this.process_reveal_pending = true;
                                        cx.notify();
                                    })))
                        })))
                    .child(crate::workspace::scroll_viewport("process-row-clip", "processes:rows-viewport".into()).flex_1().min_h_0().child(list))))
            .child(ScrollableMask::new(Axis::Vertical, self.table_scroll.base_handle()))
            .child(Scrollbar::vertical(&self.table_scroll).mode(ScrollbarMode::Always))
            .child(Scrollbar::horizontal(&horizontal).mode(ScrollbarMode::Always))
            .into_any_element();
        div()
            .size_full()
            .flex()
            .flex_col()
            .gap_1()
            .child(toolbar)
            .child(div().flex_1().min_h_0().child(table))
            .when(self.standalone, |view| view.child(self.process_details(cx)))
            .when(count == 0, |view| {
                view.child(div().p_2().child("No processes match this search."))
            })
            .into_any_element()
    }
}

#[cfg(test)]
mod tests {
    use super::{InputEvent, MonitorPanel, ProcessSignal};
    use crate::native_tests::{draw, harness, native_key, panel};
    use gpui_kit::{AppContext, Entity, Modifiers, TestAppContext, VisualTestContext, point, px};

    fn focus_table(processes: &Entity<MonitorPanel>, cx: &mut VisualTestContext) {
        cx.update(|window, cx| {
            processes.read(cx).controls["table"]
                .handle
                .clone()
                .focus(window, cx)
        });
        draw(cx);
    }

    #[gpui_kit::test]
    fn search_and_sort_controls_preserve_identity_and_navigate_visible_rows(
        cx: &mut TestAppContext,
    ) {
        let (view, cx) = harness(cx);
        let processes = panel(&view, "processes", cx);
        focus_table(&processes, cx);
        cx.update(|_, cx| {
            processes.update(cx, |this, cx| {
                let mut data = this.shared.borrow_mut();
                data.processes.truncate(3);
                for (index, row) in data.processes.iter_mut().enumerate() {
                    row.cells[1] = ["Firefox", "terminal", "editor"][index].into();
                    row.numeric[0] = Some([9., 80., 20.][index]);
                }
                cx.notify();
            })
        });
        draw(cx);
        assert_eq!(
            cx.read(|cx| processes.read(cx).process_projection()),
            vec![1, 2, 0]
        );
        let row = cx.debug_bounds("process-row:0").unwrap();
        cx.simulate_click(row.origin + point(px(15.), px(10.)), Modifiers::none());
        draw(cx);
        let selected = cx
            .read(|cx| processes.read(cx).selected.clone())
            .expect("pointer selects a row");
        assert_eq!(cx.read(|cx| processes.read(cx).selected_index()), Some(1));
        let heading = cx.debug_bounds("process-sort:2").unwrap();
        cx.simulate_click(heading.center(), Modifiers::none());
        draw(cx);
        assert_eq!(
            cx.read(|cx| processes.read(cx).process_projection()),
            vec![0, 2, 1]
        );
        assert_eq!(
            cx.read(|cx| processes.read(cx).selected.clone()),
            Some(selected.clone())
        );
        let input = cx.read(|cx| processes.read(cx).process_state.input.clone().unwrap());
        cx.update(|window, cx| {
            input.update(cx, |input, cx| {
                input.set_value("FIREFOX", window, cx);
                cx.emit(InputEvent::Change);
            })
        });
        draw(cx);
        assert_eq!(
            cx.read(|cx| processes.read(cx).process_projection()),
            vec![0]
        );
        assert_eq!(
            cx.read(|cx| processes.read(cx).selected.clone()),
            Some(selected)
        );
        focus_table(&processes, cx);
        native_key("down", cx);
        draw(cx);
        assert_eq!(cx.read(|cx| processes.read(cx).selected_index()), Some(0));
        assert!(cx.debug_bounds("process-row:1").is_none());
    }

    #[gpui_kit::test]
    fn confirmation_cancel_keeps_identity_and_fixture_execution_reports_error(
        cx: &mut TestAppContext,
    ) {
        let (view, cx) = harness(cx);
        let processes = panel(&view, "processes", cx);
        focus_table(&processes, cx);
        let identity = cx.read(|cx| {
            processes.read(cx).shared.borrow().processes[0]
                .identity
                .clone()
        });
        cx.update(|_, cx| {
            processes.update(cx, |this, cx| {
                this.prepare_process_action(identity.clone(), ProcessSignal::Kill, cx)
            })
        });
        draw(cx);
        // A later selection must not retarget a pending confirmation.
        cx.update(|_, cx| {
            processes.update(cx, |this, _| {
                this.selected = Some(this.shared.borrow().processes[1].identity.clone());
            })
        });
        assert_eq!(
            cx.read(|cx| processes
                .read(cx)
                .process_state
                .confirmation
                .as_ref()
                .unwrap()
                .0
                .clone()),
            identity
        );
        let cancel = cx.debug_bounds("process-action:cancel").unwrap();
        cx.simulate_click(cancel.center(), Modifiers::none());
        draw(cx);
        cx.read(|cx| {
            let panel = processes.read(cx);
            assert!(panel.process_state.confirmation.is_none());
            let data = panel.shared.borrow();
            assert!(!data.process_action.busy);
            assert!(data.process_action.notice.is_empty());
        });
        cx.update(|_, cx| {
            processes.update(cx, |this, cx| {
                this.prepare_process_action(identity.clone(), ProcessSignal::Terminate, cx)
            })
        });
        draw(cx);
        let confirm = cx.debug_bounds("process-action:confirm").unwrap();
        cx.simulate_click(confirm.center(), Modifiers::none());
        draw(cx);
        cx.read(|cx| {
            let panel = processes.read(cx);
            assert!(panel.process_state.confirmation.is_none());
            let data = panel.shared.borrow();
            assert!(!data.process_action.busy);
            assert_eq!(
                data.process_action.notice,
                "Process actions require a live system snapshot."
            );
        });
        cx.update(|_, cx| {
            processes.update(cx, |this, cx| {
                this.shared
                    .borrow_mut()
                    .processes
                    .retain(|row| row.identity != identity);
                this.prepare_process_action(identity.clone(), ProcessSignal::Kill, cx);
            })
        });
        assert!(cx.read(|cx| {
            processes
                .read(cx)
                .shared
                .borrow()
                .process_action
                .notice
                .contains("has exited")
        }));
    }
    #[gpui_kit::test]
    fn pending_action_rejects_duplicate_confirmation_and_selection_changes(
        cx: &mut TestAppContext,
    ) {
        let (view, cx) = harness(cx);
        let processes = panel(&view, "processes", cx);
        focus_table(&processes, cx);
        cx.update(|_, cx| {
            processes.update(cx, |this, cx| {
                let original = this.shared.borrow().processes[0].identity.clone();
                let other = this.shared.borrow().processes[1].identity.clone();
                this.prepare_process_action(original.clone(), ProcessSignal::Kill, cx);
                this.shared.borrow_mut().process_action.busy = true;
                this.shared.borrow_mut().process_action.notice =
                    "Awaiting Windows authorization".into();
                this.selected = Some(other.clone());
                this.prepare_process_action(other, ProcessSignal::Terminate, cx);
                this.confirm_process_action(cx);
                this.confirm_process_action(cx);
                assert!(this.shared.borrow().process_action.busy);
                assert_eq!(
                    this.shared.borrow().process_action.notice,
                    "Awaiting Windows authorization"
                );
                let confirmation = this.process_state.confirmation.as_ref().unwrap();
                assert_eq!(confirmation.0, original);
                assert_eq!(confirmation.2, ProcessSignal::Kill);
            });
        });
        draw(cx);
        // The table still handles navigation while authorization is pending.
        native_key("down", cx);
        draw(cx);
        assert!(cx.read(|cx| processes.read(cx).selected.is_some()));
    }

    #[test]
    fn completion_releases_busy_state_without_claiming_unobserved_exit() {
        use super::ProcessActionState;
        use system_pulse_collectors::process_control::ProcessActionOutcome;
        for (outcome, expected) in [
            (
                ProcessActionOutcome::SignalSent,
                "Waiting for the process list",
            ),
            (
                ProcessActionOutcome::CloseRequested,
                "exit has not been confirmed",
            ),
            (
                ProcessActionOutcome::TerminationPending,
                "exit is still pending",
            ),
            (ProcessActionOutcome::ExitObserved, "has exited"),
        ] {
            let mut state = ProcessActionState {
                busy: true,
                ..Default::default()
            };
            state.finish_action("owned target", 4242, Ok(outcome));
            assert!(!state.busy);
            assert!(state.notice.contains("owned target (PID 4242)"));
            assert!(state.notice.contains(expected));
            assert_eq!(
                state.notice.contains("has exited"),
                outcome == ProcessActionOutcome::ExitObserved
            );
        }
        let mut state = ProcessActionState {
            busy: true,
            ..Default::default()
        };
        state.finish_action(
            "owned target",
            4242,
            Err("Unknown outcome; check the process list".into()),
        );
        assert!(!state.busy);
        assert_eq!(state.notice, "Unknown outcome; check the process list");
    }

    #[gpui_kit::test]
    fn recreated_process_panel_cannot_resubmit_an_inflight_action(cx: &mut TestAppContext) {
        let (view, cx) = harness(cx);
        let processes = panel(&view, "processes", cx);
        cx.update(|_, cx| {
            let (monitor, shared) = processes.update(cx, |this, _| {
                this.shared.borrow_mut().process_action.busy = true;
                this.shared.borrow_mut().process_action.notice = "Awaiting authorization".into();
                (this.monitor.clone(), this.shared.clone())
            });
            let replacement = cx.new(|cx| MonitorPanel::new_standalone(monitor, shared, cx));
            replacement.update(cx, |this, cx| {
                let identity = this.shared.borrow().processes[0].identity.clone();
                this.prepare_process_action(identity, ProcessSignal::Kill, cx);
                assert!(this.process_state.confirmation.is_none());
                assert!(this.shared.borrow().process_action.busy);
                assert_eq!(
                    this.shared.borrow().process_action.notice,
                    "Awaiting authorization"
                );
            });
            processes.update(cx, |this, _| {
                this.shared.borrow_mut().process_action.finish_action(
                    "original target",
                    4242,
                    Err("Authorization cancelled".into()),
                );
            });
            replacement.update(cx, |this, _| {
                assert!(!this.shared.borrow().process_action.busy);
                assert_eq!(
                    this.shared.borrow().process_action.notice,
                    "Authorization cancelled"
                );
                assert!(this.process_state.confirmation.is_none());
            });
        });
    }
}
