"""Observe packaged Windows GPU discovery and independent performance counters."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import uuid

from performance_compare import require
from performance_verify import ROOT, PRODUCTION, same_production
from release_ci_verify import archive_files, verify_archive
from windows_process_actions_collect import build_identity, deploy_package
from windows_runtime_collect import remote

HARNESSES = ("windows_gpu_collect.py", "windows_gpu.ps1", "windows_runtime.ps1",
             "windows_runtime_collect.py", "windows_process_actions_collect.py")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.environ.get("SYSTEM_PULSE_WINDOWS_HOST"))
    parser.add_argument("--build-log", type=Path, required=True)
    parser.add_argument("--package-dir", type=Path, required=True)
    args = parser.parse_args()
    require(args.host and not args.host.startswith("-"), "missing Windows host")
    revision, binary_hash = build_identity(args.build_log.read_text(errors="replace"))
    same_production(revision)
    package = verify_archive(args.package_dir, "x86_64-pc-windows-msvc", revision)
    archive = args.package_dir / package["archive"]
    require(hashlib.sha256(archive_files(archive)["system-pulse.exe"]).hexdigest() == binary_hash,
            "package binary differs from native build")
    subprocess.run(["git", "diff", "--exit-code", "HEAD", "--", *PRODUCTION,
                    *("scripts/system-pulse/" + name for name in HARNESSES)], cwd=ROOT, check=True)
    hashes = {name: hashlib.sha256((ROOT / "scripts/system-pulse" / name).read_bytes()).hexdigest()
              for name in HARNESSES}
    for name in HARNESSES:
        subprocess.run(["git", "ls-files", "--error-unmatch", "scripts/system-pulse/" + name],
                       cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    run_id = uuid.uuid4().hex
    task = "SystemPulse-Gpu-" + run_id
    cache = Path(tempfile.mkdtemp(prefix="system-pulse-windows-gpu-"))
    parent, binary = deploy_package(args.host, task, archive, package)
    helpers, separator, _ = (ROOT / "scripts/system-pulse/windows_runtime.ps1").read_text().partition("$script:app=$null")
    require(separator, "runtime helper boundary changed")
    quote = lambda value: "'" + value.replace("'", "''") + "'"
    prelude = (f"$RunId='{run_id}'\n$SourceCommit='{revision}'\n$ExpectedBinarySha256='{binary_hash}'\n"
               f"$OutputDirectory={quote(parent + '/evidence')}\n$script:binary={quote(binary)}\n")
    local = cache / "gpu.ps1"
    local.write_text(prelude + helpers + (ROOT / "scripts/system-pulse/windows_gpu.ps1").read_text(), encoding="utf-8-sig")
    subprocess.run(["scp", "-O", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", str(local),
                    f"{args.host}:workspace/{task}/gpu.ps1"], check=True, timeout=90)
    remote(args.host, r'''
$scriptPath=Join-Path $env:USERPROFILE 'workspace\__TASK__\gpu.ps1'
$action=New-ScheduledTaskAction -Execute "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" -Argument ('-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "'+$scriptPath+'"')
$principal=New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
$settings=New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 8)
Register-ScheduledTask -TaskName '__TASK__' -Action $action -Principal $principal -Settings $settings|Out-Null
Start-ScheduledTask -TaskName '__TASK__'
'''.replace("__TASK__", task))
    print(f"Windows GPU run: {task}; evidence: {cache}", flush=True)
    completed = False
    deadline = time.monotonic() + 9 * 60
    try:
        while time.monotonic() < deadline:
            time.sleep(5)
            state = json.loads(remote(args.host, f"$t=Get-ScheduledTask -TaskName '{task}';"
                f"$i=Get-ScheduledTaskInfo -TaskName '{task}';"
                "@{state=[string]$t.State;result=$i.LastTaskResult;started=$i.LastRunTime.Year -ge 2026}|ConvertTo-Json -Compress"))
            if state["started"] and state["state"] != "Running" and state["result"] != 267009:
                completed = True
                break
        require(completed, "GPU native task timed out; inspect " + task)
        evidence = cache / "evidence"
        subprocess.run(["scp", "-O", "-r", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
                        f"{args.host}:workspace/{task}/evidence", str(evidence)], check=True, timeout=120)
        require(state["result"] == 0, "GPU native task failed; inspect " + str(evidence))
        record = json.loads((evidence / "result.json").read_text(encoding="utf-8-sig"))
        require(record["run_id"] == run_id and record["status"] == "PASS", "wrong native GPU result")
        require(record["source_commit"] == revision and record["binary_sha256"] == binary_hash, "native GPU identity mismatch")
        require(hashes == {name: hashlib.sha256((ROOT / "scripts/system-pulse" / name).read_bytes()).hexdigest()
                           for name in HARNESSES}, "GPU harness changed during observation")
        (evidence / "windows-build.log").write_bytes(args.build_log.read_bytes())
        (evidence / "package.json").write_text(json.dumps(package, indent=2) + "\n")
        record["harness_sha256"] = hashes
        record["artifacts_sha256"] = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                                      for path in sorted(evidence.iterdir()) if path.is_file() and path.name != "receipt.json"}
        (evidence / "receipt.json").write_text(json.dumps(record, indent=2) + "\n")
        print(f"Collected GPU observations: {evidence}; independent verification and visual review remain required", flush=True)
    finally:
        if completed:
            remote(args.host, f"Unregister-ScheduledTask -TaskName '{task}' -Confirm:$false")


if __name__ == "__main__":
    main()
