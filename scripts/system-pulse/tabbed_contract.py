"""Independent text and clipping checks for the tabbed presentation."""

from host_accuracy import check_reading, format_sample, require
from native_contract import contained

SCREENS = (
    "summary", "cpu", "memory", "gpu", "disks", "network", "energy",
    "thermals", "processes", "settings",
)


def clipped_visible(bounds, window, ancestors):
    clips = [window]
    for ancestor in ancestors:
        aid = ancestor.get("id") or ""
        if ancestor.get("role") == "menu" or aid.endswith((":viewport", "-viewport")) or aid in {"screen:" + s for s in SCREENS}:
            require(ancestor.get("bounds") is not None, "missing native clipping bounds")
            clips.append(ancestor["bounds"])
    return contained(bounds, clips)


def expected_metric(frame, sensor_id, interval_ms):
    require(type(interval_ms) is int and interval_ms > 0, "missing sampling interval")
    snapshot = frame["snapshot"]
    sensor = next(s for s in snapshot["sensors"] if s["id"] == sensor_id)
    reading = next(r for r in snapshot["readings"] if r["sensor_id"] == sensor_id)
    check_reading(sensor, reading)
    if reading["value"] is None:
        return {
            "WarmingUp": "Warming up", "Failed": "Reading failed",
            "Unavailable": "Unavailable",
        }[reading["availability"]]
    text = format_sample(dict(reading, unit=sensor["unit"]))
    observed = max(
        (o["captured_ns"] // 1_000_000 for o in reading["observations"]),
        default=snapshot["capture_finished_ns"] // 1_000_000,
    )
    # Production accepts samples as stale after two requested intervals.
    if frame["rendered_at_collector_ms"] - observed > 2 * interval_ms:
        text += " · stale"
    return text


def check_metric(frame, sensor_id, actual, interval_ms):
    expected = expected_metric(frame, sensor_id, interval_ms)
    require(actual == expected, f"native metric differs: {sensor_id}: {actual!r} != {expected!r}")
    return expected


REQUIRED_CASES = frozenset({
    "screens-devices-metrics", "process-actions", "settings-presets",
    "minimum-window", "restart", "unavailable-recovery",
})


def check_replay(result, binary_sha256):
    require(result["status"] == "PASS" and result["binary_sha256"] == binary_sha256,
            "tabbed replay did not pass against the built binary")
    require(len(result["cases"]) == len(REQUIRED_CASES)
            and set(result["cases"]) == REQUIRED_CASES, "missing tabbed product cases")
    require(len(result["checks"]) == len(REQUIRED_CASES), "missing product check descriptions")
    accounted = list(result["devices"])
    for lost in result["disappeared_devices"]:
        require(lost["choice"]["id"] not in {m["id"] for m in lost["frame"]["snapshot"]["monitors"]},
                "available device incorrectly recorded as disappeared")
        accounted.append(lost["choice"])
    key = lambda choice: (choice["screen"], choice["id"], choice["title"])
    require(sorted(accounted, key=key) == sorted(result["expected_devices"], key=key),
            "not every discovered device was selected or independently observed gone")
    require(len(result["children"]) == 3 and all(child["exit_code"] is not None for child in result["children"]),
            "owned process-action children remain running")


def device_label(monitor, monitors):
    """Expected visible identity when hardware reports duplicate product names."""
    if monitor["kind"] == "Gpu" and sum(m["title"] == monitor["title"] for m in monitors) > 1:
        return monitor["title"] + " · " + monitor["id"]
    return monitor["title"]
