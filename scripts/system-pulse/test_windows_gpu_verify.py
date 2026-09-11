"""Safe violating examples for Windows GPU acceptance boundaries."""
import copy
import unittest

from performance_compare import InvalidMeasurement
from windows_gpu_verify import validate_snapshot, validate_scheduler, validate_memory, validate_independent, validate_ui, validate_preservation


def fixture():
    inventory = [dict(PNPDeviceID=r"PCI\VEN_8086&DEV_1234\ONE", Status="OK")]
    identity = "windows-gpu:" + inventory[0]["PNPDeviceID"]
    snapshot = dict(monitors=[dict(id=identity, kind="Gpu", summary_sensor_id=identity + "/usage")], sensors=[], readings=[])
    for suffix in ("usage", "vram", "shared-used", "temperature", "power", "clock-graphics", "clock-memory"):
        sid = identity + "/" + suffix
        snapshot["sensors"].append(dict(id=sid, monitor_id=identity, kind="Scalar"))
        snapshot["readings"].append(dict(sensor_id=sid, availability="Unavailable", value=None, total=None, reason="No supported source", observations=[]))
    return inventory, snapshot


class InventoryTests(unittest.TestCase):
    def test_detected_device_with_missing_telemetry_passes(self):
        inventory, snapshot = fixture()
        validate_snapshot(snapshot, inventory)

    def test_missing_duplicate_changed_identity_and_fabricated_zero_fail(self):
        changes = [lambda s: s["monitors"].clear(),
                   lambda s: s["monitors"].append(copy.deepcopy(s["monitors"][0])),
                   lambda s: s["monitors"][0].update(id="windows-gpu:0"),
                   lambda s: s["readings"][0].update(value=0),
                   lambda s: s["readings"][0].update(reason=None),
                   lambda s: s["readings"].pop()]
        for change in changes:
            inventory, snapshot = fixture()
            change(snapshot)
            with self.assertRaises(InvalidMeasurement):
                validate_snapshot(snapshot, inventory)

    def test_three_vendors_and_identical_models_keep_distinct_ids(self):
        inventory, snapshot = fixture()
        for vendor in ("1002", "10DE"):
            other_inventory, other = fixture()
            old = other["monitors"][0]["id"]
            other_inventory[0]["PNPDeviceID"] = other_inventory[0]["PNPDeviceID"].replace("8086", vendor)
            new = "windows-gpu:" + other_inventory[0]["PNPDeviceID"]
            other["monitors"][0].update(id=new, summary_sensor_id=new + "/usage")
            for sensor in other["sensors"]:
                sensor.update(id=sensor["id"].replace(old, new), monitor_id=new)
            for reading in other["readings"]:
                reading["sensor_id"] = reading["sensor_id"].replace(old, new)
            inventory.extend(other_inventory)
            for key in snapshot:
                snapshot[key].extend(other[key])
        self.assertEqual(len(validate_snapshot(snapshot, inventory)), 3)


class ReadingTests(unittest.TestCase):
    def test_preservation_rejects_diagnostics_missing_processes_and_wrong_quit(self):
        ui = dict(selected_screen="GPU", pid=42, sequence=9, controls=[
            dict(name=name, offscreen=False) for name in
            ("Intel Iris", "GPU utilization", "Dedicated GPU memory", "Shared GPU memory", "Unavailable")])
        record = dict(diagnostics_enabled=False, diagnostic_rows=[dict(pid=1, name="init")],
                      normal_rows=[dict(pid=42, name="system-pulse.exe")], normal_gpu=ui,
                      quit=dict(pid=42, menu_owner=42, exit_code=0))
        validate_preservation(record, [dict(Name="Intel Iris")])
        for change in (lambda r: r.update(diagnostics_enabled=True),
                       lambda r: r.update(normal_rows=[]),
                       lambda r: r["quit"].update(menu_owner=1),
                       lambda r: r["quit"].update(exit_code=1)):
            bad = copy.deepcopy(record)
            change(bad)
            with self.assertRaises(InvalidMeasurement):
                validate_preservation(bad, [dict(Name="Intel Iris")])

    def test_independent_counters_match_luid_and_reject_other_adapter_or_wrong_values(self):
        sid = "windows-gpu:test"
        frame = dict(monitors=[dict(id=sid, kind="Gpu")], readings=[
            dict(sensor_id=sid + "/" + suffix, availability="Available", value=value,
                 observations=[dict(integers=dict(adapter_luid=9))])
            for suffix, value in (("usage", 50), ("vram", 128), ("shared-used", 1024))])
        sample = dict(counters=[dict(instance="luid_0x00000000_0x00000009_phys_0_eng_0_engtype_3D",
                                    status=0, value=value, path="\\" + path)
                               for path, value in (("Utilization Percentage", 50), ("Dedicated Usage", 128), ("Shared Usage", 1024))])
        validate_independent([frame] * 3, [sample] * 8)
        wrong = copy.deepcopy(sample)
        for counter in wrong["counters"]:
            counter["instance"] = counter["instance"].replace("00000009", "00000008")
        with self.assertRaises(InvalidMeasurement):
            validate_independent([frame] * 3, [wrong] * 8)
        wrong = copy.deepcopy(sample)
        wrong["counters"][0]["value"] = 1
        with self.assertRaises(InvalidMeasurement):
            validate_independent([frame] * 3, [wrong] * 8)

    def test_native_ui_needs_device_and_physical_memory_labels(self):
        record = dict(selected_screen="GPU", pid=1, sequence=4, controls=[
            dict(name=name, offscreen=False) for name in
            ("Intel Iris", "GPU utilization", "Dedicated GPU memory", "Shared GPU memory", "Unavailable")])
        validate_ui(record, [dict(Name="Intel Iris")])
        record["controls"] = [c for c in record["controls"] if c["name"] != "Shared GPU memory"]
        with self.assertRaises(InvalidMeasurement):
            validate_ui(record, [dict(Name="Intel Iris")])

    def test_scheduler_recomputes_busiest_engine_and_rejects_wrong_value(self):
        observations = []
        for node, ticks in ((0, 5_000_000), (1, 2_500_000)):
            for ns, value in ((1_000_000_000, 0), (2_000_000_000, ticks)):
                observations.append(dict(captured_ns=ns, integers=dict(adapter_luid=9, node_id=node, running_ticks=value)))
        reading = dict(availability="Available", value=50., observations=observations)
        validate_scheduler(reading)
        for bad in (0., 75., float("nan")):
            with self.assertRaises(InvalidMeasurement):
                validate_scheduler(dict(reading, value=bad))

    def test_shared_memory_cannot_acquire_dedicated_capacity(self):
        reading = dict(availability="Available", value=2048, total=None,
                       observations=[dict(integers=dict(shared_bytes=2048, dedicated_bytes=128, dedicated_limit_bytes=512))])
        validate_memory(reading, True)
        with self.assertRaises(InvalidMeasurement):
            validate_memory(dict(reading, total=512), True)
        with self.assertRaises(InvalidMeasurement):
            validate_memory(dict(reading, value=0), True)


if __name__ == "__main__":
    unittest.main()
