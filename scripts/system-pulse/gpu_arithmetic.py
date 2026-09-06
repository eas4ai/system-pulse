"""Independent GPU arithmetic over original operands and timed native reads.

Source integer precision is exact. Only the final binary64 computation allows
the predeclared (at most four) ULP rounding difference. No collector imports.
"""

import math
import struct

from host_accuracy import check_counter, map_window, require


def integer(value):
    require(
        type(value) is int and 0 <= value <= 2**64 - 1,
        "invalid native unsigned integer",
    )
    return value


def window(observation, policy):
    a, b = observation["read_started_ns"], observation["captured_ns"]
    integer(a)
    integer(b)
    require(0 <= b - a <= policy["max_query_ns"], "invalid/slow source query")
    return a, b


def bracket(value, query, samples, policy):
    integer(value)
    for sample in samples:
        integer(sample["value"])
        require(
            0 <= sample["end"] - sample["start"] <= policy["max_query_ns"],
            "invalid observer query duration",
        )
    ordered = sorted(samples, key=lambda s: s["start"])
    require(
        all(
            a["end"] <= b["start"] and a["value"] <= b["value"]
            for a, b in zip(ordered, ordered[1:])
        ),
        "observer overlap/counter reset",
    )
    a, b = check_counter(value, query, samples)
    require(
        query[1] - a["start"] <= policy["max_gap_ns"]
        and b["end"] - query[0] <= policy["max_gap_ns"],
        "stale native bracket",
    )
    return a["value"], b["value"]


def state_names(states):
    require(1 <= len(states) <= 128, "missing state layout")
    names = ["OFF"] + [f"P{i}" for i in range(1, len(states))]
    require(set(states) == set(names), "unknown state mapping")
    return names


def weighted_frequency(states, table):
    names = state_names(states)
    active = sum(integer(states[n]) for n in names[1:])
    require(active > 0, "frequency undefined without active residency")
    weighted = 0
    for index, name in enumerate(names[1:], 1):
        if states[name]:
            require(
                index < len(table) and table[index] > 0,
                "unknown active frequency mapping",
            )
            weighted += states[name] * integer(table[index])
    require(weighted <= 2**64 - 1, "weighted frequency overflow")
    return float(weighted) / float(active)


def same_number(actual, expected, ulps):
    require(type(ulps) is int and 0 <= ulps <= 4, "invalid rounding allowance")
    require(
        type(actual) in (int, float)
        and math.isfinite(actual)
        and math.isfinite(expected),
        "missing/nonfinite physical value",
    )
    require(
        abs(actual - expected) <= ulps * math.ulp(float(expected)),
        f"independent arithmetic mismatch: {actual!r} != {expected!r}",
    )


def gauge(value, query, samples, policy, precision):
    require(
        math.isfinite(value) and precision >= 0 and math.isfinite(precision),
        "invalid gauge/precision",
    )
    before = [s for s in samples if s["end"] <= query[0]]
    after = [s for s in samples if s["start"] >= query[1]]
    require(before and after, "gauge missing before/after observations")
    a, b = max(before, key=lambda s: s["end"]), min(after, key=lambda s: s["start"])
    require(
        query[1] - a["start"] <= policy["max_gap_ns"]
        and b["end"] - query[0] <= policy["max_gap_ns"],
        "stale gauge comparison",
    )
    selected = [s for s in samples if a["start"] <= s["start"] <= b["start"]]
    require(
        all(
            math.isfinite(s["value"])
            and 0 <= s["end"] - s["start"] <= policy["max_query_ns"]
            for s in selected
        ),
        "invalid gauge observation",
    )
    require(
        min(s["value"] for s in selected) - precision
        <= value
        <= max(s["value"] for s in selected) + precision,
        "unexplained native gauge mismatch",
    )


def verify_reading(
    field, sensor, reading, samples, collector_clock, observer_clock, policy
):
    require(
        reading["sensor_id"] == sensor["id"] == field["sensor_id"],
        "wrong sensor identity",
    )
    for key in ("source", "scope", "unit", "kind"):
        require(sensor[key] == field[key], "wrong sensor " + key)
    status = reading["availability"]
    require(
        status in ("Available", "Unavailable", "Failed", "WarmingUp"),
        "unknown availability",
    )
    require(
        reading["total"] is None or field["kind"] == "Capacity",
        "incorrect memory scope/total",
    )
    observations = reading["observations"]
    if status != "Available":
        require(
            reading["value"] is None
            and reading["total"] is None
            and bool(reading["reason"]),
            "invalid availability claim",
        )
        # Native limitations must be independently inventoried; an author reason
        # alone cannot waive an accessible required field.
        if not observations:
            require(
                field.get("limitation")
                in ("absent", "denied", "unattributable", "failed"),
                "accessible required field omitted",
            )
            require(
                status
                == ("Failed" if field["limitation"] == "failed" else "Unavailable"),
                "native limitation has incorrect availability",
            )
            return False
    require(
        observations and len(observations) <= 2, "missing/invalid original endpoints"
    )
    formula = field["formula"]
    for o in observations:
        require(
            o["source"] == field.get("raw_source", field["source"]), "wrong raw source"
        )
        window(o, policy)
        if "driver_id" in field:
            require(
                o["integers"]["driver_id"] == field["driver_id"], "wrong native device"
            )
    a, b = observations[0], observations[-1]
    ai, bi = a["integers"], b["integers"]
    total = None
    undefined_frequency = False
    counter_keys = []
    gauge_key = None
    if formula.startswith("apple-") and formula in (
        "apple-energy",
        "apple-activity",
        "apple-frequency",
    ):
        require(len(observations) == 2, "counter needs two endpoints")
        states = formula != "apple-energy"
        for o in observations:
            i = o["integers"]
            require(
                i["channel_id"] == field["channel_id"]
                and i["format"] == (2 if states else 1)
                and i["encoded_unit"]
                == (72058115876454424 if states else 216173288919924736),
                "wrong channel format or source unit",
            )
        if states:
            names = state_names(
                {k[6:]: v for k, v in bi.items() if k.startswith("ticks/")}
            )
            require(
                ai["state_count"] == bi["state_count"] == len(names),
                "changed state layout",
            )
            counter_keys = ["ticks/" + n for n in names]
        else:
            counter_keys = ["energy_nj"]
        deltas = {k: integer(bi[k]) - integer(ai[k]) for k in counter_keys}
        require(all(v >= 0 for v in deltas.values()), "counter reset")
        elapsed = b["captured_ns"] - a["captured_ns"]
        require(elapsed > 0, "nonpositive elapsed time")
        if formula == "apple-energy":
            expected = float(deltas["energy_nj"]) / float(elapsed)
        elif formula == "apple-activity":
            require(sum(deltas.values()) > 0, "zero residency denominator")
            expected = (
                100.0
                * float(sum(deltas.values()) - deltas["ticks/OFF"])
                / float(sum(deltas.values()))
            )
        else:
            table = field["frequency_hz"]
            for index, name in enumerate(names):
                require(
                    ai.get("hz/" + name)
                    == bi.get("hz/" + name)
                    == (table[index] if index < len(table) else None),
                    "changed frequency mapping",
                )
            undefined_frequency = (
                sum(v for k, v in deltas.items() if k != "ticks/OFF") == 0
            )
            expected = (
                None
                if undefined_frequency
                else weighted_frequency({k[6:]: v for k, v in deltas.items()}, table)
            )
    elif formula == "apple-memory":
        require(
            field["unit"] == "Bytes"
            and field["kind"] == "Scalar"
            and "GPU shared memory" in field["scope"]
            and bi["has_unified_memory"] == 1,
            "incorrect shared-memory semantics",
        )
        require(
            any(
                field["source"].endswith("/" + key + ";bytes")
                for key in ("Alloc system memory", "In use system memory")
            ),
            "wrong accelerator key",
        )
        gauge_key, expected = "bytes", float(integer(bi["bytes"]))
    elif formula in ("apple-smc", "apple-hid"):
        expected = b["decimals"]["celsius"]
        gauge_key = "celsius"
        if formula == "apple-smc":
            raw = integer(bi["bytes_le"]).to_bytes(4, "little")
            key = field["source"].split("/")[1].split(";")[0]
            require(
                bi["key_fourcc"] == int.from_bytes(key.encode("ascii"), "big")
                and bi["type_fourcc"] == int.from_bytes(b"flt ", "big")
                and bi["size"] == 4
                and bi["result"] == bi["status"] == bi["return_code"] == 0
                and bi["response_size"] == 80,
                "invalid SMC native status/type/size",
            )
            require(expected == struct.unpack("<f", raw)[0], "SMC raw decode mismatch")
        else:
            require(
                bi["event_type"] == 15 and bi["event_field"] == 15 << 16,
                "wrong HID event unit/type",
            )
        require(math.isfinite(expected), "nonfinite temperature")
    else:
        from gpu_intel_arithmetic import calculate

        expected, total, counter_keys, gauge_key = calculate(field, reading)
    for o in observations:
        mapped = map_window(window(o, policy), collector_clock, observer_clock)
        matching = [
            s
            for s in samples
            if s["source"] == o["source"]
            and all(
                s.get(k) == field[k] for k in ("driver_id", "channel_id") if k in field
            )
            and s.get("sensor_id", field["sensor_id"]) == field["sensor_id"]
        ]
        for key in counter_keys:
            bracket(
                o["integers"][key],
                mapped,
                [
                    dict(start=s["start"], end=s["end"], value=s["values"][key])
                    for s in matching
                ],
                policy,
            )
        if formula == "intel-memory":
            from gpu_intel_arithmetic import compare_memory

            compare_memory(field, o, mapped, matching, policy)
        elif gauge_key:
            value = (
                o["decimals"][gauge_key]
                if gauge_key == "celsius"
                else integer(o["integers"]["magnitude"])
                * (-1 if o["integers"]["negative"] else 1)
                if gauge_key == "signed_value"
                else o["integers"][gauge_key]
            )
            gauge(
                value,
                mapped,
                [
                    dict(start=s["start"], end=s["end"], value=s["values"][gauge_key])
                    for s in matching
                ],
                policy,
                field["precision"],
            )
    if formula in ("apple-activity", "apple-frequency") and "table_hex" in field:
        data = bytes.fromhex(field["table_hex"])
        pairs = [p[0] for p in struct.iter_unpack("<Q", data)]
        for o in observations:
            raw = o["integers"]
            require(
                raw["table/driver_id"] == field["table_driver_id"]
                and raw["table/byte_length"] == len(data),
                "wrong original frequency table identity/length",
            )
            query = window(
                dict(
                    read_started_ns=raw["table/read_started_ns"],
                    captured_ns=raw["table/captured_ns"],
                ),
                policy,
            )
            mapped = map_window(query, collector_clock, observer_clock)
            matching = [
                s
                for s in samples
                if s["source"] == field["table_source"]
                and s.get("driver_id") == field["table_driver_id"]
            ]
            for n, pair in enumerate(pairs):
                key = "pair_le/" + str(n)
                require(
                    raw["table/" + key] == pair,
                    "raw frequency table mapping differs from inventory",
                )
                gauge(
                    pair,
                    mapped,
                    [
                        dict(start=s["start"], end=s["end"], value=s["values"][key])
                        for s in matching
                    ],
                    policy,
                    0,
                )
    if formula == "intel-perf":
        from gpu_intel_arithmetic import delta_bracket

        matching = [
            s
            for s in samples
            if s["source"] == field["source"]
            and s.get("sensor_id") == field["sensor_id"]
        ]
        require(
            len({s["opened_ns"] for s in matching}) == 1, "native perf handle reset"
        )
        previous = map_window(window(a, policy), collector_clock, observer_clock)
        current = map_window(window(b, policy), collector_clock, observer_clock)
        for key in ["active"] + (["total"] if field["ticks"] else []):
            delta_bracket(
                integer(bi[key]) - integer(ai[key]),
                previous,
                current,
                [
                    dict(start=s["start"], end=s["end"], value=s["values"][key])
                    for s in matching
                ],
                policy,
            )
    if undefined_frequency:
        require(
            status == "Unavailable" and reading["value"] is None and reading["reason"],
            "no active residency must not publish a frequency",
        )
        return False
    if formula == "apple-smc" and expected < 15:
        require(
            status == "Unavailable" and "plausibility guard" in reading["reason"],
            "SMC software guard not preserved",
        )
        return True
    require(status == "Available", "invalid noncurrent accessible reading")
    same_number(reading["value"], expected, policy["rounding_ulps"])
    if total is None:
        require(reading["total"] is None, "invented capacity total")
    else:
        same_number(reading["total"], total, policy["rounding_ulps"])
    return True
