//! Fonts are embedded so an installed application never reads from the checkout.
use std::borrow::Cow;

const FONTS: [&[u8]; 4] = [
    include_bytes!("../assets/fonts/Inter-Regular.ttf"),
    include_bytes!("../assets/fonts/IBMPlexSans-Regular.ttf"),
    include_bytes!("../assets/fonts/JetBrainsMono-Regular.ttf"),
    include_bytes!("../assets/fonts/IBMPlexMono-Regular.ttf"),
];

pub fn install(cx: &mut gpui::App) -> Result<(), String> {
    cx.text_system()
        .add_fonts(FONTS.into_iter().map(Cow::Borrowed).collect())
        .map_err(|error| format!("Load bundled fonts: {error}"))
}

#[cfg(test)]
mod tests {
    #[test]
    fn every_bundled_choice_has_font_bytes_and_license_notices() {
        for font in super::FONTS {
            assert!(font.len() > 1000);
            assert_eq!(&font[..4], &[0, 1, 0, 0]);
        }
        for license in [
            include_str!("../assets/fonts/IBM-Plex-LICENSE.txt"),
            include_str!("../assets/fonts/Inter-JetBrainsMono-OFL.txt"),
        ] {
            assert!(license.contains("SIL OPEN FONT LICENSE"));
        }
    }
}
