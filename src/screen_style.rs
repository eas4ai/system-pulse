use gpui_kit::component::ActiveTheme;
use gpui_kit::*;
use system_pulse_model::Screen;

#[derive(Clone, Copy)]
pub(crate) struct Palette {
    pub background: Hsla,
    pub surface: Hsla,
    pub raised: Hsla,
    pub border: Hsla,
    pub text: Hsla,
    pub muted: Hsla,
    pub selected: Hsla,
}

pub(crate) fn palette(cx: &App) -> Palette {
    if cx.theme().is_dark() {
        Palette {
            background: rgb(0x242523).into(),
            surface: rgb(0x1f201e).into(),
            raised: rgb(0x2c2d2a).into(),
            border: rgb(0x42443e).into(),
            text: rgb(0xe2e4df).into(),
            muted: rgb(0xa4a79e).into(),
            selected: rgb(0x303b54).into(),
        }
    } else {
        Palette {
            background: rgb(0xf3f4f1).into(),
            surface: rgb(0xffffff).into(),
            raised: rgb(0xe6e9e1).into(),
            border: rgb(0xcbd0c5).into(),
            text: rgb(0x252923).into(),
            muted: rgb(0x596252).into(),
            selected: rgb(0xdce8f7).into(),
        }
    }
}

pub(crate) fn accent(screen: Screen, cx: &App) -> Hsla {
    let dark = cx.theme().is_dark();
    rgb(match screen {
        Screen::Cpu | Screen::Disks => {
            if dark {
                0x87c966
            } else {
                0x437d2c
            }
        }
        Screen::Memory => {
            if dark {
                0xb764e8
            } else {
                0x8535b8
            }
        }
        Screen::Energy => {
            if dark {
                0xe8d64b
            } else {
                0x887000
            }
        }
        Screen::Thermals => {
            if dark {
                0xe6a54a
            } else {
                0x9c5d15
            }
        }
        _ => {
            if dark {
                0x6aacf0
            } else {
                0x326ead
            }
        }
    })
    .into()
}

pub(crate) fn heading(text: impl Into<SharedString>, size: f32, cx: &App) -> Div {
    div()
        .text_size(px(size * 0.86))
        .font_family("Michroma")
        .font_weight(FontWeight::MEDIUM)
        .text_color(palette(cx).text)
        .child(text.into())
}

pub(crate) fn section(cx: &App) -> Div {
    let colors = palette(cx);
    div()
        .flex()
        .flex_col()
        .gap_3()
        .p_3()
        .rounded(px(8.))
        .border_1()
        .border_color(colors.border)
        .bg(colors.surface)
        .min_w_0()
}

pub(crate) fn empty(title: &str, detail: &str, cx: &App) -> AnyElement {
    section(cx)
        .min_h(px(180.))
        .justify_center()
        .child(heading(title.to_owned(), 22., cx))
        .child(
            div()
                .text_sm()
                .text_color(palette(cx).muted)
                .child(detail.to_owned()),
        )
        .into_any_element()
}
