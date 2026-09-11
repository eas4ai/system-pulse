"""Sign a verified native Windows package and compile its optional PawnIO installer."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess

from package_binary import make_archive

PAWNIO_SHA256 = "1f519a22e47187f70a1379a48ca604981c4fcf694f4e65b734aaa74a9fba3032"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_package(package):
    manifest = json.loads((package / "package-files.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or not {"build.json", "system-pulse.exe"} <= manifest.keys():
        raise ValueError("Package manifest lacks native build provenance")
    for name, expected in manifest.items():
        parts = PurePosixPath(name)
        if parts.is_absolute() or ".." in parts.parts or "\\" in name or ":" in name:
            raise ValueError("Package manifest contains an unsafe path")
        path = package / name
        if path.is_symlink() or not path.is_file() or digest(path) != expected:
            raise ValueError("Package file is missing or changed: " + name)
    files = {p.relative_to(package).as_posix() for p in package.rglob("*") if p.is_file()}
    if files != set(manifest) | {"package-files.json"}:
        raise ValueError("Package contains unrecorded files")
    build = json.loads((package / "build.json").read_text(encoding="utf-8"))
    if build.get("target") != "x86_64-pc-windows-msvc":
        raise ValueError("Installer requires a native Windows x64 package")
    if not re.fullmatch(r"[0-9a-f]{40}", build.get("source_commit", "")):
        raise ValueError("Package source revision is invalid")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", build.get("version", "")):
        raise ValueError("Package version is invalid")
    if build.get("binary_sha256") != digest(package / "system-pulse.exe"):
        raise ValueError("Native binary does not match build provenance")
    return build


def verify_prerequisite(path):
    if digest(path) != PAWNIO_SHA256:
        raise ValueError("PawnIO prerequisite differs from the pinned official 2.2.0 release")


def powershell(script):
    encoded = base64.b64encode(("$ErrorActionPreference='Stop'; " + script).encode("utf-16le")).decode()
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                            check=True, capture_output=True, text=True, timeout=180)
    return result.stdout.strip()


def ps_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def signature(path):
    result = json.loads(powershell("$s=Get-AuthenticodeSignature " + ps_quote(path) +
        "; if ($s.Status -ne 'Valid') {throw 'Authenticode verification failed'}; "
        "@{status=$s.Status.ToString();subject=$s.SignerCertificate.Subject;"
        "thumbprint=$s.SignerCertificate.Thumbprint}|ConvertTo-Json -Compress"))
    return result


def safe_command_path(path):
    if any(c in str(path) for c in '&|<>"%^!\r\n'):
        raise ValueError("Signing paths may not contain command interpreter metacharacters")
    return str(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--pawnio", type=Path, required=True)
    parser.add_argument("--iscc", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if os.name != "nt":
        raise ValueError("Sign and compile the installer on Windows")
    source, pawnio, output = args.package.resolve(), args.pawnio.resolve(), args.output.resolve()
    build = validate_package(source)
    verify_prerequisite(pawnio)
    prerequisite_signature = signature(pawnio)
    output.mkdir(parents=True, exist_ok=False)
    package = output / source.name
    shutil.copytree(source, package)
    binary = package / "system-pulse.exe"
    subprocess.run(["cmd.exe", "/d", "/c", "sign", safe_command_path(binary)], check=True, timeout=300)
    application_signature = signature(binary)
    build["unsigned_binary_sha256"] = build["binary_sha256"]
    build["binary_sha256"] = digest(binary)
    build["authenticode"] = application_signature
    (package / "build.json").write_text(json.dumps(build, indent=2) + "\n", encoding="utf-8")
    manifest = {p.relative_to(package).as_posix(): digest(p) for p in sorted(package.rglob("*"))
                if p.is_file() and p.name != "package-files.json"}
    (package / "package-files.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    validate_package(package)
    archive = make_archive(package, output, True)
    script = Path(__file__).resolve().parents[2] / "package/windows/system-pulse.iss"
    command = [str(args.iscc), "/DPackageDir=" + safe_command_path(package),
               "/DPawnIOSetup=" + safe_command_path(pawnio), "/DOutputDir=" + safe_command_path(output),
               "/DAppVersion=" + build["version"], "/DSourceRevision=" + build["source_commit"][:12],
               "/Ssystempulse=cmd.exe /d /c sign $f", str(script)]
    with (output / "installer-build.log").open("w", encoding="utf-8") as log:
        subprocess.run(command, check=True, stdout=log, stderr=subprocess.STDOUT, timeout=600)
    installer = output / ("system-pulse-" + build["version"] + "-windows-x86_64-" + build["source_commit"][:12] + "-setup.exe")
    installer_signature = signature(installer)
    result = {"source_commit": build["source_commit"], "installer": installer.name,
              "installer_sha256": digest(installer), "installer_signature": installer_signature,
              "binary_sha256": build["binary_sha256"], "application_signature": application_signature,
              "pawnio_sha256": PAWNIO_SHA256, "pawnio_signature": prerequisite_signature,
              "archive": archive.name, "archive_sha256": digest(archive)}
    (output / "installer.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
