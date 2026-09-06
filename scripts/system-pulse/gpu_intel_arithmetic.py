"""Intel sysfs/DRM/perf arithmetic independent of the Rust adapter."""

from host_accuracy import require
from gpu_arithmetic import integer


def delta_bracket(delta, previous, current, samples, policy):
    ordered = sorted(samples, key=lambda s: s["start"])
    require(
        ordered
        and all(0 <= s["end"] - s["start"] <= policy["max_query_ns"] for s in ordered),
        "invalid independent perf query",
    )
    require(
        all(
            a["end"] <= b["start"] and integer(a["value"]) <= integer(b["value"])
            for a, b in zip(ordered, ordered[1:])
        ),
        "independent perf reset/overlap",
    )

    def endpoints(query):
        preceding = [s for s in ordered if s["end"] <= query[0]]
        following = [s for s in ordered if s["start"] >= query[1]]
        require(preceding and following, "missing entire-window perf bracket")
        a, b = preceding[-1], following[0]
        require(
            query[1] - a["start"] <= policy["max_gap_ns"]
            and b["end"] - query[0] <= policy["max_gap_ns"],
            "stale independent perf bracket",
        )
        return a["value"], b["value"]

    p, c = endpoints(previous), endpoints(current)
    lower, upper = max(0, c[0] - p[1]), c[1] - p[0]
    require(
        upper >= 0 and lower <= delta <= upper,
        "unexplained independent perf delta mismatch",
    )
    return lower, upper


def calculate(field, reading):
    observations = reading["observations"]
    a, b = observations[0], observations[-1]
    ai, bi = a["integers"], b["integers"]
    formula = field["formula"]
    total = None
    keys = []
    gauge = None
    if formula in ("intel-sysfs", "intel-energy"):
        require(
            (bi["numerator"], bi["denominator"])
            == (field["numerator"], field["denominator"]),
            "wrong native source unit conversion",
        )
        if formula == "intel-energy":
            require(
                len(observations) == 2
                and ai["denominator"] == bi["denominator"] == 1_000_000,
                "energy baseline/unit missing",
            )
            dt = (b["captured_ns"] - a["captured_ns"]) / 1e9
            delta = integer(bi["value"]) - integer(ai["value"])
            require(dt > 0 and delta >= 0, "energy reset/invalid elapsed time")
            expected = float(delta) / 1e6 / dt
            keys = ["value"]
        else:
            if field.get("signed"):
                require(bi["negative"] in (0, 1), "invalid native sign")
                value = integer(bi["magnitude"]) * (-1 if bi["negative"] else 1)
                gauge = "signed_value"
            else:
                value = integer(bi["value"])
                gauge = "value"
            expected = float(value) * float(bi["numerator"]) / float(bi["denominator"])
    elif formula == "intel-perf":
        require(len(observations) == 2, "perf missing endpoints")
        for key in (
            "ticks",
            "capacity",
            "config_active",
            "config_total",
            "energy_denominator",
            "pmu_type",
            "cpu",
        ):
            require(ai[key] == bi[key] == field[key], "wrong perf metadata " + key)
        enabled = integer(bi["enabled_ns"]) - integer(ai["enabled_ns"])
        running = integer(bi["running_ns"]) - integer(ai["running_ns"])
        active = integer(bi["active"]) - integer(ai["active"])
        dt = (b["captured_ns"] - a["captured_ns"]) / 1e9
        require(
            enabled > 0 and enabled == running and active >= 0 and dt > 0,
            "perf reset/multiplexing/elapsed mismatch",
        )
        denominator = bi["energy_denominator"]
        if denominator:
            require(denominator == 2**32, "unknown RAPL native unit")
            expected = float(active) / float(denominator) / dt
        else:
            measured_total = (
                integer(bi["total"]) - integer(ai["total"]) if bi["ticks"] else dt * 1e9
            )
            require(
                bi["ticks"] in (0, 1)
                and bi["capacity"] == 1
                and 0 <= active <= measured_total
                and measured_total > 0,
                "invalid engine scope/normalization",
            )
            expected = float(active) / float(measured_total) * 100.0
        # Each native perf handle starts counting at its own open. Compare deltas
        # separately; absolute-count comparisons across handles would be invalid.
    elif formula == "intel-memory":
        from gpu_intel_capture import validate_region

        validate_region(field["driver"], bi)
        require(
            bi["class"] == field["region_class"]
            and bi["instance"] == field["region_instance"],
            "wrong memory region identity",
        )
        local = bi["class"] == 1
        name = field["memory_metric"]
        if name == "total":
            expected = bi["total_bytes"]
            gauge = "total_bytes"
        else:
            visible = name == "cpu-visible"
            count_key = "cpu_visible_count_bytes" if visible else "count_bytes"
            total_key = "cpu_visible_total_bytes" if visible else "total_bytes"
            count, capacity = bi[count_key], bi[total_key]
            if field["driver"] == "i915":
                require(
                    local and count < capacity,
                    "i915 free accounting cannot establish measured zero/shared allocation",
                )
                expected = capacity - count
            else:
                expected = count
            total = capacity if local else None
            gauge = count_key
        require(
            field["unit"] == "Bytes" and (local or field["kind"] == "Counter"),
            "wrong memory quantity",
        )
    else:
        raise AssertionError("unknown GPU formula " + formula)
    return expected, total, keys, gauge
