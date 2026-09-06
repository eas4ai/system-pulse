"""Native OS and deployed provider originals, independent of sensor formulas."""

import ctypes
import os
from pathlib import Path
import plistlib
import re
import shlex
import struct
import time
import uuid

from host_accuracy import require

API_LIMITATION = "No independent runtime API version query; owning OS and loaded image build retained"
KERNEL_API_LIMITATION = (
    "Kernel-owned API has no independent version; owning kernel build retained"
)


def hex_file(path, optional=False):
    try:
        with Path(path).open("rb") as stream:
            data = stream.read(1024 * 1024 + 1)
        require(len(data) <= 1024 * 1024, "native version original exceeds bound")
        return dict(path=str(path), raw_hex=data.hex())
    except OSError as error:
        if not optional:
            raise
        return dict(path=str(path), errno=error.errno)


def linux_os(root=Path("/")):
    root = Path(root)
    names = os.uname()
    product = root / "etc/os-release"
    if not product.exists():
        product = root / "usr/lib/os-release"
    return dict(
        uname={
            key: str(value).encode().hex()
            for key, value in [
                ("system", names.sysname),
                ("release", names.release),
                ("version", names.version),
                ("machine", names.machine),
            ]
        },
        product=hex_file(product),
        kernel=hex_file(root / "proc/version"),
    )


class DrmVersion(ctypes.Structure):
    _fields_ = [
        ("major", ctypes.c_int),
        ("minor", ctypes.c_int),
        ("patch", ctypes.c_int),
        ("name_len", ctypes.c_size_t),
        ("name", ctypes.c_void_p),
        ("date_len", ctypes.c_size_t),
        ("date", ctypes.c_void_p),
        ("desc_len", ctypes.c_size_t),
        ("desc", ctypes.c_void_p),
    ]


def drm_version(fd):
    native = ctypes.CDLL(None, use_errno=True)
    query = DrmVersion()
    opcode = 0xC0006400 | (ctypes.sizeof(query) << 16)
    started = time.monotonic_ns()

    def call():
        code = native.ioctl(
            ctypes.c_int(fd), ctypes.c_ulong(opcode), ctypes.byref(query)
        )
        if code < 0:
            raise OSError(ctypes.get_errno(), os.strerror(ctypes.get_errno()))
        require(code == 0, "unexpected DRM version result")

    call()
    lengths = {key: getattr(query, key + "_len") for key in ("name", "date", "desc")}
    require(
        all(0 <= value <= 4096 for value in lengths.values()),
        "DRM version string bound",
    )
    buffers = {
        key: ctypes.create_string_buffer(value + 1) for key, value in lengths.items()
    }
    for key, buffer in buffers.items():
        setattr(query, key, ctypes.addressof(buffer))
    call()
    require(
        all(getattr(query, key + "_len") == value for key, value in lengths.items()),
        "DRM version length changed",
    )
    info = os.fstat(fd)
    return dict(
        source="DRM_IOCTL_VERSION",
        major=query.major,
        minor=query.minor,
        patch=query.patch,
        strings={
            key: bytes(buffer)[: lengths[key]].hex() for key, buffer in buffers.items()
        },
        dev=f"{os.major(info.st_rdev)}:{os.minor(info.st_rdev)}",
        started_ns=started,
        finished_ns=time.monotonic_ns(),
    )


def linux_host():
    from gpu_intel_capture import anchor, discover, open_drm
    from gpu_intel_sources import Sysfs

    fs = Sysfs()
    devices = []
    for device in discover(Path("/"), fs):
        fd = open_drm(device)
        try:
            version = drm_version(fd)
        finally:
            os.close(fd)
        module = "/sys/module/" + device["driver"]
        devices.append(
            dict(
                identity=device,
                drm=version,
                module={
                    key: hex_file(module + "/" + path, optional=True)
                    for key, path in [
                        ("version", "version"),
                        ("srcversion", "srcversion"),
                        ("build_id", "notes/.note.gnu.build-id"),
                    ]
                },
                kernel_api_version=None,
                version_limitation=KERNEL_API_LIMITATION,
            )
        )
    return dict(
        schema=1,
        pid=os.getpid(),
        clock_anchor=anchor(),
        os=linux_os(),
        devices=devices,
        sysfs=fs.record,
    )


def raw_text(raw):
    data = bytes.fromhex(raw)
    require(len(data) <= 1024 * 1024, "native version text exceeds bound")
    text = data.decode("utf-8")
    require("\0" not in text, "embedded NUL in native version text")
    return text


def os_facts(original):
    names = {
        key: raw_text(original["uname"][key])
        for key in ("system", "release", "version", "machine")
    }
    require(all(names.values()), "missing OS/kernel/architecture fact")
    product = original["product"]
    if names["system"] == "Linux":
        require(
            product["path"] in ("/etc/os-release", "/usr/lib/os-release")
            and original["kernel"]["path"] == "/proc/version",
            "wrong native Linux OS sources",
        )
        values = {}
        for line in raw_text(product["raw_hex"]).splitlines():
            if not line or line.startswith("#"):
                continue
            key, separator, value = line.partition("=")
            require(
                separator
                and re.fullmatch("[A-Z][A-Z_0-9]*", key)
                and key not in values,
                "invalid/duplicate os-release key",
            )
            words = shlex.split(value, comments=False, posix=True)
            require(len(words) <= 1, "invalid os-release value")
            values[key] = words[0] if words else ""
        require(
            all(values.get(key) for key in ("ID", "NAME", "VERSION_ID")),
            "missing OS product/version",
        )
        kernel = raw_text(original["kernel"]["raw_hex"]).strip()
        require(
            kernel.startswith("Linux version " + names["release"] + " ")
            and names["version"] in kernel,
            "kernel build original disagrees with uname",
        )
        return dict(
            **names,
            product=values,
            kernel_build=kernel,
            product_build_limitation=None
            if values.get("BUILD_ID")
            else "os-release publishes no BUILD_ID; exact loaded kernel build retained",
        )
    require(
        names["system"] == "Darwin"
        and product["path"] == "/System/Library/CoreServices/SystemVersion.plist",
        "wrong native Apple OS source",
    )
    values = plistlib.loads(bytes.fromhex(product["raw_hex"]))
    require(
        all(
            isinstance(values.get(key), str) and values[key]
            for key in ("ProductName", "ProductVersion", "ProductBuildVersion")
        ),
        "missing Apple OS product/build",
    )
    require(
        raw_text(original["kern_osversion_hex"]) == values["ProductBuildVersion"],
        "Apple product build disagrees with loaded kernel OS build",
    )
    return dict(**names, product=values)


def image_facts(row, api, requested, symbol):
    require(
        row["api"] == api
        and row["requested_path"] == requested
        and row["symbol"] == symbol
        and row["standalone_api_version"] is None
        and row["version_limitation"] == API_LIMITATION,
        "missing/misnamed native provider or fabricated API version",
    )
    header = bytes.fromhex(row["header_hex"])
    commands = bytes.fromhex(row["commands_hex"])
    require(len(header) == 32, "invalid loaded image header")
    values = struct.unpack("<8I", header)
    require(
        values[0] == 0xFEEDFACF
        and 0 < values[4] <= 512
        and values[5] == len(commands) <= 1024 * 1024,
        "invalid native loaded image command bounds",
    )
    offset = 0
    identity = None
    versions = None
    for _ in range(values[4]):
        require(offset + 8 <= len(commands), "truncated native image command")
        code, size = struct.unpack_from("<II", commands, offset)
        require(
            size >= 8 and offset + size <= len(commands),
            "invalid native image command size",
        )
        if code == 0x1B:
            require(identity is None and size == 24, "invalid/duplicate image UUID")
            identity = str(uuid.UUID(bytes=commands[offset + 8 : offset + 24])).upper()
        elif code == 0xD:
            require(
                versions is None and size >= 24,
                "invalid/duplicate dylib version command",
            )
            versions = struct.unpack_from("<II", commands, offset + 16)
        offset += size
    require(
        offset == len(commands)
        and identity
        and versions is not None
        and row["image_uuid"] == identity
        and row["dylib_current_version_raw"] == versions[0]
        and row["dylib_compatibility_version_raw"] == versions[1],
        "loaded image build/version differs from original Mach-O bytes",
    )
    require(
        row["loaded_path"].startswith(requested.rsplit("/", 1)[0] + "/")
        and row["loaded_path"].endswith("/" + requested.rsplit("/", 1)[1]),
        "unrelated loaded provider image",
    )
    return dict(
        api=api,
        image_uuid=identity,
        loaded_path=row["loaded_path"],
        dylib_current_version_raw=versions[0],
        dylib_compatibility_version_raw=versions[1],
        standalone_api_version=None,
        version_limitation=API_LIMITATION,
    )


APPLE_IMAGES = (
    (
        "Metal",
        "/System/Library/Frameworks/Metal.framework/Metal",
        "MTLCreateSystemDefaultDevice",
    ),
    (
        "IOKit",
        "/System/Library/Frameworks/IOKit.framework/IOKit",
        "IOServiceGetMatchingService",
    ),
    ("IOReport", "/usr/lib/libIOReport.dylib", "IOReportCopyAllChannels"),
    (
        "HID",
        "/System/Library/Frameworks/IOKit.framework/IOKit",
        "IOHIDEventSystemClientCreate",
    ),
    (
        "SMC",
        "/System/Library/Frameworks/IOKit.framework/IOKit",
        "IOConnectCallStructMethod",
    ),
)


def host_facts(original, inventory):
    require(
        original["schema"] == 1
        and type(original["pid"]) is int
        and original["pid"] > 0,
        "invalid native host metadata owner",
    )
    system = os_facts(original["os"])
    selected = inventory["device"]
    facts = []
    if inventory["hardware_class"] == "apple-silicon":
        require(
            system["system"] == "Darwin"
            and len(original["images"]) == len(APPLE_IMAGES),
            "wrong/missing Apple host/provider inventory",
        )
        images = [
            image_facts(row, *spec)
            for row, spec in zip(original["images"], APPLE_IMAGES)
        ]
        loaded = {}
        for image in images:
            identity = tuple(
                image[k]
                for k in (
                    "image_uuid",
                    "dylib_current_version_raw",
                    "dylib_compatibility_version_raw",
                )
            )
            require(
                loaded.setdefault(image["loaded_path"], identity) == identity,
                "APIs disagree about the same loaded provider image",
            )
        require(
            len(original["devices"]) == len(inventory["discovery"])
            and {d["registry_id"] for d in original["devices"]}
            == {d["registry_id"] for d in inventory["discovery"]},
            "Apple provider census differs from physical inventory",
        )
        for row in original["devices"]:
            identity = next(
                d
                for d in inventory["discovery"]
                if d["registry_id"] == row["registry_id"]
            )
            require(
                row["name"] == identity["name"]
                and row["lookup_registry_id"] == row["registry_id"],
                "Apple provider queried from another physical GPU",
            )
            registry = plistlib.loads(bytes.fromhex(row["registry_plist_hex"]))
            bundle = plistlib.loads(bytes.fromhex(row["bundle_plist_hex"]))
            loaded = plistlib.loads(bytes.fromhex(row["kernel_plist_hex"]))
            identifier = registry.get(
                "CFBundleIdentifierKernel", registry.get("CFBundleIdentifier")
            )
            require(
                isinstance(identifier, str)
                and identifier
                and set(loaded) == {identifier},
                "loaded kext lookup differs from selected registry provider",
            )
            kernel = loaded[identifier]
            require(
                kernel["CFBundleIdentifier"] == identifier
                and kernel.get("CFBundleVersion")
                and isinstance(kernel.get("OSBundleUUID"), bytes)
                and len(kernel["OSBundleUUID"]) == 16,
                "missing selected loaded kernel driver build/version",
            )
            require(
                bundle.get("CFBundleIdentifier")
                and bundle.get("CFBundleVersion")
                and row["bundle_path"].startswith("/System/Library/")
                and registry.get("IOClass")
                and row["metal_class"] == registry.get("MetalPluginClassName"),
                "selected Metal implementation/provider build missing or inconsistent",
            )
            if registry.get("IOSourceVersion"):
                require(
                    registry["IOSourceVersion"] == kernel["CFBundleVersion"],
                    "loaded GPU driver version disagrees with registry source version",
                )
            facts.append(
                dict(
                    registry_id=row["registry_id"],
                    metal_class=row["metal_class"],
                    bundle_path=row["bundle_path"],
                    bundle=bundle,
                    kernel_identifier=identifier,
                    kernel_version=kernel["CFBundleVersion"],
                    kernel_uuid=kernel["OSBundleUUID"].hex(),
                    registry=registry,
                )
            )
        return dict(
            os=system,
            images=images,
            devices=sorted(facts, key=lambda d: d["registry_id"]),
        )
    require(system["system"] == "Linux", "wrong Intel operating system")
    from gpu_intel_capture import discover
    from gpu_intel_sources import Sysfs

    discovered = discover(Path("/"), Sysfs(original["sysfs"]))
    require(
        {d["monitor_id"] for d in discovered}
        == {d["monitor_id"] for d in inventory["discovery"]}
        and len(original["devices"]) == len(discovered),
        "Linux provider census differs from physical inventory",
    )
    require(
        len({r["identity"]["monitor_id"] for r in original["devices"]})
        == len(discovered),
        "duplicate Linux native provider",
    )
    for row in original["devices"]:
        identity = row["identity"]
        matches = [d for d in discovered if d["monitor_id"] == identity["monitor_id"]]
        require(
            len(matches) == 1 and matches[0] == identity,
            "Linux provider queried from another physical GPU",
        )
        version = row["drm"]
        require(
            version["source"] == "DRM_IOCTL_VERSION"
            and raw_text(version["strings"]["name"]) == identity["driver"]
            and version["dev"] in {a["dev"] for a in identity["aliases"]}
            and all(
                type(version[k]) is int and version[k] >= 0
                for k in ("major", "minor", "patch")
            )
            and version["started_ns"] <= version["finished_ns"],
            "DRM driver/API version lacks native identity",
        )
        for key in ("date", "desc"):
            raw_text(version["strings"][key])
        require(
            row["kernel_api_version"] is None
            and row["version_limitation"] == KERNEL_API_LIMITATION,
            "fabricated independent kernel API version",
        )
        module = {}
        for key, suffix in [
            ("version", "version"),
            ("srcversion", "srcversion"),
            ("build_id", "notes/.note.gnu.build-id"),
        ]:
            entry = row["module"][key]
            require(
                entry["path"] == "/sys/module/" + identity["driver"] + "/" + suffix,
                "unrelated loaded module version source",
            )
            if "raw_hex" in entry:
                data = bytes.fromhex(entry["raw_hex"])
                require(data, "empty loaded module version/build original")
                module[key] = data.hex()
            else:
                require(
                    entry.get("errno") in (2, 13),
                    "unexplained loaded module version omission",
                )
                module[key] = dict(
                    unavailable_errno=entry["errno"],
                    owning_kernel_build=system["kernel_build"],
                )
        facts.append(
            dict(
                identity={k: identity[k] for k in selected},
                drm={
                    k: v
                    for k, v in version.items()
                    if k not in ("started_ns", "finished_ns", "dev")
                },
                module=module,
                kernel_api_version=None,
                version_limitation=KERNEL_API_LIMITATION,
            )
        )
    return dict(
        os=system, devices=sorted(facts, key=lambda d: d["identity"]["monitor_id"])
    )


def validate_provenance(paths, report, inventory, lifecycle):
    from gpu_evidence import read_json, read_lines

    host = read_json(paths["host.json"])
    by_role = {r["role"]: r for r in lifecycle}
    require(
        "host-metadata" in by_role
        and host["pid"] == by_role["host-metadata"]["pid"]
        and read_lines(paths["host-metadata.stdout"]) == [host],
        "host metadata has no original executed owner",
    )
    expected = host_facts(host, inventory)
    if "launcher-host.json" in paths:
        launcher = read_json(paths["launcher-host.json"])
        require(
            all(
                launcher[key] == expected["os"][key]
                for key in ("system", "release", "machine")
            ),
            "capture launcher OS facts disagree with native metadata",
        )
    raw = [read_json(paths["native-inventory.json"])] + read_lines(
        paths["native-observer.jsonl"]
    )
    for frame in raw:
        require(
            frame["host"]["pid"] == frame["pid"]
            and host_facts(frame["host"], inventory) == expected,
            "native inventory/observer host or provider build changed",
        )
        for key, fact in [("os_release", "release"), ("machine", "machine")]:
            require(
                key not in frame or frame[key] == expected["os"][fact],
                "legacy native OS fact disagrees with original OS metadata",
            )
    work = read_lines(paths["workload.stdout"])[0]
    if report["hardware_class"] == "apple-silicon":
        require(
            work["host"]["pid"] == work["pid"]
            and host_facts(work["host"], inventory) == expected,
            "Metal workload host/provider build differs from observation",
        )
    else:
        require(
            "workload-provider" in by_role,
            "missing queried Vulkan provider version owner",
        )
        provider = read_json(paths["workload-provider.json"])
        require(
            read_lines(paths["workload-provider.stdout"]) == [provider]
            and provider["pid"] == by_role["workload-provider"]["pid"]
            and provider["schema"] == 1
            and provider["mode"] == "metadata",
            "Vulkan provider metadata differs from native execution",
        )
        keys = (
            "pci",
            "vendor_id",
            "device_id",
            "api_version_raw",
            "driver_version_raw",
            "loader_api_version_raw",
        )
        require(
            all(provider[k] == work[k] for k in keys)
            and os_facts(provider["os"]) == os_facts(work["os"]) == expected["os"],
            "Vulkan work/query OS or deployed provider version changed",
        )
        require(
            work["pci"] == inventory["device"]["pci"]
            and work["vendor_id"] == int(inventory["device"]["vendor"], 16)
            and work["device_id"] == int(inventory["device"]["device_id"], 16),
            "Vulkan provider belongs to another GPU",
        )
        require(
            all(type(work[k]) is int and 0 <= work[k] <= 0xFFFFFFFF for k in keys[3:])
            and all(
                (work[k] >> 29) == 0 and work[k] >= ((1 << 22) | (1 << 12))
                for k in ("api_version_raw", "loader_api_version_raw")
            ),
            "missing actual Vulkan API/driver version query",
        )
        for row in (provider, work):
            require(
                type(row["query_started_ns"]) is int
                and type(row["query_finished_ns"]) is int
                and 0 <= row["query_started_ns"] <= row["query_finished_ns"]
                and row["query_finished_ns"] - row["query_started_ns"]
                <= 15_000_000_000,
                "unbounded/missing actual Vulkan provider query",
            )
            require(
                row["driver_version_semantics"]
                == "vendor-defined raw uint32; no semantic decoding"
                and row["api_version_semantics"]
                == "Vulkan VkPhysicalDeviceProperties.apiVersion",
                "invented Vulkan driver version encoding",
            )
    return expected
