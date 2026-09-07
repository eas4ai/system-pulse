use system_pulse_model::{HistoryStore, ReadingStatus, Sample, Workspace};

use system_pulse_model::{
    MonitorDescriptor as Monitor, PhysicalUnit, Quantity, SensorDescriptor as Sensor,
};

pub(crate) fn catalog() -> Vec<Monitor> {
    vec![
        Monitor {
            id: "cpu".into(),
            title: "CPU".into(),
            summary: "overall".into(),
            sensors: vec![
                Sensor {
                    id: "overall".into(),
                    title: "Overall utilization".into(),
                    quantity: Quantity::Percentage,
                    unit: PhysicalUnit::Percent,
                },
                Sensor {
                    id: "core0".into(),
                    title: "Core 0 utilization".into(),
                    quantity: Quantity::Percentage,
                    unit: PhysicalUnit::Percent,
                },
            ],
        },
        Monitor {
            id: "gpu:fixture-a".into(),
            title: "GPU A".into(),
            summary: "utilization".into(),
            sensors: vec![Sensor {
                id: "utilization".into(),
                title: "Utilization".into(),
                quantity: Quantity::Percentage,
                unit: PhysicalUnit::Percent,
            }],
        },
        Monitor {
            id: "gpu:fixture-b".into(),
            title: "GPU B".into(),
            summary: "utilization".into(),
            sensors: vec![Sensor {
                id: "utilization".into(),
                title: "Utilization".into(),
                quantity: Quantity::Percentage,
                unit: PhysicalUnit::Percent,
            }],
        },
        Monitor {
            id: "memory".into(),
            title: "Memory".into(),
            summary: "capacity".into(),
            sensors: vec![Sensor {
                id: "capacity".into(),
                title: "RAM used / total".into(),
                quantity: Quantity::Percentage,
                unit: PhysicalUnit::Percent,
            }],
        },
        Monitor {
            id: "volume:fixture-home".into(),
            title: "Home volume".into(),
            summary: "capacity".into(),
            sensors: vec![Sensor {
                id: "capacity".into(),
                title: "Capacity used / total".into(),
                quantity: Quantity::Percentage,
                unit: PhysicalUnit::Percent,
            }],
        },
        Monitor {
            id: "interface:fixture-lan".into(),
            title: "LAN".into(),
            summary: "traffic".into(),
            sensors: vec![Sensor {
                id: "traffic".into(),
                title: "RX / TX throughput".into(),
                quantity: Quantity::Percentage,
                unit: PhysicalUnit::Percent,
            }],
        },
        Monitor {
            id: "processes".into(),
            title: "Processes".into(),
            summary: "count".into(),
            sensors: vec![],
        },
        Monitor {
            id: "settings".into(),
            title: "Settings".into(),
            summary: "".into(),
            sensors: vec![],
        },
    ]
}

pub(crate) fn discover(workspace: &mut Workspace, monitors: &[Monitor]) {
    crate::live::discover(workspace, monitors);
}

pub(crate) fn sample(monitor: &str, sensor: &str, tick: u64) -> Sample {
    let value = (((tick % 12) * 7 + sensor.len() as u64 * 3) % 80 + 10) as f64;
    let status = match tick % 12 {
        8 => ReadingStatus::Unavailable,
        9 => ReadingStatus::Stale,
        _ => ReadingStatus::Current,
    };
    let (text, unit) = match monitor {
        "memory" => (format!("{:.1} / 32", value / 4.), "GiB"),
        "volume:fixture-home" => (format!("{:.0} / 1000", value * 10.), "GiB"),
        "interface:fixture-lan" => (format!("RX {:.1} · TX {:.1}", value, value / 4.), "MiB/s"),
        "processes" => ("500".to_owned(), "processes"),
        _ => (format!("{value:.0}"), "%"),
    };
    Sample {
        at_ms: tick * 1000,
        value: if status == ReadingStatus::Unavailable {
            None
        } else {
            Some(value)
        },
        text: if status == ReadingStatus::Unavailable {
            "Unavailable".into()
        } else {
            text
        },
        unit: unit.into(),
        status,
        quantity: Default::default(),
        total: None,
        reason: None,
    }
}

pub(crate) fn advance(history: &mut HistoryStore, tick: u64) -> Result<(), String> {
    for monitor in catalog() {
        let mut ids: Vec<_> = monitor
            .sensors
            .iter()
            .map(|sensor| sensor.id.as_str())
            .collect();
        if !monitor.summary.is_empty() && !ids.contains(&monitor.summary.as_str()) {
            ids.push(&monitor.summary);
        }
        for sensor in ids {
            history.push(&monitor.id, sensor, sample(&monitor.id, sensor, tick))?;
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn fixtures_continue_through_gaps_and_keep_stable_identity() {
        let mut history = HistoryStore::new(12).unwrap();
        for tick in 1..=14 {
            advance(&mut history, tick).unwrap();
        }
        let cpu = history.samples("cpu", "overall").unwrap();
        assert_eq!(cpu.len(), 12);
        assert_eq!(cpu.front().unwrap().at_ms, 3000);
        assert_eq!(cpu.back().unwrap().at_ms, 14000);
        assert_eq!(cpu.iter().filter(|s| s.chart_value().is_none()).count(), 2);
        assert!(history.latest("gpu:fixture-a", "utilization").is_some());
        assert!(history.latest("gpu:fixture-b", "utilization").is_some());
    }
    #[test]
    fn rediscovery_preserves_disconnected_devices_and_missing_sensor_choices() {
        let mut workspace = Workspace::new(serde_json::json!({}));
        discover(&mut workspace, &catalog());
        workspace.panel_mut("gpu:fixture-a").collapsed = true;
        workspace.panel_mut("cpu").sensor_mut("core0").meter = system_pulse_model::Meter::Radial;
        workspace.panel_mut("cpu").sensor_mut("core0").collapsed = true;
        workspace.panel_mut("cpu").sensor_mut("core0").visible = false;
        let mut changed = catalog();
        changed.reverse();
        changed.retain(|monitor| monitor.id != "gpu:fixture-a");
        changed
            .iter_mut()
            .find(|monitor| monitor.id == "cpu")
            .unwrap()
            .sensors
            .retain(|sensor| sensor.id != "core0");
        discover(&mut workspace, &changed);
        assert!(workspace.panels["gpu:fixture-a"].collapsed);
        assert!(!workspace.panels["gpu:fixture-b"].collapsed);
        discover(&mut workspace, &catalog());
        let sensor = &workspace.panels["cpu"].sensors["core0"];
        assert!(sensor.collapsed);
        assert!(!sensor.visible);
        assert_eq!(sensor.meter, system_pulse_model::Meter::Radial);
    }

    #[test]
    fn readings_repeat_a_twelve_tick_cycle_with_monotonic_timestamps() {
        for tick in 1..=12 {
            let first = sample("cpu", "overall", tick);
            let next = sample("cpu", "overall", tick + 12);
            assert_eq!(first.value, next.value);
            assert_eq!(first.text, next.text);
            assert_eq!(first.status, next.status);
            assert_eq!(next.at_ms - first.at_ms, 12_000);
        }
    }
}

pub(crate) fn processes() -> Vec<crate::live::ProcessView> {
    (0..500)
        .map(|index| crate::live::ProcessView {
            numeric: [None; 5],
            identity: system_pulse_collectors::ProcessIdentity {
                pid: 1000 + index,
                start_time_ticks: 1,
            },
            cells: vec![
                (1000 + index).to_string(),
                format!("fixture-process-{index}"),
                format!("{}%", index % 100),
                "1 MiB".into(),
                "1 KiB/s".into(),
                "2 KiB/s".into(),
                "1 count".into(),
                "fixture".into(),
            ],
        })
        .collect()
}
