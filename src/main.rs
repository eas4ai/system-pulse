use gpui::*;
use gpui_component::{ActiveTheme, Root};
use system_pulse::workspace::WorkspaceView;

mod application;

fn main() {
    application::with_application(|app| {
        app.with_assets(gpui_component_assets::Assets).run(|cx| {
            gpui_component::init(cx);
            if let Err(error) = system_pulse::install_assets(cx) {
                eprintln!("{error}");
                cx.quit();
                return;
            }
            cx.on_window_closed(|cx, _| {
                if cx.windows().is_empty() {
                    cx.quit();
                }
            })
            .detach();
            let bounds = Bounds::centered(None, size(px(1280.), px(880.)), cx);
            cx.spawn(async move |cx| {
                let opened = cx.open_window(
                    WindowOptions {
                        window_bounds: Some(WindowBounds::Windowed(bounds)),
                        window_min_size: Some(size(px(960.), px(640.))),
                        ..WindowOptions::default()
                    },
                    |window, cx| {
                        window.set_window_title("System Pulse");
                        window.set_app_id("org.systempulse.SystemPulse");
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
