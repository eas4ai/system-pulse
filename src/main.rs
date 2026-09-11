mod application;

fn main() {
    #[cfg(target_os = "windows")]
    if let Some(code) = system_pulse_collectors::windows_thermal::helper_entry(std::env::args_os())
    {
        std::process::exit(code);
    }
    if let Some(code) =
        system_pulse_collectors::process_control::helper_entry(std::env::args_os().skip(1))
    {
        std::process::exit(code);
    }
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
