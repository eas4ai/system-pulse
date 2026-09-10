"""Collect native Windows observations using the executable from a passing build."""

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import uuid

from performance_compare import require
from performance_verify import ROOT, PRODUCTION, same_production


def remote(host, script):
    script = ("[Console]::OutputEncoding = New-Object Text.UTF8Encoding $false; "
              "$ProgressPreference='SilentlyContinue'; $ErrorActionPreference='Stop'; " + script)
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    result = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", host,
         "powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
        text=True, capture_output=True, timeout=90,
    )
    if result.returncode:
        raise RuntimeError("Windows command failed:\n" + result.stdout + result.stderr)
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.environ.get("SYSTEM_PULSE_WINDOWS_HOST"))
    parser.add_argument("--build-log", type=Path, required=True,
                        help="Output retained by the successful Cairn REL-001 build")
    args = parser.parse_args()
    require(bool(args.host) and not args.host.startswith("-"), "set the Windows SSH host")
    build = args.build_log.read_text()
    revision = re.findall(r"PASS REL-001 ([a-f0-9]{40})", build)
    binary = re.findall(r"Hash\s*:\s*([a-fA-F0-9]{64})", build)
    require(len(revision) == len(binary) == 1, "expected one successful Windows build and binary")
    revision, binary = revision[0], binary[0].lower()
    same_production(revision)
    subprocess.run(["git", "diff", "--exit-code", "HEAD", "--", *PRODUCTION], cwd=ROOT, check=True)
    run_id = uuid.uuid4().hex
    task = "SystemPulse-Runtime-" + run_id
    parent = Path(tempfile.mkdtemp(prefix="system-pulse-native-windows-"))
    script_path = parent / (task + ".ps1")
    harness = ROOT / "scripts/system-pulse/windows_runtime.ps1"
    prelude = (f"$RunId='{run_id}'\n$SourceCommit='{revision}'\n"
               f"$ExpectedBinarySha256='{binary}'\n"
               f"$OutputDirectory=Join-Path $env:USERPROFILE 'workspace\\{task}'\n")
    script_path.write_text(prelude + harness.read_text(), encoding="utf-8-sig")
    subprocess.run(["scp", "-O", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
                    str(script_path), f"{args.host}:{script_path.name}"], check=True, timeout=90)
    setup = r"""
$action=New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "'+(Join-Path $env:USERPROFILE '__TASK__.ps1')+'"')
$principal=New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
$settings=New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 8)
Register-ScheduledTask -TaskName '__TASK__' -Action $action -Principal $principal -Settings $settings | Out-Null
Start-ScheduledTask -TaskName '__TASK__'
""".replace("__TASK__", task)
    remote(args.host, setup)
    print(f"Native Windows run {run_id}; evidence will be in {parent / task}", flush=True)
    deadline = time.monotonic() + 9 * 60
    completed = False
    try:
        while time.monotonic() < deadline:
            time.sleep(5)
            state = json.loads(remote(args.host, (
                f"$t=Get-ScheduledTask -TaskName '{task}'; "
                f"$i=Get-ScheduledTaskInfo -TaskName '{task}'; "
                "@{state=[string]$t.State;result=$i.LastTaskResult;"
                "started=$i.LastRunTime.Year -ge 2026}|ConvertTo-Json -Compress")))
            if state["started"] and state["state"] != "Running":
                completed = True
                break
        require(completed, "Windows runtime task timed out; inspect its retained task and output")
        subprocess.run(["scp", "-O", "-r", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
                        f"{args.host}:workspace/{task}", str(parent / task)], check=True, timeout=120)
        require(state["result"] == 0, f"Windows runtime failed; inspect {parent / task}")
        evidence = parent / task
        result = json.loads((evidence / "result.json").read_text(encoding="utf-8-sig"))
        require(result["run_id"] == run_id and result["status"] == "PASS", "wrong runtime receipt")
        result["harness_sha256"] = {
            name: hashlib.sha256((ROOT / "scripts/system-pulse" / name).read_bytes()).hexdigest()
            for name in ("windows_runtime.ps1", "windows_runtime_collect.py")
        }
        result["build_log_sha256"] = hashlib.sha256(args.build_log.read_bytes()).hexdigest()
        result["artifacts_sha256"] = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(evidence.iterdir()) if path.is_file() and path.name != "result.json"
        }
        (evidence / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(f"Collected native observations: {evidence}", flush=True)
        print("Review the screenshots and run windows_runtime_verify.py before recording acceptance.")
    finally:
        if completed:
            remote(args.host, f"Unregister-ScheduledTask -TaskName '{task}' -Confirm:$false; "
                             f"Remove-Item (Join-Path $env:USERPROFILE '{task}.ps1')")


if __name__ == "__main__":
    main()
