//! Curated, portable appearance choices. Unknown saved choices are rejected.
use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ColorTheme {
    #[default]
    Dark,
    Light,
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum UiFont {
    #[default]
    Inter,
    IbmPlexSans,
}
impl UiFont {
    pub fn family(self) -> &'static str {
        match self {
            Self::Inter => "Inter Variable",
            Self::IbmPlexSans => "IBM Plex Sans",
        }
    }
    pub fn label(self) -> &'static str {
        match self {
            Self::Inter => "Inter",
            Self::IbmPlexSans => "IBM Plex Sans",
        }
    }
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum NumericFont {
    #[default]
    JetbrainsMono,
    IbmPlexMono,
}
impl NumericFont {
    pub fn family(self) -> &'static str {
        match self {
            Self::JetbrainsMono => "JetBrains Mono",
            Self::IbmPlexMono => "IBM Plex Mono",
        }
    }
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(default)]
pub struct Appearance {
    pub theme: ColorTheme,
    pub ui_font: UiFont,
    pub numeric_font: NumericFont,
}

#[cfg(test)]
mod tests {
    use crate::Workspace;
    #[test]
    fn legacy_workspace_receives_complete_appearance_defaults() {
        let workspace: Workspace = serde_json::from_str(r#"{"dock":{}}"#).unwrap();
        let value = serde_json::to_value(workspace).unwrap();
        assert_eq!(
            value["appearance"],
            serde_json::json!({"theme":"dark", "ui_font":"inter", "numeric_font":"jetbrains_mono"})
        );
    }
    #[test]
    fn appearance_roundtrips_and_unknown_choices_are_rejected() {
        let raw = serde_json::json!({"dock":{}, "appearance":{"theme":"light", "ui_font":"ibm_plex_sans", "numeric_font":"ibm_plex_mono"}});
        let workspace: Workspace = serde_json::from_value(raw.clone()).unwrap();
        assert_eq!(
            serde_json::to_value(workspace).unwrap()["appearance"],
            raw["appearance"]
        );
        let mut invalid = raw;
        invalid["appearance"]["ui_font"] = "unbundled-font".into();
        assert!(serde_json::from_value::<Workspace>(invalid).is_err());
    }
}
