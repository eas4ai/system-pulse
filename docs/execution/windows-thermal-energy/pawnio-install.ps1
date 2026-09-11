
$p='C:\Users\shawn\workspace\PawnIO_setup-2.2.0-review.exe'
$sha=(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant()
$s=Get-AuthenticodeSignature -LiteralPath $p
if($sha -ne '1f519a22e47187f70a1379a48ca604981c4fcf694f4e65b734aaa74a9fba3032' -or $s.Status -ne 'Valid'){throw 'Installer provenance failed'}
$process=Start-Process -FilePath $p -ArgumentList '-install','-silent' -PassThru
if(!$process.WaitForExit(60000)){throw 'PawnIO installer still running after 60 seconds'}
$r=[ordered]@{observed_utc=[DateTime]::UtcNow.ToString('o');installer_sha256=$sha;exit_code=$process.ExitCode}
$r['installed']=Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\PawnIO' | Select-Object DisplayName,DisplayVersion,InstallLocation
$r['driver']=Get-CimInstance Win32_SystemDriver -Filter "Name='PawnIO'" | Select-Object Name,State,StartMode,PathName
$r | ConvertTo-Json -Depth 4
