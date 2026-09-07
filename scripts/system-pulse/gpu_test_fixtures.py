"""Synthetic full-ingestion fixtures. These never establish hardware accuracy."""

import copy
import json
import shutil
import plistlib
import struct
import uuid
from test_gpu_evidence import originals_fixture
from test_gpu_intel import physical_fixture
from gpu_intel_capture import independent_inventory, normalize_observer
from gpu_capture import sha256
from gpu_verify import declared_inputs, ROOT
import subprocess
from host_accuracy import format_sample, SYMBOLS


def apple_metadata(raw, pid):
    from gpu_provenance import APPLE_IMAGES, API_LIMITATION

    def plist(value):
        return plistlib.dumps(value).hex()

    product = dict(
        ProductName="macOS fixture",
        ProductVersion="26.0",
        ProductBuildVersion="fixture-A",
    )
    names = dict(
        system="Darwin",
        release="25.0.0-fixture",
        version="Darwin Kernel Version fixture",
        machine="arm64",
    )
    images = []
    identities = {}
    for index, (api, path, symbol) in enumerate(APPLE_IMAGES):
        identity = identities.setdefault(path, uuid.UUID(int=index + 1))
        commands = (
            struct.pack("<II", 0x1B, 24)
            + identity.bytes
            + struct.pack("<6I", 0xD, 24, 0, 0, 65536, 65536)
        )
        images.append(
            dict(
                api=api,
                requested_path=path,
                symbol=symbol,
                loaded_path=path,
                header_hex=struct.pack(
                    "<8I", 0xFEEDFACF, 0x100000C, 0, 6, 2, len(commands), 0, 0
                ).hex(),
                commands_hex=commands.hex(),
                image_uuid=str(identity).upper(),
                dylib_current_version_raw=65536,
                dylib_compatibility_version_raw=65536,
                standalone_api_version=None,
                version_limitation=API_LIMITATION,
            )
        )
    registry = dict(
        CFBundleIdentifierKernel="fixture.gpu.driver",
        IOClass="FixtureAccelerator",
        MetalPluginClassName="FixtureMetalDevice",
        IOSourceVersion="1.2",
    )
    kernel = {
        "fixture.gpu.driver": dict(
            CFBundleIdentifier="fixture.gpu.driver",
            CFBundleVersion="1.2",
            OSBundleUUID=uuid.UUID(int=91).bytes,
        )
    }
    device = raw["devices"][0]
    provider = dict(
        registry_id=device["registry_id"],
        lookup_registry_id=device["registry_id"],
        name=device["name"],
        metal_class="FixtureMetalDevice",
        bundle_path="/System/Library/Extensions/FixtureMetal.bundle",
        registry_plist_hex=plist(registry),
        kernel_plist_hex=plist(kernel),
        bundle_plist_hex=plist(
            dict(CFBundleIdentifier="fixture.gpu.metal", CFBundleVersion="1.2")
        ),
    )
    return dict(
        schema=1,
        pid=pid,
        os=dict(
            uname={k: v.encode().hex() for k, v in names.items()},
            product=dict(
                path="/System/Library/CoreServices/SystemVersion.plist",
                raw_hex=plist(product),
            ),
            kern_osversion_hex=b"fixture-A".hex(),
        ),
        images=images,
        devices=[provider],
    )


def apple_frame(t, pid):
    from test_gpu_apple_capture import raw_frame

    raw = raw_frame()
    raw["pid"] = pid
    raw["clock_anchor"] = dict(monotonic_before_ns=0, monotonic_after_ns=0, unix_ns=0)
    for row in [raw["ioreport"]] + raw["memory"] + raw["tables"] + raw["smc"]:
        row.update(start=t, end=t + 1)
    states = raw["ioreport"]["channels"][0]["states"]
    states[0]["residency"] = 1000 + 2 * t
    states[1]["residency"] = 1000 + t
    raw["ioreport"]["channels"][1]["integer"] = 2000 + t
    raw["host"] = apple_metadata(raw, pid)
    return raw


def apple_specimen():
    from gpu_apple_capture import independent_inventory

    raw = apple_frame(30, 16)
    inv = independent_inventory(raw)
    mid = inv["device"]["monitor_id"]
    snapshot = dict(
        sequence=1,
        clock_anchor=raw["clock_anchor"],
        monitors=[dict(id=mid, kind="Gpu", title="Apple M1 Pro")],
        sensors=[],
        readings=[],
    )
    for field in inv["fields"]:
        sid = field["sensor_id"]
        formula = field["formula"]
        observations = []
        value = None
        sensor = {k: field[k] for k in ("source", "scope", "unit", "kind")}
        sensor.update(id=sid, monitor_id=mid, title=sid)
        if not field.get("limitation"):
            for t in (
                [32, 35]
                if formula in ("apple-activity", "apple-frequency", "apple-energy")
                else [33]
            ):
                ints = {k: field[k] for k in ("driver_id", "channel_id") if k in field}
                decimals = {}
                if formula in ("apple-activity", "apple-frequency"):
                    ints.update(format=2, encoded_unit=72058115876454424, state_count=2)
                    ints.update(
                        {
                            "ticks/OFF": 1000 + 2 * t,
                            "ticks/P1": 1000 + t,
                            "hz/OFF": 0,
                            "hz/P1": 300000000,
                            "table/driver_id": 21,
                            "table/byte_length": 16,
                            "table/read_started_ns": t,
                            "table/captured_ns": t + 1,
                        }
                    )
                    for n, pair in enumerate(
                        struct.iter_unpack("<Q", bytes.fromhex(field["table_hex"]))
                    ):
                        ints["table/pair_le/" + str(n)] = pair[0]
                    value = 100.0 / 3 if formula == "apple-activity" else 300000000.0
                elif formula == "apple-energy":
                    ints.update(
                        format=1, encoded_unit=216173288919924736, energy_nj=2000 + t
                    )
                    value = 1.0
                elif formula == "apple-memory":
                    value = 4096.0 if sid.endswith("shared-allocated") else 1024.0
                    ints.update(bytes=int(value), has_unified_memory=1)
                elif formula == "apple-smc":
                    key = field["source"].split("/")[1].split(";")[0]
                    ints.update(
                        bytes_le=int.from_bytes(struct.pack("<f", 20.0), "little"),
                        key_fourcc=int.from_bytes(key.encode(), "big"),
                        type_fourcc=int.from_bytes(b"flt ", "big"),
                        size=4,
                        result=0,
                        status=0,
                        return_code=0,
                        response_size=80,
                    )
                    decimals["celsius"] = value = 20.0
                observations.append(
                    dict(
                        source=field.get("raw_source", field["source"]),
                        integers=ints,
                        decimals=decimals,
                        read_started_ns=t,
                        captured_ns=t + 1,
                    )
                )
        snapshot["sensors"].append(sensor)
        snapshot["readings"].append(
            dict(
                sensor_id=sid,
                value=value,
                total=None,
                availability="Available" if value is not None else "Unavailable",
                reason=None
                if value is not None
                else "Independent source is " + field["limitation"],
                observations=observations,
            )
        )
    return raw, snapshot, inv


def apple_artifacts(root, paths, report, records, put, build, raw):
    from gpu_host_capture import console_session

    report["hardware_class"] = "apple-silicon"
    del build["executables"]["workload"]
    del report["executables"]["workload"]
    put("build.json", build)
    for record in list(records):
        if record["role"] in ("workload-build", "workload-provider"):
            records.remove(record)
            for name in [
                record["stdout"],
                record["stderr"],
                record["role"] + "-started.json",
                record["role"] + "-finished.json",
            ]:
                paths.pop(name).unlink()
    paths.pop("workload-provider.json").unlink()
    by_role = {r["role"]: r for r in records}
    binary = str(root / "bin/observer")
    by_role["host-metadata"]["command"] = [binary, "host"]
    for role, count in [("inventory", "1"), ("observer", "600")]:
        by_role[role]["command"] = [binary, "observe", count, "100"]
    by_role["workload"]["command"] = [binary, "workload", "19", "12"]
    by_role["workload"]["executable_sha256"] = report["executables"]["observer"]
    work = json.loads(paths["workload.stdout"].read_text())
    work.update(api="Metal", registry_id=19, host=apple_metadata(raw, 15))
    for key in (
        "os",
        "pci",
        "vendor_id",
        "device_id",
        "devices",
        "api_version_raw",
        "driver_version_raw",
        "loader_api_version_raw",
        "driver_version_semantics",
        "api_version_semantics",
    ):
        work.pop(key, None)
    put("workload.stdout", work)
    for r in records:
        if r["role"].startswith("ax"):
            r["command"][1] = "ax"
    close = json.loads(paths["axclose.stdout"].read_text())
    close["method"] = "AXPressCloseButton"
    put("axclose.stdout", close)
    for role, pid, command in [
        (
            "helper-build",
            43,
            [
                "/usr/bin/clang",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-fobjc-arc",
                "-framework",
                "Foundation",
                "-framework",
                "Metal",
                "-framework",
                "IOKit",
                "-framework",
                "ApplicationServices",
                str(root / "source/scripts/system-pulse/gpu_apple_native.m"),
                str(root / "source/scripts/system-pulse/gpu_apple_ax.m"),
                "-o",
                binary,
            ],
        ),
        (
            "console-session",
            44,
            [
                "/usr/sbin/ioreg",
                "-a",
                "-l",
                "-w",
                "0",
                "-d",
                "1",
                "-k",
                "IOConsoleUsers",
            ],
        ),
    ]:
        record = dict(
            by_role["host-metadata"],
            role=role,
            pid=pid,
            command=command,
            stdout=role + ".stdout",
            stderr=role + ".stderr",
        )
        records.append(record)
        for stream in ("stdout", "stderr"):
            path = root / record[stream]
            path.write_text("")
            paths[record[stream]] = path
    session = [
        dict(
            IOConsoleLocked=False,
            IOConsoleUsers=[
                dict(
                    kCGSSessionOnConsoleKey=True,
                    kCGSessionLoginDoneKey=True,
                    CGSSessionScreenIsLocked=False,
                )
            ],
        )
    ]
    paths["console-session.stdout"].write_bytes(plistlib.dumps(session))
    put("console-session.json", console_session(session))


def linux_metadata(raw, pid):
    names = dict(
        system="Linux",
        release="6.17.0-complete-control",
        version="#1 synthetic verifier specimen",
        machine="x86_64",
    )
    os_data = dict(
        uname={k: v.encode().hex() for k, v in names.items()},
        product=dict(
            path="/etc/os-release",
            raw_hex=b'ID=specimen\nNAME="Verifier specimen"\nVERSION_ID="1"\nBUILD_ID="fixture-build"\n'.hex(),
        ),
        kernel=dict(
            path="/proc/version",
            raw_hex=(
                "Linux version "
                + names["release"]
                + " (test compiler) "
                + names["version"]
                + "\n"
            )
            .encode()
            .hex(),
        ),
    )
    devices = []
    for raw_device in raw["devices"]:
        identity = {
            k: raw_device[k]
            for k in (
                "pci",
                "driver",
                "physical_path",
                "monitor_id",
                "aliases",
                "vendor",
                "device_id",
            )
        }
        version = dict(
            source="DRM_IOCTL_VERSION",
            major=1,
            minor=3,
            patch=0,
            strings={
                k: v.encode().hex()
                for k, v in [
                    ("name", identity["driver"]),
                    ("date", "20260101"),
                    ("desc", "synthetic native interface specimen"),
                ]
            },
            dev=identity["aliases"][0]["dev"],
            started_ns=0,
            finished_ns=1,
        )
        module = {
            key: dict(path="/sys/module/" + identity["driver"] + "/" + suffix, errno=2)
            for key, suffix in [
                ("version", "version"),
                ("srcversion", "srcversion"),
                ("build_id", "notes/.note.gnu.build-id"),
            ]
        }
        devices.append(
            dict(
                identity=identity,
                drm=version,
                module=module,
                kernel_api_version=None,
                version_limitation="Kernel-owned API has no independent version; owning kernel build retained",
            )
        )
    return dict(
        schema=1,
        pid=pid,
        clock_anchor=raw["clock_anchor"],
        os=os_data,
        devices=devices,
        sysfs=raw["sysfs"],
    )


def full_host_fixture(root, apple=False):
    paths, report, policy, actions, diagnostics, records, put = originals_fixture(root)
    raw, _, _, snapshot = physical_fixture()
    raw["pid"] = 16
    raw["os_release"] = "6.17.0-complete-control"
    raw["machine"] = "x86_64"
    raw["host"] = linux_metadata(raw, 16)
    for d in raw["devices"]:
        d["drm"]["memory"].update(start=30, end=31)
    inv = independent_inventory(raw, raw["devices"][0]["pci"])
    if apple:
        raw, snapshot, inv = apple_specimen()
    mid = inv["device"]["monitor_id"]
    field = (
        next(f for f in inv["fields"] if f["formula"] == "apple-activity")
        if apple
        else next(f for f in inv["fields"] if f.get("memory_metric") == "allocation")
    )
    sid = field["sensor_id"]
    for reading in snapshot["readings"]:
        for observation in reading["observations"]:
            if not apple:
                observation.update(read_started_ns=33, captured_ns=34)
    for sensor in snapshot["sensors"]:
        sensor["title"] = "Allocation" if sensor["id"] == sid else sensor["id"]
    for m in snapshot["monitors"]:
        m["summary_sensor_id"] = sid
    for d in diagnostics:
        d["snapshot"] = copy.deepcopy(snapshot)
        d["snapshot"]["sequence"] = (
            len(
                [
                    v
                    for v in diagnostics[: diagnostics.index(d)]
                    if v["application_pid"] == d["application_pid"]
                ]
            )
            + 1
        )
        d["rendered_at_collector_ms"] = 0
        d["rendered"] = []
        for sensor, reading in zip(snapshot["sensors"], snapshot["readings"]):
            current = reading["availability"] == "Available"
            text = (
                format_sample(dict(reading, unit=sensor["unit"]))
                if current
                else "Unavailable · " + SYMBOLS[sensor["unit"]]
            )
            label = (
                ("Apple M1 Pro · " if apple else "Intel GPU · " + mid + " · ")
                + sensor["title"]
                + " · "
                + text
                + ((" · " + reading["reason"]) if reading["reason"] else "")
            )
            value_text, unit = text.rsplit(" ", 1)
            d["rendered"].append(
                dict(
                    monitor_id=mid,
                    sensor_id=sensor["id"],
                    element_id=mid + ":value:" + sensor["id"],
                    label=label,
                    sample=dict(
                        value=reading["value"],
                        total=reading["total"],
                        reason=reading["reason"],
                        text=value_text,
                        unit=unit,
                        status="current" if current else "unavailable",
                    ),
                )
            )

    def translate(v):
        if isinstance(v, str):
            if v == "gpu":
                return mid
            return (
                v.replace("gpu:", mid + ":")
                .replace("gpu/usage", sid)
                .replace("Usage", "Allocation")
            )
        if isinstance(v, list):
            return [translate(x) for x in v]
        if isinstance(v, dict):
            return {translate(k): translate(x) for k, x in v.items()}
        return v

    for i, action in enumerate(actions):
        action = translate(action)
        actions[i] = action
        for side in ["before", "after"]:
            rows = action[side]["elements"]
            next(r for r in rows if r["object_key"] == "value")["title"] = next(
                e for e in diagnostics[0]["rendered"] if e["sensor_id"] == sid
            )["label"]
            for n, e in enumerate(diagnostics[0]["rendered"]):
                if e["sensor_id"] == sid:
                    continue
                row = copy.deepcopy(next(r for r in rows if r["object_key"] == "value"))
                row.update(
                    object_key="extra" + str(n),
                    identifier=e["element_id"],
                    title=e["label"],
                )
                rows.append(row)
            put(action["state_" + side + "_path"], action["state_" + side])
            if action["name"] == "restore":
                put(action[side + "_path"], action[side])
        if action["name"] != "restore":
            put(action["native_path"], action)
    plan = translate(json.loads(paths["action-plan.json"].read_text()))
    put("action-plan.json", plan)
    for record in records:
        if record["role"].startswith("ax") and len(record["command"]) > 4:
            record["command"][3] = json.dumps(
                translate(json.loads(record["command"][3]))
            )
    policy.update(
        hardware_class=inv["hardware_class"],
        device=inv["device"],
        fields=inv["fields"],
        declared_unix_ns=1,
        sample_count=4,
        warmup_samples=0,
        retries=0,
        rounding_ulps=4,
        max_query_ns=10,
        max_gap_ns=100,
        freshness_ns=1000,
        deadline_ns=1000,
        poll_interval_ns=100,
        action_plan_sha256=sha256(paths["action-plan.json"]),
    )
    put("policy.json", policy)
    put("inventory.json", inv)
    put("actions.json", actions)
    work = json.loads(paths["workload.stdout"].read_text())
    work.update(
        os=copy.deepcopy(raw["host"]["os"]),
        api_version_raw=(1 << 22) | (3 << 12),
        driver_version_raw=123456,
        loader_api_version_raw=(1 << 22) | (3 << 12),
        driver_version_semantics="vendor-defined raw uint32; no semantic decoding",
        api_version_semantics="Vulkan VkPhysicalDeviceProperties.apiVersion",
    )
    put("workload.stdout", work)
    provider = {
        k: work[k]
        for k in (
            "pci",
            "vendor_id",
            "device_id",
            "api_version_raw",
            "driver_version_raw",
            "loader_api_version_raw",
            "driver_version_semantics",
            "api_version_semantics",
            "os",
        )
    }
    provider.update(
        schema=1, mode="metadata", pid=42, query_started_ns=1, query_finished_ns=2
    )
    put("workload-provider.stdout", provider)
    put("workload-provider.json", provider)
    for name in [
        "workspace-before.json",
        "workspace-after.json",
        "workspace-restored.json",
    ]:
        put(name, actions[-1]["state_after"])
    snapshots = [dict(copy.deepcopy(snapshot), sequence=n) for n in range(1, 5)]

    def lines(name, rows):
        p = root / name
        p.write_text("".join(json.dumps(row) + "\n" for row in rows))
        paths[name] = p

    for name in ["collector.stdout", "snapshots.jsonl"]:
        lines(name, snapshots)
    lines("diagnostics.jsonl", diagnostics)
    put("native-inventory.json", raw)
    lines("inventory.stdout", [raw])
    first = copy.deepcopy(raw)
    first["pid"] = 12
    first["host"]["pid"] = 12
    last = copy.deepcopy(first)
    if apple:
        last = apple_frame(37, 12)
    else:
        for d in last["devices"]:
            d["drm"]["memory"].update(start=35, end=36)
    for name in ["observer.stdout", "native-observer.jsonl"]:
        lines(name, [first, last])
    normalizer = normalize_observer
    if apple:
        from gpu_apple_capture import normalize_observer as normalizer
    lines("observer.jsonl", [normalizer(r, inv) for r in [first, last]])
    inputs = {
        name: sha256(ROOT / name)
        for name in subprocess.check_output(
            ["git", "ls-files", "-z", "--", *declared_inputs()], cwd=ROOT
        )
        .decode()
        .split("\0")
        if name
    }
    for name in inputs:
        target = root / "source" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    build = json.loads(paths["build.json"].read_text())
    for role, name in build["executables"].items():
        p = root / name
        p.parent.mkdir(exist_ok=True)
        p.write_text("synthetic verifier specimen " + role)
        report["executables"][role] = sha256(p)
    build.update(
        inputs=inputs,
        exit_code=0,
        source_commit="ece89eaec5c7e0775b44583dcefaa92661cc46ca",
        build_stdout="build.stdout",
        build_stderr="build.stderr",
    )
    put("build.json", build)
    report.update(schema=1, mode="native", inputs=inputs, capture_started_unix_ns=2)
    for record in records:
        role = record["role"]
        exe = (
            "application"
            if role.startswith("application")
            else "collector"
            if role == "collector"
            else "workload"
            if role in ("workload", "workload-provider")
            else "observer"
        )
        record["executable_sha256"] = report["executables"][exe]

    def sync():
        for record in records:
            for stream in ["stdout", "stderr"]:
                record[stream + "_sha256"] = sha256(paths[record[stream]])
            put(record["role"] + "-finished.json", record)
            put(
                record["role"] + "-started.json",
                {
                    k: record[k]
                    for k in [
                        "pid",
                        "command",
                        "started_ns",
                        "started_unix_ns",
                        "deadline_ns",
                    ]
                },
            )
        put("lifecycle.json", records)
        report["artifacts"] = [
            dict(
                path=str(p.relative_to(root)), bytes=p.stat().st_size, sha256=sha256(p)
            )
            for p in root.rglob("*")
            if p.is_file() and p.name != "report.json"
        ]
        put("report.json", report)

    host = apple_metadata(raw, 41) if apple else linux_metadata(raw, 41)
    put("host.json", host)
    put("host-metadata.stdout", host)
    put(
        "launcher-host.json",
        {
            k: bytes.fromhex(host["os"]["uname"][k]).decode()
            for k in ("system", "release", "machine")
        },
    )
    if apple:
        apple_artifacts(root, paths, report, records, put, build, raw)
    sync()
    return dict(
        paths=paths,
        report=report,
        policy=policy,
        actions=actions,
        diagnostics=diagnostics,
        records=records,
        put=put,
        lines=lines,
        sync=sync,
        inputs=inputs,
        inventory=inv,
    )
