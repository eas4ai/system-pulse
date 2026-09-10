# Real native fault and cleanup tests on newly created disposable processes only.
param(
    [Parameter(Mandatory=$true)][string]$Fixture,
    [Parameter(Mandatory=$true)][string]$FaultSource,
    [Parameter(Mandatory=$true)][string]$Output
)
$ErrorActionPreference='Stop'
Add-Type -Path $FaultSource
[PulseOwnedProcessFault]::RemoveObserverDebugPrivilege()
$result=@{status='FAIL';owned=@();checks=@()}
$result.observer_debug_privilege_removed=$true
$owned=New-Object Collections.Generic.List[System.Diagnostics.Process]
$guards=New-Object Collections.Generic.List[PulseOwnedProcessFault]
$directory=Split-Path -Parent $Output
try {
    $self=[Diagnostics.Process]::GetCurrentProcess()
    $refused=$false
    try {[PulseOwnedProcessFault]::new($self)|Out-Null}
    catch {if($_.Exception.ToString() -notmatch 'Cannot fault the observer'){throw};$refused=$true}
    finally {$self.Dispose()}
    if(!$refused){throw 'Fault helper accepted its own observer'}
    $result.checks+='observer-refused'
    $control=Start-Process $Fixture -ArgumentList @('windowless',('"'+(Join-Path $directory 'fault-control.log')+'"')) -PassThru
    $owned.Add($control);$null=$control.Handle
    $denial=Start-Process $Fixture -ArgumentList @('windowless',('"'+(Join-Path $directory 'fault-denial.log')+'"')) -PassThru
    $owned.Add($denial);$null=$denial.Handle
    $denied=[PulseOwnedProcessFault]::new($denial);$guards.Add($denied)
    if($denied.NewTerminationAccessError() -ne 0){throw 'Fresh owned fixture was already inaccessible'}
    $denied.DenyNewTerminationHandles()
    if($denied.NewTerminationAccessError() -ne 5){throw 'Owned DACL did not deny new termination handles'}
    $denied.Crash()
    if(!$denial.WaitForExit(5000) -or [uint32]([int64]$denial.ExitCode -band 0xffffffffL) -ne 0xC0000001L){throw 'Pinned fault handle did not terminate the denied fixture'}
    $result.checks+='access-denied-and-pinned-crash'
    $heartbeatLog=Join-Path $directory 'fault-heartbeat.log'
    $heartbeat=Start-Process $Fixture -ArgumentList @('heartbeat',('"'+$heartbeatLog+'"')) -PassThru
    $owned.Add($heartbeat);$null=$heartbeat.Handle
    $suspended=[PulseOwnedProcessFault]::new($heartbeat);$guards.Add($suspended)
    $deadline=(Get-Date).AddSeconds(5)
    do {Start-Sleep -Milliseconds 100}while((!(Test-Path $heartbeatLog) -or (Get-Item $heartbeatLog).Length -lt 20) -and (Get-Date) -lt $deadline)
    if(!(Test-Path $heartbeatLog) -or (Get-Item $heartbeatLog).Length -lt 20){throw 'Owned heartbeat fixture did not start'}
    $result.suspended_threads=$suspended.Suspend()
    $before=(Get-Item $heartbeatLog).Length
    Start-Sleep -Milliseconds 500
    if((Get-Item $heartbeatLog).Length -ne $before){throw 'Owned fixture continued writing while suspended'}
    $suspended.Resume()
    $deadline=(Get-Date).AddSeconds(5)
    do {Start-Sleep -Milliseconds 100}while((Get-Item $heartbeatLog).Length -le $before -and (Get-Date) -lt $deadline)
    if((Get-Item $heartbeatLog).Length -le $before){throw 'Owned heartbeat did not resume'}
    $result.checks+='suspend-and-resume-observed-heartbeat'
    $null=$suspended.Suspend()
    $suspended.Dispose()
    if(!$heartbeat.WaitForExit(5000)){throw 'Suspended owned fixture survived job closure'}
    $result.checks+='job-cleans-suspended-process'
    if($control.HasExited -or [IO.File]::ReadAllText((Join-Path $directory 'fault-control.log')) -ne "ready`n"){throw 'Unrelated control was changed'}
    $result.checks+='unrelated-control-unchanged'
    $result.status='PASS'
} catch {$result.error=$_.Exception.ToString()}
finally {
    foreach($guard in $guards) {
        try {$guard.Dispose()}catch{$result.status='FAIL';$result.cleanup_error=$_.Exception.ToString()}
    }
    foreach($process in $owned) {
        try {
            if(!$process.HasExited){$process.Kill()}
            $result.owned+=@{pid=$process.Id;exited=$process.WaitForExit(5000)}
            if(!$result.owned[-1].exited){throw 'Owned fixture survived final cleanup'}
        } catch {$result.status='FAIL';$result.cleanup_error=$_.Exception.ToString()}
        finally {$process.Dispose()}
    }
    $result|ConvertTo-Json -Depth 20|Set-Content -LiteralPath $Output -Encoding UTF8
}
if($result.status -ne 'PASS'){Write-Error $result.error;exit 1}
Write-Output 'PASS: native access denial, pinned crash, suspend/resume, job cleanup and unrelated-control checks'
