use crate::Workspace;
use serde_json::Value;

/// Shared byte limit for serialized workspace and preset configurations.
/// The 451-panel retained-catalog regression is about 1.5 MiB; 16 MiB leaves
/// headroom for multiple generations without capping or truncating devices.
/// Diagnostic snapshots have a separate latest-record bound and do not use this.
pub const MAX_CONFIGURATION_BYTES: usize = 16 * 1024 * 1024;

pub fn validate_configuration_size(bytes: usize) -> Result<(), String> {
    if bytes > MAX_CONFIGURATION_BYTES {
        Err(format!(
            "Saved state is {bytes} bytes and exceeds the {} MiB configuration limit",
            MAX_CONFIGURATION_BYTES / (1024 * 1024)
        ))
    } else {
        Ok(())
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RejectedInput {
    pub original: String,
    pub error: String,
}

#[derive(Debug)]
pub struct Session {
    pub workspace: Workspace,
    pub rejected: Option<RejectedInput>,
}

impl Session {
    /// The UI supplies a known-valid default split arrangement and dock validator.
    pub fn restore(
        raw: &str,
        fallback: Workspace,
        validate_dock: impl Fn(&Value) -> Result<(), String>,
    ) -> Self {
        let restored = validate_configuration_size(raw.len())
            .and_then(|_| {
                serde_json::from_str::<Workspace>(raw)
                    .map_err(|error| format!("Cannot read saved workspace: {error}"))
            })
            .and_then(|workspace| {
                workspace.validate()?;
                validate_dock(&workspace.dock)?;
                Ok(workspace)
            });
        match restored {
            Ok(workspace) => Self {
                workspace,
                rejected: None,
            },
            Err(error) => Self {
                workspace: fallback,
                rejected: Some(RejectedInput {
                    original: raw.to_owned(),
                    error,
                }),
            },
        }
    }

    pub fn autosave_json(&self) -> Result<String, String> {
        if self.rejected.is_some() {
            return Err(
                "Autosave is blocked until explicit recovery of the saved workspace".into(),
            );
        }
        self.workspace.validate()?;
        let json =
            serde_json::to_string_pretty(&self.workspace).map_err(|error| error.to_string())?;
        validate_configuration_size(json.len())?;
        Ok(json)
    }

    /// Called only by the UI's explicit recovery action, never an autosave timer.
    pub fn accept_recovery(&mut self) {
        self.rejected = None;
    }
}
