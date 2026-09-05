"""Fresh stdlib OS observations, independent of collector descriptors."""

import argparse
import collections
import errno
import json
import os
from pathlib import Path
import pwd
import re
import select
import signal
import stat
import subprocess
import sys
import threading
import time

from host_accuracy import (
    check_reading,
    check_counter,
    check_process_counter,
    clock_intersection,
    map_window,
    parse_process_stat,
    require,
    connection_counts,
    normalized,
)

CPU_FIELDS = ("user", "nice", "system", "idle", "iowait", "irq", "softirq", "steal")
DISK_FIELDS = {
    "read_ops": 0,
    "read_sectors": 2,
    "read_ms": 3,
    "write_ops": 4,
    "write_sectors": 6,
    "write_ms": 7,
}
PSEUDO_FS = set(
    "proc sysfs devpts cgroup cgroup2 securityfs debugfs tracefs configfs pstore bpf mqueue hugetlbfs fusectl autofs binfmt_misc rpc_pipefs nsfs efivarfs".split()
)


def anchor():
    before = time.monotonic_ns()
    wall = time.time_ns()
    after = time.monotonic_ns()
    return before, after, wall


def unescape(value):
    return re.sub(r"\\([0-7]{3})", lambda m: chr(int(m[1], 8)), value)


def observe(source, reader):
    start = time.monotonic_ns()
    try:
        value = reader()
        return {
            "source": source,
            "start": start,
            "end": time.monotonic_ns(),
            "value": value,
            "errno": None,
        }
    except OSError as error:
        return {
            "source": source,
            "start": start,
            "end": time.monotonic_ns(),
            "value": None,
            "errno": error.errno,
            "error": error.strerror,
        }


def scalar(path):
    return observe(
        str(path),
        lambda: (
            lambda value: int(value)
            if re.fullmatch(r"[+-]?[0-9]+", value)
            else float(value)
        )(Path(path).read_text().strip()),
    )


def process(pid):
    root = Path("/proc") / str(pid)
    observation = observe(
        str(root / "stat"), lambda: parse_process_stat((root / "stat").read_text())
    )
    status = observe(
        str(root / "status"),
        lambda: int(
            next(
                line.split()[1]
                for line in (root / "status").read_text().splitlines()
                if line.startswith("Uid:")
            )
        ),
    )
    io = observe(
        str(root / "io"),
        lambda: dict(
            (k, int(v))
            for k, v in (
                line.split(":", 1) for line in (root / "io").read_text().splitlines()
            )
            if k in ("read_bytes", "write_bytes")
        ),
    )
    return {"stat": observation, "uid": status, "io": io}


def start_child():
    code = "import ctypes,time; ctypes.CDLL(None).prctl(15,b'pulse ) probe',0,0,0); time.sleep(600)"
    child = subprocess.Popen([sys.executable, "-B", "-c", code])
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        info = process(child.pid)
        if info["stat"]["value"] and info["stat"]["value"]["name"] == "pulse ) probe":
            return child, info
        time.sleep(0.02)
    stop_child(child)
    raise AssertionError("real probe child did not initialize within five seconds")


def stop_child(child):
    if child.poll() is None:
        child.terminate()
        child.send_signal(signal.SIGCONT)
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=5)
            raise AssertionError(
                f"owned process {child.pid} required forced SIGKILL cleanup"
            )
    return child.returncode


class Observer:
    def __init__(self):
        self.capabilities = []
        self.errors = []
        self.scalars = set()
        self.disks = set()
        self.mounts = []
        self.anchors = []
        self.samples = []
        self.stop = threading.Event()
        self.failure = None
        self.previous_pids = set()
        self.inventory_started_ns = time.monotonic_ns()
        self.enumerate()
        self.inventory_finished_ns = time.monotonic_ns()

    def add(self, sid, source, unit, probe):
        self.capabilities.append(
            {"id": sid, "source": str(source), "unit": unit, "probe": probe}
        )

    def enumerate(self):
        # Enumerate the operating system first. Descriptors are not available here.
        cpu = Path("/proc/stat").read_text().splitlines()
        for line in cpu:
            name = line.split()[0]
            if re.fullmatch(r"cpu[0-9]*", name):
                sid = (
                    "cpu:host/usage"
                    if name == "cpu"
                    else "cpu:host/core-" + name[3:] + "-usage"
                )
                self.add(
                    sid,
                    "/proc/stat:" + name,
                    "Percent",
                    {"errno": None, "value": list(map(int, line.split()[1:9]))},
                )
                if name != "cpu":
                    source = f"/sys/devices/system/cpu/{name}/cpufreq/scaling_cur_freq"
                    probe = scalar(source)
                    if probe["errno"] == errno.ENOENT:
                        source = "/proc/cpuinfo:cpu MHz"
                        raw = Path("/proc/cpuinfo").read_text()
                        blocks = [
                            dict(
                                (k.strip(), v.strip())
                                for k, v in (
                                    line.split(":", 1)
                                    for line in b.splitlines()
                                    if ":" in line
                                )
                            )
                            for b in raw.split("\n\n")
                        ]
                        values = {
                            b["processor"]: float(b["cpu MHz"])
                            for b in blocks
                            if "processor" in b and "cpu MHz" in b
                        }
                        probe = {
                            "errno": None if name[3:] in values else errno.ENODATA,
                            "value": values.get(name[3:]),
                        }
                    else:
                        self.scalars.add(source)
                    self.add(
                        "cpu:host/core-" + name[3:] + "-frequency",
                        source,
                        "Hertz",
                        probe,
                    )
        for suffix, source, unit in [
            (f"load-{n}", "/proc/loadavg", "Load") for n in (1, 5, 15)
        ] + [
            ("uptime", "/proc/uptime", "Seconds"),
            ("threads", "/proc/loadavg: fourth field total", "Count"),
            ("processes", "/proc", "Count"),
        ]:
            path = source.split(":")[0]
            probe = observe(
                path,
                lambda p=path: len(list(Path(p).iterdir()))
                if p == "/proc"
                else Path(p).read_text(),
            )
            self.add("cpu:host/" + suffix, source, unit, probe)
        for suffix in (
            "used",
            "total",
            "available",
            "free",
            "cache",
            "buffers",
            "other",
            "swap",
            "swap-total",
            "page-faults",
            "major-page-faults",
        ):
            source = "/proc/vmstat" if "faults" in suffix else "/proc/meminfo"
            self.add(
                "memory:host/" + suffix,
                source,
                "Count" if "faults" in suffix else "Bytes",
                observe(source, lambda p=source: Path(p).read_text()),
            )
        for hw in Path("/sys/class/hwmon").glob("hwmon*"):
            driver = observe(
                str(hw / "name"), lambda: (hw / "name").read_text().strip()
            )
            if driver["value"] not in (
                "coretemp",
                "k10temp",
                "zenpower",
                "cpu_thermal",
                "scpi_sensors",
            ):
                continue
            stable = str((hw / "device").resolve()).lstrip("/")
            for source in hw.glob("temp*_input"):
                label_path = source.with_name(source.name.replace("_input", "_label"))
                label = observe(
                    str(label_path), lambda: label_path.read_text().strip()
                )["value"] or source.name.removesuffix("_input")
                self.add(
                    f"cpu:host/temperature:{stable}:{label}",
                    str(source),
                    "Celsius",
                    scalar(source),
                )
                self.scalars.add(str(source))
        for card in Path("/sys/class/drm").glob("card[0-9]*"):
            if not re.fullmatch(r"card[0-9]+", card.name):
                continue
            base = card / "device"
            vendor = observe(
                str(base / "vendor"), lambda: (base / "vendor").read_text().strip()
            )
            if vendor["errno"] is not None:
                self.errors.append(vendor)
                continue
            if vendor["value"] != "0x1002":
                self.errors.append(
                    {
                        "source": str(base),
                        "vendor": vendor["value"],
                        "scope": "independent non-AMD adapter not implemented",
                    }
                )
                continue
            unique = observe(
                str(base / "unique_id"),
                lambda: (base / "unique_id").read_text().strip(),
            )["value"]
            identity = unique if unique and unique != "0" else base.resolve().name
            mid = "amdgpu:" + identity
            self.add(
                mid + "/usage",
                str(base / "gpu_busy_percent"),
                "Percent",
                scalar(base / "gpu_busy_percent"),
            )
            self.scalars.add(str(base / "gpu_busy_percent"))
            paths = [base / "mem_info_vram_used", base / "mem_info_vram_total"]
            self.add(
                mid + "/vram",
                "; ".join(map(str, paths)),
                "Bytes",
                {
                    "errno": next(
                        (p["errno"] for p in map(scalar, paths) if p["errno"]), None
                    ),
                    "value": [scalar(p)["value"] for p in paths],
                },
            )
            self.scalars.update(map(str, paths))
            for hw in (base / "hwmon").glob("hwmon*"):
                fields = [
                    ("temp" + str(n), "temp" + str(n) + "_input", "Celsius")
                    for n in (1, 2, 3)
                ]
                fields += [
                    ("power-average", "power1_average", "Watts"),
                    ("power-instant", "power1_input", "Watts"),
                    ("clock-graphics", "freq1_input", "Hertz"),
                    ("clock-memory", "freq2_input", "Hertz"),
                    ("fan-rpm", "fan1_input", "Rpm"),
                ]
                for suffix, file, unit in fields:
                    source = str(hw / file)
                    self.add(mid + "/" + suffix, source, unit, scalar(source))
                    self.scalars.add(source)
        for interface in Path("/sys/class/net").iterdir():
            name = interface.name
            device = interface / "device"
            mac = observe(
                str(interface / "address"),
                lambda: (interface / "address").read_text().strip(),
            )["value"]
            if device.exists():
                mid = f"network:path:{device.resolve()}:name:{name}"
            elif mac and mac != "00:00:00:00:00:00":
                mid = f"network:mac:{mac}:name:{name}"
            else:
                mid = f"network:name:{name}"
            for direction in ("rx", "tx"):
                source = str(interface / "statistics" / (direction + "_bytes"))
                self.scalars.add(source)
                for suffix, unit in [
                    (direction, "BytesPerSecond"),
                    (direction + "-total", "Bytes"),
                ]:
                    self.add(mid + "/" + suffix, source, unit, scalar(source))
            self.add(
                mid + "/connections",
                "/proc/net/tcp; /proc/net/tcp6; sysinfo::NetworkData::ip_networks",
                "Count",
                {"errno": None, "value": name},
            )
        uuids = {p.resolve(): p.name for p in Path("/dev/disk/by-uuid").glob("*")}
        for line in Path("/proc/self/mountinfo").read_text().splitlines():
            left, right = line.split(" - ", 1)
            a = left.split()
            b = right.split()
            if b[0] in PSEUDO_FS:
                continue
            mount, source, root = map(unescape, (a[4], b[1], a[3]))
            block = a[2]
            if b[0] == "fuseblk":
                probe = observe(source, lambda: os.stat(source))
                if probe["errno"] is None and stat.S_ISBLK(probe["value"].st_mode):
                    block = f"{os.major(probe['value'].st_rdev)}:{os.minor(probe['value'].st_rdev)}"
            uuid = uuids.get(Path(source).resolve())
            backing = observe(
                "/sys/dev/block/" + block + "/loop/backing_file",
                lambda: Path("/sys/dev/block/" + block + "/loop/backing_file")
                .read_text()
                .strip(),
            )["value"]
            identity = (
                "uuid:" + uuid
                if uuid
                else "loop-file:" + backing
                if backing
                else "source:" + source
            )
            mid = f"volume:{identity}:{root}:{mount}"
            self.mounts.append(mount)
            self.add(
                mid + "/capacity",
                f"statvfs({mount})",
                "Bytes",
                observe(mount, lambda m=mount: list(os.statvfs(m))),
            )
            path = f"/sys/dev/block/{block}/stat"
            self.disks.add(path)
            for suffix, unit in [
                ("read", "BytesPerSecond"),
                ("write", "BytesPerSecond"),
                ("iops", "CountPerSecond"),
                ("latency", "Milliseconds"),
            ]:
                self.add(
                    mid + "/" + suffix,
                    path,
                    unit,
                    observe(path, lambda p=path: Path(p).read_text()),
                )

    def capture_processes(self, pids):
        # Births are most vulnerable to the collector outrunning the observer.
        # Every enumerated PID is still sampled and joined by actual start ticks.
        ordered = sorted(pids, key=lambda pid: pid in self.previous_pids)
        result = {str(pid): process(pid) for pid in ordered}
        self.previous_pids = set(pids)
        return result

    def capture(self):
        self.anchors.append(anchor())
        rows = {}

        def put(source, reader):
            rows[source] = observe(source, reader)

        put(
            "/proc",
            lambda: [int(p.name) for p in Path("/proc").iterdir() if p.name.isdigit()],
        )
        processes = self.capture_processes(rows["/proc"]["value"])
        put(
            "/proc/stat",
            lambda: {
                line.split()[0]: dict(zip(CPU_FIELDS, map(int, line.split()[1:9])))
                for line in Path("/proc/stat").read_text().splitlines()
                if re.match(r"^cpu[0-9]* ", line)
            },
        )
        put(
            "/proc/vmstat",
            lambda: {
                k: int(v)
                for k, v in (
                    line.split()
                    for line in Path("/proc/vmstat").read_text().splitlines()
                )
                if k in ("pgfault", "pgmajfault")
            },
        )
        put(
            "/proc/meminfo",
            lambda: {
                k: int(v.split()[0])
                for k, v in (
                    line.split(":", 1)
                    for line in Path("/proc/meminfo").read_text().splitlines()
                )
            },
        )
        put("/proc/loadavg", lambda: Path("/proc/loadavg").read_text().strip())
        put("/proc/uptime", lambda: Path("/proc/uptime").read_text().strip())
        for path in self.scalars:
            rows[path] = scalar(path)
        for path in self.disks:
            put(
                path,
                lambda p=path: {
                    key: int(Path(p).read_text().split()[index])
                    for key, index in DISK_FIELDS.items()
                },
            )
        for mount in self.mounts:
            put(f"statvfs({mount})", lambda m=mount: list(os.statvfs(m)))
        self.anchors.append(anchor())
        self.samples.append({"sources": rows, "processes": processes})

    def run(self):
        try:
            deadline = time.monotonic() + 35
            while not self.stop.is_set():
                require(
                    time.monotonic() < deadline and len(self.samples) < 2048,
                    "independent observer bounded capture exceeded",
                )
                self.capture()
        except BaseException as error:
            self.failure = error


def connections(snapshot):
    evidence = snapshot["network_attribution"]
    require(evidence, "missing connection attribution")
    address = evidence["interface_addresses"]
    queries = [
        address["query"],
        evidence["tcp_v4"]["query"],
        evidence["tcp_v6"]["query"],
    ]
    for query in queries:
        require(
            snapshot["capture_started_ns"]
            <= query["read_started_ns"]
            <= query["captured_ns"]
            <= snapshot["capture_finished_ns"],
            "invalid connection query window",
        )
    for key, family in [("tcp_v4", "Ipv4"), ("tcp_v6", "Ipv6")]:
        table = evidence[key]
        require(table["address_family"] == family, "wrong address family")
        require(
            table["word_byte_order"]
            == ("LittleEndian" if sys.byteorder == "little" else "BigEndian"),
            "wrong address endianness",
        )
        for row in table["rows"]:
            require(
                set(row) == {"line_number", "local_address_hex", "state_hex"},
                "unexpected connection data retained",
            )
    available = all(q["availability"] == "Available" for q in queries)
    counts = connection_counts(
        address["interfaces"],
        evidence["tcp_v4"]["rows"] if available else [],
        evidence["tcp_v6"]["rows"] if available else [],
        sys.byteorder,
    )
    owners = collections.defaultdict(set)
    for name, values in address["interfaces"].items():
        for value in values:
            value = normalized(value)
            if not value.is_unspecified:
                owners[value].add(name)
    attributable = {next(iter(v)) for v in owners.values() if len(v) == 1}
    readings = {r["sensor_id"]: r for r in snapshot["readings"]}
    for monitor in snapshot["monitors"]:
        if monitor["kind"] != "Network":
            continue
        r = readings[monitor["id"] + "/connections"]
        name = monitor["title"]
        expected = (
            "Unavailable"
            if name not in attributable
            else "Available"
            if available
            else "Failed"
        )
        require(
            r["availability"] == expected,
            f"connection status {name}: {r['availability']} != {expected}",
        )
        if expected == "Available":
            require(r["value"] == counts[name], f"connection count {name}")
    return len(counts)


def monitor_identity(sensor_id):
    if sensor_id.startswith("cpu:host/"):
        return "cpu:host", "Cpu"
    if sensor_id.startswith("memory:host/"):
        return "memory:host", "Memory"
    for prefix, kind in (
        ("amdgpu:", "Gpu"),
        ("network:", "Network"),
        ("volume:", "Volume"),
    ):
        if sensor_id.startswith(prefix):
            return sensor_id.rsplit("/", 1)[0], kind
    raise AssertionError(f"independent monitor identity unsupported: {sensor_id}")


def verify_inventory(capabilities, snapshot):
    expected = {c["id"]: c for c in capabilities}
    require(len(expected) == len(capabilities), "duplicate independent sensor identity")
    sensors = {s["id"]: s for s in snapshot["sensors"]}
    readings = {r["sensor_id"]: r for r in snapshot["readings"]}
    require(
        len(sensors) == len(snapshot["sensors"]), "duplicate collector sensor identity"
    )
    require(
        len(readings) == len(snapshot["readings"]),
        "duplicate collector reading identity",
    )
    require(
        set(sensors) == set(readings) == set(expected),
        f"unverified capture-window sensor discovery: extra={sorted(set(sensors) - set(expected))}, missing={sorted(set(expected) - set(sensors))}, reading_difference={sorted(set(readings) ^ set(sensors))}",
    )
    expected_monitors = dict(monitor_identity(sid) for sid in expected)
    monitors = {m["id"]: m["kind"] for m in snapshot["monitors"]}
    require(
        len(monitors) == len(snapshot["monitors"]),
        "duplicate collector monitor identity",
    )
    require(
        monitors == expected_monitors,
        f"unverified capture-window monitor discovery: extra={sorted(set(monitors) - set(expected_monitors))}, missing={sorted(set(expected_monitors) - set(monitors))}, wrong_kinds={[mid for mid in monitors.keys() & expected_monitors.keys() if monitors[mid] != expected_monitors[mid]]}",
    )
    aliases = {
        "/proc/meminfo": {"/proc/meminfo", "/proc/meminfo (kB = 1024 bytes)"},
        "/proc/loadavg: fourth field total": {
            "/proc/loadavg: total scheduling entities"
        },
        "/proc": {"/proc numeric directories"},
        "/proc/net/tcp; /proc/net/tcp6; sysinfo::NetworkData::ip_networks": {
            "Snapshot.network_attribution"
        },
    }
    for sid, capability in expected.items():
        sensor = sensors[sid]
        require(
            sensor["monitor_id"] == monitor_identity(sid)[0],
            f"wrong monitor attribution: {sid}",
        )
        require(
            sensor["source"] == capability["source"]
            and sensor["unit"] == capability["unit"],
            f"wrong OS source/unit: {sid}",
        )
        allowed = aliases.get(capability["source"], {capability["source"]})
        for observation in readings[sid]["observations"]:
            require(
                observation["source"] in allowed,
                f"wrong raw source attribution: {sid}: {observation['source']}",
            )


def verify_stable_totals(observer, snapshot, collector, external):
    evidence = []
    for reading in snapshot["readings"]:
        for observation in reading["observations"]:
            source, values = observation["source"], observation["integers"]
            totals = []
            if source.startswith("/proc/meminfo"):
                totals = [
                    ("/proc/meminfo", key, values[key], lambda value, k=key: value[k])
                    for key in ("MemTotal", "SwapTotal")
                    if key in values
                ]
            elif source.startswith("statvfs("):
                totals = [
                    (
                        source,
                        "capacity_bytes",
                        values["blocks"] * values["fragment_size"],
                        lambda value: value[1] * value[2],
                    )
                ]
            elif reading["sensor_id"].startswith("amdgpu:") and "total" in values:
                paths = source.split("; ")
                require(
                    len(paths) == 2 and paths[1].endswith("/mem_info_vram_total"),
                    "invalid GPU total source",
                )
                totals = [(paths[1], "total", values["total"], lambda value: value)]
            start = observation["read_started_ns"]
            window = map_window(
                (
                    snapshot["capture_started_ns"] if start is None else start,
                    observation["captured_ns"],
                ),
                collector,
                external,
            )
            for path, key, value, extract in totals:
                attempts = [
                    sample["sources"][path]
                    for sample in observer.samples
                    if path in sample["sources"]
                ]
                samples = [
                    {**sample, "value": extract(sample["value"])}
                    for sample in attempts
                    if sample["errno"] is None
                ]
                before = [sample for sample in samples if sample["end"] <= window[0]]
                after = [sample for sample in samples if sample["start"] >= window[1]]
                context = f"stable total {reading['sensor_id']} {path} {key} query={window} attempts={attempts}"
                require(before and after, "missing stable-total bracket: " + context)
                a, b = (
                    max(before, key=lambda sample: sample["end"]),
                    min(after, key=lambda sample: sample["start"]),
                )
                require(
                    a["value"] == b["value"],
                    "changed independent total; exact comparison unavailable: "
                    + context,
                )
                require(
                    value == a["value"],
                    f"wrong independent stable total {value} != {a['value']}: "
                    + context,
                )
                evidence.append(
                    {
                        "sensor_id": reading["sensor_id"],
                        "source": path,
                        "key": key,
                        "value": value,
                        "window": window,
                        "before": a,
                        "after": b,
                        "snapshot_sequence": snapshot["sequence"],
                    }
                )
    return evidence


def verify_capture(observer, snapshots, child_info):
    require(len(snapshots) >= 3, "missing fresh snapshot sequence")
    require(observer.failure is None, f"external observer failed: {observer.failure}")
    external = clock_intersection(observer.anchors)
    collector = clock_intersection(
        [
            (
                s["clock_anchor"]["monotonic_before_ns"],
                s["clock_anchor"]["monotonic_after_ns"],
                s["clock_anchor"]["unix_ns"],
            )
            for s in snapshots
        ]
    )
    counts = collections.Counter()
    final_capabilities = getattr(observer, "final_capabilities", None)
    if final_capabilities is not None:

        def projection(capabilities):
            return {(c["id"], c["source"], c["unit"]) for c in capabilities}

        initial_ids, final_ids = (
            projection(observer.capabilities),
            projection(final_capabilities),
        )
        require(
            initial_ids == final_ids,
            f"independent inventory changed during capture: added={sorted(final_ids - initial_ids)}, removed={sorted(initial_ids - final_ids)}; see final-inventory.json",
        )
    brackets = []
    missing = []
    stable_totals = []
    expected = {c["id"]: c for c in observer.capabilities}
    for sid, capability in expected.items():
        if capability["probe"]["errno"] is not None or sid.endswith(
            ("/latency", "/connections")
        ):
            continue
        require(
            any(
                r["sensor_id"] == sid and r["availability"] == "Available"
                for s in snapshots
                for r in s["readings"]
            ),
            f"accessibly probed field never measured: {sid}",
        )
    require(
        not any(
            e.get("scope") == "independent non-AMD adapter not implemented"
            for e in observer.errors
        ),
        "accessible GPU adapter has no independent verifier",
    )
    for snapshot in snapshots:
        verify_inventory(observer.capabilities, snapshot)
        stable_totals.extend(
            verify_stable_totals(observer, snapshot, collector, external)
        )
        sensors = {s["id"]: s for s in snapshot["sensors"]}
        readings = {r["sensor_id"]: r for r in snapshot["readings"]}
        for sid, capability in expected.items():
            require(sid in sensors and sid in readings, f"OS capability missing: {sid}")
            require(
                sensors[sid]["source"] == capability["source"]
                and sensors[sid]["unit"] == capability["unit"],
                f"wrong OS source/unit: {sid}",
            )
        for reading in snapshot["readings"]:
            counts["exact_readings"] += check_reading(
                sensors[reading["sensor_id"]], reading
            )
        counts["connection_interfaces"] += connections(snapshot)
        process_pids = set()
        for row in snapshot["processes"]:
            pid, start_ticks = (
                row["identity"]["pid"],
                row["identity"]["start_time_ticks"],
            )
            require(
                pid not in process_pids, f"duplicate process PID in snapshot: {pid}"
            )
            process_pids.add(pid)
            for key, suffix, unit, filename in [
                ("cpu_percent", "cpu", "Percent", "stat"),
                ("memory_bytes", "memory", "Bytes", "stat"),
                ("read_bytes_per_second", "read", "BytesPerSecond", "io"),
                ("write_bytes_per_second", "write", "BytesPerSecond", "io"),
                ("threads", "threads", "Count", "stat"),
            ]:
                reading = row[key]
                expected_id = f"process:{pid}:{start_ticks}/{suffix}"
                expected_source = f"/proc/{pid}/{filename}"
                require(
                    reading["sensor_id"] == expected_id,
                    f"process field identity does not match row: {reading['sensor_id']} != {expected_id}",
                )
                for observation in reading["observations"]:
                    require(
                        observation["source"] == expected_source,
                        f"process raw source does not match row: {observation['source']} != {expected_source}",
                    )
                counts["exact_process_fields"] += check_reading(
                    {"id": expected_id, "unit": unit, "source": expected_source},
                    reading,
                )
            for observation in row["cpu_percent"]["observations"]:
                require(
                    observation["integers"]["start_time_ticks"]
                    == row["identity"]["start_time_ticks"],
                    "process start identity mismatch",
                )
        for reading in snapshot["readings"] + [
            r[k]
            for r in snapshot["processes"]
            for k in ("cpu_percent", "read_bytes_per_second", "write_bytes_per_second")
        ]:
            sid = reading["sensor_id"]
            for observation in reading["observations"]:
                source = observation["source"]
                values = observation["integers"]
                targets = {}
                if source.startswith("/proc/stat:"):
                    targets = {k: (source.split(":")[1], k) for k in CPU_FIELDS}
                elif source == "/proc/vmstat":
                    targets = {
                        "value": ("pgmajfault" if "major-page" in sid else "pgfault",)
                    }
                elif source in observer.disks:
                    targets = {k: (k,) for k in DISK_FIELDS}
                elif "/statistics/" in source:
                    targets = {k: () for k in values}
                elif sid.startswith("process:"):
                    if source.endswith("/stat"):
                        targets = {
                            k: ("utime" if k == "utime_ticks" else "stime",)
                            for k in ("utime_ticks", "stime_ticks")
                            if k in values
                        }
                    elif source.endswith("/io"):
                        targets = {
                            "bytes": (
                                "read_bytes"
                                if sid.endswith("/read")
                                else "write_bytes",
                            )
                        }
                if not targets:
                    continue
                start = observation.get("read_started_ns")
                window = map_window(
                    (
                        snapshot["capture_started_ns"] if start is None else start,
                        observation["captured_ns"],
                    ),
                    collector,
                    external,
                )
                for key, projection in targets.items():
                    samples = []
                    attempts = []
                    expected_identity = None
                    for captured in observer.samples:
                        if sid.startswith("process:"):
                            _, pid, start_ticks = sid.split("/")[0].split(":")
                            expected_identity = {
                                "pid": int(pid),
                                "start_time_ticks": int(start_ticks),
                            }
                            row = captured["processes"].get(pid)
                            attempts.append(
                                {
                                    "process_enumeration": captured["sources"]["/proc"],
                                    "stat": row["stat"] if row else None,
                                    "io": row["io"]
                                    if row and source.endswith("/io")
                                    else None,
                                }
                            )
                            if (
                                not row
                                or not row["stat"]["value"]
                                or row["stat"]["value"]["start_ticks"]
                                != int(start_ticks)
                            ):
                                continue
                            raw = row["io" if source.endswith("/io") else "stat"]
                        else:
                            raw = captured["sources"].get(
                                "/proc/stat"
                                if source.startswith("/proc/stat:")
                                else source
                            )
                        if not raw or raw["errno"] is not None:
                            continue
                        value = raw["value"]
                        for p in projection:
                            value = value[p]
                        samples.append(
                            {
                                "start": raw["start"],
                                "end": raw["end"],
                                "value": value,
                                "identity": expected_identity,
                            }
                        )
                    try:
                        a, b = (
                            check_process_counter(
                                values[key], window, expected_identity, samples
                            )
                            if expected_identity is not None
                            else check_counter(values[key], window, samples)
                        )
                    except AssertionError as error:
                        if "missing entire-window bracket" not in str(error):
                            raise AssertionError(
                                f"{sid} {source} {key}: {error}"
                            ) from error
                        missing.append(
                            {
                                "sensor_id": sid,
                                "source": source,
                                "key": key,
                                "value": values[key],
                                "query_window": window,
                                "external_windows": samples,
                                "external_attempts": attempts,
                                "identity": expected_identity,
                                "failure": str(error),
                                "snapshot_sequence": snapshot["sequence"],
                            }
                        )
                        continue
                    brackets.append(
                        {
                            "sensor_id": sid,
                            "source": source,
                            "key": key,
                            "value": values[key],
                            "window": window,
                            "before": a,
                            "after": b,
                        }
                    )
                    counts["counter_brackets"] += 1
    require(
        counts["counter_brackets"] > 0 and counts["exact_process_fields"] > 0,
        "empty comparison suite",
    )
    return {
        "status": "FAIL" if missing else "PASS",
        "counts": dict(counts),
        "external_offset": external,
        "collector_offset": collector,
        "brackets": brackets,
        "missing_brackets": missing,
        "stable_totals": stable_totals,
        "independent_stable_totals": len(stable_totals),
        "inventory_scope": "initial and final independent inventories"
        if final_capabilities is not None
        else "retained initial inventory only",
    }


def read_four_and_stop(child, output, seconds=30):
    """Keep every emitted byte, then stop the owned process before final reads."""
    deadline = time.monotonic() + seconds
    fd = child.stdout.fileno()
    os.set_blocking(fd, False)
    data = bytearray()
    while data.count(b"\n") < 4:
        require(time.monotonic() < deadline, "four-snapshot output deadline expired")
        if not select.select(
            [fd], [], [], min(0.1, max(0, deadline - time.monotonic()))
        )[0]:
            continue
        chunk = os.read(fd, 65536)
        require(chunk, "collector exited before four complete snapshots")
        output.write(chunk)
        output.flush()
        data.extend(chunk)
        require(len(data) <= 512 * 1024 * 1024, "capture exceeded512MiB bound")
    # No parsing or other expensive work before this stop request.
    child.send_signal(signal.SIGSTOP)
    stop_deadline = time.monotonic() + 5
    while True:
        observed = process(child.pid)
        info = observed["stat"]["value"]
        require(
            info is not None and info["state"] != "Z",
            "owned collector exited before stop acknowledgement",
        )
        if info["state"] == "T":
            break
        require(
            time.monotonic() < stop_deadline,
            "owned collector stop acknowledgement expired",
        )
        time.sleep(0.005)
    while True:
        try:
            chunk = os.read(fd, 65536)
        except BlockingIOError:
            break
        if not chunk:
            break
        output.write(chunk)
        output.flush()
        data.extend(chunk)
    require(
        data.count(b"\n") == 4 and data.endswith(b"\n"),
        "extra complete or partial snapshot output",
    )
    return observed


def run(output, binary):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    observer = Observer()
    child, child_info = start_child()
    worker = None
    collector_process = None
    try:
        gate = output / "collector-exec-gate"
        launcher = "import os,pathlib,sys,time; gate=pathlib.Path(sys.argv[1]); \nwhile not gate.exists(): time.sleep(.005)\nos.execv(sys.argv[2],[sys.argv[2],'--count','8','--interval-ms','1000'])"
        with (
            (output / "snapshots.jsonl").open("wb") as out,
            (output / "collector.log").open("w") as err,
        ):
            collector_process = subprocess.Popen(
                [sys.executable, "-B", "-c", launcher, str(gate), str(binary)],
                stdout=subprocess.PIPE,
                stderr=err,
            )
            observer.capture()
            lifecycle_before = process(collector_process.pid)
            (output / "collector-start.json").write_text(
                json.dumps(lifecycle_before, indent=2)
            )
            worker = threading.Thread(
                target=observer.run, name="independent-proc-observer"
            )
            worker.start()
            gate.touch()
            stopped = read_four_and_stop(collector_process, out)
            (output / "collector-stopped.json").write_text(
                json.dumps(stopped, indent=2)
            )
            observer.stop.set()
            worker.join(timeout=10)
            require(not worker.is_alive(), "observer timeout")
            observer.capture()
            lifecycle_after = process(collector_process.pid)
            lifecycle = {
                "before_exec": lifecycle_before,
                "stop_acknowledgement": stopped,
                "after_final_independent_capture": lifecycle_after,
                "binary": str(binary),
                "declared_snapshots": 4,
                "supervisor_termination": "SIGTERM then SIGCONT; expected -15, separate from native normal exit0",
            }
            (output / "collector-lifecycle.json").write_text(
                json.dumps(lifecycle, indent=2)
            )
            require(
                lifecycle_before["stat"]["value"]["start_ticks"]
                == stopped["stat"]["value"]["start_ticks"]
                == lifecycle_after["stat"]["value"]["start_ticks"],
                "owned collector identity changed",
            )
            require(
                lifecycle_after["stat"]["errno"] is None
                and lifecycle_after["io"]["errno"] is None,
                "live stopped collector counters inaccessible",
            )
            collector_process.send_signal(signal.SIGTERM)
            collector_process.send_signal(signal.SIGCONT)
            require(
                collector_process.wait(timeout=5) == -signal.SIGTERM,
                "unexpected supervised collector exit status",
            )
            fd = collector_process.stdout.fileno()
            extra = bytearray()
            drain_deadline = time.monotonic() + 2
            while True:
                require(
                    time.monotonic() < drain_deadline,
                    "collector output cleanup did not close",
                )
                if not select.select([fd], [], [], 0.05)[0]:
                    continue
                chunk = os.read(fd, 65536)
                if not chunk:
                    break
                out.write(chunk)
                out.flush()
                extra.extend(chunk)
            collector_process.stdout.close()
            lifecycle["exit_code"] = collector_process.returncode
            (output / "collector-lifecycle.json").write_text(
                json.dumps(lifecycle, indent=2)
            )
            require(
                not extra, "extra collector bytes emitted after declared four snapshots"
            )
        snapshots = [
            json.loads(line)
            for line in (output / "snapshots.jsonl").read_text().splitlines()
        ]
        child_after = process(child.pid)
        identity = {
            "pid": child.pid,
            "start_time_ticks": child_info["stat"]["value"]["start_ticks"],
        }
        require(
            child_after["stat"]["value"]["start_ticks"] == identity["start_time_ticks"],
            "real child identity changed",
        )
        rows = [
            next((r for r in s["processes"] if r["identity"] == identity), None)
            for s in snapshots
        ]
        require(all(rows), "real child snapshot appearance absent")
        for row in rows:
            require(
                row["name"] == "pulse ) probe", "process parentheses parsed incorrectly"
            )
            for field, key, factor in (
                ("memory_bytes", "rss_pages", os.sysconf("SC_PAGE_SIZE")),
                ("threads", "threads", 1),
            ):
                require(
                    child_info["stat"]["value"][key]
                    == child_after["stat"]["value"][key],
                    "controlled child gauge changed across independent endpoints",
                )
                require(
                    row[field]["value"] == child_info["stat"]["value"][key] * factor,
                    "controlled child independent stat gauge mismatch",
                )
            uid = child_info["uid"]["value"]
            require(
                row["user"] == pwd.getpwuid(uid).pw_name, "real child user mismatch"
            )
        (output / "capabilities.json").write_text(
            json.dumps(
                {
                    "capabilities": observer.capabilities,
                    "scope_limits": observer.errors,
                    "nvidia_hardware_accuracy": "UNVERIFIED; no NVIDIA hardware comparison",
                    "other_native_platforms": "macOS/Windows UNVERIFIED",
                },
                indent=2,
            )
        )
        (output / "external-observations.json").write_text(
            json.dumps({"anchors": observer.anchors, "samples": observer.samples})
        )
        (output / "child.json").write_text(
            json.dumps(
                {
                    "before": child_info,
                    "after": child_after,
                    "identity": identity,
                    "snapshot_rows": rows,
                },
                indent=2,
            )
        )
        final_inventory = Observer()
        observer.final_capabilities = final_inventory.capabilities
        (output / "final-inventory.json").write_text(
            json.dumps(
                {
                    "started_ns": final_inventory.inventory_started_ns,
                    "finished_ns": final_inventory.inventory_finished_ns,
                    "capabilities": final_inventory.capabilities,
                    "scope_limits": final_inventory.errors,
                },
                indent=2,
            )
        )
        result = verify_capture(observer, snapshots, child_info)
        (output / "stable-totals.json").write_text(
            json.dumps(result.pop("stable_totals"), indent=2)
        )
        (output / "counter-brackets.json").write_text(
            json.dumps(result.pop("brackets"))
        )
        (output / "missing-brackets.json").write_text(
            json.dumps(result.pop("missing_brackets"), indent=2)
        )
        stop_child(child)
        with (output / "after-exit.jsonl").open("w") as out:
            p = subprocess.run(
                ["rtk", "proxy", str(binary), "--count", "1"],
                stdout=out,
                stderr=subprocess.PIPE,
                timeout=5,
            )
        require(p.returncode == 0, "post-exit collector failed")
        exited = json.loads((output / "after-exit.jsonl").read_text())
        require(
            all(r["identity"] != identity for r in exited["processes"]),
            "old real child identity remained after exit",
        )
        result.update(
            {
                "snapshots": len(snapshots),
                "child_identity": identity,
                "child_exit_verified": True,
                "nvml": [
                    d for d in snapshots[-1]["diagnostics"] if d["backend"] == "nvml"
                ],
            }
        )
        (output / "result.json").write_text(json.dumps(result, indent=2))
        print(json.dumps(result), flush=True)
        require(
            result["status"] == "PASS",
            "missing mandatory counter brackets; see missing-brackets.json",
        )
        return result
    except BaseException as error:
        if collector_process:
            (output / "collector-failure-state.json").write_text(
                json.dumps(process(collector_process.pid), indent=2)
            )
        (output / "failure.json").write_text(
            json.dumps({"status": "FAIL", "error": str(error)}, indent=2)
        )
        raise
    finally:
        observer.stop.set()
        if worker:
            worker.join(timeout=10)
        (output / "external-observations.json").write_text(
            json.dumps({"anchors": observer.anchors, "samples": observer.samples})
        )
        (output / "capabilities.json").write_text(
            json.dumps(
                {
                    "capabilities": observer.capabilities,
                    "scope_limits": observer.errors,
                    "nvidia_hardware_accuracy": "UNVERIFIED; DriverNotLoaded is not accuracy evidence",
                    "other_native_platforms": "macOS/Windows UNVERIFIED",
                },
                indent=2,
            )
        )
        cleanup = []
        for owned in (child, collector_process):
            if owned is None:
                continue
            error = None
            try:
                stop_child(owned)
            except BaseException as failure:
                error = str(failure)
            cleanup.append(
                {
                    "pid": owned.pid,
                    "exit_code": owned.returncode,
                    "error": error,
                    "proc_exists": Path(f"/proc/{owned.pid}").exists(),
                }
            )
            if owned.stdout is not None and not owned.stdout.closed:
                owned.stdout.close()
        (output / "cleanup.json").write_text(json.dumps(cleanup, indent=2))
        if any(item["error"] or item["proc_exists"] for item in cleanup):
            result_path = output / "result.json"
            result = json.loads(result_path.read_text()) if result_path.exists() else {}
            result.update(status="FAIL", cleanup=cleanup)
            result_path.write_text(json.dumps(result, indent=2))
            raise AssertionError("host cleanup failed; see cleanup.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--binary", type=Path, required=True)
    args = parser.parse_args()
    run(args.output, args.binary.resolve())
