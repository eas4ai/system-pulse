#!/usr/bin/env python3
"""Rootless System Pulse installation; removal only touches recorded, unchanged files."""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import tempfile

APP = "lib/system-pulse"
DESKTOP = "share/applications/org.systempulse.SystemPulse.desktop"
ICON = "share/icons/hicolor/scalable/apps/org.systempulse.SystemPulse.svg"
RECORD = APP + "/install-record.json"


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def relative_path(value):
    path = PurePosixPath(value)
    if (
        not value
        or str(path) != value
        or path.is_absolute()
        or ".." in path.parts
        or any(ord(c) < 32 for c in value)
    ):
        raise ValueError(f"Invalid package path: {value!r}")
    return path


def destination(prefix, name):
    relative_path(name)
    if not (name.startswith(APP + "/") or name in ("bin/system-pulse", DESKTOP, ICON)):
        raise ValueError(f"Path is outside this application's installation: {name}")
    path = prefix / name
    for ancestor in path.parents:
        if ancestor == prefix:
            break
        if ancestor.is_symlink():
            raise ValueError(f"Installation parent is a symbolic link: {ancestor}")
    return path


def load_json(path):
    with path.open("rb") as source:
        raw = source.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError("Installation manifest exceeds 2 MB")
    return json.loads(raw)


def prefix_path(prefix):
    path = Path(prefix).expanduser().resolve()
    if "=" in str(path) or any(ord(c) < 32 for c in str(path)):
        raise ValueError(
            "The desktop launcher requires a prefix without '=' or control characters"
        )
    return path


def desktop_entry(prefix):
    # Desktop Entry spec: string unescaping precedes Exec argument unquoting.
    # https://specifications.freedesktop.org/desktop-entry/latest/exec-variables.html
    executable = str(prefix / APP / "system-pulse")
    escaped = "".join(
        "\\\\" if c == "\\" else "\\" + c if c in '"`$' else "%%" if c == "%" else c
        for c in executable
    )
    # Escape the quoting backslashes for the .desktop string value layer.
    escaped = escaped.replace("\\", "\\\\")
    icon = str(prefix / ICON).replace("\\", "\\\\")
    return (
        "[Desktop Entry]\nType=Application\nName=System Pulse\n"
        "Comment=Live system readings and process controls\n"
        f'Exec="{escaped}"\nIcon={icon}\n'
        "Terminal=false\nCategories=System;Monitor;\n"
        "StartupWMClass=org.systempulse.SystemPulse\n"
    ).encode()


def matches(path, entry):
    if entry["kind"] == "symlink":
        return path.is_symlink() and os.readlink(path) == entry["target"]
    return (
        path.is_file()
        and not path.is_symlink()
        and digest(path) == entry["sha256"]
        and (path.stat().st_mode & 0o777) == entry["mode"]
    )


def read_record(prefix):
    record_path = destination(prefix, RECORD)
    if record_path.is_symlink():
        raise ValueError("Installation record is a symbolic link")
    if not record_path.exists():
        return None
    record = load_json(record_path)
    if (
        not isinstance(record, dict)
        or record.get("schema") != 1
        or not isinstance(record.get("files"), dict)
    ):
        raise ValueError("Invalid installation record")
    for name, entry in record["files"].items():
        destination(prefix, name)
        if name == RECORD or not isinstance(entry, dict):
            raise ValueError("Invalid installation record entry")
        if entry.get("kind") == "file":
            if entry.get("mode") not in (0o644, 0o755):
                raise ValueError("Invalid recorded file mode")
            value = entry.get("sha256", "")
            if (
                not isinstance(value, str)
                or len(value) != 64
                or any(c not in "0123456789abcdef" for c in value)
            ):
                raise ValueError("Invalid recorded digest")
        elif (
            entry.get("kind") != "symlink"
            or name != "bin/system-pulse"
            or entry.get("target") != "../lib/system-pulse/system-pulse"
        ):
            raise ValueError("Invalid recorded symbolic link")
    return record


def make_parents(path, created):
    missing = []
    while not path.exists():
        missing.append(path)
        path = path.parent
    for path in reversed(missing):
        path.mkdir()
        created.append(path)


def install(package, prefix):
    package, prefix = Path(package).resolve(), prefix_path(prefix)
    manifest = load_json(package / "package-files.json")
    if (
        not isinstance(manifest, dict)
        or not {"system-pulse", "icon.svg", "install.py"} <= manifest.keys()
    ):
        raise ValueError("Package lacks the application, icon or installer")
    sources, entries = {}, {}
    for name, expected in manifest.items():
        relative_path(name)
        if name == "install-record.json":
            raise ValueError("Package uses reserved installer metadata")
        source = package / name
        if (
            not source.is_file()
            or source.is_symlink()
            or not source.resolve().is_relative_to(package)
            or digest(source) != expected
        ):
            raise ValueError(f"Missing or changed package file: {name}")
        target = APP + "/" + name
        destination(prefix, target)
        sources[target] = source
        entries[target] = {
            "kind": "file",
            "sha256": expected,
            "mode": 0o755 if name in ("system-pulse", "install.py") else 0o644,
        }
    desktop = desktop_entry(prefix)
    sources[DESKTOP] = desktop
    entries[DESKTOP] = {
        "kind": "file",
        "sha256": hashlib.sha256(desktop).hexdigest(),
        "mode": 0o644,
    }
    sources[ICON] = package / "icon.svg"
    entries[ICON] = {"kind": "file", "sha256": digest(sources[ICON]), "mode": 0o644}
    entries["bin/system-pulse"] = {
        "kind": "symlink",
        "target": "../lib/system-pulse/system-pulse",
    }
    record = {"schema": 1, "files": entries}
    previous = read_record(prefix)
    if previous == record and all(
        matches(destination(prefix, name), entry) for name, entry in entries.items()
    ):
        return "already installed"
    if previous is not None:
        raise FileExistsError(
            "A different or modified installation exists; uninstall it first. Saved configuration is preserved."
        )
    # Preflight every destination before creating any file or directory.
    for name in [*entries, RECORD]:
        path = destination(prefix, name)
        if path.exists() or path.is_symlink():
            raise FileExistsError(f"Refusing to replace an unowned file: {path}")
    written, directories = [], []
    try:
        sources[RECORD] = (json.dumps(record, indent=2) + "\n").encode()
        for name in [*entries, RECORD]:
            path = destination(prefix, name)
            make_parents(path.parent, directories)
            if name == "bin/system-pulse":
                path.symlink_to(entries[name]["target"])
            else:
                with tempfile.NamedTemporaryFile(
                    dir=path.parent, prefix=".pulse-", delete=False
                ) as temp:
                    temp_path = Path(temp.name)
                    try:
                        source = sources[name]
                        if isinstance(source, bytes):
                            temp.write(source)
                        else:
                            with source.open("rb") as stream:
                                shutil.copyfileobj(stream, temp)
                        temp.flush()
                        os.fsync(temp.fileno())
                        os.chmod(
                            temp_path,
                            0o755
                            if name in (APP + "/system-pulse", APP + "/install.py")
                            else 0o644,
                        )
                        # Exclusive link publication never replaces a raced-in file.
                        os.link(temp_path, path)
                    finally:
                        temp_path.unlink(missing_ok=True)
            written.append(name)
    except BaseException:
        for name in reversed(written):
            path = destination(prefix, name)
            if name == RECORD or matches(path, entries[name]):
                path.unlink(missing_ok=True)
        for path in reversed(directories):
            try:
                path.rmdir()
            except OSError:
                pass  # Leave nonempty directories and any concurrent user files.
        raise
    return "installed"


def uninstall(prefix):
    prefix = prefix_path(prefix)
    record = read_record(prefix)
    if record is None:
        return []
    retained = {}
    parents = set()
    for name, entry in record["files"].items():
        path = destination(prefix, name)
        if not path.exists() and not path.is_symlink():
            continue
        if matches(path, entry):
            path.unlink()
            parents.update(
                parent
                for parent in path.parents
                if parent != prefix and prefix in parent.parents
            )
        else:
            retained[name] = entry
    record_path = destination(prefix, RECORD)
    if retained:
        with tempfile.NamedTemporaryFile(
            mode="w", dir=record_path.parent, prefix=".pulse-", delete=False
        ) as temp:
            json.dump({"schema": 1, "files": retained}, temp, indent=2)
            temp.flush()
            os.fsync(temp.fileno())
        os.replace(temp.name, record_path)
    else:
        record_path.unlink()
        parents.add(record_path.parent)
    for path in sorted(parents, key=lambda p: len(p.parts), reverse=True):
        try:
            path.rmdir()
        except OSError:
            pass  # Empty application directories only; user files remain.
    return sorted(retained)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", type=Path, default=Path.home() / ".local")
    parser.add_argument("--uninstall", action="store_true")
    args = parser.parse_args()
    try:
        if args.uninstall:
            retained = uninstall(args.prefix)
            if retained:
                print(
                    "Retained modified files: " + ", ".join(retained), file=sys.stderr
                )
                return 1
            print("Removed System Pulse. Saved configuration is preserved.")
        else:
            status = install(Path(__file__).parent, args.prefix)
            print(
                f"System Pulse {status}: {prefix_path(args.prefix) / 'bin/system-pulse'}"
            )
    except (OSError, ValueError) as error:
        print(f"System Pulse installation: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
