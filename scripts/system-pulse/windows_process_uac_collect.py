"""Collect one human-operated Windows UAC case from the shipped package."""

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
from windows_process_actions_collect import ORDINARY_CASES, build_identity, deploy_package
from windows_runtime_collect import remote


CASES = {
    "ordinary": dict(operator_action="No UAC prompt is expected"),
    "consent-force": dict(mode="windowless", signal="kill", expected_exit=True,
                          expected_status="has exited", operator_action="Approve"),
    "consent-graceful": dict(mode="cooperative", signal="terminate", expected_exit=True,
                             expected_status="has exited", operator_action="Approve"),
    "consent-refused": dict(mode="refusing", signal="terminate", expected_exit=False,
                            expected_status="application did not close", operator_action="Approve"),
    "consent-cancel": dict(mode="windowless", signal="kill", expected_exit=False,
                           expected_status="authorization was cancelled", operator_action="Cancel"),
    "consent-stale": dict(mode="windowless", signal="kill", expected_exit=True,
                          expected_status="already exited", operator_action="Wait for the observer's target-exited cue, then approve",
                          fault="target-exit-during-consent"),
    "consent-delayed": dict(mode="delayed", signal="terminate", expected_exit=False,
                            expected_status="application did not close", operator_action="Approve",
                            verify_responsive=True),
}
HARNESS_FILES = (
    "windows_process_uac_collect.py", "windows_process_uac_supervise.ps1",
    "windows_process_trace.cs", "windows_process_actions.ps1", "windows_process_fixture.cs",
    "windows_process_actions_collect.py", "windows_runtime_collect.py",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.environ.get("SYSTEM_PULSE_WINDOWS_HOST"))
    parser.add_argument("--build-log", type=Path, required=True)
    parser.add_argument("--package-dir", type=Path, required=True)
    parser.add_argument("--case", choices=CASES, required=True)
    parser.add_argument("--operator-ready", action="store_true",
                        help="The human is at the Windows desktop and knows this case's action")
    args = parser.parse_args()
    require(args.case == "ordinary" or args.operator_ready,
            "Arrange the actual Windows prompt response before starting")
    require(bool(args.host) and not args.host.startswith("-"), "set the Windows SSH host")
    revision, binary_hash = build_identity(args.build_log.read_text(errors="replace"))
    same_production(revision)
    package = verify_archive(args.package_dir, "x86_64-pc-windows-msvc", revision)
    archive = args.package_dir / package["archive"]
    require(hashlib.sha256(archive_files(archive)["system-pulse.exe"]).hexdigest() == binary_hash,
            "packaged executable differs from the passing native build")
    inputs = [*PRODUCTION, *("scripts/system-pulse/" + name for name in HARNESS_FILES)]
    subprocess.run(["git", "diff", "--exit-code", "HEAD", "--", *inputs], cwd=ROOT, check=True)
    subprocess.run(["git", "ls-files", "--error-unmatch", *inputs[len(PRODUCTION):]],
                   cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    harness_hashes = {name: hashlib.sha256((ROOT / "scripts/system-pulse" / name).read_bytes()).hexdigest()
                      for name in HARNESS_FILES}
    task = "SystemPulse-UAC-" + uuid.uuid4().hex
    cache = Path(tempfile.mkdtemp(prefix="system-pulse-windows-uac-"))
    parent, binary = deploy_package(args.host, task, archive, package)
    config = dict(
        ui_task=task + "-UI", ui_configuration=parent + "\\ui.json",
        trace_source=parent + "\\windows_process_trace.cs",
        target_log=parent + "\\elevated-target.log", observer_result=parent + "\\observer.json",
        ordinary_baseline=args.case == "ordinary",
        ui=dict(output=parent + "\\evidence", binary=binary, fixture=parent + "\\owned-fixture.exe",
                source_commit=revision, binary_sha256=binary_hash, uac_observation=True,
                cases=ORDINARY_CASES if args.case == "ordinary" else [dict(name=args.case, **CASES[args.case])]),
    )
    (cache / "supervisor.json").write_text(json.dumps(config, indent=2), encoding="utf-8-sig")
    sources = ["windows_process_uac_supervise.ps1", "windows_process_trace.cs",
               "windows_process_actions.ps1", "windows_process_fixture.cs"]
    for name in sources:
        (cache / name).write_text((ROOT / "scripts/system-pulse" / name).read_text(), encoding="utf-8-sig")
    for name in ["supervisor.json", *sources]:
        subprocess.run(["scp", "-O", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
                        str(cache / name), f"{args.host}:workspace/{task}/{name}"], check=True, timeout=90)
    setup = r'''
$parent=Join-Path $env:USERPROFILE 'workspace\__TASK__'
$account=[Security.Principal.WindowsIdentity]::GetCurrent().Name
& "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe" /nologo /target:winexe /reference:System.Windows.Forms.dll ("/out:"+(Join-Path $parent 'owned-fixture.exe')) (Join-Path $parent 'windows_process_fixture.cs')
if($LASTEXITCODE -ne 0){throw 'Owned fixture compilation failed'}
$settings=New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 6)
foreach($entry in @(
    @{suffix='-UI';script='windows_process_actions.ps1';config='ui.json';level='Limited'},
    @{suffix='';script='windows_process_uac_supervise.ps1';config='supervisor.json';level='Highest'}
)) {
    $action=New-ScheduledTaskAction -Execute "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" -Argument ('-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "'+(Join-Path $parent $entry.script)+'" -Configuration "'+(Join-Path $parent $entry.config)+'"')
    $principal=New-ScheduledTaskPrincipal -UserId $account -LogonType Interactive -RunLevel $entry.level
    Register-ScheduledTask -TaskName ('__TASK__'+$entry.suffix) -Action $action -Principal $principal -Settings $settings|Out-Null
}
Start-ScheduledTask -TaskName '__TASK__'
'''.replace("__TASK__", task)
    print(f"Case {args.case}: {CASES[args.case]['operator_action']}. Evidence: {cache}", flush=True)
    remote(args.host, setup)
    completed = False
    cue_shown = False
    deadline = time.monotonic() + 5 * 60
    try:
        while time.monotonic() < deadline:
            time.sleep(2)
            state = json.loads(remote(args.host,
                f"$t=Get-ScheduledTask -TaskName '{task}';$i=Get-ScheduledTaskInfo -TaskName '{task}';"
                f"$path=Join-Path $env:USERPROFILE 'workspace\\{task}\\observer.json';"
                "$fault=$false;if(Test-Path $path){try{$fault=[bool](Get-Content -Raw $path|ConvertFrom-Json).fault_applied}catch{}};"
                "@{state=[string]$t.State;result=$i.LastTaskResult;started=$i.LastRunTime.Year -ge 2026;fault=$fault}|ConvertTo-Json -Compress"))
            if state["fault"] and not cue_shown:
                print("Owned target has exited. Approve the waiting Windows prompt now.", flush=True)
                cue_shown = True
            if state["started"] and state["state"] != "Running":
                completed = True
                break
        require(completed, f"Native supervisor timed out; inspect retained task {task}")
        artifacts = ["observer.json", "evidence"]
        if args.case != "ordinary":
            artifacts.append("elevated-target.log")
        for name in artifacts:
            subprocess.run(["scp", "-O", "-r", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
                            f"{args.host}:workspace/{task}/{name}", str(cache / name)], check=True, timeout=120)
        observer = json.loads((cache / "observer.json").read_text(encoding="utf-8-sig"))
        require(state["result"] == 0 and observer.get("status") == "COLLECTED",
                f"Native UAC observation failed; inspect {cache}")
        require(harness_hashes == {name: hashlib.sha256((ROOT / "scripts/system-pulse" / name).read_bytes()).hexdigest()
                                  for name in HARNESS_FILES}, "harness changed during collection")
        receipt = dict(source_commit=revision, binary_sha256=binary_hash, package=package,
                       build_log_sha256=hashlib.sha256(args.build_log.read_bytes()).hexdigest(),
                       case=args.case, harness_sha256=harness_hashes,
                       artifacts_sha256={str(path.relative_to(cache)): hashlib.sha256(path.read_bytes()).hexdigest()
                                         for path in sorted(cache.rglob("*")) if path.is_file()})
        (cache / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        print(f"Collected native observation: {cache}; acceptance still requires independent verification", flush=True)
    finally:
        if completed:
            remote(args.host, f"foreach($name in @('{task}','{task}-UI')){{"
                   "$t=Get-ScheduledTask -TaskName $name;"
                   "if($t.State -ne 'Running'){Unregister-ScheduledTask -TaskName $name -Confirm:$false}}")


if __name__ == "__main__":
    main()
