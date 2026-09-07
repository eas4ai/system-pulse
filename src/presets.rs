//! Preset transactions and legacy import. Publish mutations only after durable save.
use super::*;
use system_pulse_model::{BuiltinPreset, PresetLibrary};

#[path = "preset_manager.rs"]
mod manager;
pub(crate) use manager::PresetManager;

#[derive(Clone)]
pub(crate) enum PresetCommand {
    Create(String),
    Overwrite(String),
    Rename(String, String),
    Delete(String),
    Recall(String),
    Builtin(BuiltinPreset),
}

pub(crate) fn load(
    directory: Option<&std::path::Path>,
    legacy: Option<&str>,
    fixture_mode: bool,
) -> (PresetLibrary, Option<String>) {
    let loaded = (|| {
        if let Some(directory) = directory
            && let Some(raw) = storage::read(&directory.join("presets.json"))?
        {
            let library = PresetLibrary::from_json(&raw)?;
            for workspace in library.presets.values() {
                validate_dock_mode(&workspace.dock, fixture_mode)?;
            }
            return Ok(library);
        }
        let mut library = PresetLibrary::default();
        if let Some(raw) = legacy {
            let fallback = Workspace::new(
                serde_json::to_value(default_dock_for(&initial_catalog(fixture_mode)))
                    .expect("default serializes"),
            );
            let session = restore_session(raw, fallback, fixture_mode);
            if let Some(rejected) = session.rejected {
                return Err(format!("Legacy preset was preserved: {}", rejected.error));
            }
            library.create("Imported preset", session.workspace)?;
        }
        Ok(library)
    })();
    match loaded {
        Ok(library) => (library, None),
        Err(error) => (
            PresetLibrary::default(),
            Some(format!(
                "Preset library could not be read. The original file is untouched; fix it and restart before saving presets. {error}"
            )),
        ),
    }
}

impl WorkspaceView {
    pub(crate) fn preset_command(
        &mut self,
        command: PresetCommand,
        window: &mut Window,
        cx: &mut Context<Self>,
    ) {
        if self.shared.borrow().preset_busy {
            return;
        }
        match &command {
            PresetCommand::Recall(name) => {
                let workspace = self.shared.borrow().presets.get(name).cloned();
                if let Some(workspace) = workspace {
                    match serde_json::to_string(&workspace) {
                        Ok(raw) => {
                            self.restore(&raw, window, cx);
                            self.record(cx);
                            self.queue_save(cx);
                        }
                        Err(error) => self.shared.borrow_mut().preset_notice = error.to_string(),
                    }
                } else {
                    self.shared.borrow_mut().preset_notice = "This preset no longer exists".into();
                }
                self.notify_panels(cx);
                return;
            }
            PresetCommand::Builtin(kind) => {
                let catalog = self.shared.borrow().catalog.clone();
                let workspace = crate::layout::preset(*kind, &catalog);
                self.restore(
                    &serde_json::to_string(&workspace).expect("built-in serializes"),
                    window,
                    cx,
                );
                self.record(cx);
                self.queue_save(cx);
                self.notify_panels(cx);
                return;
            }
            _ => {}
        }
        if self.read_blocked || self.shared.borrow().preset_error.is_some() {
            self.shared.borrow_mut().preset_notice =
                "Preset writes are blocked until the saved-state read error is corrected".into();
            self.notify_panels(cx);
            return;
        }
        self.record(cx);
        let prepared = (|| {
            let data = self.shared.borrow();
            // Preserve the existing rejected-workspace guard for every preset mutation.
            if data.session.rejected.is_some() {
                return Err("Accept the recovered layout before changing presets".into());
            }
            let mut candidate = data.presets.clone();
            match command {
                PresetCommand::Create(ref name) => {
                    candidate.create(name, data.session.workspace.clone())?
                }
                PresetCommand::Overwrite(ref name) => {
                    candidate.overwrite(name, data.session.workspace.clone())?
                }
                PresetCommand::Rename(ref from, ref to) => candidate.rename(from, to)?,
                PresetCommand::Delete(ref name) => candidate.remove(name)?,
                _ => unreachable!(),
            }
            let raw = candidate.to_json()?;
            Ok((candidate, raw))
        })();
        let (candidate, raw) = match prepared {
            Ok(prepared) => prepared,
            Err(error) => {
                self.shared.borrow_mut().preset_notice = error;
                self.notify_panels(cx);
                return;
            }
        };
        let Some(directory) = &self.directory else {
            let mut data = self.shared.borrow_mut();
            data.presets = candidate;
            data.preset_notice = "Preset library updated".into();
            drop(data);
            self.notify_panels(cx);
            return;
        };
        let path = directory.join("presets.json");
        let storage = self.storage.clone();
        self.revision += 1;
        let revision = self.revision;
        self.shared.borrow_mut().preset_busy = true;
        self.shared.borrow_mut().preset_notice = "Saving presets…".into();
        cx.spawn(async move |weak, cx| {
            let result = smol::unblock(move || storage.write(&path, revision, &raw)).await;
            let _ = weak.update(cx, |this, cx| {
                let mut data = this.shared.borrow_mut();
                data.preset_busy = false;
                data.preset_notice = match result {
                    Ok(()) => {
                        data.presets = candidate;
                        "Preset library saved".into()
                    }
                    Err(error) => error,
                };
                drop(data);
                this.notify_panels(cx);
            });
        })
        .detach();
        self.notify_panels(cx);
    }
}

#[cfg(test)]
mod tests {
    use super::load;
    use system_pulse_model::{PresetLibrary, Workspace};
    #[test]
    fn legacy_import_and_bad_library_preserve_original_files() {
        let dir = std::env::temp_dir().join(format!(
            "system-pulse-presets-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir(&dir).unwrap();
        struct Cleanup(std::path::PathBuf);
        impl Drop for Cleanup {
            fn drop(&mut self) {
                let _ = std::fs::remove_dir_all(&self.0);
            }
        }
        let _cleanup = Cleanup(dir.clone());
        let workspace =
            Workspace::new(serde_json::to_value(crate::workspace::default_dock()).unwrap());
        let legacy = serde_json::to_string(&workspace).unwrap();
        std::fs::write(dir.join("preset.json"), &legacy).unwrap();
        let (imported, error) = load(Some(&dir), Some(&legacy), true);
        assert!(error.is_none());
        assert_eq!(
            imported.get("Imported preset").unwrap().dock,
            workspace.dock
        );
        assert_eq!(
            std::fs::read_to_string(dir.join("preset.json")).unwrap(),
            legacy
        );
        assert!(!dir.join("presets.json").exists());
        let mut library = PresetLibrary::default();
        library.create("New library", workspace).unwrap();
        std::fs::write(dir.join("presets.json"), library.to_json().unwrap()).unwrap();
        let (loaded, error) = load(Some(&dir), Some(&legacy), true);
        assert!(error.is_none());
        assert_eq!(loaded, library);
        std::fs::write(dir.join("presets.json"), "{broken").unwrap();
        let (loaded, error) = load(Some(&dir), Some(&legacy), true);
        assert!(error.is_some());
        assert!(loaded.presets.is_empty());
        assert_eq!(
            std::fs::read_to_string(dir.join("presets.json")).unwrap(),
            "{broken"
        );
        assert_eq!(
            std::fs::read_to_string(dir.join("preset.json")).unwrap(),
            legacy
        );
    }
}
