"""Adversarial operand evidence; no production conversion imports."""

import unittest
import struct

try:
    from gpu_arithmetic import verify_reading, bracket, weighted_frequency
except ImportError:
    verify_reading = bracket = weighted_frequency = None


class ArithmeticTests(unittest.TestCase):
    def setUp(self):
        self.field = dict(
            sensor_id="gpu:apple:device/power",
            formula="apple-energy",
            source="IOReport/Energy Model/GPU Energy;nJ",
            scope="device",
            unit="Watts",
            kind="Power",
            driver_id=19,
            channel_id=7,
        )
        self.policy = dict(max_query_ns=100, max_gap_ns=100, rounding_ulps=4)
        self.reading = dict(
            sensor_id=self.field["sensor_id"],
            value=2.0,
            total=None,
            availability="Available",
            reason=None,
            observations=[],
        )
        for end, energy in [(1000, 100), (2000, 2100)]:
            self.reading["observations"].append(
                dict(
                    source=self.field["source"],
                    read_started_ns=end - 10,
                    captured_ns=end,
                    integers=dict(
                        driver_id=19,
                        channel_id=7,
                        format=1,
                        encoded_unit=216173288919924736,
                        energy_nj=energy,
                    ),
                    decimals={},
                )
            )
        self.samples = [
            dict(
                start=t - 10,
                end=t,
                source=self.field["source"],
                driver_id=19,
                channel_id=7,
                values={"energy_nj": e},
            )
            for t, e in [(980, 90), (1020, 110), (1980, 2090), (2020, 2110)]
        ]
        self.sensor = dict(
            id=self.field["sensor_id"],
            source=self.field["source"],
            scope="device",
            unit="Watts",
            kind="Power",
        )

    def verify(self):
        self.assertIsNotNone(
            verify_reading, "GPU arithmetic verifier is not implemented"
        )
        return verify_reading(
            self.field,
            self.sensor,
            self.reading,
            self.samples,
            (0, 0),
            (0, 0),
            self.policy,
        )

    def test_actual_irregular_elapsed_and_native_brackets(self):
        self.verify()

    def test_adversarial_readings(self):
        changes = {
            "wrong value": lambda: self.reading.update(value=1.0),
            "wrong binary sensor": lambda: self.reading.update(sensor_id="different"),
            "wrong unit": lambda: self.sensor.update(unit="Bytes"),
            "wrong source": lambda: self.sensor.update(source="PMGR/GPU0;mJ"),
            "wrong scope": lambda: self.sensor.update(scope="package"),
            "invented total": lambda: self.reading.update(total=16000),
            "changed elapsed": lambda: self.reading["observations"][1].update(
                captured_ns=1900
            ),
            "missing window": lambda: self.reading["observations"][0].pop(
                "read_started_ns"
            ),
            "counter reset": lambda: self.reading["observations"][1]["integers"].update(
                energy_nj=1
            ),
            "wrong device": lambda: self.reading["observations"][1]["integers"].update(
                driver_id=20
            ),
            "wrong raw unit": lambda: self.reading["observations"][1][
                "integers"
            ].update(encoded_unit=1),
            "missing field": lambda: self.reading["observations"][1]["integers"].pop(
                "energy_nj"
            ),
            "native mismatch": lambda: self.samples[-1]["values"].update(
                energy_nj=2000
            ),
            "stale observation": lambda: self.samples[0].update(start=0, end=1),
            "unavailable current": lambda: self.reading.update(
                availability="Unavailable", reason="denied"
            ),
            "unknown status": lambda: self.reading.update(availability="PASS"),
        }
        for name, change in changes.items():
            with self.subTest(name=name):
                self.setUp()
                change()
                self.assertIsNotNone(
                    verify_reading, "GPU arithmetic verifier is not implemented"
                )
                with self.assertRaises(
                    (AssertionError, KeyError, ValueError, TypeError)
                ):
                    self.verify()

    def test_overlapping_query_is_not_bracket(self):
        self.assertIsNotNone(bracket, "GPU bracket verifier is not implemented")
        with self.assertRaises(AssertionError):
            bracket(
                100,
                (10, 20),
                [dict(start=9, end=11, value=90), dict(start=19, end=21, value=110)],
                self.policy,
            )

    def test_frequency_mapping_and_active_denominator(self):
        self.assertIsNotNone(
            weighted_frequency, "GPU frequency verifier is not implemented"
        )
        self.assertEqual(
            weighted_frequency({"OFF": 20, "P1": 10, "P2": 30}, [0, 300, 700]), 600
        )
        for states, table in [
            ({"OFF": 1, "P1": 0}, [0, 300]),
            ({"OFF": 1, "P1": 1, "P2": 1}, [0, 300]),
            ({"OFF": 1, "unknown": 1}, [0, 300]),
        ]:
            with self.assertRaises(AssertionError):
                weighted_frequency(states, table)

    def test_smc_guard_decodes_original_bytes_and_does_not_touch_hid(self):
        self.field.update(
            formula="apple-smc",
            source="SMC/Tg05;flt little-endian;Celsius",
            unit="Celsius",
            kind="Temperature",
            precision=0,
        )
        self.field.pop("driver_id")
        self.field.pop("channel_id")
        self.sensor.update(
            source=self.field["source"], unit="Celsius", kind="Temperature"
        )
        bits = int.from_bytes(struct.pack("<f", 9.2), "little")
        value = struct.unpack("<f", struct.pack("<I", bits))[0]
        self.reading.update(
            value=None,
            availability="Unavailable",
            reason="Conservative SMC software plausibility guard",
        )
        self.reading["observations"] = [
            dict(
                source=self.field["source"],
                read_started_ns=990,
                captured_ns=1000,
                integers=dict(
                    key_fourcc=int.from_bytes(b"Tg05", "big"),
                    type_fourcc=int.from_bytes(b"flt ", "big"),
                    size=4,
                    bytes_le=bits,
                    return_code=0,
                    response_size=80,
                    result=0,
                    status=0,
                ),
                decimals=dict(celsius=value),
            )
        ]
        self.samples = [
            dict(
                start=t - 10,
                end=t,
                source=self.field["source"],
                values=dict(celsius=value),
            )
            for t in (980, 1020)
        ]
        self.verify()
        self.reading.update(value=value, availability="Available", reason=None)
        with self.assertRaises(AssertionError):
            self.verify()
        self.field.update(formula="apple-hid", source="HID/GPU MTR Temp Sensor;Celsius")
        self.sensor["source"] = self.field["source"]
        self.reading["observations"][0]["source"] = self.field["source"]
        self.reading["observations"][0]["integers"] = dict(
            event_type=15, event_field=15 << 16
        )
        for s in self.samples:
            s["source"] = self.field["source"]
        self.verify()


class ResidencyTests(unittest.TestCase):
    def fixture(self, active=10):
        from test_gpu_apple_capture import raw_frame
        from gpu_apple_capture import independent_inventory

        raw = raw_frame()
        inv = independent_inventory(raw)
        field = next(f for f in inv["fields"] if f["formula"] == "apple-frequency")
        sensor = dict(
            id=field["sensor_id"],
            **{k: field[k] for k in ("source", "scope", "unit", "kind")},
        )
        observations = []
        samples = []
        for t, off, p1 in [(1000, 100, 20), (2000, 120, 20 + active)]:
            integers = dict(
                driver_id=19,
                channel_id=9,
                format=2,
                encoded_unit=72058115876454424,
                state_count=2,
                **{
                    "ticks/OFF": off,
                    "ticks/P1": p1,
                    "hz/OFF": 0,
                    "hz/P1": 300000000,
                    "table/driver_id": 21,
                    "table/byte_length": 16,
                    "table/read_started_ns": t - 10,
                    "table/captured_ns": t,
                },
            )
            for n, pair in enumerate(
                struct.iter_unpack("<Q", bytes.fromhex(field["table_hex"]))
            ):
                integers["table/pair_le/" + str(n)] = pair[0]
            observations.append(
                dict(
                    source=field["raw_source"],
                    read_started_ns=t - 10,
                    captured_ns=t,
                    integers=integers,
                    decimals={},
                )
            )
            for at in (t - 20, t + 20):
                samples.append(
                    dict(
                        source=field["raw_source"],
                        driver_id=19,
                        channel_id=9,
                        start=at - 10,
                        end=at,
                        values={"ticks/OFF": off, "ticks/P1": p1},
                    )
                )
                samples.append(
                    dict(
                        source=field["table_source"],
                        driver_id=21,
                        start=at - 10,
                        end=at,
                        values={
                            "pair_le/" + str(n): p[0]
                            for n, p in enumerate(
                                struct.iter_unpack(
                                    "<Q", bytes.fromhex(field["table_hex"])
                                )
                            )
                        },
                    )
                )
        reading = dict(
            sensor_id=field["sensor_id"],
            value=300000000 if active else None,
            total=None,
            availability="Available" if active else "Unavailable",
            reason=None if active else "No active residency",
            observations=observations,
        )
        return field, sensor, reading, samples

    def test_frequency_uses_raw_table_and_no_active_is_unavailable(self):
        policy = dict(max_query_ns=100, max_gap_ns=100, rounding_ulps=4)
        for active in (0, 10):
            field, sensor, reading, samples = self.fixture(active)
            self.assertEqual(
                verify_reading(field, sensor, reading, samples, (0, 0), (0, 0), policy),
                bool(active),
            )
        for key, value in [
            ("table/pair_le/1", 1),
            ("table/driver_id", 22),
            ("table/read_started_ns", 0),
        ]:
            field, sensor, reading, samples = self.fixture()
            reading["observations"][1]["integers"][key] = value
            with self.subTest(key=key), self.assertRaises(AssertionError):
                verify_reading(field, sensor, reading, samples, (0, 0), (0, 0), policy)


if __name__ == "__main__":
    unittest.main()
