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
        if self.sensors.contains_key(id) {
            return self.sensors.get_mut(id).expect("sensor exists");
        }

        let order = self.sensors.values().map(|sensor| sensor.order).max();
        let order = match order {
            Some(order) => match order.checked_add(1) {
                Some(next) => next,
                None => {
                    let mut ids: Vec<_> = self.sensors.keys().cloned().collect();
                    ids.sort_by(|id_a, id_b| {
                        self.sensors[id_a]
                            .order
                            .cmp(&self.sensors[id_b].order)
                            .then_with(|| id_a.cmp(id_b))
                    });
                    for (order, sensor_id) in ids.iter().enumerate() {
                        self.sensors
                            .get_mut(sensor_id)
                            .expect("sensor exists")
                            .order = order as u32;
                    }
                    self.sensors.len() as u32
                }
            },
            None => 0,
        };
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

/// Largest accepted width or height for a persisted expanded panel size.
pub const MAX_EXPANDED_DIMENSION: f32 = 16_384.0;

fn default_interval_ms() -> u64 {
    1000
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
    #[serde(default)]
    pub monitors: BTreeMap<String, MonitorDescriptor>,
    #[serde(default = "default_interval_ms")]
    pub interval_ms: u64,
    #[serde(default)]
    pub appearance: crate::Appearance,
}

impl Workspace {
    pub fn new(dock: Value) -> Self {
        Self {
            schema_version: schema_version(),
            dock,
            panels: BTreeMap::new(),
            monitors: BTreeMap::new(),
            interval_ms: default_interval_ms(),
            appearance: crate::Appearance::default(),
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
        if ![500, 1000, 2000, 5000].contains(&self.interval_ms) {
            return Err("Unsupported sampling interval".into());
        }
        for (id, monitor) in &self.monitors {
            if id.trim().is_empty()
                || id != &monitor.id
                || monitor.sensors.iter().any(|s| s.id.trim().is_empty())
            {
                return Err("Invalid saved monitor metadata identity".into());
            }
        }
        for (id, panel) in &self.panels {
            if id.trim().is_empty() {
                return Err("Empty monitor identity".into());
            }
            for value in [panel.expanded_size.width, panel.expanded_size.height] {
                if !value.is_finite() || value <= 0.0 || value > MAX_EXPANDED_DIMENSION {
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

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct SensorDescriptor {
    pub id: String,
    pub title: String,
    pub quantity: crate::Quantity,
    pub unit: crate::PhysicalUnit,
}
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct MonitorDescriptor {
    pub id: String,
    pub title: String,
    pub summary: String,
    pub sensors: Vec<SensorDescriptor>,
}
