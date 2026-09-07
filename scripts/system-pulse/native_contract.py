"""Pure independent native text checks, shared by replay and mutation regressions."""

from host_accuracy import check_reading, format_sample, require, SYMBOLS


def check_input_record(record, expected_keys=None):
    observations = record["observations"]
    require(
        observations
        and all("error" not in item and 0 <= item["age"] <= 2 for item in observations),
        "input starved fresh publication",
    )
    require(
        len({item["sequence"] for item in observations}) >= 3,
        "input did not retain three fresh sequences",
    )
    require(
        (record["after"] - record["before"]) * record["sign"] > 0,
        "input had no signed movement",
    )
    if expected_keys is not None:
        require(record["key_count"] == expected_keys, "wrong exact input burst count")


def horizontal_pair(node, left, right):
    """Find the requested adjacent single-monitor children of a horizontal stack."""

    def monitor(child):
        if child.get("panel_name") != "TabPanel" or len(child.get("children", [])) != 1:
            return None
        return child["children"][0].get("info", {}).get("panel", {}).get("monitor_id")

    children = node.get("children", [])
    if (
        node.get("panel_name") == "StackPanel"
        and node.get("info", {}).get("stack", {}).get("axis") == 0
    ):
        for index in range(len(children) - 1):
            if (
                monitor(children[index]) == left
                and monitor(children[index + 1]) == right
            ):
                return node
    for child in children:
        found = horizontal_pair(child, left, right)
        if found is not None:
            return found
    return None


def reading_text(frame, reading, unit):
    if reading["value"] is None:
        status = {
            "Failed": "Failed",
            "Unavailable": "Unavailable",
            "WarmingUp": "Warming up",
        }[reading["availability"]]
        text = status + " · " + SYMBOLS[unit]
    else:
        text = format_sample(dict(reading, unit=unit))
        at = max(
            (o["captured_ns"] // 1000000 for o in reading["observations"]),
            default=frame["snapshot"]["capture_finished_ns"] // 1000000,
        )
        if frame["rendered_at_collector_ms"] - at > 2000:
            text += " · Stale"
    if reading["reason"] is not None:
        text += " · " + reading["reason"]
    return text


def expected_label(frame, entry):
    snapshot = frame["snapshot"]
    sid = entry["sensor_id"]
    if entry["process_identity"] is not None:
        row = next(
            r
            for r in snapshot["processes"]
            if r["identity"] == entry["process_identity"]
        )
        column = int(entry["element_id"].rsplit(":", 1)[1])
        if column == 0:
            expected = str(row["identity"]["pid"])
        elif column == 1:
            expected = row["name"]
        elif column == 7:
            expected = (
                row["user"]
                if row["user"] is not None
                else "Unavailable · " + (row["user_reason"] or "User unavailable")
            )
        else:
            key, unit = [
                ("cpu_percent", "Percent"),
                ("memory_bytes", "Bytes"),
                ("read_bytes_per_second", "BytesPerSecond"),
                ("write_bytes_per_second", "BytesPerSecond"),
                ("threads", "Count"),
            ][column - 2]
            reading = row[key]
            check_reading({"id": reading["sensor_id"], "unit": unit}, reading)
            expected = reading_text(frame, reading, unit)
    else:
        if entry["monitor_id"] == "processes":
            sid = "cpu:host/processes"
            title = "Processes"
        else:
            title = next(
                m["title"]
                for m in snapshot["monitors"]
                if m["id"] == entry["monitor_id"]
            )
        sensor = next(s for s in snapshot["sensors"] if s["id"] == sid)
        reading = next(r for r in snapshot["readings"] if r["sensor_id"] == sid)
        check_reading(sensor, reading)
        sample = entry["sample"]
        require(sample is not None, "missing rendered numeric sample")
        require(
            sample["value"] == reading["value"] and sample["total"] == reading["total"],
            "rendered sample changed raw physical quantity",
        )
        if reading["value"] is not None:
            require(
                sample["text"] + " " + sample["unit"]
                == format_sample(dict(reading, unit=sensor["unit"])),
                "rendered sample number/unit differs from independent formatting",
            )
        require(sample["reason"] == reading["reason"], "rendered reason changed")
        expected = (
            title
            + " · "
            + (
                ""
                if entry["element_id"].endswith(":summary")
                else sensor["title"] + " · "
            )
            + reading_text(frame, reading, sensor["unit"])
        )
    require(
        entry["label"] == expected,
        f"independent label mismatch {entry['label']!r} != {expected!r}",
    )
    return expected


def contained(bounds, clips):
    x, y, width, height = bounds
    return (
        width > 0
        and height > 0
        and bool(clips)
        and all(
            cx <= x and cy <= y and x + width <= cx + cw and y + height <= cy + ch
            for cx, cy, cw, ch in clips
        )
    )


def check_transport_record(record):
    require(
        record["exit_code"] == 0
        and record["proc_exists"] is False
        and record["forced_kill"] is False
        and record["errors"] == [],
        f"private accessibility transport cleanup failed: {record}",
    )
