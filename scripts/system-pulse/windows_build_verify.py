"""Build committed source on a Windows SSH host; retain logs outside the checkout."""

import base64
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import uuid


def main():
    host = os.environ.get("SYSTEM_PULSE_WINDOWS_HOST")
    if not host or host.startswith("-"):
        raise SystemExit("Set SYSTEM_PULSE_WINDOWS_HOST to the Windows SSH destination")
    root = Path(__file__).resolve().parents[2]
    subprocess.run(["git", "diff", "--exit-code", "HEAD"], cwd=root, check=True)
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()
    evidence = Path(tempfile.mkdtemp(prefix="system-pulse-windows-"))
    archive = evidence / "source.tar.gz"
    subprocess.run(
        ["git", "archive", "--format=tar.gz", f"--output={archive}", revision],
        cwd=root, check=True,
    )
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    token = f"system-pulse-{revision[:12]}-{uuid.uuid4().hex[:8]}"
    # Windows OpenSSH installations may expose SCP before configuring SFTP.
    subprocess.run(
        ["scp", "-O", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
         str(archive), f"{host}:{token}.tar.gz"], check=True, timeout=300,
    )
    script = r"""
$ErrorActionPreference = 'Stop'
$env:PATH = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
$archive = Join-Path $env:USERPROFILE '__TOKEN__.tar.gz'
if ((Get-FileHash $archive -Algorithm SHA256).Hash.ToLower() -ne '__DIGEST__') { throw 'Source archive hash mismatch' }
$source = Join-Path $env:USERPROFILE 'workspace\__TOKEN__'
New-Item -ItemType Directory -Path $source -ErrorAction Stop | Out-Null
& tar -xzf $archive -C $source
if ($LASTEXITCODE -ne 0) { throw 'Source extraction failed' }
Set-Location $source
$env:CARGO_TARGET_DIR = Join-Path $env:USERPROFILE 'workspace\system-pulse-build-target'
$env:CARGO_BUILD_JOBS = '2'
$lockHash = (Get-FileHash Cargo.lock -Algorithm SHA256).Hash
Write-Output 'Source commit: __REVISION__'
Write-Output "Source directory: $source"
foreach ($tool in @('git','cmake','rustc','cargo')) {
    & $tool --version
    if ($LASTEXITCODE -ne 0) { throw "Prerequisite failed: $tool" }
}
& cargo test --locked -p system-pulse-model -p system-pulse-collectors -p system-pulse
if ($LASTEXITCODE -ne 0) { throw 'Windows tests failed' }
& cargo build --release --locked -p system-pulse
if ($LASTEXITCODE -ne 0) { throw 'Windows release build failed' }
if ((Get-FileHash Cargo.lock -Algorithm SHA256).Hash -ne $lockHash) { throw 'Lockfile changed during verification' }
$binary = Join-Path $env:CARGO_TARGET_DIR 'release\system-pulse.exe'
Get-FileHash $binary -Algorithm SHA256 | Format-List
Write-Output 'PASS REL-001 __REVISION__'
"""
    script = script.replace("__TOKEN__", token).replace("__DIGEST__", digest)
    script = script.replace("__REVISION__", revision)
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    (evidence / "remote.ps1").write_text(script)
    log = evidence / "build.log"
    print(f"Windows build evidence: {evidence}", flush=True)
    with log.open("w") as output:
        result = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", host,
             "powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
            stdout=output, stderr=subprocess.STDOUT, timeout=8 * 60 * 60,
        )
    contents = log.read_text(errors="replace")
    print("\n".join(contents.splitlines()[-35:]))
    if result.returncode or f"PASS REL-001 {revision}" not in contents:
        raise SystemExit(f"Windows verification failed; inspect {log}")


if __name__ == "__main__":
    main()
