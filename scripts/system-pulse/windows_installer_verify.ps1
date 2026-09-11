param(
    [Parameter(Mandatory=$true)][string]$Installer,
    [Parameter(Mandatory=$true)][string]$ExpectedInstallerSha256,
    [Parameter(Mandatory=$true)][string]$ExpectedBinarySha256,
    [Parameter(Mandatory=$true)][string]$OutputDirectory
)
$ErrorActionPreference='Stop'
$principal=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if(!$principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Installer lifecycle verification requires an authorized elevated test session'}
$applicationKey='HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{82C76189-3134-4B89-A742-5CBAA4388645}_is1'
if(Test-Path $applicationKey){throw 'An existing System Pulse installation must not be replaced by this test'}
if((Get-FileHash $Installer -Algorithm SHA256).Hash -ne $ExpectedInstallerSha256){throw 'Installer hash mismatch'}
$signature=Get-AuthenticodeSignature $Installer
if($signature.Status -ne 'Valid'){throw 'Installer signature is invalid'}
New-Item -ItemType Directory -Path $OutputDirectory -ErrorAction Stop|Out-Null
$installPath=Join-Path $env:ProgramFiles ('SystemPulse-InstallerCheck-'+[guid]::NewGuid().ToString('N'))
$pawnKey='HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\PawnIO'
function PawnState {
    if(!(Test-Path $pawnKey)){return $null}
    $entry=Get-ItemProperty $pawnKey
    $driver=Get-CimInstance Win32_SystemDriver -Filter "Name='PawnIO'"
    return [ordered]@{version=$entry.DisplayVersion;location=$entry.InstallLocation;driver_path=$driver.PathName;start_mode=$driver.StartMode;state=$driver.State}
}
function Run-Setup($tasks,$name) {
    $arguments=@('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',('/DIR="'+$installPath+'"'),('/TASKS="'+$tasks+'"'),('/LOG="'+(Join-Path $OutputDirectory ($name+'.log'))+'"'))
    $process=Start-Process -FilePath $Installer -ArgumentList $arguments -PassThru
    if(!$process.WaitForExit(180000)){throw 'Installer did not exit within three minutes; inspect the test installation before cleanup'}
    if($process.ExitCode -ne 0){throw "Installer exited $($process.ExitCode)"}
    return $process.ExitCode
}
$before=PawnState
if($null -eq $before){throw 'This shared-driver preservation case requires the already approved PawnIO installation'}
$first=Run-Setup '' 'install'
$binary=Join-Path $installPath 'system-pulse.exe'
if((Get-FileHash $binary -Algorithm SHA256).Hash -ne $ExpectedBinarySha256){throw 'Installed application differs from signed package'}
$binarySignature=Get-AuthenticodeSignature $binary
if($binarySignature.Status -ne 'Valid'){throw 'Installed application signature invalid'}
$uninstaller=Join-Path $installPath 'unins000.exe'
$uninstallSignature=Get-AuthenticodeSignature $uninstaller
if($uninstallSignature.Status -ne 'Valid'){throw 'Uninstaller signature invalid'}
if(!(Test-Path (Join-Path $installPath 'source.tar.gz'))){throw 'Installed source archive missing'}
$second=Run-Setup 'cputemperature' 'existing-driver-install'
$afterInstall=PawnState
if((ConvertTo-Json -Compress $before) -ne (ConvertTo-Json -Compress $afterInstall)){throw 'Installer changed existing shared PawnIO state'}
$uninstall=Start-Process -FilePath $uninstaller -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',('/LOG="'+(Join-Path $OutputDirectory 'uninstall.log')+'"')) -PassThru
if(!$uninstall.WaitForExit(180000)){throw 'Uninstaller did not exit within three minutes'}
if($uninstall.ExitCode -ne 0){throw "Uninstaller exited $($uninstall.ExitCode)"}
# Inno may finish deleting its executable just after its original process exits.
foreach($attempt in 1..20){if(!(Test-Path $installPath)){break};Start-Sleep -Milliseconds 250}
if(Test-Path $installPath){throw 'Owned installation directory remains after uninstall'}
if(Test-Path $applicationKey){throw 'Application uninstall registration remains'}
$afterUninstall=PawnState
if((ConvertTo-Json -Compress $before) -ne (ConvertTo-Json -Compress $afterUninstall)){throw 'Uninstall changed shared PawnIO state'}
@{status='PASS';installer_sha256=$ExpectedInstallerSha256;binary_sha256=$ExpectedBinarySha256;
  installer_signer=$signature.SignerCertificate.Subject;application_signer=$binarySignature.SignerCertificate.Subject;
  uninstaller_signer=$uninstallSignature.SignerCertificate.Subject;install_exit=$first;existing_driver_install_exit=$second;
  uninstall_exit=$uninstall.ExitCode;owned_directory_removed=$true;shared_driver_before=$before;
  shared_driver_after=$afterUninstall;scope='Install, reinstall with existing PawnIO, and uninstall; fresh driver prerequisite branch is separate'} |
  ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 (Join-Path $OutputDirectory 'result.json')
