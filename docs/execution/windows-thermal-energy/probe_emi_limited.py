
from pathlib import Path
import sys,base64,uuid
sys.path.insert(0,'scripts/system-pulse')
from windows_runtime_collect import remote
p=Path('docs/execution/windows-thermal-energy')
task='SystemPulse-EmiProbe-'+uuid.uuid4().hex[:12]
body="& {\n"+(p/'emi-probe.ps1').read_text()+"\n} | Out-File -Encoding utf8 ($PSCommandPath + '.json')\n"
encoded=base64.b64encode(body.encode()).decode()
script=r"""
$task='TASK'
$path=Join-Path $env:TEMP ($task+'.ps1')
[IO.File]::WriteAllBytes($path,[Convert]::FromBase64String('ENCODED'))
$action=New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -ExecutionPolicy Bypass -File "'+$path+'"')
$principal=New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $task -Action $action -Principal $principal -Settings (New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Seconds 45)) -Force | Out-Null
try {
 Start-ScheduledTask -TaskName $task
 for($i=0;$i -lt 20;$i++){
  Start-Sleep -Seconds 2
  if((Test-Path ($path+'.json')) -and (Get-ScheduledTask -TaskName $task).State -ne 'Running'){break}
 }
 if((Get-ScheduledTask -TaskName $task).State -eq 'Running'){throw 'Probe still running'}
 Get-Content -Raw ($path+'.json')
} finally {
 Stop-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue
 Unregister-ScheduledTask -TaskName $task -Confirm:$false
}
""".replace('TASK',task).replace('ENCODED',encoded)
out=remote('shawn@10.66.231.23',script)
(p/'emi-unelevated.json').write_text(out)
print(out)
