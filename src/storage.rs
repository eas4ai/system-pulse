use crate::diagnostics::timing::{Timing, bounded_error};
use std::{
    collections::BTreeMap,
    fs,
    io::{Read, Write},
    path::{Path, PathBuf},
    sync::{Arc, Mutex},
};
use system_pulse_model::{MAX_CONFIGURATION_BYTES, validate_configuration_size};

#[derive(Clone, Default)]
pub(crate) struct Storage(Arc<Mutex<BTreeMap<PathBuf, u64>>>);

enum Durability {
    Durable,
    Transient,
}

pub(crate) fn directory() -> Result<PathBuf, String> {
    if let Some(path) = std::env::var_os("SYSTEM_PULSE_STATE_DIR") {
        return Ok(path.into());
    }
    #[cfg(target_os = "windows")]
    let base = std::env::var_os("APPDATA").map(PathBuf::from);
    #[cfg(target_os = "macos")]
    let base =
        std::env::var_os("HOME").map(|p| PathBuf::from(p).join("Library/Application Support"));
    #[cfg(not(any(target_os = "windows", target_os = "macos")))]
    let base = std::env::var_os("XDG_CONFIG_HOME")
        .map(PathBuf::from)
        .or_else(|| std::env::var_os("HOME").map(|p| PathBuf::from(p).join(".config")));
    base.map(|p| p.join("system-pulse"))
        .ok_or_else(|| "No platform configuration directory is available".into())
}

pub(crate) fn read(path: &Path) -> Result<Option<String>, String> {
    let file = match fs::File::open(path) {
        Ok(file) => file,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(e) => return Err(format!("Read {}: {e}", path.display())),
    };
    let mut bytes = Vec::new();
    file.take(MAX_CONFIGURATION_BYTES as u64 + 1)
        .read_to_end(&mut bytes)
        .map_err(|e| e.to_string())?;
    validate_configuration_size(bytes.len())
        .map_err(|error| format!("Read {}: {error}", path.display()))?;
    String::from_utf8(bytes)
        .map(Some)
        .map_err(|e| format!("State is not UTF-8: {e}"))
}

impl Storage {
    pub(crate) fn write(&self, path: &Path, revision: u64, data: &str) -> Result<(), String> {
        validate_configuration_size(data.len())
            .map_err(|error| format!("Save {}: {error}", path.display()))?;
        self.atomic_write(path, revision, data, Durability::Durable, None)
    }

    /// Diagnostics retain one latest complete record, independent of configuration
    /// byte limits and disk durability. Only the diagnostic worker uses this entry point.
    pub(crate) fn write_diagnostic(
        &self,
        path: &Path,
        revision: u64,
        data: &str,
    ) -> Result<(), String> {
        self.atomic_write(path, revision, data, Durability::Transient, None)
    }

    pub(crate) fn write_diagnostic_timed(
        &self,
        path: &Path,
        revision: u64,
        data: &str,
        timing: &mut Timing,
    ) -> Result<(), String> {
        self.atomic_write(path, revision, data, Durability::Transient, Some(timing))
    }

    fn atomic_write(
        &self,
        path: &Path,
        revision: u64,
        data: &str,
        durability: Durability,
        mut timing: Option<&mut Timing>,
    ) -> Result<(), String> {
        let mut versions = self.0.lock().map_err(|_| "Storage lock poisoned")?;
        if versions.get(path).is_some_and(|saved| *saved > revision) {
            return Ok(());
        }
        if let Some(t) = &mut timing {
            t.stages.temp_write_started_ns = Some(t.clock.now());
        }
        let parent = path.parent().ok_or("State path has no parent")?;
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
        let temp = path.with_extension(format!("{}.tmp", std::process::id()));
        let result = (|| -> std::io::Result<()> {
            let mut file = fs::File::create(&temp)?;
            if let Some(t) = &mut timing {
                #[cfg(unix)]
                {
                    use std::os::unix::fs::MetadataExt;
                    match file.metadata() {
                        Ok(metadata) => {
                            t.temp_device = Some(metadata.dev());
                            t.temp_inode = Some(metadata.ino());
                        }
                        Err(error) => {
                            t.trace_error =
                                Some(bounded_error(&format!("Temporary file identity: {error}")))
                        }
                    }
                }
                #[cfg(not(unix))]
                {
                    t.trace_error = Some("Temporary device/inode observation requires Unix".into());
                }
            }
            file.write_all(data.as_bytes())?;
            if let Some(t) = &mut timing {
                t.stages.temp_write_completed_ns = Some(t.clock.now());
            }
            if matches!(durability, Durability::Durable) {
                file.sync_all()?;
            }
            if let Some(t) = &mut timing {
                t.stages.rename_started_ns = Some(t.clock.now());
            }
            let renamed = fs::rename(&temp, path);
            #[cfg(target_os = "windows")]
            let renamed = if matches!(durability, Durability::Transient) {
                // Windows can deny replacement while a diagnostic consumer reads
                // the previous record. Only this background-worker publication
                // retries; durable configuration writes retain their policy.
                let mut renamed = renamed;
                for _ in 0..10 {
                    if !renamed
                        .as_ref()
                        .err()
                        .is_some_and(|error| matches!(error.raw_os_error(), Some(5 | 32)))
                    {
                        break;
                    }
                    std::thread::sleep(std::time::Duration::from_millis(10));
                    renamed = fs::rename(&temp, path);
                }
                renamed
            } else {
                renamed
            };
            renamed?;
            if let Some(t) = &mut timing {
                t.stages.rename_completed_ns = Some(t.clock.now());
            }
            Ok(())
        })();
        if let Err(error) = result {
            if let Err(cleanup) = fs::remove_file(&temp) {
                if cleanup.kind() != std::io::ErrorKind::NotFound {
                    if let Some(t) = &mut timing {
                        t.trace_error =
                            Some(bounded_error(&format!("Temporary cleanup: {cleanup}")));
                    }
                }
            }
            return Err(format!("Save {}: {error}", path.display()));
        }
        versions.insert(path.to_owned(), revision);
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[cfg(target_os = "windows")]
    #[test]
    fn diagnostic_waits_for_a_short_windows_reader_before_replacing_the_record() {
        use std::os::windows::fs::OpenOptionsExt;
        let dir = std::env::temp_dir().join(format!("pulse-short-reader-{}", std::process::id()));
        let path = dir.join("latest.json");
        let storage = Storage::default();
        storage.write_diagnostic(&path, 1, "old").unwrap();
        let reader = fs::OpenOptions::new()
            .read(true)
            .share_mode(1)
            .open(&path)
            .unwrap();
        let release = std::thread::spawn(move || {
            std::thread::sleep(std::time::Duration::from_millis(40));
            drop(reader);
        });
        let result = storage.write_diagnostic(&path, 2, "new");
        release.join().unwrap();
        let actual = fs::read_to_string(&path).unwrap();
        fs::remove_dir_all(dir).unwrap();
        assert!(result.is_ok(), "{result:?}");
        assert_eq!(actual, "new");
    }

    #[cfg(target_os = "windows")]
    #[test]
    fn diagnostic_keeps_a_persistently_locked_windows_record_and_cleans_its_temp() {
        use std::os::windows::fs::OpenOptionsExt;
        let dir = std::env::temp_dir().join(format!("pulse-held-reader-{}", std::process::id()));
        let path = dir.join("latest.json");
        let storage = Storage::default();
        storage.write_diagnostic(&path, 1, "old").unwrap();
        let reader = fs::OpenOptions::new()
            .read(true)
            .share_mode(1)
            .open(&path)
            .unwrap();
        let started = std::time::Instant::now();
        assert!(storage.write_diagnostic(&path, 2, "new").is_err());
        assert!(started.elapsed() < std::time::Duration::from_secs(2));
        assert_eq!(fs::read_to_string(&path).unwrap(), "old");
        assert_eq!(fs::read_dir(&dir).unwrap().count(), 1);
        drop(reader);
        storage.write_diagnostic(&path, 2, "new").unwrap();
        assert_eq!(fs::read_to_string(&path).unwrap(), "new");
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn diagnostic_publication_and_configuration_saves_use_distinct_flush_policies() {
        // Also run under strace to verify the actual flush policy of each entrypoint.
        let dir = std::env::temp_dir().join(format!("pulse-flush-policy-{}", std::process::id()));
        let storage = Storage::default();
        for name in ["workspace.json", "preset.json", "latest.json"] {
            let path = dir.join(name);
            let data = serde_json::json!({"target": name, "revision": 1}).to_string();
            if name == "latest.json" {
                storage.write_diagnostic(&path, 1, &data).unwrap();
            } else {
                storage.write(&path, 1, &data).unwrap();
            }
            assert_eq!(fs::read_to_string(&path).unwrap(), data);
        }
        assert_eq!(fs::read_dir(&dir).unwrap().count(), 3);
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn stale_diagnostic_revision_cannot_replace_newer_complete_json() {
        let dir =
            std::env::temp_dir().join(format!("pulse-diagnostic-revisions-{}", std::process::id()));
        let path = dir.join("latest.json");
        let storage = Storage::default();
        let previous = serde_json::json!({"render_revision": 1, "payload": "x".repeat(4096)});
        let latest = serde_json::json!({"render_revision": 3, "payload": "complete"});
        storage
            .write_diagnostic(&path, 1, &previous.to_string())
            .unwrap();
        storage
            .write_diagnostic(&path, 3, &latest.to_string())
            .unwrap();
        storage.clone().write_diagnostic(&path, 2, "stale").unwrap();
        let actual: serde_json::Value = serde_json::from_slice(&fs::read(&path).unwrap()).unwrap();
        assert_eq!(actual, latest);
        assert_eq!(fs::read_dir(&dir).unwrap().count(), 1);
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn failed_diagnostic_replace_preserves_target_cleans_temp_and_allows_retry() {
        let dir =
            std::env::temp_dir().join(format!("pulse-diagnostic-replace-{}", std::process::id()));
        let target = dir.join("latest.json");
        fs::create_dir_all(&target).unwrap();
        fs::write(target.join("original"), "preserve").unwrap();
        let storage = Storage::default();
        let error = storage.write_diagnostic(&target, 3, "new").unwrap_err();
        assert!(error.contains("Save") && error.contains("latest.json"));
        assert_eq!(
            fs::read_to_string(target.join("original")).unwrap(),
            "preserve"
        );
        assert_eq!(fs::read_dir(&dir).unwrap().count(), 1);
        fs::remove_dir_all(&target).unwrap();
        let data = r#"{"render_revision":2}"#;
        storage.write_diagnostic(&target, 2, data).unwrap();
        assert_eq!(fs::read_to_string(&target).unwrap(), data);
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn older_work_cannot_replace_a_newer_atomic_snapshot() {
        let dir = std::env::temp_dir().join(format!("system-pulse-storage-{}", std::process::id()));
        let path = dir.join("state.json");
        let storage = Storage::default();
        storage.write(&path, 2, "new").unwrap();
        storage.write(&path, 1, "old").unwrap();
        assert_eq!(read(&path).unwrap().as_deref(), Some("new"));
        fs::remove_file(path).unwrap();
        fs::remove_dir(dir).unwrap();
    }
    #[test]
    fn reads_are_bounded_and_invalid_bytes_remain_untouched() {
        let dir = std::env::temp_dir().join(format!("system-pulse-read-{}", std::process::id()));
        fs::create_dir_all(&dir).unwrap();
        let path = dir.join("state.json");
        let bytes = vec![b'x'; MAX_CONFIGURATION_BYTES + 1];
        fs::write(&path, &bytes).unwrap();
        assert!(read(&path).unwrap_err().contains("16 MiB"));
        assert_eq!(fs::read(&path).unwrap(), bytes);
        fs::write(&path, [255]).unwrap();
        assert!(read(&path).unwrap_err().contains("UTF-8"));
        assert_eq!(fs::read(&path).unwrap(), [255]);
        assert!(read(&dir).is_err());
        fs::remove_file(path).unwrap();
        fs::remove_dir(dir).unwrap();
    }

    #[test]
    fn failed_atomic_replace_does_not_modify_original_target() {
        let dir = std::env::temp_dir().join(format!("system-pulse-write-{}", std::process::id()));
        fs::create_dir_all(&dir).unwrap();
        let target = dir.join("state.json");
        fs::create_dir(&target).unwrap();
        fs::write(target.join("original"), "preserve").unwrap();
        assert!(Storage::default().write(&target, 1, "new").is_err());
        assert_eq!(
            fs::read_to_string(target.join("original")).unwrap(),
            "preserve"
        );
        assert_eq!(
            fs::read_dir(&dir).unwrap().count(),
            1,
            "failed temporary write must be cleaned up"
        );
        fs::remove_file(target.join("original")).unwrap();
        fs::remove_dir(target).unwrap();
        fs::remove_dir(dir).unwrap();
    }
    fn retained_workspace() -> system_pulse_model::Workspace {
        use system_pulse_model::{
            Meter, MonitorDescriptor, PhysicalUnit, Quantity, SensorDescriptor,
        };
        let mut workspace = system_pulse_model::Workspace::new(serde_json::json!({}));
        let mut children = Vec::new();
        for index in 0..451 {
            let id = format!(
                "volume:uuid:retained-device-{index:04}:/:/retained-generation/{}/filesystem-{index:04}",
                index / 151
            );
            let sensors: Vec<_> = (0..6)
                .map(|sensor| SensorDescriptor {
                    id: format!("{id}/physical-reading-{sensor}"),
                    title: format!("Retained filesystem physical reading {sensor}"),
                    quantity: Quantity::Capacity,
                    unit: PhysicalUnit::Bytes,
                })
                .collect();
            let panel = workspace.panel_mut(&id);
            panel.collapsed = index % 3 == 0;
            panel.visible = index % 5 != 0;
            for sensor in &sensors {
                panel.sensor_mut(&sensor.id).meter = Meter::Bar;
            }
            let monitor = MonitorDescriptor {
                id: id.clone(),
                title: format!("Retained filesystem {index}"),
                summary: sensors[0].id.clone(),
                sensors,
            };
            workspace.monitors.insert(id.clone(), monitor);
            children.push(serde_json::json!({"panel_name":"TabPanel", "info":{"tabs":{"active_index":0}}, "children":[{"panel_name":"SystemPulseMonitor","info":{"panel":{"monitor_id":id}},"children":[]}]}));
        }
        workspace.dock = serde_json::json!({"version":1,"center":{"panel_name":"StackPanel","info":{"stack":{"axis":1,"sizes":vec![280.; children.len()]}},"children":children}});
        workspace.validate().unwrap();
        crate::workspace::validate_dock(&workspace.dock).unwrap();
        workspace
    }

    #[test]
    fn retained_451_panel_workspace_and_preset_roundtrip_without_losing_absent_choices() {
        let workspace = retained_workspace();
        let session = system_pulse_model::Session {
            workspace: workspace.clone(),
            rejected: None,
        };
        let raw = session.autosave_json().unwrap();
        assert!(
            raw.len() > 1_048_576,
            "regression must exceed the original read bound"
        );
        let dir = std::env::temp_dir().join(format!("pulse-large-catalog-{}", std::process::id()));
        let storage = Storage::default();
        for name in ["workspace.json", "preset.json"] {
            let path = dir.join(name);
            storage.write(&path, 1, &raw).unwrap();
            let loaded = read(&path).unwrap().unwrap();
            assert_eq!(loaded, raw);
            let restored = system_pulse_model::Session::restore(
                &loaded,
                system_pulse_model::Workspace::new(serde_json::json!({})),
                crate::workspace::validate_dock,
            );
            assert!(restored.rejected.is_none());
            assert_eq!(restored.workspace, workspace);
            fs::remove_file(path).unwrap();
        }
        fs::remove_dir(dir).unwrap();
    }

    #[test]
    fn over_limit_workspace_and_preset_saves_preserve_readable_prior_files() {
        let dir = std::env::temp_dir().join(format!("pulse-save-bound-{}", std::process::id()));
        let storage = Storage::default();
        let mut workspace = retained_workspace();
        let previous = serde_json::to_string(&workspace).unwrap();
        workspace.monitors.values_mut().next().unwrap().title =
            "x".repeat(MAX_CONFIGURATION_BYTES + 1);
        let oversized = serde_json::to_string(&workspace).unwrap();
        for name in ["workspace.json", "preset.json"] {
            let path = dir.join(name);
            storage.write(&path, 1, &previous).unwrap();
            let result = storage.write(&path, 3, &oversized);
            assert!(
                result.is_err(),
                "over-limit save must be rejected before replacing {name}"
            );
            let error = result.unwrap_err();
            assert!(
                error.contains("16 MiB") && error.contains(name),
                "save error must identify the limit and target"
            );
            assert_eq!(read(&path).unwrap().as_deref(), Some(previous.as_str()));
            assert_eq!(
                fs::read_dir(&dir).unwrap().count(),
                1,
                "rejected save must not leave a temporary file"
            );
            storage.write(&path, 2, &previous).unwrap();
            fs::remove_file(path).unwrap();
        }
        fs::remove_dir(dir).unwrap();
    }
}
