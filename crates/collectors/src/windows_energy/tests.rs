use super::*;

fn wide(value: &str) -> Vec<u8> {
    value
        .encode_utf16()
        .chain(Some(0))
        .flat_map(u16::to_le_bytes)
        .collect()
}
fn metadata(names: &[&str]) -> Vec<u8> {
    let mut bytes = vec![0; 68];
    bytes[..20].copy_from_slice(&wide("Microsoft"));
    bytes[32..40].copy_from_slice(&wide("PPM"));
    bytes[66..68].copy_from_slice(&(names.len() as u16).to_le_bytes());
    for name in names {
        let name = wide(name);
        bytes.extend(0u32.to_le_bytes());
        bytes.extend((name.len() as u16).to_le_bytes());
        bytes.extend(name);
    }
    bytes
}

#[test]
fn windows_energy_metadata_validates_units_lengths_names_and_duplicates() {
    let bytes = metadata(&["RAPL_Package0_PKG", "RAPL_Package0_DRAM"]);
    let parsed = parse_metadata(2, &bytes).unwrap();
    assert_eq!(parsed.channels.len(), 2);
    assert_eq!(parsed.channels[1], "RAPL_Package0_DRAM");
    for size in 0..bytes.len() {
        assert!(parse_metadata(2, &bytes[..size]).is_err());
    }
    let mut invalid = bytes.clone();
    invalid[68] = 1;
    assert!(parse_metadata(2, &invalid).is_err());
    let mut invalid = bytes.clone();
    invalid[72] = 255;
    assert!(parse_metadata(2, &invalid).is_err());
    let mut invalid = bytes.clone();
    invalid[74..76].copy_from_slice(&0xd800u16.to_le_bytes());
    assert!(parse_metadata(2, &invalid).is_err());
    assert!(parse_metadata(2, &metadata(&["same", "same"])).is_err());
    assert!(parse_metadata(2, &metadata(&[])).is_err());
    assert!(parse_metadata(3, &bytes).is_err());
}

#[test]
fn windows_energy_v1_and_native_v2_reply_layouts_are_supported() {
    let mut v1 = vec![0; 72];
    v1[4..24].copy_from_slice(&wide("Microsoft"));
    v1[36..44].copy_from_slice(&wide("PPM"));
    let name = wide("RAPL_Package0_PKG");
    v1[70..72].copy_from_slice(&(name.len() as u16).to_le_bytes());
    v1.extend(name);
    assert_eq!(
        parse_metadata(1, &v1).unwrap().channels,
        ["RAPL_Package0_PKG"]
    );
    v1[0] = 1;
    assert!(parse_metadata(1, &v1).is_err());
    let capture: serde_json::Value =
        serde_json::from_str(include_str!("emi-fixture.json")).unwrap();
    let decode = |value: &serde_json::Value| {
        value
            .as_str()
            .unwrap()
            .split('-')
            .map(|b| u8::from_str_radix(b, 16).unwrap())
            .collect::<Vec<_>>()
    };
    let parsed = parse_metadata(2, &decode(&capture["metadata"]["hex"])).unwrap();
    assert_eq!(parsed.channels.len(), 4);
    let values = parse_values(&decode(&capture["samples"][0]["hex"]), 4).unwrap();
    assert!(values[0].energy > 0);
    assert_eq!(values[1].energy, 0);
    assert!(parse_values(&[0; 15], 1).is_err());
    assert!(parse_values(&[0; 17], 1).is_err());
    assert!(parse_values(&[], 0).is_err());
    assert!(parse_metadata(2, &metadata(&vec!["x"; 65])).is_err());
    assert!(parse_metadata(2, &vec![0; MAX_METADATA + 1]).is_err());
}
fn device(instance: &str) -> Device {
    Device {
        instance: instance.into(),
        path: format!("interface:{instance}"),
    }
}
fn sample(energy: u64, time: u64, started: u64) -> Sample {
    Sample {
        metadata: parse_metadata(2, &metadata(&["RAPL_Package0_PKG", "RAPL_Package0_DRAM"]))
            .unwrap(),
        values: vec![Value { energy, time }, Value { energy: 0, time }],
        started,
        ended: started + 1,
    }
}
fn run(state: &mut State, sample: Result<Sample>) -> Snapshot {
    let mut snapshot = Snapshot::default();
    publish(&mut snapshot, &device("ACPI\\cpu0"), state, sample);
    snapshot
}
#[test]
fn windows_energy_derives_3_6_watts_and_never_publishes_zero_only_domain() {
    let mut state = State::default();
    let first = run(&mut state, Ok(sample(100, 100, 1)));
    assert_eq!(first.readings[0].availability, Availability::WarmingUp);
    assert_eq!(first.readings[1].availability, Availability::Unavailable);
    let next = run(&mut state, Ok(sample(1100, 110, 3)));
    assert_eq!(next.readings[0].value, Some(3.6));
    assert_eq!(next.readings[0].observations.len(), 2);
    assert_eq!(
        next.readings[0].observations[1].integers["absolute_energy_picowatt_hours"],
        1100
    );
    assert_eq!(next.readings[0].observations[1].read_started_ns, Some(3));
    assert_eq!(next.readings[1].availability, Availability::Unavailable);
    assert_eq!(next.sensors.len(), 2); // no package/component sum
    let idle = run(&mut state, Ok(sample(1100, 120, 5)));
    assert_eq!(idle.readings[0].value, Some(0.0));
}
#[test]
fn windows_energy_failed_queries_metadata_changes_and_rollbacks_reset_baselines() {
    for failure in 0..6 {
        let mut state = State::default();
        run(&mut state, Ok(sample(100, 100, 1)));
        let result = match failure {
            0 => Err("read denied".into()),
            1 => Ok(sample(99, 110, 3)),
            2 => Ok(sample(200, 100, 3)),
            3 => Ok(sample(200, 110, 1)),
            4 => {
                let mut s = sample(200, 110, 3);
                s.ended = 2;
                Ok(s)
            }
            _ => {
                let mut s = sample(200, 110, 3);
                s.values.pop();
                Ok(s)
            }
        };
        let failed = run(&mut state, result);
        assert_eq!(
            failed.readings[0].availability,
            Availability::Failed,
            "failure {failure}"
        );
        assert_eq!(
            run(&mut state, Ok(sample(300, 120, 5))).readings[0].availability,
            Availability::WarmingUp
        );
        assert_eq!(
            run(&mut state, Ok(sample(1300, 130, 7))).readings[0].value,
            Some(3.6)
        );
    }
    let mut state = State::default();
    run(&mut state, Ok(sample(100, 100, 1)));
    let mut changed = sample(1100, 110, 3);
    changed.metadata.revision += 1;
    assert_eq!(
        run(&mut state, Ok(changed)).readings[0].availability,
        Availability::WarmingUp
    );
}
#[test]
fn windows_energy_first_nonzero_observation_warms_and_generic_scope_is_explicit() {
    let mut state = State::default();
    run(&mut state, Ok(sample(0, 100, 1)));
    assert_eq!(
        run(&mut state, Ok(sample(100, 110, 3))).readings[0].availability,
        Availability::WarmingUp
    );
    let mut other = sample(200, 120, 5);
    other.metadata.channels = vec!["generic meter".into(), "RAPL_PackageX_PKG".into()];
    let snapshot = run(&mut state, Ok(other));
    assert!(snapshot.sensors.is_empty());
    assert_eq!(snapshot.diagnostics.len(), 2);
    assert!(
        snapshot
            .diagnostics
            .iter()
            .all(|d| d.availability == Availability::Unavailable)
    );
    assert!(
        domain("RAPL_Package0_PP1")
            .unwrap()
            .1
            .contains("Integrated GPU")
    );
}
struct Fake {
    inventories: std::collections::VecDeque<Result<Vec<Device>>>,
    samples: std::collections::VecDeque<Result<Sample>>,
}
impl Backend for Fake {
    fn inventory(&mut self) -> Result<Vec<Device>> {
        self.inventories.pop_front().unwrap()
    }
    fn sample(&mut self, _: &Device, _: Instant) -> Result<Sample> {
        self.samples.pop_front().unwrap()
    }
}
#[test]
fn windows_energy_inventory_failure_retains_sensors_and_removal_clears_baselines() {
    let inventories = vec![
        Ok(vec![device("cpu")]),
        Err("inventory denied".into()),
        Ok(vec![device("cpu")]),
        Ok(vec![]),
        Ok(vec![device("cpu")]),
    ]
    .into();
    let samples = vec![
        Ok(sample(100, 100, 1)),
        Ok(sample(1100, 110, 3)),
        Ok(sample(2100, 120, 5)),
    ]
    .into();
    let mut collector = WindowsEnergyCollector {
        backend: Box::new(Fake {
            inventories,
            samples,
        }),
        devices: Vec::new(),
        states: BTreeMap::new(),
    };
    for expected in [
        Some(Availability::WarmingUp),
        Some(Availability::Failed),
        Some(Availability::WarmingUp),
        None,
        Some(Availability::WarmingUp),
    ] {
        let mut snapshot = Snapshot::default();
        collector.collect(&mut snapshot, Instant::now());
        assert_eq!(
            snapshot.readings.first().map(|r| r.availability.clone()),
            expected
        );
    }
}
#[test]
fn windows_energy_device_and_channel_identities_cannot_collapse() {
    assert!(validate_inventory(vec![device("cpu"), device("CPU")]).is_err());
    assert!(validate_inventory(vec![device("")]).is_err());
    assert!(validate_inventory(vec![device("cpu"); 129]).is_err());
    let mut snapshot = Snapshot::default();
    publish(
        &mut snapshot,
        &device("cpu1"),
        &mut State::default(),
        Ok(sample(100, 100, 1)),
    );
    publish(
        &mut snapshot,
        &device("cpu2"),
        &mut State::default(),
        Ok(sample(100, 100, 1)),
    );
    let ids: BTreeSet<_> = snapshot.sensors.iter().map(|s| &s.id).collect();
    assert_eq!(ids.len(), 4);
    let mut state = State::default();
    let first = run(&mut state, Ok(sample(100, 100, 1)));
    let mut reordered = sample(1100, 110, 3);
    reordered.metadata.channels.reverse();
    reordered.values.reverse();
    let next = run(&mut state, Ok(reordered));
    assert_eq!(first.sensors[0].id, next.sensors[1].id);
    assert_eq!(next.readings[1].availability, Availability::WarmingUp);
}
