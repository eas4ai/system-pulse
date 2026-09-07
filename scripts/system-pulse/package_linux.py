#!/usr/bin/env python3
"""Build a checksummed Linux package from a committed workspace."""

import argparse
import hashlib
import html
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tarfile
import time

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT


def capture(command):
    return subprocess.check_output(command, cwd=ROOT, text=True, timeout=30).strip()


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def run(command, log, timeout):
    with log.open("x") as output:
        subprocess.run(
            command,
            cwd=ROOT,
            stdout=output,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=True,
        )


def write_licenses(report, package):
    crates = report["crates"]
    unknown = [
        c["package"]["name"]
        for c in crates
        if not c.get("license") or c["license"] == "Unknown"
    ]
    if not crates or unknown:
        raise ValueError("Missing resolved dependency licenses: " + ", ".join(unknown))
    groups = []
    sections = []
    for group in report["licenses"]:
        names = sorted(
            f"{c['crate']['name']} {c['crate']['version']}" for c in group["used_by"]
        )
        if not group["text"].strip():
            raise ValueError("Empty dependency license notice")
        groups.append(
            {"license": group["id"], "packages": names, "text": group["text"]}
        )
        sections.append(
            f"<section><h2>{html.escape(group['name'])}</h2><p>{html.escape(', '.join(names))}</p><pre>{html.escape(group['text'])}</pre></section>"
        )
    data = {
        "generator": "cargo-about 0.9.2",
        "packages": [
            {
                "name": c["package"]["name"],
                "version": c["package"]["version"],
                "license": c["license"],
                "source": c["package"].get("source"),
                "repository": c["package"].get("repository"),
            }
            for c in crates
        ],
        "notices": groups,
    }
    (package / "dependency-licenses.json").write_text(json.dumps(data, indent=2) + "\n")
    (package / "LICENSES.html").write_text(
        "<!doctype html><html lang=en><meta charset=utf-8><title>System Pulse dependency notices</title>"
        "<style>body{max-width:80rem;margin:3rem auto;padding:0 1rem;font:16px/1.5 system-ui}pre{white-space:pre-wrap;font:13px/1.5 monospace}section{border-top:1px solid #bbb;margin-top:2rem}</style>"
        f"<h1>System Pulse dependency notices</h1><p>Notices for {len(crates)} packages in the Linux build, including build dependencies.</p>"
        + "".join(sections)
        + "</html>\n"
    )
    return len(crates)


def require_committed_source():
    status = capture(["git", "status", "--porcelain", "--untracked-files=normal"])
    # Cairn opens its capture streams before invoking this mechanism. Only
    # untracked runtime streams are exempt; git archive includes committed files.
    stream = (
        r"\?\? \.cairn/evidence/[A-Z]+-[0-9]{3}/[0-9]{8}T[0-9]{9}Z-[0-9]+\.(out|err)"
    )
    changes = [
        line
        for line in status.splitlines()
        if line.strip() != "?? .cairn/in-progress" and not re.fullmatch(stream, line)
    ]
    if changes:
        raise ValueError("Commit the source before packaging: " + "; ".join(changes))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cargo-about", default="cargo-about")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(ROOT):
        raise ValueError("Package output must be outside the checkout")
    require_committed_source()
    target = next(
        line.removeprefix("host: ")
        for line in capture(["rustc", "-vV"]).splitlines()
        if line.startswith("host: ")
    )
    if target != "x86_64-unknown-linux-gnu":
        raise ValueError("This package recipe currently verifies x86-64 glibc Linux")
    about = shutil.which(args.cargo_about)
    if not about or capture([about, "--version"]) != "cargo-about 0.9.2":
        raise ValueError(
            "Install cargo-about 0.9.2 with --locked --features cli, or pass its path"
        )
    output.mkdir(parents=True, exist_ok=False)
    commit = capture(["git", "rev-parse", "HEAD"])
    name = f"system-pulse-0.1.0-linux-x86_64-{commit[:12]}"
    package = output / name
    package.mkdir()
    print("Building the release executable", flush=True)
    run(
        ["cargo", "build", "--release", "--locked", "-p", "system-pulse"],
        output / "build.log",
        1200,
    )
    print("Collecting pinned dependency notices", flush=True)
    report_path = output / "license-report.json"
    run(
        [
            about,
            "generate",
            "--locked",
            "--fail",
            "--manifest-path",
            str(APP / "Cargo.toml"),
            "--config",
            str(APP / "package/about.toml"),
            "--format",
            "json",
            "--output-file",
            str(report_path),
        ],
        output / "licenses.log",
        600,
    )
    dependency_count = write_licenses(json.loads(report_path.read_text()), package)
    for source, name in [
        (ROOT / "target/release/system-pulse", "system-pulse"),
        (APP / "COPYING", "COPYING"),
        (APP / "package/install.py", "install.py"),
        (APP / "package/icon.svg", "icon.svg"),
        (APP / "package/README.md", "README.md"),
    ]:
        shutil.copyfile(source, package / name)
    (package / "system-pulse").chmod(0o755)
    (package / "install.py").chmod(0o755)
    notices = package / "notices"
    notices.mkdir()
    for source in (APP / "assets/fonts").iterdir():
        if source.is_file() and source.suffix.lower() not in (".ttf", ".otf"):
            shutil.copyfile(source, notices / source.name)
    for source, name in [
        (ROOT / "crates/collectors/src/intel/UAPI-NOTICE", "Intel-UAPI-NOTICE"),
        (ROOT / "crates/collectors/src/apple/NOTICE.md", "Apple-NOTICE.md"),
    ]:
        shutil.copyfile(source, notices / name)
    run(
        [
            "git",
            "archive",
            "--format=tar.gz",
            "--prefix=system-pulse-source/",
            "-o",
            str(package / "source.tar.gz"),
            commit,
        ],
        output / "source.log",
        120,
    )
    libraries = capture(["ldd", str(package / "system-pulse")])
    if "not found" in libraries:
        raise ValueError("The package build host lacks a required shared library")
    build = {
        "source_commit": commit,
        "source_subject": capture(["git", "show", "-s", "--format=%s", commit]),
        "target": target,
        "built_unix_ns": time.time_ns(),
        "rustc": capture(["rustc", "--version"]),
        "libc": platform.libc_ver(),
        "os_release": Path("/etc/os-release").read_text(),
        "runtime_libraries": libraries.splitlines(),
        "binary_sha256": digest(package / "system-pulse"),
        "source_archive_sha256": digest(package / "source.tar.gz"),
        "dependency_count": dependency_count,
        "embedded_fonts": json.loads((APP / "assets/fonts/sources.json").read_text()),
        "verification": "Packaging checks only; native acceptance is recorded separately against this binary.",
    }
    (package / "build.json").write_text(json.dumps(build, indent=2) + "\n")
    files = {
        str(path.relative_to(package)): digest(path)
        for path in sorted(package.rglob("*"))
        if path.is_file()
    }
    (package / "package-files.json").write_text(json.dumps(files, indent=2) + "\n")
    archive = output / (package.name + ".tar.gz")
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(package, arcname=package.name)
    (output / "SHA256SUMS").write_text(f"{digest(archive)}  {archive.name}\n")
    print(
        json.dumps(
            {
                "package": str(package),
                "archive": str(archive),
                "source_commit": commit,
                "sha256": digest(archive),
                "dependencies": dependency_count,
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
