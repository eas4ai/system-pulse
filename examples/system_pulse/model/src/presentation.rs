use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::BTreeMap;

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Meter {
    #[default]
    Number,
    Sparkline,
    Line,
    Bar,
    Radial,
}

#[derive(Clone, Copy, Debug, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct ExpandedSize {
    pub width: f32,
    pub height: f32,
}

impl Default for ExpandedSize {
    fn default() -> Self {
        Self {
            width: 420.0,
            height: 280.0,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct SensorState {
    pub visible: bool,
    pub collapsed: bool,
    pub order: u32,
    pub meter: Meter,
}

impl Default for SensorState {
    fn default() -> Self {
        Self {
            visible: true,
            collapsed: false,
            order: 0,
            meter: Meter::Number,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct PanelState {
    pub visible: bool,
    pub collapsed: bool,
    pub expanded_size: ExpandedSize,
    pub sensors: BTreeMap<String, SensorState>,
}

impl Default for PanelState {
    fn default() -> Self {
        Self {
            visible: true,
            collapsed: false,
            expanded_size: ExpandedSize::default(),
            sensors: BTreeMap::new(),
        }
    }
}

impl PanelState {
    pub fn sensor_mut(&mut self, id: &str) -> &mut SensorState {
        let order = self
            .sensors
            .values()
            .map(|sensor| sensor.order)
            .max()
            .map_or(0, |order| order.saturating_add(1));
        self.sensors
            .entry(id.to_owned())
            .or_insert_with(|| SensorState {
                order,
                ..SensorState::default()
            })
    }

    pub fn visible_sensors(&self) -> Vec<(&str, &SensorState)> {
        let mut rows: Vec<_> = self
            .sensors
            .iter()
            .filter(|(_, sensor)| sensor.visible)
            .map(|(id, sensor)| (id.as_str(), sensor))
            .collect();
        rows.sort_by(|(id_a, a), (id_b, b)| a.order.cmp(&b.order).then_with(|| id_a.cmp(id_b)));
        rows
    }
}

fn schema_version() -> u32 {
    1
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Workspace {
    #[serde(default = "schema_version")]
    pub schema_version: u32,
    pub dock: Value,
    #[serde(default)]
    pub panels: BTreeMap<String, PanelState>,
}

impl Workspace {
    pub fn new(dock: Value) -> Self {
        Self {
            schema_version: schema_version(),
            dock,
            panels: BTreeMap::new(),
        }
    }

    pub fn panel_mut(&mut self, id: &str) -> &mut PanelState {
        self.panels.entry(id.to_owned()).or_default()
    }

    pub fn validate(&self) -> Result<(), String> {
        if self.schema_version != schema_version() {
            return Err(format!(
                "Unsupported presentation schema {}",
                self.schema_version
            ));
        }
        for (id, panel) in &self.panels {
            if id.trim().is_empty() {
                return Err("Empty monitor identity".into());
            }
            for value in [panel.expanded_size.width, panel.expanded_size.height] {
                if !value.is_finite() || value <= 0.0 || value > 16384.0 {
                    return Err(format!("Invalid preferred expanded size for {id}"));
                }
            }
            if panel.sensors.keys().any(|id| id.trim().is_empty()) {
                return Err(format!("Empty sensor identity in {id}"));
            }
        }
        Ok(())
    }
}
