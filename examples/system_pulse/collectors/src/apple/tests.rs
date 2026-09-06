use super::*;

#[test]
fn residency_and_weighted_frequency_use_actual_states() {
    let states = vec![("OFF".into(), 250), ("P1".into(), 375), ("P2".into(), 375)];
    let result = residency(&states, &[0, 400_000_000, 800_000_000]);
    assert_eq!(result.0.unwrap(), 75.0);
    assert_eq!(result.1.unwrap(), 600_000_000.0);
}
#[test]
fn power_uses_measured_elapsed() {
    assert_eq!(power(3_000_000_000, 1_500_000_000).unwrap(), 2.0);
}

#[test]
fn unknown_active_mapping_preserves_activity() {
    let (usage, frequency) = residency(&[("OFF".into(), 250), ("P1".into(), 750)], &[]);
    assert_eq!(usage.unwrap(), 75.0);
    assert!(frequency.is_err());
}
#[test]
fn inactive_frequency_and_invalid_arithmetic_are_not_measurements() {
    assert!(residency(&[("OFF".into(), 10)], &[0]).1.is_err());
    assert!(
        residency(&[("OFF".into(), u64::MAX), ("P1".into(), 1)], &[0, 1])
            .0
            .is_err()
    );
    assert!(
        residency(&[("OFF".into(), 0), ("P1".into(), u64::MAX)], &[0, 2])
            .1
            .is_err()
    );
    assert!(residency(&[("renamed".into(), 3)], &[0]).0.is_err());
    assert!(power(1, 0).is_err());
}
#[test]
fn table_decoder_rejects_wrong_layout() {
    assert_eq!(decode_table(&[0; 8]).unwrap(), vec![0]);
    assert!(decode_table(&[0; 7]).is_err());
    assert!(decode_table(&[]).is_err());
    assert!(decode_table(&[1; 8]).is_err());
}
#[test]
fn native_identity_is_order_and_name_independent() {
    let a = identity("IODeviceTree:/arm-io/sgx@1", 55, true);
    let b = identity("IODeviceTree:/arm-io/sgx@2", 56, true);
    assert_ne!(a.unwrap(), b.unwrap());
    assert_eq!(
        identity("IODeviceTree:/arm-io/sgx@1", 55, true),
        identity("IODeviceTree:/arm-io/sgx@1", 999, true)
    );
    assert!(identity("", 55, true).is_err());
    assert!(identity("IOService:/GPU", 55, true).is_err());
}

fn energy(end: u64, value: u64) -> RawObservation {
    raw_window(
        "IOReport/Energy Model/GPU Energy;nJ",
        end.saturating_sub(1),
        end,
        [
            ("driver_id", 55),
            ("channel_id", 7),
            ("format", 1),
            ("encoded_unit", ENERGY_UNIT),
            ("energy_nj", value),
        ],
    )
}
#[test]
fn counter_failure_regression_units_and_time_reset_baselines() {
    let mut counter = Baseline::default();
    assert_eq!(
        counter
            .read("power", Ok(energy(10, 0)), 55, false)
            .0
            .availability,
        Availability::WarmingUp
    );
    assert_eq!(
        counter
            .read("power", Ok(energy(1_500_000_010, 3_000_000_000)), 55, false)
            .0
            .value,
        Some(2.0)
    );
    assert!(
        counter
            .read("power", Err("channel absent".into()), 55, false)
            .0
            .value
            .is_none()
    );
    assert_eq!(
        counter
            .read("power", Ok(energy(2_000_000_010, 4_000_000_000)), 55, false)
            .0
            .availability,
        Availability::WarmingUp
    );
    assert!(
        counter
            .read("power", Ok(energy(3_000_000_010, 0)), 55, false)
            .0
            .value
            .is_none()
    );
    assert_eq!(
        counter
            .read("power", Ok(energy(4_000_000_010, 10)), 55, false)
            .0
            .availability,
        Availability::WarmingUp
    );
    let mut bad = energy(5_000_000_010, 100);
    bad.integers.insert("encoded_unit".into(), 0);
    assert!(counter.read("power", Ok(bad), 55, false).0.value.is_none());
    assert_eq!(
        counter
            .read("power", Ok(energy(7, 1)), 55, false)
            .0
            .availability,
        Availability::WarmingUp
    );
    assert!(
        counter
            .read("power", Ok(energy(7, 2)), 55, false)
            .0
            .value
            .is_none()
    );
    assert_eq!(
        counter
            .read("power", Ok(energy(8, 3)), 55, false)
            .0
            .availability,
        Availability::WarmingUp
    );
}
#[test]
fn registry_instance_change_and_channel_layout_cannot_bridge() {
    let mut counter = Baseline::default();
    counter.read("power", Ok(energy(1, 1)), 55, false);
    assert!(
        counter
            .read("power", Ok(energy(2, 2)), 66, false)
            .0
            .value
            .is_none()
    );
    let mut changed = energy(3, 3);
    changed.integers.insert("channel_id".into(), 8);
    counter.read("power", Ok(energy(2, 2)), 55, false);
    assert!(
        counter
            .read("power", Ok(changed), 55, false)
            .0
            .value
            .is_none()
    );
}

fn device(path: &str, runtime: u64, end: u64) -> DeviceInput {
    let mut e = energy(end, end);
    e.integers.insert("driver_id".into(), runtime);
    DeviceInput {
        path: path.into(),
        name: "Apple GPU".into(),
        runtime,
        unified: true,
        states: Err("GPUPH absent".into()),
        energy: Ok(e),
        allocated: Ok(raw_window(
            "IOKit/PerformanceStatistics/Alloc system memory;bytes",
            end,
            end,
            [("bytes", 8192), ("driver_id", runtime)],
        )),
        in_use: Err("In use system memory absent".into()),
        temperatures: vec![(
            "hid".into(),
            "HID/GPU MTR Temp Sensor;Celsius".into(),
            Ok({
                let mut o = raw_window("HID", end, end, []);
                o.decimals.insert("celsius".into(), 45.0);
                o
            }),
        )],
    }
}
#[test]
fn reordering_names_absence_reappearance_and_instance_changes_preserve_identity() {
    let mut collector = Collector::default();
    let a = "IODeviceTree:/arm-io/sgx@1";
    let b = "IODeviceTree:/arm-io/sgx@2";
    let mut first = Snapshot::default();
    collector.append(&mut first, Ok(vec![device(a, 55, 1), device(b, 66, 1)]));
    let mut second = Snapshot::default();
    collector.append(&mut second, Ok(vec![device(b, 66, 2), device(a, 55, 2)]));
    assert_eq!(
        first.monitors.iter().map(|v| &v.id).collect::<Vec<_>>(),
        second.monitors.iter().map(|v| &v.id).collect::<Vec<_>>()
    );
    assert_ne!(first.monitors[0].id, first.monitors[1].id);
    let mut empty = Snapshot::default();
    collector.append(&mut empty, Ok(vec![]));
    assert!(collector.baselines.is_empty());
    let mut back = Snapshot::default();
    collector.append(&mut back, Ok(vec![device(a, 99, 3)]));
    assert_eq!(back.monitors[0].id, first.monitors[0].id);
    assert_eq!(
        back.readings
            .iter()
            .find(|r| r.sensor_id.ends_with("/power"))
            .unwrap()
            .availability,
        Availability::WarmingUp
    );
    let mut changed = Snapshot::default();
    collector.append(&mut changed, Ok(vec![device(a, 100, 4)]));
    assert_eq!(
        changed
            .readings
            .iter()
            .find(|r| r.sensor_id.ends_with("/power"))
            .unwrap()
            .availability,
        Availability::WarmingUp
    );
}
#[test]
fn independent_memory_temperature_and_power_survive_missing_states() {
    let mut collector = Collector::default();
    let mut snapshot = Snapshot::default();
    collector.append(
        &mut snapshot,
        Ok(vec![device("IODeviceTree:/arm-io/sgx@1", 55, 1)]),
    );
    let memory = snapshot
        .sensors
        .iter()
        .find(|r| r.id.ends_with("/shared-allocated"))
        .unwrap();
    assert_eq!(memory.kind, SensorKind::Scalar);
    assert_eq!(memory.unit, Unit::Bytes);
    assert_eq!(memory.scale, None);
    assert!(memory.scope.contains("shared"));
    assert_eq!(
        snapshot
            .readings
            .iter()
            .find(|r| r.sensor_id.ends_with("/shared-allocated"))
            .unwrap()
            .value,
        Some(8192.0)
    );
    assert_eq!(
        snapshot
            .readings
            .iter()
            .find(|r| r.sensor_id.ends_with("/temperature-hid"))
            .unwrap()
            .value,
        Some(45.0)
    );
    assert!(
        snapshot
            .readings
            .iter()
            .find(|r| r.sensor_id.ends_with("/fan"))
            .unwrap()
            .value
            .is_none()
    );
}
#[test]
fn duplicate_physical_candidates_and_wrong_accelerator_memory_are_rejected() {
    let mut collector = Collector::default();
    let mut snapshot = Snapshot::default();
    let path = "IODeviceTree:/arm-io/sgx@1";
    collector.append(
        &mut snapshot,
        Ok(vec![device(path, 55, 1), device(path, 66, 1)]),
    );
    assert!(snapshot.monitors.is_empty());
    assert!(!snapshot.diagnostics.is_empty());
    let mut wrong = device(path, 55, 2);
    wrong
        .allocated
        .as_mut()
        .unwrap()
        .integers
        .insert("driver_id".into(), 66);
    let mut snapshot = Snapshot::default();
    collector.append(&mut snapshot, Ok(vec![wrong]));
    assert!(
        snapshot
            .readings
            .iter()
            .find(|r| r.sensor_id.ends_with("/shared-allocated"))
            .unwrap()
            .value
            .is_none()
    );
}

#[test]
fn smc_guard_preserves_raw_and_recovers_without_affecting_hid() {
    let observation = |v| {
        let mut o = raw_window(
            "SMC/Tg05;flt little-endian;Celsius",
            1,
            2,
            [("bytes_le", (v as f32).to_bits() as u64)],
        );
        o.decimals.insert("celsius".into(), v);
        o
    };
    let low = smc_temperature("temp", Ok(observation(9.2)));
    assert_eq!(low.availability, Availability::Unavailable);
    assert_eq!(low.value, None);
    assert!(low.reason.unwrap().contains("plausibility"));
    assert_eq!(low.observations.len(), 1);
    assert_eq!(
        smc_temperature("temp", Ok(observation(15.0))).value,
        Some(15.0)
    );
    assert_eq!(
        smc_temperature("temp", Ok(observation(49.0))).value,
        Some(49.0)
    );
    assert_eq!(
        scalar("hid", Ok(observation(9.2)), None, true).value,
        Some(9.2)
    );
    assert_eq!(
        smc_temperature("temp", Err("permission denied".into())).availability,
        Availability::Failed
    );
    assert_eq!(
        smc_temperature("temp", Err(SourceFailure::unavailable("key absent"))).availability,
        Availability::Unavailable
    );
}
#[test]
fn native_counts_and_smc_layout_codes_and_units_are_checked() {
    assert_eq!(bounded_count(2, 16).unwrap(), 2);
    assert!(bounded_count(-1, 16).is_err());
    assert!(bounded_count(17, 16).is_err());
    let bytes = 45.0f32.to_le_bytes();
    let kind = u32::from_be_bytes(*b"flt ");
    assert_eq!(decode_smc(kind, &bytes, 0, 80, 0, 0).unwrap(), 45.0);
    assert!(decode_smc(kind, &bytes, 1, 80, 0, 0).is_err());
    assert!(decode_smc(kind, &bytes, 0, 79, 0, 0).is_err());
    assert!(decode_smc(kind, &bytes, 0, 80, 1, 0).is_err());
    assert!(decode_smc(kind, &bytes, 0, 80, 0, 1).is_err());
    assert!(decode_smc(0, &bytes, 0, 80, 0, 0).is_err());
    assert!(decode_smc(kind, &bytes[..3], 0, 80, 0, 0).is_err());
    assert!(decode_smc(kind, &f32::NAN.to_le_bytes(), 0, 80, 0, 0).is_err());
}

#[test]
fn hid_names_require_the_attributed_gpu_sensor_family() {
    assert!(attributed_hid("GPU MTR Temp Sensor"));
    assert!(attributed_hid("GPU MTR Temp Sensor0"));
    assert!(!attributed_hid("CPU MTR Temp Sensor0"));
    assert!(!attributed_hid("GPU temperature guess"));
    assert!(!attributed_hid("GPU MTR Temp Sensor anything"));
}
