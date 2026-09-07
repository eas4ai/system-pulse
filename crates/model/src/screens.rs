use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Screen {
    #[default]
    Summary,
    Cpu,
    Memory,
    Gpu,
    Disks,
    Network,
    Energy,
    Thermals,
    Processes,
    Settings,
}

impl Screen {
    pub const ALL: [Self; 10] = [
        Self::Summary,
        Self::Cpu,
        Self::Memory,
        Self::Gpu,
        Self::Disks,
        Self::Network,
        Self::Energy,
        Self::Thermals,
        Self::Processes,
        Self::Settings,
    ];

    pub fn id(self) -> &'static str {
        match self {
            Self::Summary => "summary",
            Self::Cpu => "cpu",
            Self::Memory => "memory",
            Self::Gpu => "gpu",
            Self::Disks => "disks",
            Self::Network => "network",
            Self::Energy => "energy",
            Self::Thermals => "thermals",
            Self::Processes => "processes",
            Self::Settings => "settings",
        }
    }

    pub fn title(self) -> &'static str {
        match self {
            Self::Summary => "Summary",
            Self::Cpu => "CPU",
            Self::Memory => "Memory",
            Self::Gpu => "GPU",
            Self::Disks => "Disks",
            Self::Network => "Network",
            Self::Energy => "Energy",
            Self::Thermals => "Thermals",
            Self::Processes => "Processes",
            Self::Settings => "Settings",
        }
    }

    pub fn has_device_selection(self) -> bool {
        matches!(
            self,
            Self::Gpu | Self::Disks | Self::Network | Self::Energy | Self::Thermals
        )
    }

    pub fn adjacent(self, forward: bool) -> Self {
        let index = Self::ALL
            .iter()
            .position(|screen| *screen == self)
            .unwrap_or(0);
        Self::ALL[(index + if forward { 1 } else { Self::ALL.len() - 1 }) % Self::ALL.len()]
    }
}

#[derive(Clone, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(default)]
pub struct ScreenState {
    pub active: Screen,
    pub devices: BTreeMap<Screen, String>,
}

impl ScreenState {
    pub(crate) fn validate(&self) -> Result<(), String> {
        for (screen, id) in &self.devices {
            if !screen.has_device_selection() || id.trim().is_empty() {
                return Err(format!("Invalid device selection for {}", screen.title()));
            }
        }
        Ok(())
    }
}
