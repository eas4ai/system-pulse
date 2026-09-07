//! Native tray lifetime and the retained System Pulse dashboard.
mod icon;

use crate::screens::ApplicationView;
use gpui_kit::component::{ActiveTheme, Root};
use gpui_kit::*;
use gpui_tray::{Icon, Tray};
use std::time::Duration;

actions!(system_pulse_tray, [OpenSystemPulse, QuitSystemPulse]);

struct Desktop {
    view: Option<Entity<ApplicationView>>,
    window: Option<AnyWindowHandle>,
    tray: Option<Tray>,
    frame: Option<icon::Frame>,
    timer: Option<Task<()>>,
    quitting: bool,
}
impl Global for Desktop {}

/// Install one CPU tray icon and open the dashboard.
pub fn start(cx: &mut App) {
    cx.set_quit_mode(QuitMode::Explicit);
    cx.set_global(Desktop {
        view: None,
        window: None,
        tray: None,
        frame: None,
        timer: None,
        quitting: false,
    });
    cx.on_action(|_: &OpenSystemPulse, cx| open(cx));
    cx.on_action(|_: &QuitSystemPulse, cx| {
        cx.global_mut::<Desktop>().quitting = true;
        cx.quit();
    });
    let frame = icon::render(&[]);
    let tray = Icon::from_rgba(frame.pixels.clone(), icon::SIZE as u32, icon::SIZE as u32)
        .and_then(|icon| {
            Tray::builder()
                .icon(icon)
                .title("System Pulse")
                .tooltip(frame.tooltip.clone())
                .on_activate(OpenSystemPulse)
                .menu(|_| {
                    vec![
                        MenuItem::action("Open System Pulse", OpenSystemPulse),
                        MenuItem::separator(),
                        MenuItem::action("Quit", QuitSystemPulse),
                    ]
                })
                .build(cx)
        });
    match tray {
        Ok(tray) => {
            cx.global_mut::<Desktop>().tray = Some(tray);
            cx.global_mut::<Desktop>().frame = Some(frame);
        }
        Err(error) => eprintln!("System Pulse tray unavailable: {error}"),
    }
    cx.on_window_closed(|cx, _| {
        if !cx.windows().is_empty() {
            return;
        }
        let view = cx.global::<Desktop>().view.clone();
        if let Some(view) = view {
            view.update(cx, |view, cx| view.detach_window(cx));
        }
        cx.global_mut::<Desktop>().window = None;
        if cx.global::<Desktop>().quitting || !available(cx) {
            cx.quit();
        }
    })
    .detach();
    cx.on_app_quit(|cx| {
        let state = cx.global_mut::<Desktop>();
        state.quitting = true;
        state.timer.take();
        let tray = state.tray.take();
        if let Some(tray) = tray
            && let Err(error) = tray.close(cx)
        {
            eprintln!("Close System Pulse tray: {error}");
        }
        async {}
    })
    .detach();
    let timer = cx.spawn(async move |cx| {
        loop {
            cx.background_executor()
                .timer(Duration::from_millis(250))
                .await;
            cx.update(refresh);
        }
    });
    cx.global_mut::<Desktop>().timer = Some(timer);
    open(cx);
}

fn available(cx: &App) -> bool {
    cx.global::<Desktop>()
        .tray
        .as_ref()
        .is_some_and(Tray::is_available)
}

fn open(cx: &mut App) {
    if cx.global::<Desktop>().quitting {
        return;
    }
    if let Some(window) = cx.global::<Desktop>().window
        && window
            .update(cx, |_, window, _| window.activate_window())
            .is_ok()
    {
        return;
    }
    let bounds = Bounds::centered(None, size(px(1280.), px(880.)), cx);
    let opened = cx.open_window(
        WindowOptions {
            window_bounds: Some(WindowBounds::Windowed(bounds)),
            window_min_size: Some(size(px(960.), px(640.))),
            ..WindowOptions::default()
        },
        |window, cx| {
            window.set_window_title("System Pulse");
            window.set_app_id("org.systempulse.SystemPulse");
            let view = match cx.global::<Desktop>().view.clone() {
                Some(view) => {
                    view.update(cx, |view, cx| view.attach_window(window, cx));
                    view
                }
                None => cx.new(|cx| ApplicationView::new(window, cx)),
            };
            cx.global_mut::<Desktop>().view = Some(view.clone());
            cx.new(|cx| Root::new(view, window, cx).bg(cx.theme().background))
        },
    );
    match opened {
        Ok(window) => cx.global_mut::<Desktop>().window = Some(window.into()),
        Err(error) => {
            eprintln!("Open System Pulse: {error}");
            if !available(cx) {
                cx.quit();
            }
        }
    }
}

fn refresh(cx: &mut App) {
    if cx.global::<Desktop>().quitting {
        return;
    }
    if cx.global::<Desktop>().window.is_none() && !available(cx) {
        // A shell restart or removed tray host must not strand a background app.
        open(cx);
    }
    let (Some(view), Some(tray)) = (
        cx.global::<Desktop>().view.clone(),
        cx.global::<Desktop>().tray.clone(),
    ) else {
        return;
    };
    let frame = icon::render(&view.read(cx).cpu_samples(cx));
    if cx.global::<Desktop>().frame.as_ref() == Some(&frame) {
        return;
    }
    let result = Icon::from_rgba(frame.pixels.clone(), icon::SIZE as u32, icon::SIZE as u32)
        .and_then(|icon| tray.set_icon(Some(icon), cx))
        .and_then(|_| tray.set_tooltip(Some(frame.tooltip.clone()), cx));
    match result {
        Ok(()) => cx.global_mut::<Desktop>().frame = Some(frame),
        Err(error) => {
            eprintln!("Update System Pulse tray: {error}");
            cx.global_mut::<Desktop>().tray = None;
            if let Err(error) = tray.close(cx) {
                eprintln!("Close failed tray: {error}");
            }
            if cx.global::<Desktop>().window.is_none() {
                open(cx);
            }
        }
    }
}
