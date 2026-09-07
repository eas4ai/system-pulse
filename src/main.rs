mod application;

fn main() {
    application::with_application(|app| {
        app.with_assets(gpui_kit::assets::Assets).run(|cx| {
            gpui_kit::init(cx);
            if let Err(error) = system_pulse::install_assets(cx) {
                eprintln!("{error}");
                cx.quit();
                return;
            }
            system_pulse::tray::start(cx);
        })
    });
}
