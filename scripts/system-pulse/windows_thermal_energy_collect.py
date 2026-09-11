"""Capture the signed packaged thermal/energy UI with explicit human consent gates.

The Limited interactive task writes request.json at each gate. The operator must
deny/approve UAC as requested, supply fresh independent.json at the independent
gate, and terminate only the identified helper at the helper-exit gate. Timeouts
retain partial artifacts and cannot produce a passing receipt.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import uuid

from performance_compare import require
from performance_verify import ROOT, PRODUCTION, same_production
from release_ci_verify import archive_files, verify_archive
from windows_process_actions_collect import build_identity, deploy_package
from windows_runtime_collect import remote

HARNESSES = (
    "windows_thermal_energy_collect.py",
    "windows_thermal_energy.ps1",
    "windows_thermal_energy_verify.py",
    "test_windows_thermal_energy_verify.py",
    "windows_runtime.ps1",
    "windows_runtime_collect.py",
    "windows_process_actions_collect.py",
    "windows_process_actions_verify.py",
    "windows_gpu_collect.py",
    "windows_gpu_verify.py",
    "release_ci_verify.py",
    "package_binary.py",
    "package_linux.py",
    "performance_verify.py",
    "performance_compare.py",
    "performance_macos.py",
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def signed_build_identity(build, revision, unsigned_hash, signed_hash):
    require(
        build["source_commit"] == revision
        and build["target"] == "x86_64-pc-windows-msvc",
        "signed package source or target differs from native build",
    )
    require(
        build["unsigned_binary_sha256"] == unsigned_hash
        and build["binary_sha256"] == signed_hash,
        "signing provenance does not connect the native build to the measured executable",
    )
    signature = build["authenticode"]
    require(
        signature["status"] == "Valid"
        and signature["subject"]
        and signature["thumbprint"],
        "signed package lacks valid Authenticode provenance",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.environ.get("SYSTEM_PULSE_WINDOWS_HOST"))
    parser.add_argument("--build-log", type=Path, required=True)
    parser.add_argument("--package-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--gate-timeout", type=int, default=180)
    args = parser.parse_args()
    require(args.host and not args.host.startswith("-"), "missing Windows SSH host")
    require(
        30 <= args.gate_timeout <= 180,
        "consent gate must be between 30 and 180 seconds",
    )
    revision, unsigned_hash = build_identity(args.build_log.read_text(errors="replace"))
    same_production(revision)
    package = verify_archive(args.package_dir, "x86_64-pc-windows-msvc", revision)
    archive = args.package_dir / package["archive"]
    files = archive_files(archive)
    build = json.loads(files["build.json"])
    binary_hash = hashlib.sha256(files["system-pulse.exe"]).hexdigest()
    signed_build_identity(build, revision, unsigned_hash, binary_hash)
    inputs = [*PRODUCTION, *("scripts/system-pulse/" + name for name in HARNESSES)]
    subprocess.run(
        ["git", "diff", "--exit-code", "HEAD", "--", *inputs], cwd=ROOT, check=True
    )
    for name in HARNESSES:
        subprocess.run(
            ["git", "ls-files", "--error-unmatch", "scripts/system-pulse/" + name],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
        )
    hashes = {name: digest(ROOT / "scripts/system-pulse" / name) for name in HARNESSES}
    run_id = uuid.uuid4().hex
    task = "SystemPulse-ThermalEnergy-" + run_id
    cache = args.output or Path(
        tempfile.mkdtemp(prefix="system-pulse-windows-thermal-")
    )
    cache.mkdir(parents=True, exist_ok=True)
    require(not (cache / "evidence").exists(), "output already contains evidence")
    parent, binary = deploy_package(args.host, task, archive, package)
    helpers, separator, _ = (
        (ROOT / "scripts/system-pulse/windows_runtime.ps1")
        .read_text()
        .partition("$script:app=$null")
    )
    require(separator, "runtime helper boundary changed")

    def quote(value):
        return "'" + value.replace("'", "''") + "'"

    prelude = (
        f"$RunId='{run_id}'\n$SourceCommit='{revision}'\n$ExpectedBinarySha256='{binary_hash}'\n"
        f"$GateTimeout={args.gate_timeout}\n$OutputDirectory={quote(parent + '/evidence')}\n$script:binary={quote(binary)}\n"
    )
    script = cache / "thermal-energy.ps1"
    script.write_text(
        prelude
        + helpers
        + (ROOT / "scripts/system-pulse/windows_thermal_energy.ps1").read_text(),
        encoding="utf-8-sig",
    )
    subprocess.run(
        [
            "scp",
            "-O",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=15",
            str(script),
            f"{args.host}:workspace/{task}/thermal-energy.ps1",
        ],
        check=True,
        timeout=90,
    )
    remote(
        args.host,
        r"""
$scriptPath=Join-Path $env:USERPROFILE 'workspace\__TASK__\thermal-energy.ps1'
$action=New-ScheduledTaskAction -Execute "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" -Argument ('-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "'+$scriptPath+'"')
$principal=New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
$settings=New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 23)
Register-ScheduledTask -TaskName '__TASK__' -Action $action -Principal $principal -Settings $settings|Out-Null
Start-ScheduledTask -TaskName '__TASK__'
""".replace("__TASK__", task),
    )
    print(
        json.dumps(
            dict(
                task=task,
                run_id=run_id,
                remote_evidence=parent + "/evidence",
                local_evidence=str(cache / "evidence"),
            )
        ),
        flush=True,
    )
    completed = False
    last_request = None
    state = {}
    deadline = time.monotonic() + 24 * 60
    try:
        while time.monotonic() < deadline:
            time.sleep(3)
            state = json.loads(
                remote(
                    args.host,
                    f"$t=Get-ScheduledTask -TaskName '{task}';$i=Get-ScheduledTaskInfo -TaskName '{task}';"
                    f"$p=Join-Path $env:USERPROFILE 'workspace\\{task}\\evidence\\request.json';$r=$null;if(Test-Path $p){{$r=[IO.File]::ReadAllText($p)|ConvertFrom-Json}};"
                    "@{state=[string]$t.State;result=$i.LastTaskResult;started=$i.LastRunTime.Year -ge 2026;request=$r}|ConvertTo-Json -Depth 12 -Compress",
                )
            )
            request = state.get("request")
            if request and request != last_request:
                print(json.dumps(request), flush=True)
                last_request = request
            if (
                state["started"]
                and state["state"] != "Running"
                and state["result"] != 267009
            ):
                completed = True
                break
        evidence = cache / "evidence"
        subprocess.run(
            [
                "scp",
                "-O",
                "-r",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=15",
                f"{args.host}:workspace/{task}/evidence",
                str(evidence),
            ],
            check=True,
            timeout=180,
        )
        require(
            completed and state["result"] == 0,
            "native thermal task failed/timed out; partial evidence retained at "
            + str(evidence),
        )
        record = json.loads((evidence / "result.json").read_text(encoding="utf-8-sig"))
        require(
            record["status"] == "PASS"
            and record["run_id"] == run_id
            and record["source_commit"] == revision
            and record["binary_sha256"] == binary_hash,
            "wrong native thermal result identity",
        )
        require(
            hashes
            == {
                name: digest(ROOT / "scripts/system-pulse" / name) for name in HARNESSES
            },
            "harness changed during native observation",
        )
        (evidence / "windows-build.log").write_bytes(args.build_log.read_bytes())
        (evidence / "build.json").write_bytes(files["build.json"])
        (evidence / "package.json").write_text(json.dumps(package, indent=2) + "\n")
        packaged = evidence / "package"
        packaged.mkdir()
        shutil.copy2(archive, packaged / archive.name)
        shutil.copy2(args.package_dir / "SHA256SUMS", packaged / "SHA256SUMS")
        record["harness_sha256"] = hashes
        record["artifacts_sha256"] = {
            p.relative_to(evidence).as_posix(): digest(p)
            for p in sorted(evidence.rglob("*"))
            if p.is_file() and p.name != "receipt.json"
        }
        (evidence / "receipt.json").write_text(json.dumps(record, indent=2) + "\n")
        print(
            "Native evidence retained at "
            + str(evidence)
            + "; visual review, platform/process preservation and independent acceptance remain required",
            flush=True,
        )
    finally:
        if completed:
            remote(
                args.host,
                f"Unregister-ScheduledTask -TaskName '{task}' -Confirm:$false",
            )


if __name__ == "__main__":
    main()
