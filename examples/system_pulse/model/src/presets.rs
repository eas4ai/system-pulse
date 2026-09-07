use crate::Workspace;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct PresetLibrary {
    pub schema_version: u32,
    pub presets: BTreeMap<String, Workspace>,
}
impl Default for PresetLibrary {
    fn default() -> Self {
        Self {
            schema_version: 1,
            presets: BTreeMap::new(),
        }
    }
}
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum BuiltinPreset {
    Default,
    Minimal,
    GpuFocus,
    Developer,
}
impl BuiltinPreset {
    pub const ALL: [Self; 4] = [
        Self::Default,
        Self::Minimal,
        Self::GpuFocus,
        Self::Developer,
    ];
    pub fn name(self) -> &'static str {
        match self {
            Self::Default => "Default",
            Self::Minimal => "Minimal",
            Self::GpuFocus => "GPU Focus",
            Self::Developer => "Developer",
        }
    }
}

fn name(value: &str) -> Result<String, String> {
    let value = value.trim();
    if value.is_empty() || value.chars().count() > 64 || value.chars().any(char::is_control) {
        return Err("Use a preset name of 1–64 characters without control characters".into());
    }
    if BuiltinPreset::ALL
        .into_iter()
        .any(|builtin| builtin.name().eq_ignore_ascii_case(value))
    {
        return Err("Built-in presets are protected; choose a different name".into());
    }
    Ok(value.to_owned())
}

impl PresetLibrary {
    fn key(&self, value: &str) -> Option<String> {
        let folded = value.trim().to_lowercase();
        self.presets
            .keys()
            .find(|name| name.to_lowercase() == folded)
            .cloned()
    }
    pub fn create(&mut self, value: &str, workspace: Workspace) -> Result<(), String> {
        let name = name(value)?;
        if self.key(&name).is_some() {
            return Err(
                "A preset with that name already exists; use Overwrite to replace it".into(),
            );
        }
        if self.presets.len() >= 100 {
            return Err("The preset library is full (100 presets)".into());
        }
        workspace.validate()?;
        self.presets.insert(name, workspace);
        Ok(())
    }
    pub fn overwrite(&mut self, value: &str, workspace: Workspace) -> Result<(), String> {
        name(value)?;
        let key = self.key(value).ok_or("The preset no longer exists")?;
        workspace.validate()?;
        self.presets.insert(key, workspace);
        Ok(())
    }
    pub fn rename(&mut self, from: &str, to: &str) -> Result<(), String> {
        name(from)?;
        let from = self.key(from).ok_or("The preset no longer exists")?;
        let to = name(to)?;
        if self.key(&to).is_some_and(|key| key != from) {
            return Err("A preset with that name already exists".into());
        }
        let workspace = self.presets.remove(&from).expect("validated key exists");
        self.presets.insert(to, workspace);
        Ok(())
    }
    pub fn remove(&mut self, value: &str) -> Result<(), String> {
        name(value)?;
        let key = self.key(value).ok_or("The preset no longer exists")?;
        self.presets.remove(&key);
        Ok(())
    }
    pub fn get(&self, value: &str) -> Option<&Workspace> {
        self.key(value).and_then(|key| self.presets.get(&key))
    }
    pub fn validate(&self) -> Result<(), String> {
        if self.schema_version != 1 {
            return Err("Unsupported preset library version".into());
        }
        if self.presets.len() > 100 {
            return Err("The preset library exceeds 100 presets".into());
        }
        let mut seen = std::collections::BTreeSet::new();
        for (key, workspace) in &self.presets {
            if name(key)? != *key || !seen.insert(key.to_lowercase()) {
                return Err("Duplicate or noncanonical preset name".into());
            }
            workspace.validate()?;
        }
        Ok(())
    }
    pub fn from_json(raw: &str) -> Result<Self, String> {
        crate::validate_configuration_size(raw.len())?;
        let library: Self =
            serde_json::from_str(raw).map_err(|error| format!("Read preset library: {error}"))?;
        library.validate()?;
        Ok(library)
    }
    pub fn to_json(&self) -> Result<String, String> {
        self.validate()?;
        let raw = serde_json::to_string_pretty(self).map_err(|error| error.to_string())?;
        crate::validate_configuration_size(raw.len())?;
        Ok(raw)
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn named_presets_keep_independent_workspace_choices() {
        let mut library = PresetLibrary::default();
        let mut workspace = Workspace::new(serde_json::json!({}));
        workspace.interval_ms = 2000;
        library.create("Work", workspace.clone()).unwrap();
        workspace.interval_ms = 5000;
        library.create("Quiet", workspace.clone()).unwrap();
        assert_eq!(library.presets["Work"].interval_ms, 2000);
        assert_eq!(library.presets["Quiet"].interval_ms, 5000);
    }
}

#[cfg(test)]
mod mutation_tests {
    use super::*;
    fn workspace() -> Workspace {
        Workspace::new(serde_json::json!({}))
    }
    #[test]
    fn explicit_crud_roundtrips_without_changing_other_presets() {
        let mut library = PresetLibrary::default();
        library.create("Work", workspace()).unwrap();
        library.create("Quiet", workspace()).unwrap();
        let original = library.clone();
        assert!(library.create(" work ", workspace()).is_err());
        assert!(library.rename("Work", "QUIET").is_err());
        assert_eq!(library, original);
        let mut changed = workspace();
        changed.interval_ms = 5000;
        changed.appearance.theme = crate::ColorTheme::Light;
        changed.panel_mut("cpu:host").collapsed = true;
        library.overwrite("work", changed.clone()).unwrap();
        library.rename("Work", "Coding").unwrap();
        assert!(library.get("Work").is_none());
        assert_eq!(library.get("coding"), Some(&changed));
        assert_eq!(library.get("Quiet"), Some(&workspace()));
        let raw = library.to_json().unwrap();
        assert_eq!(PresetLibrary::from_json(&raw).unwrap(), library);
        library.remove("Coding").unwrap();
        assert_eq!(library.presets.len(), 1);
    }
    #[test]
    fn builtins_invalid_names_and_invalid_workspaces_cannot_mutate_library() {
        let mut library = PresetLibrary::default();
        for invalid in [
            "",
            "  ",
            "a\nb",
            "Default",
            "minimal",
            "GPU Focus",
            "Developer",
        ] {
            assert!(library.create(invalid, workspace()).is_err());
            assert!(library.remove(invalid).is_err());
            assert!(library.overwrite(invalid, workspace()).is_err());
        }
        assert!(library.create(&"a".repeat(65), workspace()).is_err());
        let mut invalid = workspace();
        invalid.interval_ms = 13;
        assert!(library.create("Invalid", invalid).is_err());
        assert!(library.presets.is_empty());
    }
    #[test]
    fn malformed_future_and_ambiguous_libraries_are_rejected() {
        assert!(PresetLibrary::from_json("invalid").is_err());
        assert!(PresetLibrary::from_json(r#"{"schema_version":2,"presets":{}}"#).is_err());
        let mut library = PresetLibrary::default();
        library.presets.insert("Work".into(), workspace());
        library.presets.insert("work".into(), workspace());
        assert!(library.to_json().is_err());
    }
}
