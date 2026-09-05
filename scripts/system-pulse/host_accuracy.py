"""Independent Linux acceptance arithmetic. No collector code or test measurements imported."""

import collections
import ipaddress
import math
import os
import re


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def exact(actual, expected, context):
    # Match declared IEEE binary64 operations exactly; no numeric tolerance.
    require(
        actual is not None
        and expected is not None
        and math.isfinite(actual)
        and math.isfinite(expected),
        f"{context}: nonfinite/missing operands {actual}, {expected}",
    )
    require(
        actual == expected,
        f"{context}: actual={actual!r} expected={expected!r}",
    )


def clock_intersection(anchors):
    require(bool(anchors), "missing clock anchors")
    low = max(wall - after for before, after, wall in anchors)
    high = min(wall - before for before, after, wall in anchors)
    require(
        all(before <= after for before, after, wall in anchors),
        "reversed clock bracket",
    )
    require(low <= high, f"observed clock discontinuity: {low} > {high}")
    return low, high


def map_window(window, collector_offset, external_offset):
    start, end = window
    require(start <= end, "reversed source query")
    return start + collector_offset[0] - external_offset[1], end + collector_offset[
        1
    ] - external_offset[0]


def check_counter(value, window, samples):
    before = [s for s in samples if s["end"] <= window[0]]
    after = [s for s in samples if s["start"] >= window[1]]
    require(before and after, f"missing entire-window bracket: {window}")
    a = max(before, key=lambda s: s["end"])
    b = min(after, key=lambda s: s["start"])
    require(
        a["value"] <= b["value"],
        "external counter reset; no accuracy comparison possible",
    )
    require(
        a["value"] <= value <= b["value"],
        f"counter outside bracket: {a['value']} <= {value} <= {b['value']}",
    )
    return a, b


def check_process_counter(value, window, identity, samples):
    matched = [sample for sample in samples if sample["identity"] == identity]
    return check_counter(value, window, matched)


def check_gauge_domain(unit, value, percent_max=100):
    require(math.isfinite(value), "nonfinite gauge")
    require(unit == "Celsius" or value >= 0, f"negative {unit}")
    if unit == "Percent":
        require(value <= percent_max, "percentage outside declared source bounds")


def parse_process_stat(text):
    opening, closing = text.index("("), text.rindex(")")
    fields = text[closing + 2 :].split()
    return {
        "pid": int(text[:opening].strip()),
        "name": text[opening + 1 : closing],
        "state": fields[0],
        "ppid": int(fields[1]),
        "start_ticks": int(fields[19]),
        "utime": int(fields[11]),
        "stime": int(fields[12]),
        "rss_pages": int(fields[21]),
        "threads": int(fields[17]),
    }


def check_process_cpu(value, observations, ticks_per_second):
    require(len(observations) == 2, "process CPU needs two observations")
    a, b = observations

    def ticks(o):
        i = o["integers"]
        return i.get("utime", i.get("utime_ticks")) + i.get(
            "stime", i.get("stime_ticks")
        )

    elapsed = (b["captured_ns"] - a["captured_ns"]) / 1e9
    require(elapsed > 0 and ticks(b) >= ticks(a), "invalid process CPU endpoints")
    exact(
        value,
        100.0 * float(ticks(b) - ticks(a)) / float(ticks_per_second) / elapsed,
        "process one-core CPU",
    )


def check_reading(sensor, reading):
    sid = reading["sensor_id"]
    require(sensor["id"] == sid, "reading identity mismatch")
    observations = reading["observations"]
    if reading["availability"] != "Available":
        require(
            reading["value"] is None and reading["reason"],
            f"{sid}: missing truthful unavailable reason",
        )
        return False
    require(observations, f"{sid}: available without raw operands")
    source = observations[-1]["source"]
    i = observations[-1]["integers"]
    d = observations[-1]["decimals"]
    suffix = sid.rsplit("/", 1)[-1]
    unit = sensor["unit"]
    value = reading["value"]
    total = None
    check_gauge_domain(
        unit, value, float("inf") if sid.startswith("process:") or "fan" in sid else 100
    )
    if source.startswith("/proc/stat:"):
        require(len(observations) == 2, "CPU needs two endpoints")
        names = ("user", "nice", "system", "idle", "iowait", "irq", "softirq", "steal")
        a, b = [o["integers"] for o in observations]
        delta = {k: b[k] - a[k] for k in names}
        require(
            all(v >= 0 for v in delta.values()) and sum(delta.values()) > 0,
            "invalid CPU counters",
        )
        expected = (
            100.0
            * float(sum(delta.values()) - delta["idle"] - delta["iowait"])
            / sum(delta.values())
        )
    elif source.startswith("/proc/meminfo"):
        if suffix == "used":
            expected = i["MemTotal"] - i["MemAvailable"]
            total = i["MemTotal"] * 1024
        elif suffix in ("total", "available", "free", "buffers", "swap-total"):
            expected = i[
                {
                    "total": "MemTotal",
                    "available": "MemAvailable",
                    "free": "MemFree",
                    "buffers": "Buffers",
                    "swap-total": "SwapTotal",
                }[suffix]
            ]
        elif suffix == "cache":
            expected = i["Cached"] + i["SReclaimable"] - i["Shmem"]
        elif suffix == "other":
            expected = (
                i["MemTotal"]
                - i["MemFree"]
                - (i["Cached"] + i["SReclaimable"] - i["Shmem"])
                - i["Buffers"]
            )
        elif suffix == "swap":
            expected = i["SwapTotal"] - i["SwapFree"]
            total = i["SwapTotal"] * 1024
        else:
            raise AssertionError(f"unimplemented memory field {sid}")
        expected *= 1024
    elif source.startswith("statvfs("):
        expected = (i["blocks"] - i["free_blocks"]) * i["fragment_size"]
        total = i["blocks"] * i["fragment_size"]
    elif "used" in i and "total" in i:
        expected = i["used"]
        total = i["total"]
    elif sid.startswith("process:") and suffix == "cpu":
        require(i["ticks_per_second"] == os.sysconf("SC_CLK_TCK"), "wrong CLK_TCK")
        check_process_cpu(value, observations, i["ticks_per_second"])
        return True
    elif sid.startswith("process:") and suffix == "memory":
        require(i["page_size"] == os.sysconf("SC_PAGE_SIZE"), "wrong RSS page factor")
        expected = i["rss_pages"] * i["page_size"]
    elif len(observations) == 2:
        a, b = [o["integers"] for o in observations]
        elapsed = (
            observations[1]["captured_ns"] - observations[0]["captured_ns"]
        ) / 1e9
        require(elapsed > 0, "nonpositive rate interval")

        def delta(k):
            require(b[k] >= a[k], f"reset {sid} {k}")
            return b[k] - a[k]

        if "read_sectors" in b:
            if suffix in ("read", "write"):
                expected = delta(suffix + "_sectors") * 512 / elapsed
            elif suffix == "iops":
                expected = (delta("read_ops") + delta("write_ops")) / elapsed
            elif suffix == "latency":
                ops = delta("read_ops") + delta("write_ops")
                require(ops > 0, "latency available without completed IO")
                expected = (delta("read_ms") + delta("write_ms")) / ops
            else:
                raise AssertionError(f"unknown disk field {sid}")
        elif "bytes" in b:
            expected = delta("bytes") / elapsed
        else:
            raise AssertionError(f"unimplemented derived reading {sid}: {b.keys()}")
    elif "value" in d:
        factor = 1
        if unit == "Celsius":
            factor = 0.001
        elif unit == "Watts":
            factor = 0.000001
        elif unit == "Hertz" and "scaling_cur_freq" in source:
            factor = 1000
        elif unit == "Hertz" and source.startswith("/proc/cpuinfo"):
            factor = 1e6
        expected = d["value"] * factor
    elif "value" in i:
        expected = i["value"]
    else:
        raise AssertionError(f"unimplemented raw shape {sid}: {i.keys()} {d.keys()}")
    exact(value, expected, sid)
    if total is not None:
        exact(reading["total"], total, sid + " total")
    else:
        require(reading["total"] is None, f"unexpected capacity {sid}")
    return True


def check_capabilities(expected, sensors):
    present = {(s["source"], s["unit"]) for s in sensors}
    missing = set(expected) - present
    require(not missing, f"accessible capabilities omitted: {sorted(missing)}")


SYMBOLS = {
    "Bytes": "B",
    "BytesPerSecond": "B/s",
    "Hertz": "Hz",
    "Percent": "%",
    "Celsius": "°C",
    "Watts": "W",
    "Rpm": "RPM",
    "Count": "count",
    "CountPerSecond": "count/s",
    "Milliseconds": "ms",
    "Seconds": "s",
    "Load": "load",
}


def format_sample(sample):
    value = sample["value"]
    total = sample.get("total")
    unit = sample["unit"]
    require(unit in SYMBOLS, f"unknown physical unit {unit}")
    if value is None:
        return "Unavailable " + SYMBOLS[unit]
    divisor = 1
    prefix = ""
    scale = total if total is not None else value
    base = 1024 if unit in ("Bytes", "BytesPerSecond") else 1000
    prefixes = (
        ("", "Ki", "Mi", "Gi", "Ti", "Pi") if base == 1024 else ("", "k", "M", "G", "T")
    )
    if unit in ("Bytes", "BytesPerSecond", "Hertz"):
        for p in prefixes[1:]:
            if abs(scale) / divisor < base:
                break
            divisor *= base
            prefix = p
    if total is not None:
        number = f"{value / divisor:.1f} / {total / divisor:.1f}"
    else:
        number = f"{value / divisor:.{0 if unit in ('Count', 'Rpm') else 1}f}"
    return number + " " + prefix + SYMBOLS[unit]


def check_rendered(sample, text):
    require(
        text == format_sample(sample),
        f"independent rendered text mismatch: {text!r} != {format_sample(sample)!r}",
    )


def normalized(value):
    address = ipaddress.ip_address(value)
    return (
        address.ipv4_mapped
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped
        else address
    )


def connection_counts(addresses, tcp4, tcp6, byte_order):
    require(byte_order in ("little", "big"), "missing declared address word order")
    owners = collections.defaultdict(set)
    for interface, values in addresses.items():
        for value in values:
            address = normalized(value)
            if not address.is_unspecified:
                owners[address].add(interface)
    counts = {interface: 0 for interface in addresses}
    for rows, length in ((tcp4, 8), (tcp6, 32)):
        for row in rows:
            token = row.get("local_address", row.get("local_address_hex"))
            state = row.get("state", row.get("state_hex"))
            require(
                token is not None
                and len(token) == length
                and re.fullmatch("[0-9a-fA-F]+", token),
                "malformed retained local address",
            )
            require(
                state is not None and re.fullmatch("[0-9a-fA-F]{2}", state),
                "malformed retained state",
            )
            packed = b"".join(
                int(token[n : n + 8], 16).to_bytes(4, byte_order)
                for n in range(0, length, 8)
            )
            address = normalized(packed)
            if (
                int(state, 16) == 1
                and not address.is_unspecified
                and len(owners[address]) == 1
            ):
                counts[next(iter(owners[address]))] += 1
    return counts


def check_connection_counts(expected, addresses, tcp4, tcp6, byte_order):
    actual = connection_counts(addresses, tcp4, tcp6, byte_order)
    require(
        actual == expected, f"connection attribution mismatch {actual} != {expected}"
    )
