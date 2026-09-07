"""Native source shape tests use explicit operands, never fixture PASS flags."""

import copy
import struct
import unittest

try:
    from gpu_apple_capture import independent_inventory, normalize_observer
except ImportError:
    independent_inventory = normalize_observer = None


def raw_frame():
    channels = [
        dict(
            group="GPU Stats",
            subgroup="GPU Performance States",
            channel="GPUPH",
            unit="24Mticks",
            encoded_unit=72058115876454424,
            format=2,
            driver_id=19,
            channel_id=9,
            states=[dict(name="OFF", residency=100), dict(name="P1", residency=20)],
        ),
        dict(
            group="Energy Model",
            subgroup="",
            channel="GPU Energy",
            unit="nJ",
            encoded_unit=216173288919924736,
            format=1,
            driver_id=19,
            channel_id=7,
            integer=1000,
        ),
    ]
    return dict(
        schema=1,
        pid=15,
        clock_anchor=dict(monotonic_before_ns=1, monotonic_after_ns=2, unix_ns=1000),
        devices=[
            dict(
                name="Apple M1 Pro",
                physical_path="IODeviceTree:/arm-io/sgx@4000000",
                registry_id=19,
                has_unified_memory=True,
                ancestry=["IOService:/gpu/AGX"],
            )
        ],
        metadata=[
            {k: v for k, v in ch.items() if k not in ("integer", "states")}
            for ch in channels
        ],
        ioreport=dict(start=10, end=11, channels=channels),
        memory=[
            dict(
                start=12,
                end=13,
                registry_id=19,
                values={"Alloc system memory": 4096, "In use system memory": 1024},
            )
        ],
        tables=[
            dict(
                start=14,
                end=15,
                registry_id=21,
                physical_path="IODeviceTree:/arm-io/pmgr@10000000",
                voltage_states9_hex=struct.pack("<IIII", 0, 400, 300000000, 500).hex(),
            )
        ],
        smc=[
            dict(
                key=k,
                start=16,
                end=17,
                **(
                    dict(
                        return_code=0,
                        output_size=80,
                        data_size=4,
                        data_type=1718383648,
                        result=0,
                        status=0,
                        raw_hex=struct.pack("<f", 20.0).hex(),
                    )
                    if k in ("Tg05", "Tg0D")
                    else dict(
                        return_code=0,
                        output_size=80,
                        data_size=0,
                        data_type=0,
                        result=132,
                        status=0,
                        raw_hex="",
                    )
                ),
            )
            for k in ("Tg05", "Tg0D", "Tg0L", "Tg0T")
        ],
        hid=dict(products=["CPU temperature"], rows=[], service_count=1),
    )


class AppleCaptureTests(unittest.TestCase):
    def test_independent_inventory_demands_all_fields(self):
        self.assertIsNotNone(
            independent_inventory, "Apple native inventory adapter missing"
        )
        inventory = independent_inventory(raw_frame())
        self.assertEqual(len(inventory["fields"]), 11)
        fields = {f["sensor_id"].rsplit("/", 1)[-1]: f for f in inventory["fields"]}
        self.assertEqual(fields["shared-allocated"]["kind"], "Scalar")
        self.assertEqual(fields["frequency"]["frequency_hz"], [0, 300000000])
        self.assertEqual(fields["temperature-smc-Tg0L"]["limitation"], "absent")
        self.assertEqual(fields["temperature-hid"]["limitation"], "absent")

    def test_wrong_device_unit_table_source_and_omissions_rejected(self):
        self.assertIsNotNone(
            independent_inventory, "Apple native inventory adapter missing"
        )
        changes = [
            lambda f: f["ioreport"]["channels"][0].update(driver_id=20),
            lambda f: f["ioreport"]["channels"][1].update(channel="GPU0"),
            lambda f: f["ioreport"]["channels"][0].update(unit="percent"),
            lambda f: f["ioreport"]["channels"][0]["states"][1].update(name="unknown"),
            lambda f: f["tables"][0].update(voltage_states9_hex="0000"),
            lambda f: f["memory"].append(copy.deepcopy(f["memory"][0])),
            lambda f: f["smc"].pop(),
            lambda f: f.pop("hid"),
        ]
        for change in changes:
            f = raw_frame()
            change(f)
            with self.subTest(frame=f), self.assertRaises((AssertionError, KeyError)):
                independent_inventory(f)

    def test_nameless_hid_service_is_retained_as_unattributable(self):
        frame = raw_frame()
        frame["hid"]["products"].append(None)
        frame["hid"]["service_count"] += 1
        inventory = independent_inventory(frame)
        field = next(
            f
            for f in inventory["fields"]
            if f["sensor_id"].endswith("/temperature-hid")
        )
        self.assertEqual(field["limitation"], "unattributable")

    def test_retained_replay_rejects_normalized_invention(self):
        import gpu_evidence

        self.assertTrue(
            hasattr(gpu_evidence, "replay_native"), "raw report replay missing"
        )
        frame = raw_frame()
        inventory = independent_inventory(frame)
        normalized = normalize_observer(frame, inventory)
        gpu_evidence.replay_native(frame, [frame], inventory, [normalized])
        changed = copy.deepcopy(normalized)
        changed["samples"][0]["values"]["ticks/P1"] += 1
        with self.assertRaises(AssertionError):
            gpu_evidence.replay_native(frame, [frame], inventory, [changed])
        omitted = copy.deepcopy(inventory)
        omitted["fields"].pop()
        with self.assertRaises(AssertionError):
            gpu_evidence.replay_native(frame, [frame], omitted, [normalized])

    def test_normalization_retains_integer_and_temperature_operands(self):
        self.assertIsNotNone(normalize_observer, "Apple native normalization missing")
        frame = raw_frame()
        inventory = independent_inventory(frame)
        normalized = normalize_observer(frame, inventory)
        values = [s["values"] for s in normalized["samples"]]
        self.assertIn(dict(energy_nj=1000), values)
        self.assertIn(dict(celsius=20.0), values)


if __name__ == "__main__":
    unittest.main()
