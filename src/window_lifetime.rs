//! Keep the single sampler and its history alive independently of native windows.
use super::*;

impl WorkspaceView {
    pub(crate) fn detach_window(&mut self, cx: &mut Context<Self>) {
        self.capture_sizes(cx);
        self.record(cx);
        self.queue_save(cx);
        self.attached_window = None;
        self.screen_view = None;
        let mut data = self.shared.borrow_mut();
        data.views.clear();
        data.bounds.clear();
    }

    pub(crate) fn attach_window(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        self.shared.borrow_mut().scroll = ScrollHandle::default();
        crate::settings::apply(
            self.shared.borrow().session.workspace.appearance,
            window,
            cx,
        );
        self.dock = Self::create_dock(&self.shared, window, cx);
        self.attached_window = Some(window.window_handle());
        self.keyboard_repaint_pending = false;
        cx.notify();
    }

    pub(super) fn create_dock(
        shared: &Shared,
        window: &mut Window,
        cx: &mut Context<Self>,
    ) -> Entity<DockArea> {
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
        ensure_enabled_regions(shared, &dock, window, cx);
        cx.subscribe_in(&dock, window, |this, _, event, _, cx| {
            if matches!(event, DockEvent::LayoutChanged) {
                this.record(cx);
                this.queue_save(cx);
                cx.notify();
            }
        })
        .detach();
        dock
    }

    pub(super) fn sampling_timer(cx: &mut Context<Self>) -> Task<()> {
        cx.spawn(async move |weak, cx| {
            loop {
                cx.background_executor()
                    .timer(Duration::from_millis(100))
                    .await;
                let Ok(window) = weak.read_with(cx, |this, _| this.attached_window) else {
                    break;
                };
                if let Some(window) = window {
                    if window
                        .update(cx, |_, window, cx| {
                            weak.update(cx, |this, cx| this.deliver(window, cx))
                        })
                        .is_err()
                    {
                        // A native close may race this tick. Retain collection and
                        // let the app's window-close handler finish detaching.
                        let _ = weak.update(cx, |this, _| this.attached_window = None);
                    }
                } else if weak
                    .update(cx, |this, cx| this.deliver_optional(None, cx))
                    .is_err()
                {
                    break;
                }
            }
        })
    }
}
