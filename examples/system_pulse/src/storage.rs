use std::{
    collections::BTreeMap,
    fs,
    io::{Read, Write},
    path::{Path, PathBuf},
    sync::{Arc, Mutex},
};

#[derive(Clone, Default)]
pub(crate) struct Storage(Arc<Mutex<BTreeMap<PathBuf, u64>>>);

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
    base.map(|p| p.join("system-pulse-fixture"))
        .ok_or_else(|| "No platform configuration directory is available".into())
}

pub(crate) fn read(path: &Path) -> Result<Option<String>, String> {
    let file = match fs::File::open(path) {
        Ok(file) => file,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(e) => return Err(format!("Read {}: {e}", path.display())),
    };
    let mut bytes = Vec::new();
    file.take(1_048_577)
        .read_to_end(&mut bytes)
        .map_err(|e| e.to_string())?;
    if bytes.len() > 1_048_576 {
        return Err("Saved state exceeds 1 MiB".into());
    }
    String::from_utf8(bytes)
        .map(Some)
        .map_err(|e| format!("State is not UTF-8: {e}"))
}

impl Storage {
    pub(crate) fn write(&self, path: &Path, revision: u64, data: &str) -> Result<(), String> {
        let mut versions = self.0.lock().map_err(|_| "Storage lock poisoned")?;
        if versions.get(path).is_some_and(|saved| *saved > revision) {
            return Ok(());
        }
        let parent = path.parent().ok_or("State path has no parent")?;
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
        let temp = path.with_extension(format!("{}.tmp", std::process::id()));
        let result = (|| -> std::io::Result<()> {
            let mut file = fs::File::create(&temp)?;
            file.write_all(data.as_bytes())?;
            file.sync_all()?;
            fs::rename(&temp, path)?;
            Ok(())
        })();
        if let Err(error) = result {
            let _ = fs::remove_file(&temp);
            return Err(format!("Save {}: {error}", path.display()));
        }
        versions.insert(path.to_owned(), revision);
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
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
        let bytes = vec![b'x'; 1_048_577];
        fs::write(&path, &bytes).unwrap();
        assert!(read(&path).unwrap_err().contains("1 MiB"));
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
}
