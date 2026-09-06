"""Apple native inventory and normalization from the independent Objective-C reader.

The complete inventory is established before the collector starts. These routines
are also rerun on the retained native stdout during report ingestion.
"""

import math
import re
import struct

from host_accuracy import require
from gpu_arithmetic import integer, state_names

STATE_SOURCE = "IOReport/GPU Stats/GPU Performance States/GPUPH;24Mticks"
ENERGY_SOURCE = "IOReport/Energy Model/GPU Energy;nJ"
M1_KEYS = ("Tg05", "Tg0D", "Tg0L", "Tg0T")


def unique(rows, key, value):
    selected = [r for r in rows if r.get(key) == value]
    require(len(selected) == 1, f"missing/ambiguous native {key}={value}")
    return selected[0]


def native_channels(frame, device):
    rows = frame["ioreport"]["channels"]
    require(0 < len(rows) <= 512, "invalid native channel count")
    result = {}
    for name, group, unit, encoded, fmt in (
        ("GPUPH", "GPU Stats", "24Mticks", 72058115876454424, 2),
        ("GPU Energy", "Energy Model", "nJ", 216173288919924736, 1),
    ):
        row = unique(
            [r for r in rows if r["driver_id"] == device["registry_id"]],
            "channel",
            name,
        )
        require(
            row["group"] == group
            and row["unit"] == unit
            and row["encoded_unit"] == encoded
            and row["format"] == fmt
            and integer(row["channel_id"]) > 0,
            "wrong IOReport source/unit/format",
        )
        if fmt == 2:
            require(
                row["subgroup"] == "GPU Performance States",
                "wrong native state subgroup",
            )
            require(
                len({s["name"] for s in row["states"]}) == len(row["states"]),
                "duplicate native state",
            )
            state_names({s["name"]: integer(s["residency"]) for s in row["states"]})
        else:
            integer(row["integer"])
        result[name] = row
    return result


def frequency_table(frame):
    require(len(frame["tables"]) == 1, "frequency table attribution ambiguous")
    table = frame["tables"][0]
    data = bytes.fromhex(table["voltage_states9_hex"])
    require(
        8 <= len(data) <= 1024 and len(data) % 8 == 0,
        "invalid native frequency table bytes",
    )
    pairs = list(struct.iter_unpack("<II", data))
    hz = [p[0] for p in pairs]
    require(
        hz[0] == 0 and all(a < b for a, b in zip(hz, hz[1:])),
        "unknown native table mapping",
    )
    return hz


def smc_value(row):
    code = row.get("return_code", row.get("return"))
    require(
        code == 0 and row["output_size"] == 80 and row["status"] == 0,
        "native SMC query failed",
    )
    if row["result"] == 132:
        return None
    require(
        row["result"] == 0 and row["data_type"] == 1718383648 and row["data_size"] == 4,
        "native SMC type/size/result invalid",
    )
    raw = bytes.fromhex(row["raw_hex"])
    require(len(raw) == 4, "native SMC bytes missing")
    value = struct.unpack("<f", raw)[0]
    require(math.isfinite(value), "nonfinite native SMC value")
    return value


def independent_inventory(frame):
    require(
        frame["schema"] == 1 and len(frame["devices"]) == 1,
        "unverified Apple multi-device attribution",
    )
    device = dict(frame["devices"][0])
    require(
        device["name"]
        in ("Apple M1", "Apple M1 Pro", "Apple M1 Max", "Apple M1 Ultra"),
        "native acceptance requires a reviewed model-specific SMC inventory profile",
    )
    require(
        device["physical_path"].startswith("IODeviceTree:/")
        and "/sgx@" in device["physical_path"]
        and device["has_unified_memory"] is True
        and integer(device["registry_id"]) > 0,
        "unsupported native physical GPU identity",
    )
    monitor = "gpu:apple:" + device["physical_path"]
    device["monitor_id"] = monitor
    channels = native_channels(frame, device)
    hz = frequency_table(frame)
    scope = f"{device['physical_path']}; Metal registry ID {device['registry_id']}; hasUnifiedMemory=true; physical GPU"
    fields = []

    def field(suffix, formula, unit, kind, source, **extra):
        value = dict(
            sensor_id=monitor + "/" + suffix,
            formula=formula,
            unit=unit,
            kind=kind,
            source=source,
            scope=scope,
            precision=0,
            **extra,
        )
        fields.append(value)
        return value

    common = dict(
        driver_id=device["registry_id"], channel_id=channels["GPUPH"]["channel_id"]
    )
    table = frame["tables"][0]
    require(
        table["physical_path"].startswith("IODeviceTree:/arm-io/"),
        "pmgr outside physical GPU tree",
    )
    table_source = f"IOKit/{table['physical_path']}/voltage-states9;little-endian frequency Hz,voltage native"
    common.update(
        raw_source=STATE_SOURCE + " + " + table_source,
        table_hex=table["voltage_states9_hex"],
        table_driver_id=table["registry_id"],
        table_source=table_source,
    )
    field("usage", "apple-activity", "Percent", "Percentage", STATE_SOURCE, **common)
    field(
        "frequency",
        "apple-frequency",
        "Hertz",
        "Frequency",
        "IOReport/GPUPH + IOKit/pmgr/voltage-states9;Hz",
        frequency_hz=hz,
        **common,
    )
    field(
        "power",
        "apple-energy",
        "Watts",
        "Power",
        ENERGY_SOURCE,
        driver_id=device["registry_id"],
        channel_id=channels["GPU Energy"]["channel_id"],
    )
    memory = unique(frame["memory"], "registry_id", device["registry_id"])
    for suffix, key in (
        ("shared-allocated", "Alloc system memory"),
        ("shared-in-use", "In use system memory"),
    ):
        source = "IOKit/PerformanceStatistics/" + key + ";bytes"
        f = field(
            suffix,
            "apple-memory",
            "Bytes",
            "Scalar",
            source,
            driver_id=device["registry_id"],
            raw_source=f"IOKit/{device['physical_path']}/PerformanceStatistics/{key};bytes",
        )
        f["scope"] += "; GPU shared memory; no capacity total"
        if key not in memory["values"]:
            f["limitation"] = "absent"
        else:
            integer(memory["values"][key])
    require(
        {r["key"] for r in frame["smc"]} == set(M1_KEYS)
        and len(frame["smc"]) == len(M1_KEYS),
        "incomplete independent SMC field inventory",
    )
    for key in M1_KEYS:
        row = unique(frame["smc"], "key", key)
        f = field(
            "temperature-smc-" + key,
            "apple-smc",
            "Celsius",
            "Temperature",
            f"SMC/{key};flt little-endian;Celsius",
        )
        if smc_value(row) is None:
            f["limitation"] = "absent"
    hid = frame["hid"]
    require(
        "error" not in hid and hid["service_count"] == len(hid["products"]),
        "incomplete HID field inventory",
    )
    expected = {
        n
        for n in hid["products"]
        if isinstance(n, str) and re.fullmatch(r"GPU MTR Temp Sensor[0-9]*", n)
    }
    require(
        len(hid["products"]) <= 4096
        and {r["product"] for r in hid["rows"]} == expected
        and len(hid["rows"]) == len(expected),
        "ambiguous/missing native HID source",
    )
    for name in sorted(expected):
        field(
            "temperature-hid-" + name,
            "apple-hid",
            "Celsius",
            "Temperature",
            f"HID/{name};Celsius",
        )
    if not expected:
        field(
            "temperature-hid",
            "apple-hid",
            "Celsius",
            "Temperature",
            "HID/GPU MTR Temp Sensor;Celsius",
            limitation="unattributable" if None in hid["products"] else "absent",
        )
    field(
        "fan",
        "unattributable-fan",
        "Rpm",
        "Fan",
        "SMC/system fans",
        limitation="unattributable",
    )
    return dict(
        hardware_class="apple-silicon",
        device=device,
        fields=fields,
        captured_unix_ns=frame["clock_anchor"]["unix_ns"],
    )


def normalize_observer(frame, inventory):
    device = inventory["device"]
    require(
        frame["devices"] == [{k: v for k, v in device.items() if k != "monitor_id"}],
        "native physical GPU instance changed",
    )
    channels = native_channels(frame, device)
    hz = frequency_table(frame)
    frequency = next(
        f for f in inventory["fields"] if f["formula"] == "apple-frequency"
    )
    require(
        hz == frequency["frequency_hz"]
        and frame["tables"][0]["voltage_states9_hex"] == frequency["table_hex"],
        "native frequency mapping changed",
    )
    samples = []

    def sample(field, row, values):
        samples.append(
            dict(
                start=row["start"],
                end=row["end"],
                source=field.get("raw_source", field["source"]),
                values=values,
                **{k: field[k] for k in ("driver_id", "channel_id") if k in field},
            )
        )

    for field in inventory["fields"]:
        formula = field["formula"]
        if formula == "apple-activity":
            row = channels["GPUPH"]
            require(
                row["channel_id"] == field["channel_id"],
                "changed native channel instance",
            )
            sample(
                field,
                frame["ioreport"],
                {"ticks/" + s["name"]: integer(s["residency"]) for s in row["states"]},
            )
            table = frame["tables"][0]
            samples.append(
                dict(
                    start=table["start"],
                    end=table["end"],
                    source=field["table_source"],
                    driver_id=table["registry_id"],
                    values={
                        "pair_le/" + str(n): p[0]
                        for n, p in enumerate(
                            struct.iter_unpack(
                                "<Q", bytes.fromhex(table["voltage_states9_hex"])
                            )
                        )
                    },
                )
            )
        elif formula == "apple-energy":
            row = channels["GPU Energy"]
            require(
                row["channel_id"] == field["channel_id"],
                "changed native energy instance",
            )
            sample(field, frame["ioreport"], dict(energy_nj=integer(row["integer"])))
        elif formula == "apple-memory":
            row = unique(frame["memory"], "registry_id", device["registry_id"])
            key = field["source"].split("/")[-1].split(";")[0]
            if key in row["values"]:
                sample(field, row, dict(bytes=integer(row["values"][key])))
        elif formula == "apple-smc":
            key = field["source"].split("/")[1].split(";")[0]
            row = unique(frame["smc"], "key", key)
            value = smc_value(row)
            if value is not None:
                sample(field, row, dict(celsius=value))
        elif formula == "apple-hid" and not field.get("limitation"):
            name = field["source"][4:].split(";")[0]
            row = unique(frame["hid"]["rows"], "product", name)
            require(math.isfinite(row["celsius"]), "invalid HID temperature")
            sample(field, row, dict(celsius=row["celsius"]))
    return dict(clock_anchor=frame["clock_anchor"], samples=samples)
