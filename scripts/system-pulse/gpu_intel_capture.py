"""Read-only independent Linux Intel operands. Missing hardware is an error.

Only documented sysfs, i915/xe DRM query and perf_event_open interfaces are used.
Raw ioctl and perf bytes are retained before these independent decoders run.
"""

import argparse
import ctypes
import json
import os
from pathlib import Path
import platform
import re
import stat
import struct
import time

from host_accuracy import require


def read_text(path):
    with path.open("rb") as stream:
        data = stream.read(4097)
    require(len(data) <= 4096, "sysfs value exceeds bound")
    return data.decode().strip()


def entries(path):
    result = []
    with os.scandir(path) as scan:
        for item in scan:
            require(len(result) < 512, "native directory exceeds bound")
            result.append(Path(item.path))
    return sorted(result)


def discover(root=Path("/"), fs=None):
    from gpu_intel_sources import Sysfs

    fs = fs if fs is not None else Sysfs()
    devices = {}
    for alias in fs.scan(root / "sys/class/drm"):
        if not re.fullmatch(r"(card|renderD)[0-9]+", alias.name):
            continue
        physical = fs.resolve(alias / "device")
        vendor = fs.read(physical / "vendor")
        if vendor != "0x8086":
            continue
        driver = fs.resolve(physical / "driver").name
        if driver not in ("i915", "xe"):
            continue
        pci = physical.name
        require(
            re.fullmatch(r"[0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-7]", pci),
            "invalid physical PCI identity",
        )
        device = devices.setdefault(
            pci,
            dict(
                pci=pci,
                driver=driver,
                physical_path=str(physical),
                monitor_id="intel-pci:" + pci,
                aliases=[],
                vendor=vendor,
                device_id=fs.read(physical / "device"),
            ),
        )
        require(
            device["physical_path"] == str(physical) and device["driver"] == driver,
            "ambiguous PCI device",
        )
        device["aliases"].append(dict(path=str(alias), dev=fs.read(alias / "dev")))
    require(devices, "no accessible supported Intel physical hardware")
    return list(devices.values())


def query_buffer(call):
    size = call(None)
    require(type(size) is int and 0 < size <= 1024 * 1024, "invalid DRM sizing result")
    buffer = bytearray(size)
    require(call(buffer) == size, "DRM query status/size changed")
    return bytes(buffer)


def records(driver, data, region):
    require(driver in ("i915", "xe"), "unknown DRM driver")
    header = 16 if driver == "i915" else 8
    stride = 88 if region else (56 if driver == "i915" else 32)
    require(len(data) >= header, "truncated native DRM header")
    count = struct.unpack_from("=I", data)[0]
    require(
        0 < count <= 512
        and len(data) == header + count * stride
        and not any(data[4:header]),
        "invalid DRM count/reserved bytes",
    )
    return [data[header + n * stride : header + (n + 1) * stride] for n in range(count)]


def validate_region(driver, r):
    cls = r["class"]
    total = r["total_bytes"]
    count = r["count_bytes"]
    visible = r["cpu_visible_total_bytes"]
    vcount = r["cpu_visible_count_bytes"]
    require(
        cls in (0, 1)
        and all(
            type(v) is int and 0 <= v < 2**64 - 1
            for v in (total, count, visible, vcount)
        ),
        "invalid native memory integer/class",
    )
    require(vcount <= visible, "invalid visible memory count")
    if cls == 1:
        require(
            0 < total and count <= total and visible <= total and vcount <= count,
            "invalid local-memory bounds",
        )
        if driver == "i915":
            require(
                visible - vcount <= total - count,
                "visible allocation exceeds local allocation",
            )
        else:
            require(
                count - vcount <= total - visible,
                "non-visible allocation exceeds capacity",
            )


def decode_regions(driver, data):
    result = []
    for row in records(driver, data, True):
        cls, instance, page, total, count, visible, vcount = struct.unpack_from(
            "=HHIQQQQ", row
        )
        require(
            not any(row[40:])
            and (
                (page == 0)
                if driver == "i915"
                else (page > 0 and page & (page - 1) == 0)
            ),
            "invalid DRM reserved/page data",
        )
        r = dict(
            **{"class": cls},
            instance=instance,
            total_bytes=total,
            count_bytes=count,
            cpu_visible_total_bytes=visible,
            cpu_visible_count_bytes=vcount,
        )
        validate_region(driver, r)
        result.append(r)
    require(
        len({(r["class"], r["instance"]) for r in result}) == len(result),
        "duplicate native memory region",
    )
    return result


def decode_engines(driver, data):
    result = []
    for row in records(driver, data, False):
        cls, instance = struct.unpack_from("=HH", row)
        gt = struct.unpack_from("=H", row, 4)[0] if driver == "xe" else 0
        require(
            cls <= 4
            and (not any(row[6:]) if driver == "xe" else not any(row[4:8] + row[26:])),
            "invalid native engine layout",
        )
        result.append(dict(engine_class=cls, engine_instance=instance, gt=gt))
    require(
        len({tuple(r.values()) for r in result}) == len(result),
        "duplicate native engine",
    )
    return result


def parse_perf(data, count):
    require(
        count in (1, 2) and len(data) == 8 * (3 + count),
        "invalid native perf read size",
    )
    values = struct.unpack("=" + str(3 + count) + "Q", data)
    require(
        values[0] == count and values[2] <= values[1],
        "invalid perf count/scheduling time",
    )
    return dict(
        enabled_ns=values[1],
        running_ns=values[2],
        active=values[3],
        total=values[4] if count == 2 else 0,
    )


class I915Item(ctypes.Structure):
    _fields_ = [
        ("query_id", ctypes.c_uint64),
        ("length", ctypes.c_int32),
        ("flags", ctypes.c_uint32),
        ("data", ctypes.c_uint64),
    ]


class I915Query(ctypes.Structure):
    _fields_ = [
        ("count", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("items", ctypes.c_uint64),
    ]


class XeQuery(ctypes.Structure):
    _fields_ = [
        ("extensions", ctypes.c_uint64),
        ("query", ctypes.c_uint32),
        ("size", ctypes.c_uint32),
        ("data", ctypes.c_uint64),
        ("reserved", ctypes.c_uint64 * 2),
    ]


def drm_query(fd, driver, query_id):
    require(
        platform.machine() in ("x86_64", "aarch64"),
        "unvalidated ioctl encoding architecture",
    )
    native = ctypes.CDLL(None, use_errno=True)
    native.ioctl.restype = ctypes.c_int

    def call(buffer):
        data = (
            (ctypes.c_ubyte * len(buffer)).from_buffer(buffer)
            if buffer is not None
            else None
        )
        address = ctypes.addressof(data) if data is not None else 0
        length = len(buffer) if buffer is not None else 0
        if driver == "i915":
            item = I915Item(query_id, length, 0, address)
            query = I915Query(1, 0, ctypes.addressof(item))
            opcode = 0xC0106479
        else:
            query = XeQuery(0, query_id, length, address, (ctypes.c_uint64 * 2)())
            opcode = 0xC0286440
        code = native.ioctl(
            ctypes.c_int(fd), ctypes.c_ulong(opcode), ctypes.byref(query)
        )
        if code < 0:
            raise OSError(ctypes.get_errno(), os.strerror(ctypes.get_errno()))
        require(code == 0, "unexpected DRM ioctl result")
        return int(item.length if driver == "i915" else query.size)

    return query_buffer(call)


def open_drm(device, root=Path("/")):
    errors = []
    for alias in sorted(
        device["aliases"], key=lambda a: not Path(a["path"]).name.startswith("renderD")
    ):
        try:
            path = Path(alias["path"])
            require(
                str((path / "device").resolve(strict=True)) == device["physical_path"],
                "DRM alias changed physical GPU",
            )
            fd = os.open(
                root / "dev/dri" / path.name, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC
            )
            try:
                info = os.fstat(fd)
                require(
                    stat.S_ISCHR(info.st_mode)
                    and f"{os.major(info.st_rdev)}:{os.minor(info.st_rdev)}"
                    == alias["dev"],
                    "DRM native device number mismatch",
                )
                return fd
            except BaseException:
                os.close(fd)
                raise
        except (OSError, AssertionError) as error:
            errors.append(str(error))
    raise OSError("no attributable readable DRM node: " + "; ".join(errors))


class Perf:
    def __init__(self, spec):
        self.spec = spec
        self.fds = []
        self.opened_ns = time.monotonic_ns()
        native = ctypes.CDLL(None, use_errno=True)
        native.syscall.restype = ctypes.c_long
        number = {"x86_64": 298, "aarch64": 241}.get(platform.machine())
        require(number is not None, "unvalidated perf syscall architecture")
        try:
            for config in [spec["config_active"]] + (
                [spec["config_total"]] if spec["ticks"] else []
            ):
                attr = ctypes.create_string_buffer(
                    struct.pack(
                        "=IIQQQQQIIQ",
                        spec["pmu_type"],
                        64,
                        config,
                        0,
                        0,
                        11,
                        0,
                        0,
                        0,
                        0,
                    )
                )
                fd = native.syscall(
                    ctypes.c_long(number),
                    ctypes.byref(attr),
                    ctypes.c_int(-1),
                    ctypes.c_int(spec["cpu"]),
                    ctypes.c_int(self.fds[0] if self.fds else -1),
                    ctypes.c_ulong(8),
                )
                if fd < 0:
                    raise OSError(ctypes.get_errno(), os.strerror(ctypes.get_errno()))
                self.fds.append(fd)
        except BaseException:
            self.close()
            raise

    def read(self):
        start = time.monotonic_ns()
        data = os.read(self.fds[0], 8 * (3 + len(self.fds)))
        end = time.monotonic_ns()
        return dict(
            start=start,
            end=end,
            opened_ns=self.opened_ns,
            raw_hex=data.hex(),
            values=parse_perf(data, len(self.fds)),
        )

    def close(self):
        for fd in reversed(self.fds):
            os.close(fd)
        self.fds = []


def anchor():
    before = time.monotonic_ns()
    wall = time.time_ns()
    after = time.monotonic_ns()
    return dict(monotonic_before_ns=before, monotonic_after_ns=after, unix_ns=wall)


def capture_inventory(root=Path("/")):
    from gpu_intel_sources import (
        Sysfs,
        sysfs_fields,
        pmu_fields,
        rapl_perf,
        rapl_powercap,
    )

    root = Path(root).resolve()
    fs = Sysfs()
    devices = discover(root, fs)
    rows = []
    clock = anchor()
    for device in devices:
        row = dict(device)
        row["sysfs_fields"], row["source_errors"] = sysfs_fields(device, fs)
        row["drm"] = {}
        engines = []
        try:
            fd = open_drm(device, root)
            try:
                for name, qid in [
                    ("memory", 4 if device["driver"] == "i915" else 1),
                    ("engines", 2 if device["driver"] == "i915" else 0),
                ]:
                    start = time.monotonic_ns()
                    try:
                        data = drm_query(fd, device["driver"], qid)
                        record = dict(raw_hex=data.hex(), query_id=qid)
                        decoded = (
                            decode_regions(device["driver"], data)
                            if name == "memory"
                            else decode_engines(device["driver"], data)
                        )
                        if name == "engines":
                            engines = decoded
                    except (OSError, AssertionError) as error:
                        record = dict(
                            error=str(error),
                            errno=getattr(error, "errno", None),
                            query_id=qid,
                        )
                    row["drm"][name] = dict(
                        start=start, end=time.monotonic_ns(), **record
                    )
            finally:
                os.close(fd)
        except (OSError, AssertionError) as error:
            for name in ("memory", "engines"):
                row["drm"][name] = dict(
                    error=str(error), errno=getattr(error, "errno", None)
                )
        try:
            row["perf_fields"], row["integrated"] = pmu_fields(
                device, devices, engines, fs, root
            )
        except (OSError, AssertionError, ValueError) as error:
            row["perf_fields"] = []
            row["integrated"] = False
            row["source_errors"].append(
                dict(
                    source="PMU", error=str(error), errno=getattr(error, "errno", None)
                )
            )
        if row["integrated"]:
            for source, function, key in [
                ("RAPL perf", rapl_perf, "perf_fields"),
                ("RAPL powercap", rapl_powercap, "sysfs_fields"),
            ]:
                try:
                    row[key].append(function(device, True, fs, root))
                except (OSError, AssertionError, ValueError) as error:
                    row["source_errors"].append(
                        dict(
                            source=source,
                            error=str(error),
                            errno=getattr(error, "errno", None),
                        )
                    )
        rows.append(row)
    return dict(
        schema=1,
        mode="native"
        if str(root) == "/" and platform.system() == "Linux"
        else "development",
        root=str(root),
        clock_anchor=clock,
        pid=os.getpid(),
        devices=rows,
        sysfs=fs.record,
        os_release=platform.release(),
        machine=platform.machine(),
    )


def replay_fields(frame, row):
    """Rebuild the required field inventory from retained directory/file originals."""
    from gpu_intel_sources import (
        Sysfs,
        sysfs_fields,
        pmu_fields,
        rapl_perf,
        rapl_powercap,
    )

    fs = Sysfs(frame["sysfs"])
    fields, errors = sysfs_fields(row, fs)
    raw = row["drm"]["engines"]
    engines = (
        decode_engines(row["driver"], bytes.fromhex(raw["raw_hex"]))
        if "raw_hex" in raw
        else []
    )
    try:
        perf, integrated = pmu_fields(
            row, frame["devices"], engines, fs, Path(frame["root"])
        )
    except (OSError, AssertionError, ValueError):
        perf = []
        integrated = False
    if integrated:
        for function, target in [(rapl_perf, perf), (rapl_powercap, fields)]:
            try:
                target.append(function(row, True, fs, Path(frame["root"])))
            except (OSError, AssertionError, ValueError):
                pass
    require(
        fields == row["sysfs_fields"]
        and perf == row["perf_fields"]
        and integrated == row["integrated"],
        "independent source inventory does not match originals",
    )
    return fields, perf, integrated


def independent_inventory(frame, pci):
    require(
        frame["schema"] == 1 and frame["mode"] == "native" and frame["root"] == "/",
        "development/rooted capture cannot establish native hardware",
    )
    from gpu_intel_sources import Sysfs

    original_devices = discover(Path(frame["root"]), Sysfs(frame["sysfs"]))
    require(
        original_devices
        == [{k: d[k] for k in original_devices[0]} for d in frame["devices"]],
        "physical Intel inventory differs from original sysfs identities",
    )
    matches = [d for d in frame["devices"] if d["pci"] == pci]
    require(len(matches) == 1, "missing/ambiguous independently inventoried GPU")
    row = matches[0]
    sysfs, perf, integrated = replay_fields(frame, row)
    fields = [dict(f) for f in sysfs + perf]
    memory = row["drm"]["memory"]
    local = False
    if "raw_hex" in memory:
        for region in decode_regions(row["driver"], bytes.fromhex(memory["raw_hex"])):
            dedicated = region["class"] == 1
            local |= dedicated
            prefix = (
                ("local" if dedicated else "shared")
                + "-region-"
                + str(region["instance"])
            )
            common = dict(
                driver=row["driver"],
                region_class=region["class"],
                region_instance=region["instance"],
                formula="intel-memory",
                source=f"DRM {row['driver']} QUERY_MEMORY_REGIONS (bytes); PCI {pci}",
                unit="Bytes",
                precision=0,
            )
            scope = (
                "Dedicated device-local VRAM region; estimate of allocation, not visible-client sum"
                if dedicated
                else "This device's TTM system-memory region allocation; not total system RAM or unique resident process memory"
            )
            field = dict(
                sensor_id=row["monitor_id"] + "/" + prefix,
                kind="Capacity" if dedicated else "Counter",
                memory_metric="allocation",
                scope=scope,
                **common,
            )
            if row["driver"] == "i915" and (
                not dedicated or region["count_bytes"] == region["total_bytes"]
            ):
                field["limitation"] = "unattributable"
            fields.append(field)
            if dedicated:
                fields.append(
                    dict(
                        sensor_id=row["monitor_id"] + "/" + prefix + "-total",
                        kind="Counter",
                        memory_metric="total",
                        scope="Dedicated device-local VRAM capacity in bytes",
                        **common,
                    )
                )
                if region["cpu_visible_total_bytes"] > 0:
                    field = dict(
                        sensor_id=row["monitor_id"] + "/" + prefix + "-cpu-visible",
                        kind="Capacity",
                        memory_metric="cpu-visible",
                        scope="CPU-accessible subset of this local VRAM region; overlaps the whole region",
                        **common,
                    )
                    if (
                        row["driver"] == "i915"
                        and region["cpu_visible_count_bytes"]
                        == region["cpu_visible_total_bytes"]
                    ):
                        field["limitation"] = "unattributable"
                    fields.append(field)
    else:
        for suffix, kind, scope in [
            ("local-memory", "Capacity", "Device-local regions unavailable"),
            (
                "shared-memory",
                "Counter",
                "Device system-memory allocation unavailable; not system RAM",
            ),
        ]:
            fields.append(
                dict(
                    sensor_id=row["monitor_id"] + "/" + suffix,
                    formula="native-limitation",
                    unit="Bytes",
                    kind=kind,
                    source=f"DRM {row['driver']} QUERY_MEMORY_REGIONS (bytes); PCI {pci}",
                    scope=scope,
                    precision=0,
                    limitation="denied" if memory.get("errno") in (1, 13) else "absent",
                )
            )
    placeholders = [
        ("temperature", "Temperature", "Celsius", "Intel device hwmon temperature"),
        (
            "power",
            "Power",
            "Watts",
            "Intel device hwmon energy/power; attributable RAPL graphics domain where available",
        ),
        ("fan", "Fan", "Rpm", "Intel device hwmon tachometer"),
        ("frequency-actual", "Frequency", "Hertz", "i915/xe GT sysfs actual frequency"),
    ]
    for suffix, kind, unit, source in placeholders:
        if not any(f["kind"] == kind for f in sysfs):
            fields.append(
                dict(
                    sensor_id=row["monitor_id"] + "/" + suffix,
                    formula="native-limitation",
                    unit=unit,
                    kind=kind,
                    source=source,
                    scope="Physical GPU; no package/die or system-fan substitution",
                    precision=0,
                    limitation="absent",
                )
            )
    if not any(f["kind"] == "Percentage" for f in perf):
        fields.append(
            dict(
                sensor_id=row["monitor_id"] + "/usage",
                formula="native-limitation",
                unit="Percent",
                kind="Percentage",
                source="Linux Intel device PMU",
                scope="No whole-device activity inferred from clients or clocks",
                precision=0,
                limitation="absent",
            )
        )
    require(
        not (integrated and local), "contradictory integrated/discrete native facts"
    )
    require(integrated or local, "hardware class not independently established")
    device = {
        k: row[k]
        for k in ("pci", "driver", "physical_path", "monitor_id", "vendor", "device_id")
    }
    return dict(
        hardware_class="intel-integrated" if integrated else "intel-discrete",
        device=device,
        fields=fields,
        captured_unix_ns=frame["clock_anchor"]["unix_ns"],
    )


def normalize_observer(frame, inventory):
    current = independent_inventory(frame, inventory["device"]["pci"])
    require(
        current["device"] == inventory["device"]
        and current["fields"] == inventory["fields"],
        "native device/source inventory changed during measurement",
    )
    row = next(d for d in frame["devices"] if d["pci"] == inventory["device"]["pci"])
    samples = []
    for field in inventory["fields"]:
        if field.get("limitation"):
            continue
        formula = field["formula"]
        if formula in ("intel-sysfs", "intel-energy"):
            original = frame["sysfs"]["files"][field["path"]]
            value = int(bytes.fromhex(original["data_hex"]).decode().strip())
            require(field.get("signed") or value >= 0, "negative unsigned sysfs value")
            values = {"signed_value" if field.get("signed") else "value": value}
        elif formula == "intel-perf":
            matches = [r for r in frame["perf"] if r["sensor_id"] == field["sensor_id"]]
            require(len(matches) == 1, "missing/ambiguous native perf handle")
            original = matches[0]
            values = parse_perf(
                bytes.fromhex(original["raw_hex"]), 2 if field["ticks"] else 1
            )
            require(values == original["values"], "perf decode differs from raw read")
            require(
                values["enabled_ns"] == values["running_ns"], "native perf multiplexed"
            )
        elif formula == "intel-memory":
            original = row["drm"]["memory"]
            matches = [
                r
                for r in decode_regions(
                    row["driver"], bytes.fromhex(original["raw_hex"])
                )
                if r["class"] == field["region_class"]
                and r["instance"] == field["region_instance"]
            ]
            require(len(matches) == 1, "native memory region changed")
            values = matches[0]
        else:
            raise AssertionError("unknown independently measured Intel source")
        samples.append(
            dict(
                start=original["start"],
                end=original["end"],
                source=field["source"],
                sensor_id=field["sensor_id"],
                values=values,
                **(
                    {"opened_ns": original["opened_ns"]}
                    if formula == "intel-perf"
                    else {}
                ),
            )
        )
    return dict(clock_anchor=frame["clock_anchor"], samples=samples)


def observe(count, interval, root):
    handles = {}
    try:
        for _ in range(count):
            frame = capture_inventory(root)
            frame["perf"] = []
            live = {
                f["sensor_id"]: f
                for device in frame["devices"]
                for f in device["perf_fields"]
            }
            for sid in list(handles):
                if sid not in live or handles[sid].spec != live[sid]:
                    handles.pop(sid).close()
            for sid, spec in live.items():
                try:
                    if sid not in handles:
                        handles[sid] = Perf(spec)
                    result = handles[sid].read()
                except (OSError, AssertionError) as error:
                    if sid in handles:
                        handles.pop(sid).close()
                    result = dict(error=str(error), errno=getattr(error, "errno", None))
                frame["perf"].append(dict(sensor_id=sid, **result))
            print(json.dumps(frame), flush=True)
            if _ + 1 < count:
                time.sleep(interval / 1000)
    finally:
        for handle in handles.values():
            handle.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--interval-ms", type=int, default=100)
    parser.add_argument("--development-root", type=Path)
    args = parser.parse_args()
    require(
        1 <= args.count <= 100000
        and 10 <= args.interval_ms <= 5000
        and args.count * args.interval_ms <= 3600000,
        "native observer bounds exceeded",
    )
    observe(args.count, args.interval_ms, args.development_root or Path("/"))


if __name__ == "__main__":
    main()
