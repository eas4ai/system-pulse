"""Independent Intel sysfs/PMU source inventory with replayable original reads."""

import os
from pathlib import Path
import re
import time

from host_accuracy import require


class Sysfs:
    def __init__(self, record=None):
        self.replay = record is not None
        self.record = record if self.replay else dict(files={}, directories={})

    def read(self, path):
        path = Path(path)
        key = str(path)
        if not self.replay:
            start = time.monotonic_ns()
            try:
                with path.open("rb") as stream:
                    data = stream.read(4097)
                require(len(data) <= 4096, "sysfs read exceeds bound")
                result = dict(data_hex=data.hex())
            except OSError as e:
                result = dict(error=str(e), errno=e.errno)
            self.record["files"][key] = dict(
                start=start, end=time.monotonic_ns(), **result
            )
        result = self.record["files"][key]
        if "error" in result:
            raise OSError(result["errno"], result["error"])
        data = bytes.fromhex(result["data_hex"])
        require(len(data) <= 4096, "retained sysfs read exceeds bound")
        return data.decode().strip()

    def scan(self, path):
        path = Path(path)
        key = str(path)
        if not self.replay:
            try:
                result = []
                with os.scandir(path) as iterator:
                    for item in iterator:
                        require(len(result) < 512, "sysfs directory exceeds bound")
                        result.append(item.name)
                value = dict(names=sorted(result))
            except OSError as e:
                value = dict(error=str(e), errno=e.errno)
            self.record["directories"][key] = value
        result = self.record["directories"][key]
        if "error" in result:
            raise OSError(result["errno"], result["error"])
        names = result["names"]
        require(
            len(names) <= 512
            and len(set(names)) == len(names)
            and all(n and "/" not in n and n not in (".", "..") for n in names),
            "invalid retained directory inventory",
        )
        return [path / n for n in names]

    def resolve(self, path):
        key = str(path)
        if not self.replay:
            self.record.setdefault("resolved", {})[key] = str(
                Path(path).resolve(strict=True)
            )
        return Path(self.record["resolved"][key])


def scope(driver, provider, channel):
    if provider != driver:
        return "GT provider " + provider
    if (driver == "i915" and channel == "temp1") or (
        driver == "xe" and channel in ("temp2", "energy2", "power2")
    ):
        return "Package of this GPU; not GPU die"
    if driver == "xe" and channel in ("temp3", "temp4", "temp5"):
        return {
            "temp3": "Device VRAM",
            "temp4": "Device memory controller average",
            "temp5": "Device PCIe",
        }[channel]
    if channel.startswith("fan"):
        return "Device tachometer channel; shared tach lines can read zero independently of fan rotation"
    if channel.startswith(("energy", "power")):
        return "Whole graphics card"
    return f"Device hwmon channel {channel}; no die attribution"


def sysfs_fields(device, fs):
    fields = []
    errors = []
    physical = Path(device["physical_path"])
    driver = device["driver"]

    def scan(path):
        try:
            return fs.scan(path)
        except OSError as e:
            errors.append(dict(path=str(path), errno=e.errno, error=str(e)))
            return []

    def add(
        suffix,
        path,
        kind,
        unit,
        source_unit,
        scope,
        numerator=1,
        denominator=1,
        signed=False,
        energy=False,
    ):
        fields.append(
            dict(
                sensor_id=device["monitor_id"] + "/" + suffix,
                formula="intel-energy" if energy else "intel-sysfs",
                path=str(path),
                source=f"{path} ({source_unit})",
                kind=kind,
                unit=unit,
                scope=scope,
                numerator=numerator,
                denominator=denominator,
                signed=signed,
                precision=0,
            )
        )
        try:
            fs.read(path)
        except OSError as e:
            fields[-1]["limitation"] = (
                "denied"
                if e.errno in (1, 13)
                else "absent"
                if e.errno == 2
                else "failed"
            )

    def frequency(prefix, path, actual, requested):
        for semantics, name in [("actual", actual), ("requested", requested)]:
            add(
                prefix + "-frequency-" + semantics,
                path / name,
                "Frequency",
                "Hertz",
                "MHz",
                f"GT {prefix}; {semantics} clock",
                numerator=1_000_000,
            )

    if driver == "i915":
        for alias in device["aliases"]:
            card = Path(alias["path"])
            if not re.fullmatch(r"card[0-9]+", card.name):
                continue
            for gt in scan(card / "gt"):
                if re.fullmatch(r"gt[0-9]+", gt.name):
                    frequency(gt.name, gt, "rps_act_freq_mhz", "rps_cur_freq_mhz")
        if not fields:
            cards = [
                Path(a["path"])
                for a in device["aliases"]
                if re.fullmatch(r"card[0-9]+", Path(a["path"]).name)
            ]
            if cards:
                frequency("gt0", cards[0], "gt_act_freq_mhz", "gt_cur_freq_mhz")
    else:
        for tile in scan(physical):
            if not re.fullmatch(r"tile[0-9]+", tile.name):
                continue
            for gt in scan(tile):
                if re.fullmatch(r"gt[0-9]+", gt.name):
                    frequency(
                        tile.name + "-" + gt.name, gt / "freq0", "act_freq", "cur_freq"
                    )
    providers = {}
    complete = True
    for hwmon in scan(physical / "hwmon"):
        try:
            name = fs.read(hwmon / "name")
        except OSError as e:
            complete = False
            errors.append(dict(path=str(hwmon / "name"), errno=e.errno, error=str(e)))
            continue
        if name == driver or re.fullmatch(re.escape(driver) + r"_gt[0-9]+", name):
            providers.setdefault(name, []).append(hwmon)
    if complete:
        for provider, paths in providers.items():
            if len(paths) != 1:
                errors.append(dict(error="ambiguous hwmon provider " + provider))
                continue
            for path in scan(paths[0]):
                match = re.fullmatch(
                    r"(temp|power|energy|fan)([0-9]+)_(input|average)", path.name
                )
                if not match:
                    continue
                kind, number, attribute = match.groups()
                if attribute == "average" and kind != "power":
                    continue
                unit, quantity, source_unit, denominator = {
                    "temp": ("Celsius", "Temperature", "millidegree Celsius", 1000),
                    "power": ("Watts", "Power", "microwatts", 1_000_000),
                    "energy": ("Watts", "Power", "microjoules", 1_000_000),
                    "fan": ("Rpm", "Fan", "RPM", 1),
                }[kind]
                suffix = (
                    "hwmon-"
                    + provider
                    + "-"
                    + path.name
                    + ("-power" if kind == "energy" else "")
                )
                add(
                    suffix,
                    path,
                    quantity,
                    unit,
                    source_unit,
                    scope(driver, provider, kind + number),
                    denominator=denominator,
                    signed=kind == "temp",
                    energy=kind == "energy",
                )
    require(
        len({f["sensor_id"] for f in fields}) == len(fields),
        "ambiguous independent sysfs field",
    )
    return fields, errors


def cpu_list(text):
    values = []
    for chunk in text.split(","):
        require(re.fullmatch(r"[0-9]+(-[0-9]+)?", chunk), "invalid PMU CPU list")
        endpoints = list(map(int, chunk.split("-")))
        a, b = endpoints[0], endpoints[-1]
        require(a <= b and b < 1048576, "invalid PMU CPU range")
        values.append(a)
    require(values, "empty PMU CPU list")
    return min(values)


def pmu_fields(device, all_devices, engines, fs, root):
    root = Path(root)
    base = root / "sys/bus/event_source/devices"
    driver = device["driver"]
    pci = device["pci"]
    names = {p.name for p in fs.scan(base)}
    qualified = driver + "_" + pci.replace(":", "_")
    plain = [
        d
        for d in all_devices
        if d["driver"] == "i915" and "i915_" + d["pci"].replace(":", "_") not in names
    ]
    integrated = (
        driver == "i915"
        and len(plain) == 1
        and plain[0]["pci"] == pci
        and "i915" in names
    )
    selected = qualified if qualified in names else "i915" if integrated else None
    if selected is None:
        return [], integrated
    pmu = base / selected
    kind = int(fs.read(pmu / "type"))
    online = fs.read(root / "sys/devices/system/cpu/online")
    try:
        cpu = cpu_list(fs.read(pmu / "cpumask"))
    except FileNotFoundError:
        cpu = cpu_list(online)
    online_ranges = [list(map(int, p.split("-"))) for p in online.split(",")]
    require(any(r[0] <= cpu <= r[-1] for r in online_ranges), "PMU CPU not online")
    fields = []

    def add(suffix, active, total, scope):
        source = (
            f"{pmu} perf_event_open config={active:#x}"
            + (f",{total:#x}" if total is not None else "")
            + (" (GuC ticks)" if total is not None else " (busy ns)")
        )
        fields.append(
            dict(
                sensor_id=device["monitor_id"] + "/" + suffix,
                formula="intel-perf",
                kind="Percentage",
                unit="Percent",
                source=source,
                scope=scope,
                precision=0,
                pmu_type=kind,
                cpu=cpu,
                capacity=1,
                ticks=int(total is not None),
                config_active=active,
                config_total=total or 0,
                energy_denominator=0,
            )
        )

    if driver == "i915":
        for event in fs.scan(pmu / "events"):
            if not event.name.endswith("-busy"):
                continue
            require(
                fs.read(Path(str(event) + ".unit")) == "ns",
                "wrong i915 native event unit",
            )
            config = fs.read(event)
            require(
                re.fullmatch(r"config=0x[0-9a-fA-F]+", config),
                "unknown i915 event config",
            )
            active = int(config[9:], 16)
            cls = active >> 12
            instance = (active >> 4) & 255
            require(active & 15 == 0 and cls <= 4, "unknown i915 engine selector")
            add(
                f"engine-class{cls}-instance{instance}",
                active,
                None,
                f"Physical GPU engine class {cls}, instance {instance}; busy nanoseconds / measured elapsed nanoseconds; capacity 1",
            )
    else:
        for name, expected in {
            "event": "config:0-11",
            "engine_class": "config:20-27",
            "engine_instance": "config:12-19",
            "gt": "config:60-63",
        }.items():
            require(
                fs.read(pmu / "format" / name) == expected, "unknown xe event layout"
            )
        for name, value in [("engine-active-ticks", 2), ("engine-total-ticks", 3)]:
            require(
                int(fs.read(pmu / "events" / name).removeprefix("event=0x"), 16)
                == value,
                "unknown xe event",
            )
            try:
                require(
                    fs.read(pmu / "events" / (name + ".unit")) == "ticks",
                    "unknown xe ticks unit",
                )
            except FileNotFoundError:
                pass
        try:
            sriov = int(fs.read(Path(device["physical_path"]) / "sriov_numvfs")) > 0
        except FileNotFoundError:
            sriov = False
        for engine in engines:
            gt, cls, instance = (
                engine["gt"],
                engine["engine_class"],
                engine["engine_instance"],
            )
            require(
                gt < 16 and cls <= 4 and instance < 256,
                "xe engine selector outside bound",
            )
            selector = gt << 60 | cls << 20 | instance << 12
            prefix = (
                "PCI physical function 0 only; excludes VF activity"
                if sriov
                else "Physical GPU engine"
            )
            add(
                f"gt{gt}-engine-class{cls}-instance{instance}",
                selector | 2,
                selector | 3,
                f"{prefix}; GT {gt}, engine class {cls}, instance {instance}; active/total GuC ticks, capacity 1",
            )
    require(
        len({f["sensor_id"] for f in fields}) == len(fields),
        "duplicate native PMU engine",
    )
    return fields, integrated


def rapl_perf(device, integrated, fs, root):
    require(integrated, "RAPL has no proven integrated GPU association")
    root = Path(root)
    pmu = root / "sys/bus/event_source/devices/power"
    mask = fs.read(pmu / "cpumask")
    require(re.fullmatch(r"[0-9]+", mask), "ambiguous RAPL die count")
    cpu = int(mask)
    topology = root / f"sys/devices/system/cpu/cpu{cpu}/topology"
    package = int(fs.read(topology / "physical_package_id"))
    die = int(fs.read(topology / "die_id"))
    require(min(package, die) >= 0, "invalid RAPL physical domain")
    for path, value in [
        ("format/event", "config:0-7"),
        ("events/energy-gpu", "event=0x04"),
        ("events/energy-gpu.unit", "Joules"),
    ]:
        require(fs.read(pmu / path) == value, "wrong RAPL GPU metadata")
    require(
        float(fs.read(pmu / "events/energy-gpu.scale")) == 1 / 2**32, "wrong RAPL scale"
    )
    return dict(
        sensor_id=device["monitor_id"] + f"/rapl-package{package}-die{die}-graphics",
        formula="intel-perf",
        source=f"{pmu} perf_event_open config=0x4 (2^-32 Joules)",
        unit="Watts",
        kind="Power",
        scope=f"Intel CPU package {package}, die {die}, PP1 graphics domain associated with integrated PCI {device['pci']}; excludes CPU cores/package energy; not whole graphics-card power",
        precision=0,
        pmu_type=int(fs.read(pmu / "type")),
        cpu=cpu,
        capacity=1,
        ticks=0,
        config_active=4,
        config_total=0,
        energy_denominator=2**32,
    )


def rapl_powercap(device, integrated, fs, root):
    require(integrated, "powercap has no proven integrated GPU association")

    def zone(path):
        return re.fullmatch(r"intel-rapl(-mmio)?:[0-9]+(:[0-9]+)*", path.name)

    packages = {}
    for path in fs.scan(Path(root) / "sys/class/powercap"):
        if not zone(path):
            continue
        name = fs.read(path / "name")
        if name.startswith("package-"):
            require(
                re.fullmatch(r"package-[0-9]+", name),
                "invalid powercap package identity",
            )
            packages[fs.resolve(path)] = name
    require(len(packages) == 1, "ambiguous powercap package count")
    package, name = next(iter(packages.items()))
    domains = set()
    for path in fs.scan(package):
        if zone(path) and fs.read(path / "name") == "uncore":
            domains.add(fs.resolve(path))
    require(len(domains) == 1, "missing/ambiguous PP1 uncore domain")
    path = next(iter(domains)) / "energy_uj"
    fs.read(path)
    return dict(
        sensor_id=device["monitor_id"] + f"/rapl-{name}-uncore-power",
        formula="intel-energy",
        path=str(path),
        source=f"{path} (microjoules)",
        unit="Watts",
        kind="Power",
        scope=f"CPU {name} PP1 graphics domain associated with the unique integrated i915 GPU; not CPU package energy or whole graphics-card power",
        numerator=1,
        denominator=1_000_000,
        signed=False,
        precision=0,
    )
