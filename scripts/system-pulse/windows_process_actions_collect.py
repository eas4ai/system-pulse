"""Collect ordinary Windows process actions from a committed native build.

This runner does not collect UAC consent or credential evidence. Those cases
require a human at the Windows desktop and remain separately pending.
"""

import argparse
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
from release_ci_verify import archive_files, verify_archive
from windows_runtime_collect import remote


ORDINARY_CASES = [
    dict(name="confirmation-cancel", mode="windowless", signal="kill",
         cancel_confirmation=True, expected_exit=False),
    dict(name="graceful-cooperative", mode="cooperative", signal="terminate",
         expected_exit=True, expected_status="has exited"),
    dict(name="graceful-refused", mode="refusing", signal="terminate",
         expected_exit=False, expected_status="application did not close"),
    dict(name="graceful-unavailable", mode="windowless", signal="terminate",
         expected_exit=False, expected_status="Graceful close is unavailable"),
    dict(name="ordinary-force", mode="windowless", signal="kill",
         expected_exit=True, expected_status="has exited"),
    dict(name="stale-before-confirm", mode="windowless", signal="kill",
         exit_before_confirm=True, expected_exit=True, expected_status="already exited"),
    dict(name="delayed-graceful", mode="delayed", signal="terminate",
         verify_responsive=True, expected_exit=False, expected_status="application did not close"),
]
HARNESS_FILES = ("windows_process_actions_collect.py", "windows_process_actions.ps1",
                 "windows_process_fixture.cs", "windows_runtime_collect.py")


def build_identity(contents):
    revisions = re.findall(r"PASS REL-001 ([a-f0-9]{40})", contents)
    hashes = re.findall(r"Hash\s*:\s*([a-fA-F0-9]{64})", contents)
    require(len(revisions) == len(hashes) == 1,
            "expected one passing native build and one binary hash")
    require("Embedded Windows manifest: asInvoker; uiAccess=false" in contents,
            "native build did not verify normal launch privileges")
    return revisions[0], hashes[0].lower()


def packaged_binary_hash(files, native_hash):
    actual = hashlib.sha256(files["system-pulse.exe"]).hexdigest()
    if actual != native_hash:
        build = json.loads(files.get("build.json", b"{}"))
        signing = build.get("authenticode", {})
        require(build.get("unsigned_binary_sha256") == native_hash
                and build.get("binary_sha256") == actual
                and signing.get("status") == "Valid"
                and re.fullmatch(r"[a-fA-F0-9]{40}", signing.get("thumbprint", "")),
                "signed package lacks its native build and signature provenance")
    return actual


def deploy_package(host, task, archive, package):
    require(re.fullmatch(r"SystemPulse-[A-Za-z]+-[a-f0-9]{32}", task) is not None, "invalid native run name")
    parent = json.loads(remote(host,
        "$path=Join-Path $env:USERPROFILE 'workspace\\" + task + "';"
        "New-Item -ItemType Directory $path -ErrorAction Stop|Out-Null;"
        "New-Item -ItemType Directory (Join-Path $path 'Packaged app ü')|Out-Null;"
        "$path|ConvertTo-Json -Compress"))
    subprocess.run(["scp", "-O", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
                    str(archive), f"{host}:workspace/{task}/package.zip"], check=True, timeout=300)
    binary_path = json.loads(remote(host,
        "$parent=Join-Path $env:USERPROFILE 'workspace\\" + task + "';"
        "$archive=Join-Path $parent 'package.zip';"
        f"if((Get-FileHash $archive -Algorithm SHA256).Hash.ToLower() -ne '{package['sha256']}')"
        "{throw 'Transferred package checksum differs'};"
        "Expand-Archive -LiteralPath $archive -DestinationPath (Join-Path $parent 'Packaged app ü');"
        "$binaries=@(Get-ChildItem (Join-Path $parent 'Packaged app ü') -Recurse -File -Filter 'system-pulse.exe');"
        "if($binaries.Count -ne 1){throw 'Packaged executable is absent or ambiguous'};"
        "$binaries[0].FullName|ConvertTo-Json -Compress"))
    return parent, binary_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.environ.get("SYSTEM_PULSE_WINDOWS_HOST"))
    parser.add_argument("--build-log", type=Path, required=True)
    parser.add_argument("--package-dir", type=Path, required=True,
                        help="Locally built Windows ZIP and its SHA256SUMS")
    args = parser.parse_args()
    require(bool(args.host) and not args.host.startswith("-"), "set the Windows SSH host")
    revision, binary_hash = build_identity(args.build_log.read_text(errors="replace"))
    same_production(revision)
    package = verify_archive(args.package_dir, "x86_64-pc-windows-msvc", revision)
    archive = args.package_dir / package["archive"]
    native_hash = binary_hash
    files = archive_files(archive)
    binary_hash = packaged_binary_hash(files, native_hash)
    inputs = [*PRODUCTION, *("scripts/system-pulse/" + name for name in HARNESS_FILES)]
    subprocess.run(["git", "diff", "--exit-code", "HEAD", "--", *inputs],
                   cwd=ROOT, check=True)
    for name in HARNESS_FILES:
        subprocess.run(["git", "ls-files", "--error-unmatch", "scripts/system-pulse/" + name],
                       cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    harness_hashes = {
        name: hashlib.sha256((ROOT / "scripts/system-pulse" / name).read_bytes()).hexdigest()
        for name in HARNESS_FILES
    }
    task = "SystemPulse-Actions-" + uuid.uuid4().hex
    cache = Path(tempfile.mkdtemp(prefix="system-pulse-windows-actions-"))
    parent, binary_path = deploy_package(args.host, task, archive, package)
    if binary_hash != native_hash:
        escaped = binary_path.replace("'", "''")
        observed = json.loads(remote(args.host, "$s=Get-AuthenticodeSignature '" + escaped +
            "';@{status=$s.Status.ToString();thumbprint=$s.SignerCertificate.Thumbprint}|ConvertTo-Json -Compress"))
        signing = json.loads(files["build.json"])["authenticode"]
        require(observed.get("status") == "Valid"
                and observed.get("thumbprint", "").lower() == signing["thumbprint"].lower(),
                "transferred signed application did not verify against its recorded signer")

    config = dict(output=parent + "\\evidence", binary=binary_path,
                  fixture=parent + "\\owned-fixture.exe", source_commit=revision,
                  binary_sha256=binary_hash, cases=ORDINARY_CASES)
    (cache / "configuration.json").write_text(json.dumps(config, indent=2), encoding="utf-8-sig")
    for local, source in (("actions.ps1", "windows_process_actions.ps1"),
                          ("fixture.cs", "windows_process_fixture.cs")):
        (cache / local).write_text((ROOT / "scripts/system-pulse" / source).read_text(),
                                   encoding="utf-8-sig")
    for name in ("configuration.json", "actions.ps1", "fixture.cs"):
        subprocess.run(["scp", "-O", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
                        str(cache / name), f"{args.host}:workspace/{task}/{name}"],
                       check=True, timeout=90)
    setup = r'''
$parent=Join-Path $env:USERPROFILE 'workspace\__TASK__'
& "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe" /nologo /target:winexe /reference:System.Windows.Forms.dll ("/out:"+(Join-Path $parent 'owned-fixture.exe')) (Join-Path $parent 'fixture.cs')
if($LASTEXITCODE -ne 0){throw 'Owned fixture compilation failed'}
$action=New-ScheduledTaskAction -Execute "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" -Argument ('-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "'+(Join-Path $parent 'actions.ps1')+'" -Configuration "'+(Join-Path $parent 'configuration.json')+'"')
$principal=New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
$settings=New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 8)
Register-ScheduledTask -TaskName '__TASK__' -Action $action -Principal $principal -Settings $settings|Out-Null
Start-ScheduledTask -TaskName '__TASK__'
'''.replace("__TASK__", task)
    remote(args.host, setup)
    print(f"Native ordinary action run: {task}; evidence: {cache / 'evidence'}", flush=True)
    completed = False
    deadline = time.monotonic() + 9 * 60
    try:
        while time.monotonic() < deadline:
            time.sleep(5)
            state = json.loads(remote(args.host,
                f"$t=Get-ScheduledTask -TaskName '{task}';"
                f"$i=Get-ScheduledTaskInfo -TaskName '{task}';"
                "@{state=[string]$t.State;result=$i.LastTaskResult;"
                "started=$i.LastRunTime.Year -ge 2026}|ConvertTo-Json -Compress"))
            if state["started"] and state["state"] != "Running":
                completed = True
                break
        require(completed, f"Native task timed out; inspect retained task {task}")
        evidence = cache / "evidence"
        subprocess.run(["scp", "-O", "-r", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
                        f"{args.host}:workspace/{task}/evidence", str(evidence)],
                       check=True, timeout=120)
        record = json.loads((evidence / "result.json").read_text(encoding="utf-8-sig"))
        require(state["result"] == 0 and record.get("status") == "PASS",
                f"Native actions failed; inspect {evidence}")
        require(record.get("source_commit") == revision and record.get("binary_sha256") == binary_hash,
                "native receipt does not match the requested build")
        current_hashes = {
            name: hashlib.sha256((ROOT / "scripts/system-pulse" / name).read_bytes()).hexdigest()
            for name in HARNESS_FILES
        }
        require(current_hashes == harness_hashes, "harness changed during native collection")
        record["harness_sha256"] = harness_hashes
        record["package"] = package
        record["build_log_sha256"] = hashlib.sha256(args.build_log.read_bytes()).hexdigest()
        record["artifacts_sha256"] = {
            str(path.relative_to(evidence)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(evidence.rglob("*")) if path.is_file() and path != evidence / "result.json"
        }
        (evidence / "result.json").write_text(json.dumps(record, indent=2) + "\n")
        print(f"Collected ordinary action observations: {evidence}", flush=True)
    finally:
        if completed:
            remote(args.host, f"Unregister-ScheduledTask -TaskName '{task}' -Confirm:$false")


if __name__ == "__main__":
    main()
