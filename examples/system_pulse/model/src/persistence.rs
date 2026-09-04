use crate::Workspace;
use serde_json::Value;

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
        let restored = serde_json::from_str::<Workspace>(raw)
            .map_err(|error| format!("Cannot read saved workspace: {error}"))
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
        serde_json::to_string_pretty(&self.workspace).map_err(|error| error.to_string())
    }

    /// Called only by the UI's explicit recovery action, never an autosave timer.
    pub fn accept_recovery(&mut self) {
        self.rejected = None;
    }
}
