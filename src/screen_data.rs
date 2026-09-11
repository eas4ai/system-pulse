//! Screen projections over the accepted snapshot. No collection or synthetic samples.
use crate::workspace::Data;
use system_pulse_collectors::MonitorKind;
use system_pulse_model::{PhysicalUnit, Quantity, ReadingStatus, Sample, Screen};

#[derive(Clone, Debug)]
pub(crate) struct Channel {
    pub monitor: String,
    pub sensor: String,
    pub label: String,
    pub device: String,
    pub scope: String,
    pub quantity: Quantity,
    pub unit: PhysicalUnit,
}

impl Channel {
    pub fn latest<'a>(&self, data: &'a Data) -> Option<&'a Sample> {
        data.history.latest(&self.monitor, &self.sensor)
    }

    pub fn samples(&self, data: &Data) -> Vec<Sample> {
        data.history
            .samples(&self.monitor, &self.sensor)
            .map(|samples| samples.iter().cloned().collect())
            .unwrap_or_default()
    }

    pub fn value(&self, data: &Data) -> String {
        compact_value(self.latest(data))
    }

    pub fn measured(&self, data: &Data) -> Option<f64> {
        self.latest(data).and_then(Sample::chart_value)
    }

    pub fn visible(&self, data: &Data) -> bool {
        sensor_visible(data, &self.monitor, &self.sensor)
            && self
                .latest(data)
                .is_some_and(|sample| sample.status != ReadingStatus::Unavailable)
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub(crate) struct DeviceChoice {
    pub id: String,
    pub label: String,
}

pub(crate) fn compact_value(sample: Option<&Sample>) -> String {
    match sample {
        Some(sample) if sample.value.is_some() => {
            let value = format!("{} {}", sample.text, sample.unit).trim().to_owned();
            if sample.status == ReadingStatus::Stale {
                format!("{value} · stale")
            } else {
                value
            }
        }
        Some(sample) => match sample.status {
            ReadingStatus::WarmingUp => "Warming up".into(),
            ReadingStatus::Failed => "Reading failed".into(),
            ReadingStatus::Stale => "Stale".into(),
            _ => "Unavailable".into(),
        },
        None => "Waiting for data".into(),
    }
}

pub(crate) fn sensor_visible(data: &Data, monitor: &str, sensor: &str) -> bool {
    data.session
        .workspace
        .panels
        .get(monitor)
        .and_then(|panel| panel.sensors.get(sensor))
        .is_none_or(|sensor| sensor.visible)
}

fn channel(
    monitor: &system_pulse_model::MonitorDescriptor,
    sensor: &system_pulse_model::SensorDescriptor,
    scope: String,
) -> Channel {
    Channel {
        monitor: monitor.id.clone(),
        sensor: sensor.id.clone(),
        device: monitor.title.clone(),
        label: sensor.title.clone(),
        scope,
        quantity: sensor.quantity,
        unit: sensor.unit,
    }
}

pub(crate) fn channels(data: &Data) -> Vec<Channel> {
    let scopes: std::collections::BTreeMap<_, _> = data
        .snapshot
        .iter()
        .flat_map(|snapshot| snapshot.sensors.iter())
        .map(|sensor| (sensor.id.as_str(), sensor.scope.as_str()))
        .collect();
    data.catalog
        .iter()
        .flat_map(|monitor| {
            monitor.sensors.iter().map(|sensor| {
                channel(
                    monitor,
                    sensor,
                    scopes
                        .get(sensor.id.as_str())
                        .copied()
                        .unwrap_or_default()
                        .to_owned(),
                )
            })
        })
        .collect()
}

pub(crate) fn monitor_channels(data: &Data, id: &str) -> Vec<Channel> {
    ordered_monitor_channels(data, id, false)
}

pub(crate) fn gpu_channels(data: &Data, id: &str) -> Vec<Channel> {
    ordered_monitor_channels(data, id, true)
}

fn ordered_monitor_channels(data: &Data, id: &str, include_unavailable: bool) -> Vec<Channel> {
    let mut rows: Vec<_> = channels(data)
        .into_iter()
        .filter(|channel| {
            channel.monitor == id
                && if include_unavailable {
                    sensor_visible(data, id, &channel.sensor) && channel.latest(data).is_some()
                } else {
                    channel.visible(data)
                }
        })
        .collect();
    rows.sort_by_key(|channel| {
        let order = data
            .session
            .workspace
            .panels
            .get(id)
            .and_then(|panel| panel.sensors.get(&channel.sensor))
            .map_or(0, |sensor| sensor.order);
        (order, channel.sensor.clone())
    });
    rows
}

pub(crate) fn find(data: &Data, monitor: &str, suffix: &str) -> Option<Channel> {
    let monitor = data
        .catalog
        .iter()
        .find(|candidate| candidate.id == monitor)?;
    let id = format!("{}/{suffix}", monitor.id);
    let sensor = monitor.sensors.iter().find(|sensor| sensor.id == id)?;
    let scope = data
        .snapshot
        .as_ref()
        .and_then(|snapshot| snapshot.sensors.iter().find(|candidate| candidate.id == id))
        .map(|sensor| sensor.scope.clone())
        .unwrap_or_default();
    let channel = channel(monitor, sensor, scope);
    channel.visible(data).then_some(channel)
}

pub(crate) fn by_quantity(data: &Data, quantity: Quantity, unit: PhysicalUnit) -> Vec<Channel> {
    channels(data)
        .into_iter()
        .filter(|channel| {
            channel.quantity == quantity && channel.unit == unit && channel.visible(data)
        })
        .collect()
}

pub(crate) fn highest_current(data: &Data, channels: &[Channel]) -> Option<Channel> {
    channels
        .iter()
        .filter_map(|channel| channel.measured(data).map(|value| (channel, value)))
        .max_by(|(a, av), (b, bv)| av.total_cmp(bv).then_with(|| b.sensor.cmp(&a.sensor)))
        .map(|(channel, _)| channel.clone())
}

pub(crate) fn devices(data: &Data, screen: Screen) -> Vec<DeviceChoice> {
    let mut result = if matches!(screen, Screen::Energy | Screen::Thermals) {
        let (quantity, unit) = if screen == Screen::Energy {
            (Quantity::Power, PhysicalUnit::Watts)
        } else {
            (Quantity::Temperature, PhysicalUnit::Celsius)
        };
        by_quantity(data, quantity, unit)
            .into_iter()
            .map(|channel| DeviceChoice {
                id: channel.sensor,
                label: format!("{} · {}", channel.device, channel.label),
            })
            .collect::<Vec<_>>()
    } else {
        data.snapshot
            .as_ref()
            .map(|snapshot| {
                snapshot
                    .monitors
                    .iter()
                    .filter(|monitor| {
                        matches!(
                            (screen, &monitor.kind),
                            (Screen::Gpu, MonitorKind::Gpu)
                                | (Screen::Disks, MonitorKind::Volume)
                                | (Screen::Network, MonitorKind::Network)
                        )
                    })
                    .map(|monitor| DeviceChoice {
                        id: monitor.id.clone(),
                        label: data
                            .catalog
                            .iter()
                            .find(|candidate| candidate.id == monitor.id)
                            .map(|monitor| monitor.title.clone())
                            .unwrap_or_else(|| monitor.title.clone()),
                    })
                    .collect::<Vec<_>>()
            })
            .unwrap_or_default()
    };
    result.sort_by(|a, b| a.label.cmp(&b.label).then_with(|| a.id.cmp(&b.id)));
    result
}

/// A saved absent device never silently becomes a different device.
pub(crate) fn selected_device(data: &Data, screen: Screen) -> Option<String> {
    if let Some(id) = data.session.workspace.screens.devices.get(&screen) {
        return Some(id.clone());
    }
    let choices = devices(data, screen);
    if screen == Screen::Network
        && let Some(id) = data
            .snapshot
            .as_ref()
            .and_then(|snapshot| snapshot.preferred_network_monitor_id.as_ref())
        && choices.iter().any(|choice| &choice.id == id)
    {
        return Some(id.clone());
    }
    if screen == Screen::Thermals {
        return highest_current(
            data,
            &by_quantity(data, Quantity::Temperature, PhysicalUnit::Celsius),
        )
        .map(|channel| channel.sensor)
        .or_else(|| choices.first().map(|choice| choice.id.clone()));
    }
    // Prefer a device with a current measurement. Identity, not discovery order, breaks ties.
    let channels = channels(data);
    choices
        .iter()
        .find(|choice| {
            channels.iter().any(|channel| {
                (channel.monitor == choice.id || channel.sensor == choice.id)
                    && channel.measured(data).is_some()
            })
        })
        .or(choices.first())
        .map(|choice| choice.id.clone())
}

pub(crate) fn selected_channel(data: &Data, screen: Screen) -> Option<Channel> {
    let id = selected_device(data, screen)?;
    channels(data)
        .into_iter()
        .find(|channel| channel.sensor == id && channel.visible(data))
}

pub(crate) fn cpu_cores(data: &Data) -> Vec<Channel> {
    let mut result: Vec<_> = monitor_channels(data, "cpu:host")
        .into_iter()
        .filter(|channel| crate::dashboard::core_number(&channel.sensor).is_some())
        .collect();
    result.sort_by_key(|channel| crate::dashboard::core_number(&channel.sensor));
    result
}

pub(crate) fn current_ratio(channel: &Channel, data: &Data) -> Option<f64> {
    let sample = channel.latest(data)?;
    if channel.quantity == Quantity::Capacity {
        return sample.capacity_ratio();
    }
    if channel.quantity == Quantity::Percentage {
        return sample.chart_value().map(|value| value / 100.);
    }
    let current = sample.chart_value()?;
    let samples = channel.samples(data);
    let (low, high) = system_pulse_model::chart_range(&samples);
    (high > low).then_some((current - low) / (high - low))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn zero_is_visible_and_stale_does_not_become_current() {
        let mut sample =
            Sample::measured(1, Quantity::Power, 0., None, PhysicalUnit::Watts).unwrap();
        assert_eq!(sample.chart_value(), Some(0.));
        assert!(compact_value(Some(&sample)).starts_with('0'));
        sample.status = ReadingStatus::Stale;
        assert!(sample.chart_value().is_none());
        assert!(compact_value(Some(&sample)).ends_with("stale"));
        sample.status = ReadingStatus::Unavailable;
        sample.value = None;
        assert_eq!(compact_value(Some(&sample)), "Unavailable");
    }

    #[test]
    fn missing_sensor_is_not_a_zero_measurement() {
        assert_eq!(compact_value(None), "Waiting for data");
    }
}
