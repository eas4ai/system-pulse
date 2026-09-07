//! Display names from optional host metadata; never used as persistence keys.
use super::HostCollector;

impl HostCollector {
    pub(super) fn amd_name(&self, base: &str, pci: Option<&str>, identity: &str) -> String {
        let product = self
            .read(&format!("{base}/product_name"))
            .ok()
            .and_then(|value| display_text(&value))
            .or_else(|| {
                let properties = self.read(&format!("/run/udev/data/+pci:{}", pci?)).ok()?;
                properties.lines().find_map(|line| {
                    let model = line.strip_prefix("E:ID_MODEL_FROM_DATABASE=")?;
                    // pci.ids often supplies both a chip codename and the
                    // bracketed retail name, e.g. Navi 48 [Radeon AI PRO R9700].
                    let model = model
                        .rsplit_once('[')
                        .and_then(|(_, name)| name.strip_suffix(']'))
                        .filter(|name| name.starts_with("Radeon"))
                        .unwrap_or(model);
                    display_text(model)
                })
            })
            .unwrap_or_else(|| "AMD GPU".into());
        format!("{product} ({})", pci.unwrap_or(identity))
    }

    pub(super) fn network_name(&self, name: &str, base: &str) -> String {
        if let Some(alias) = self
            .read(&format!("{base}/ifalias"))
            .ok()
            .and_then(|value| display_text(&value))
        {
            return if alias == name {
                alias
            } else {
                format!("{alias} ({name})")
            };
        }
        let tun_flags = self
            .read(&format!("{base}/tun_flags"))
            .ok()
            .and_then(|text| u32::from_str_radix(text.trim().trim_start_matches("0x"), 16).ok());
        let kind = if name == "lo" {
            "Loopback"
        } else if self.path(&format!("{base}/wireless")).is_dir() {
            "Wi-Fi"
        } else if self.path(&format!("{base}/bridge")).is_dir() {
            if name == "docker0" {
                "Docker bridge"
            } else {
                "Network bridge"
            }
        } else if tun_flags.is_some_and(|flags| flags & 2 != 0) {
            "Virtual TAP"
        } else if tun_flags.is_some_and(|flags| flags & 1 != 0) {
            "Virtual tunnel"
        } else if name.starts_with("veth") {
            "Virtual Ethernet"
        } else if self.path(&format!("{base}/device")).exists()
            && self
                .read(&format!("{base}/type"))
                .is_ok_and(|value| value.trim() == "1")
        {
            "Ethernet"
        } else {
            "Network interface"
        };
        format!("{kind} ({name})")
    }
}

fn display_text(text: &str) -> Option<String> {
    let text = text.trim();
    (!text.is_empty() && !text.chars().any(char::is_control))
        .then(|| text.chars().take(160).collect())
}
