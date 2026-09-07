//! Process table interaction, keeping canonical snapshots separate from the visible order.
use super::*;
use crate::processes::{self, ProcessSort};
use gpui_component::{
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
    busy: bool,
    notice: String,
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
        if self.process_state.busy {
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
            self.process_state.notice.clear();
        } else {
            self.process_state.confirmation = None;
            self.process_state.notice = "This process has exited. Select another process.".into();
        }
        cx.notify();
    }

    fn confirm_process_action(&mut self, cx: &mut Context<Self>) {
        if self.process_state.busy {
            return;
        }
        let Some((identity, name, signal)) = self.process_state.confirmation.take() else {
            return;
        };
        // Fixtures can never dispatch an OS operation, even when a PID happens to match.
        if !self.shared.borrow().allow_process_actions || self.shared.borrow().snapshot.is_none() {
            self.process_state.notice = "Process actions require a live system snapshot.".into();
            cx.notify();
            return;
        }
        self.process_state.busy = true;
        self.process_state.notice = format!("Sending request to {name} (PID {})…", identity.pid);
        cx.spawn(async move |weak, cx| {
            let pid = identity.pid;
            let result = smol::unblock(move || process_control::send_signal(&identity, signal)).await;
            let _ = weak.update(cx, |this, cx| {
                this.process_state.busy = false;
                this.process_state.notice = match result {
                    Ok(()) => format!("Request sent to {name} (PID {pid}). Waiting for the process list to update."),
                    Err(error) => error,
                };
                cx.notify();
            });
        }).detach();
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
                        .flex_1()
                        .min_w_0()
                        .child(Input::new(self.process_state.input.as_ref().unwrap()).small()),
                )
                .children(
                    [
                        ("end-task", "End task…", ProcessSignal::Terminate),
                        ("force-quit", "Force quit…", ProcessSignal::Kill),
                    ]
                    .into_iter()
                    .map(|(id, label, signal)| {
                        Button::new(id)
                            .small()
                            .ghost()
                            .label(label)
                            .disabled(self.selected.is_none() || self.process_state.busy)
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
            toolbar = toolbar.child(
                div()
                    .flex()
                    .flex_wrap()
                    .items_center()
                    .gap_2()
                    .p_2()
                    .bg(cx.theme().muted)
                    .child(format!(
                        "{} {name} (PID {})?{}",
                        if force { "Force quit" } else { "End" },
                        identity.pid,
                        if force {
                            " Unsaved work may be lost."
                        } else {
                            " The process will receive a termination request."
                        }
                    ))
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
        if !self.process_state.notice.is_empty() {
            toolbar = toolbar.child(
                div()
                    .id("process-action-status")
                    .p_1()
                    .role(Role::Status)
                    .accessibility_id("process-action-status")
                    .aria_label(self.process_state.notice.clone())
                    .child(self.process_state.notice.clone()),
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

    pub(super) fn process_table(
        &mut self,
        window: &mut Window,
        cx: &mut Context<Self>,
    ) -> AnyElement {
        let toolbar = self.process_toolbar(window, cx);
        let rows = Rc::new(self.process_projection());
        // Snapshot delivery may reorder rows after a key but before layout.
        // Consume the intent even when reconciliation cleared the selection.
        if std::mem::take(&mut self.process_reveal_pending)
            && let Some(index) = self.visible_selected_index(&rows)
        {
            self.table_scroll.scroll_to_item(index, ScrollStrategy::Top);
        }
        let handle = self.controls["table"].handle.clone();
        let ring = cx.theme().ring;
        let count = rows.len();
        let widths = self.shared.borrow().process_widths;
        let width: f32 = widths.iter().sum();
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
                        Some(
                            process_row(
                                process,
                                index,
                                this.selected.as_ref() == Some(&process.identity),
                                &data.process_widths,
                                cx,
                            )
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
                controls::reveal(this.table_scroll.base_handle().bounds().dilate(px(1.)), &this.shared.borrow().scroll);
                this.request_keyboard_repaint(window, cx); cx.stop_propagation();
            }))
            .on_prepaint(move |bounds, window, _| {
                if focus.entered(window) { controls::reveal(bounds.dilate(px(1.)), &outer); window.refresh(); }
            })
            .child(div().id("process-horizontal").size_full().overflow_x_scroll().track_scroll(&horizontal)
                .child(Table::new("process-table").row_count(count + 1).column_count(8)
                    .accessibility_label(format!("{count} readable process rows; arrows navigate and scroll columns; Tab leaves table"))
                    .w(px(width)).h_full().flex().flex_col()
                    .child(TableRow::new("process-columns", 1).flex().h_7().flex_none()
                        .children(live::PROCESS_COLUMNS.iter().enumerate().map(|(column, title)| {
                            TableCell::new(("process-heading", column), column + 1).role(Role::ColumnHeader)
                                .aria_label(format!("Sort by {title}")).w(px(widths[column])).flex_none()
                                .child(Button::new(("sort-process", column)).accessibility_label(format!("Sort by {title}")).ghost().small()
                                    .child(div().debug_selector(move || format!("process-sort:{column}").into()).child(format!("{title}{}", if self.process_state.sort.column == column {
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
    use gpui::{Entity, Modifiers, TestAppContext, VisualTestContext, point, px};

    fn focus_table(processes: &Entity<MonitorPanel>, cx: &mut VisualTestContext) {
        cx.update(|window, cx| {
            processes.read(cx).controls["table"]
                .handle
                .clone()
                .focus(window, cx)
        });
        draw(cx);
    }

    #[gpui::test]
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

    #[gpui::test]
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
            let state = &processes.read(cx).process_state;
            assert!(state.confirmation.is_none());
            assert!(!state.busy);
            assert!(state.notice.is_empty());
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
            let state = &processes.read(cx).process_state;
            assert!(!state.busy);
            assert!(state.confirmation.is_none());
            assert_eq!(
                state.notice,
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
                .process_state
                .notice
                .contains("has exited")
        }));
    }
}
