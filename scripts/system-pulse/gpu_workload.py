"""Bind completed physical GPU work to independently observed load measurements."""

from gpu_desktop import anchored_time
from host_accuracy import require


def validate_intel_work(record, device, seconds):
    require(
        record["schema"] == 1
        and record["api"] == "Vulkan"
        and record["pci"] == device["pci"]
        and record["vendor_id"] == int(device["vendor"], 16) == 0x8086
        and record["device_id"] == int(device["device_id"], 16)
        and record["identity_extension"] is True
        and record["matching_devices"] == 1,
        "Vulkan work did not target the independently selected Intel PCI device",
    )
    devices = record["devices"]
    matches = [d for d in devices if d.get("pci") == device["pci"]]
    require(
        1 <= len(devices) <= 32
        and len(matches) == 1
        and all(
            matches[0][k] == record[k]
            for k in ("pci", "vendor_id", "device_id", "identity_extension")
        ),
        "Vulkan physical census lacks one attributable selected device",
    )
    require(
        record["bytes"] == 4 * 1024**2
        and record["bytes"] <= record["allocation_bytes"] <= 64 * 1024**2
        and type(record["commands_completed"]) is int
        and 0 < record["commands_completed"] == record["commands_submitted"] <= 2000000
        and record["max_in_flight"] == 1
        and 0 <= record["queue_family"] < 64
        and record["queue_flags"] & 7
        and record["fence_timeout_ns"] == 500000000
        and record["duration_ns"]
        == record["work_finished_ns"] - record["work_started_ns"]
        and 0 < record["duration_ns"] <= seconds * 10**9,
        "missing, unbounded or incomplete serial Vulkan buffer-fill work",
    )
    require(
        0
        <= record["query_started_ns"]
        <= record["query_finished_ns"]
        <= record["work_started_ns"],
        "physical identity was not queried before GPU work",
    )


def validate_overlap(work, process, diagnostics, observer, policy):
    """Require a consumed query and independent matching source inside completed work.

    Conservatively use the inner work bounds after clock uncertainty. Acceptance
    time alone cannot turn a pre-work collector query into a load measurement.
    """
    start = anchored_time(work["work_started_ns"], work["clock_anchor"])
    end = anchored_time(work["work_finished_ns"], work["clock_anchor"])
    require(
        process["started_unix_ns"]
        <= start[0]
        <= start[1]
        < end[0]
        <= end[1]
        <= process["finished_unix_ns"],
        "completed work outside owned process interval",
    )
    require(
        0
        < work["work_finished_ns"] - work["work_started_ns"]
        <= policy["workload_seconds"] * 10**9,
        "completed work interval exceeds predeclared duration",
    )
    fields = {f["sensor_id"]: f for f in policy["fields"] if not f.get("limitation")}
    for diagnostic in diagnostics:
        if not start[1] <= diagnostic["accepted_unix_ns"] <= end[0]:
            continue
        snapshot = diagnostic["snapshot"]
        for reading in snapshot["readings"]:
            field = fields.get(reading["sensor_id"])
            observations = reading["observations"]
            if not field or reading["availability"] != "Available" or not observations:
                continue
            first = anchored_time(
                observations[0]["read_started_ns"], snapshot["clock_anchor"]
            )
            last = anchored_time(
                observations[-1]["captured_ns"], snapshot["clock_anchor"]
            )
            if not start[1] <= first[0] <= last[1] <= end[0]:
                continue
            for frame in observer:
                for sample in frame["samples"]:
                    if sample["source"] != field.get("raw_source", field["source"]):
                        continue
                    if any(
                        sample.get(k) != field[k]
                        for k in ("driver_id", "channel_id")
                        if k in field
                    ):
                        continue
                    if (
                        "sensor_id" in sample
                        and sample["sensor_id"] != reading["sensor_id"]
                    ):
                        continue
                    before = anchored_time(sample["start"], frame["clock_anchor"])
                    after = anchored_time(sample["end"], frame["clock_anchor"])
                    if start[1] <= before[0] <= after[1] <= end[0]:
                        return
    raise AssertionError(
        "no consumed GPU query and independent source measurement inside completed work"
    )
