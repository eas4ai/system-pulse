use gpui::*;
use gpui_component::{ActiveTheme, Root};
use system_pulse::workspace::WorkspaceView;

mod application;

fn main() {
    application::with_application(|app| {
        app.run(|cx| {
            gpui_component::init(cx);
            cx.on_window_closed(|cx, _| {
                if cx.windows().is_empty() {
                    cx.quit();
                }
            })
            .detach();
            cx.spawn(async move |cx| {
                let opened = cx.open_window(
                    WindowOptions {
                        window_min_size: Some(size(px(960.), px(640.))),
                        ..WindowOptions::default()
                    },
                    |window, cx| {
                        window.set_window_title("System Pulse");
                        let view = cx.new(|cx| WorkspaceView::new(window, cx));
                        cx.new(|cx| Root::new(view, window, cx).bg(cx.theme().background))
                    },
                );
                if let Err(error) = opened {
                    eprintln!("Open System Pulse: {error}");
                }
            })
            .detach();
        })
    });
}
