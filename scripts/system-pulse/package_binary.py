"""Build a portable release archive for the current supported native target."""

import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import tarfile
import time
import tomllib
import zipfile

from package_linux import ROOT, capture, digest, require_committed_source, run, write_licenses, write_source_archive

TARGETS = {
    "x86_64-unknown-linux-gnu": ("linux-x86_64", "system-pulse"),
    "aarch64-apple-darwin": ("macos-arm64", "system-pulse"),
    "x86_64-pc-windows-msvc": ("windows-x86_64", "system-pulse.exe"),
}


def check_binary_header(header, target):
    """Reject an artifact for the wrong OS or CPU before distributing it."""
    if target == "x86_64-unknown-linux-gnu":
        valid = header[:6] == b"\x7fELF\x02\x01" and len(header) >= 20 and struct.unpack_from("<H", header, 18)[0] == 62
    elif target == "aarch64-apple-darwin":
        valid = header[:4] == b"\xcf\xfa\xed\xfe" and len(header) >= 8 and struct.unpack_from("<I", header, 4)[0] == 0x0100000C
    elif target == "x86_64-pc-windows-msvc":
        offset = struct.unpack_from("<I", header, 60)[0] if len(header) >= 64 else len(header)
        valid = header[:2] == b"MZ" and offset + 6 <= len(header) and header[offset:offset + 6] == b"PE\0\0\x64\x86"
    else:
        valid = False
    if not valid:
        raise ValueError("Executable header does not match target: " + target)


def runtime_libraries(binary, target):
    if target.endswith("linux-gnu"):
        libraries = capture(["ldd", str(binary)])
        if "not found" in libraries:
            raise ValueError("The build host lacks a linked runtime library")
        return libraries.splitlines()
    if target.endswith("apple-darwin"):
        return capture(["otool", "-L", str(binary)]).splitlines()
    program_files = os.environ.get("ProgramFiles(x86)")
    if not program_files:
        raise ValueError("Visual Studio installation location is unavailable")
    vswhere = Path(program_files) / "Microsoft Visual Studio/Installer/vswhere.exe"
    installation = capture([str(vswhere), "-latest", "-products", "*", "-requires",
                            "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath"])
    candidates = sorted((Path(installation) / "VC/Tools/MSVC").glob("*/bin/Hostx64/x64/dumpbin.exe"))
    if not installation or not candidates:
        raise ValueError("Install Visual C++ tools to inspect the executable's DLL dependencies")
    return capture([str(candidates[-1]), "/DEPENDENTS", str(binary)]).splitlines()


def copy_notices(package):
    notices = package / "notices"
    notices.mkdir()
    for source in (ROOT / "assets/fonts").iterdir():
        if source.is_file() and source.suffix.lower() not in (".ttf", ".otf"):
            shutil.copyfile(source, notices / source.name)
    for source, name in (("LICENSE-APACHE", "LICENSE-APACHE"),
                         ("crates/collectors/src/intel/UAPI-NOTICE", "Intel-UAPI-NOTICE"),
                         ("crates/collectors/src/apple/NOTICE.md", "Apple-NOTICE.md")):
        shutil.copyfile(ROOT / source, notices / name)


def make_archive(package, output, windows):
    archive = output / (package.name + (".zip" if windows else ".tar.gz"))
    if windows:
        with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as bundle:
            for path in sorted(package.rglob("*")):
                if path.is_file():
                    bundle.write(path, path.relative_to(package.parent).as_posix())
    else:
        with tarfile.open(archive, "w:gz") as bundle:
            bundle.add(package, arcname=package.name)
    (output / "SHA256SUMS").write_text(f"{digest(archive)}  {archive.name}\n")
    return archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target", choices=TARGETS, required=True)
    parser.add_argument("--cargo-about", default="cargo-about")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(ROOT):
        raise ValueError("Package output must be outside the checkout")
    require_committed_source()
    host = next(line.removeprefix("host: ") for line in capture(["rustc", "-vV"]).splitlines() if line.startswith("host: "))
    if host != args.target:
        raise ValueError(f"Build {args.target} on its native runner, not {host}")
    about = shutil.which(args.cargo_about)
    if not about or capture([about, "--version"]) != "cargo-about 0.9.2":
        raise ValueError("Install cargo-about 0.9.2 with --locked --features cli")
    output.mkdir(parents=True, exist_ok=False)
    commit = capture(["git", "rev-parse", "HEAD"])
    version = tomllib.loads((ROOT / "Cargo.toml").read_text())["package"]["version"]
    label, executable = TARGETS[host]
    package = output / f"system-pulse-{version}-{label}-{commit[:12]}"
    package.mkdir()
    print(f"Building {label} at {commit}", flush=True)
    run(["cargo", "build", "--release", "--locked", "-p", "system-pulse"], output / "build.log", 3600)
    metadata = json.loads(capture(["cargo", "metadata", "--locked", "--no-deps", "--format-version=1"]))
    binary = Path(metadata["target_directory"]) / "release" / executable
    with binary.open("rb") as source:
        check_binary_header(source.read(4096), host)
    config = tomllib.loads((ROOT / "package/about.toml").read_text())
    config["targets"] = [host]
    about_config = output / "about.toml"
    about_config.write_text("\n".join(f"{name} = {json.dumps(value)}" for name, value in config.items()) + "\n")
    report = output / "license-report.json"
    run([about, "generate", "--locked", "--fail", "--manifest-path", str(ROOT / "Cargo.toml"),
         "--config", str(about_config), "--format", "json", "--output-file", str(report)],
        output / "licenses.log", 1200)
    count = write_licenses(json.loads(report.read_text()), package, label)
    shutil.copyfile(binary, package / executable)
    (package / executable).chmod(0o755)
    shutil.copyfile(ROOT / "COPYING", package / "COPYING")
    shutil.copyfile(ROOT / "package/BINARY-README.md", package / "README.md")
    if host.endswith("linux-gnu"):
        for name in ("install.py", "icon.svg"):
            shutil.copyfile(ROOT / "package" / name, package / name)
    copy_notices(package)
    write_source_archive(package / "source.tar.gz", commit, output / "source.log")
    (package / "SOURCE.txt").write_text(
        f"System Pulse source commit: {commit}\nhttps://github.com/eas4ai/system-pulse/tree/{commit}\n"
        "source.tar.gz contains the committed workspace, patches and Cargo.lock.\n"
        "Extract it and run cargo build --release --locked -p system-pulse on the native platform.\n"
        "Cargo resolves the external dependency sources pinned by Cargo.lock.\n"
        "See COPYING, LICENSES.html, dependency-licenses.json and notices/ for licenses.\n")
    build = {"source_commit": commit, "target": host, "platform": label, "version": version,
             "built_unix_ns": time.time_ns(), "rustc": capture(["rustc", "--version"]),
             "host_os": platform.platform(), "libc": platform.libc_ver(),
             "runtime_libraries": runtime_libraries(package / executable, host),
             "binary_sha256": digest(package / executable), "source_archive_sha256": digest(package / "source.tar.gz"),
             "dependency_count": count, "github_run_id": os.environ.get("GITHUB_RUN_ID"),
             "verification": "Native build and archive validation; hardware runtime acceptance is recorded separately."}
    (package / "build.json").write_text(json.dumps(build, indent=2) + "\n")
    files = {path.relative_to(package).as_posix(): digest(path) for path in sorted(package.rglob("*")) if path.is_file()}
    (package / "package-files.json").write_text(json.dumps(files, indent=2) + "\n")
    require_committed_source()
    archive = make_archive(package, output, host.endswith("windows-msvc"))
    print(json.dumps({"archive": str(archive), "source_commit": commit, "sha256": digest(archive), "dependencies": count}), flush=True)


if __name__ == "__main__":
    main()
