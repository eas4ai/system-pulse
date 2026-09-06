"""Recompute every independently required field in one collector clock domain."""

from gpu_arithmetic import bracket, verify_reading, window
from host_accuracy import clock_intersection, map_window, require


def anchors(rows):
    return [
        (
            r["clock_anchor"]["monotonic_before_ns"],
            r["clock_anchor"]["monotonic_after_ns"],
            r["clock_anchor"]["unix_ns"],
        )
        for r in rows
    ]


def verify_series(snapshots, inventory, observer, policy):
    require(
        snapshots
        and all(
            a["sequence"] < b["sequence"] for a, b in zip(snapshots, snapshots[1:])
        ),
        "missing, repeated or unordered collector sequence",
    )
    collector_clock = clock_intersection(anchors(snapshots))
    observer_clock = clock_intersection(anchors(observer))
    native = [sample for frame in observer for sample in frame["samples"]]
    fields = inventory["fields"]
    ids = {f["sensor_id"] for f in fields}
    require(len(ids) == len(fields), "duplicate independent field")
    counts = dict.fromkeys(ids, 0)
    for index, snapshot in enumerate(snapshots):
        mid = inventory["device"]["monitor_id"]
        monitors = [m for m in snapshot["monitors"] if m["id"] == mid]
        require(
            len(monitors) == 1 and monitors[0]["kind"] == "Gpu",
            "missing/duplicate physical GPU discovery",
        )
        sensors = {s["id"]: s for s in snapshot["sensors"]}
        readings = {r["sensor_id"]: r for r in snapshot["readings"]}
        require(
            len(sensors) == len(snapshot["sensors"])
            and len(readings) == len(snapshot["readings"]),
            "duplicate sensor/readings in original snapshot",
        )
        require(
            {s["id"] for s in snapshot["sensors"] if s["monitor_id"] == mid} == ids,
            "GPU sensor set differs from independent native inventory",
        )
        require(
            monitors[0]["summary_sensor_id"] in ids,
            "GPU summary has no attributable sensor",
        )
        for field in fields:
            sid = field["sensor_id"]
            require(sid in sensors and sid in readings, "required field omitted")
            reading = readings[sid]
            if (
                index < policy["warmup_samples"]
                and reading["availability"] == "WarmingUp"
            ):
                require(
                    field["formula"]
                    in (
                        "apple-energy",
                        "apple-activity",
                        "apple-frequency",
                        "intel-energy",
                        "intel-perf",
                    )
                    and reading["value"] is None
                    and reading["total"] is None
                    and reading["reason"]
                    and len(reading["observations"]) == 1,
                    "invalid initial baseline allowance",
                )
                require(
                    all(
                        sensors[sid][k] == field[k]
                        for k in ("source", "scope", "unit", "kind")
                    ),
                    "initial sensor has incorrect metadata",
                )
                raw = reading["observations"][0]
                require(
                    raw["source"] == field.get("raw_source", field["source"]),
                    "initial raw source changed",
                )
                query = map_window(window(raw, policy), collector_clock, observer_clock)
                if field["formula"].startswith("apple-"):
                    require(
                        raw["integers"]["driver_id"] == field["driver_id"]
                        and raw["integers"]["channel_id"] == field["channel_id"],
                        "initial native identity changed",
                    )
                    keys = (
                        ["energy_nj"]
                        if field["formula"] == "apple-energy"
                        else [k for k in raw["integers"] if k.startswith("ticks/")]
                    )
                    require(keys, "initial source operands missing")
                    matched = [
                        s
                        for s in native
                        if s["source"] == raw["source"]
                        and s.get("driver_id") == field["driver_id"]
                        and s.get("channel_id") == field["channel_id"]
                    ]
                    for key in keys:
                        bracket(
                            raw["integers"][key],
                            query,
                            [
                                dict(
                                    start=s["start"],
                                    end=s["end"],
                                    value=s["values"][key],
                                )
                                for s in matched
                            ],
                            policy,
                        )
                continue
            counts[sid] += verify_reading(
                field,
                sensors[sid],
                reading,
                native,
                collector_clock,
                observer_clock,
                policy,
            )
    require(
        all(counts[f["sensor_id"]] > 0 or f.get("limitation") for f in fields),
        "accessible field never independently compared",
    )
    return counts
