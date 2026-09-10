# Native regression test for short-lived helper trace capture. No UAC is invoked.
param(
    [Parameter(Mandatory=$true)][string]$Binary,
    [Parameter(Mandatory=$true)][string]$TraceSource,
    [Parameter(Mandatory=$true)][string]$Output
)
$ErrorActionPreference='Stop'
Add-Type -Path $TraceSource -ReferencedAssemblies System.Management
$result=@{status='FAIL';owned=@();events=@()}
$trace=$null
$owned=New-Object Collections.Generic.List[System.Diagnostics.Process]
try {
    $trace=[PulseProcessTrace]::new()
    for($index=0;$index -lt 6;$index++) {
        $process=Start-Process -FilePath $Binary -ArgumentList '--system-pulse-windows-process-action' -PassThru
        $owned.Add($process)
        $null=$process.Handle
        if(!$process.WaitForExit(5000)){throw 'Malformed helper did not exit'}
        $result.owned+=@{pid=$process.Id;creation_ticks=[PulseProcessTrace]::Creation($process.Handle);exit_code=$process.ExitCode}
        if($process.ExitCode -ne 29){throw 'Malformed helper was accepted'}
    }
    $deadline=(Get-Date).AddSeconds(10)
    do {
        Start-Sleep -Milliseconds 100
        $events=@($trace.Snapshot())
        $complete=$true
        foreach($process in $owned) {
            $starts=@($events|Where-Object {$_.pid -eq $process.Id -and $_.kind -eq 'start'})
            $stops=@($events|Where-Object {$_.pid -eq $process.Id -and $_.kind -eq 'stop'})
            if($starts.Count -ne 1 -or $stops.Count -ne 1 -or $stops[0].exit_code -ne 29){$complete=$false}
        }
    } while(!$complete -and (Get-Date) -lt $deadline)
    if(!$complete){throw 'Trace missed or duplicated an owned helper lifecycle'}
    if(@($events|Where-Object {$_.observation_error -or $_.token_close_failed -or $_.process_close_failed}).Count){throw 'Native trace observation or handle cleanup failed'}
    $result.status='PASS'
} catch {$result.error=$_.Exception.ToString()}
finally {
    foreach($process in $owned) {
        try {
            if(!$process.HasExited){$process.Kill()}
            if(!$process.WaitForExit(5000)){throw 'Owned test helper survived cleanup'}
        } catch {$result.status='FAIL';$result.cleanup_error=$_.Exception.ToString()}
        finally {$process.Dispose()}
    }
    if($trace) {
        try {$trace.Dispose()}catch{$result.status='FAIL';$result.trace_cleanup_error=$_.Exception.ToString()}
        $result.events=@($trace.Snapshot())
    }
    $result|ConvertTo-Json -Depth 20|Set-Content -LiteralPath $Output -Encoding UTF8
}
if($result.status -ne 'PASS'){Write-Error $result.error;exit 1}
Write-Output 'PASS: six native malformed-helper start, stop and refusal observations'
