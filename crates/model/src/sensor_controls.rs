use crate::{Meter, PanelState, Quantity};
#[derive(Clone, Copy, Debug)]
pub enum SensorMove {
    Up,
    Down,
}
impl PanelState {
    pub fn move_sensor(&mut self, id: &str, direction: SensorMove) -> Result<(), String> {
        let mut ids: Vec<_> = self.sensors.keys().cloned().collect();
        ids.sort_by(|a, b| {
            self.sensors[a]
                .order
                .cmp(&self.sensors[b].order)
                .then_with(|| a.cmp(b))
        });
        let index = ids
            .iter()
            .position(|key| key == id)
            .ok_or("The sensor no longer exists")?;
        let next = match direction {
            SensorMove::Up => index.saturating_sub(1),
            SensorMove::Down => (index + 1).min(ids.len() - 1),
        };
        ids.swap(index, next);
        for (order, id) in ids.into_iter().enumerate() {
            self.sensors.get_mut(&id).expect("existing sensor").order = order as u32;
        }
        Ok(())
    }
    pub fn select_meter(
        &mut self,
        id: &str,
        quantity: Quantity,
        meter: Meter,
    ) -> Result<(), String> {
        if !quantity.meters().contains(&meter) {
            return Err("That meter is incompatible with this sensor quantity".into());
        }
        let sensor = self
            .sensors
            .get_mut(id)
            .ok_or("The sensor no longer exists")?;
        sensor.meter = meter;
        Ok(())
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn reordering_keeps_hidden_and_collapsed_sensor_state_attached_to_identity() {
        let mut panel = PanelState::default();
        panel.sensor_mut("a").collapsed = true;
        panel.sensor_mut("b").visible = false;
        panel.sensor_mut("c").meter = Meter::Line;
        panel.move_sensor("c", SensorMove::Up).unwrap();
        panel.move_sensor("c", SensorMove::Up).unwrap();
        assert_eq!(
            panel
                .visible_sensors()
                .iter()
                .map(|row| row.0)
                .collect::<Vec<_>>(),
            vec!["c", "a"]
        );
        assert_eq!(panel.sensors["c"].meter, Meter::Line);
        assert!(panel.sensors["a"].collapsed);
        assert!(!panel.sensors["b"].visible);
        panel.move_sensor("c", SensorMove::Up).unwrap();
        panel.move_sensor("c", SensorMove::Down).unwrap();
        assert_eq!(
            panel
                .visible_sensors()
                .iter()
                .map(|row| row.0)
                .collect::<Vec<_>>(),
            vec!["a", "c"]
        );
        assert!(panel.move_sensor("missing", SensorMove::Up).is_err());
    }
    #[test]
    fn explicit_meter_selection_rejects_incompatible_or_missing_targets() {
        let mut panel = PanelState::default();
        panel.sensor_mut("temperature");
        panel
            .select_meter("temperature", Quantity::Temperature, Meter::Line)
            .unwrap();
        assert!(
            panel
                .select_meter("temperature", Quantity::Temperature, Meter::Bar)
                .is_err()
        );
        assert_eq!(panel.sensors["temperature"].meter, Meter::Line);
        assert!(
            panel
                .select_meter("missing", Quantity::Percentage, Meter::Bar)
                .is_err()
        );
    }
}
