# One bounded native observation, run elevated by the test setup. Only the
# dashboard invokes runas. The operator answers that actual Windows UAC prompt.
param([Parameter(Mandatory=$true)][string]$Configuration)
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$config=Get-Content -Raw -Encoding UTF8 -LiteralPath $Configuration|ConvertFrom-Json
Add-Type -Path $config.trace_source -ReferencedAssemblies System.Management
$record=@{status='FAIL';started_utc=(Get-Date).ToUniversalTime().ToString('o');events=@()}
$trace=$null
$target=$null
$startedUi=$false

function Save-Supervision {
    $record|ConvertTo-Json -Depth 30|Set-Content -LiteralPath $config.observer_result -Encoding UTF8
}
function Read-UiRecord($name) {
    $path=Join-Path $config.ui.output $name
    if(!(Test-Path -LiteralPath $path)){return $null}
    # UI publication can overlap a read. Retry only incomplete JSON, never use
    # partially parsed fields as an instruction to the privileged supervisor.
    for($attempt=0;$attempt -lt 5;$attempt++) {
        try {return Get-Content -Raw -Encoding UTF8 -LiteralPath $path|ConvertFrom-Json}
        catch [System.ArgumentException] {Start-Sleep -Milliseconds 50}
    }
    throw "Incomplete UI observation: $name"
}

try {
    $self=[Diagnostics.Process]::GetCurrentProcess()
    try {
        if(![PulseProcessTrace]::Elevated($self.Handle)){throw 'Native observer must run elevated'}
        $record.observer=@{pid=$self.Id;creation_ticks=[PulseProcessTrace]::Creation($self.Handle);elevated=$true}
    } finally {$self.Dispose()}
    if($config.ui_task -notmatch '^SystemPulse-UAC-[a-f0-9]{32}-UI$'){throw 'Unexpected UI task name'}
    if(!$config.ordinary_baseline -and @($config.ui.cases).Count -ne 1){throw 'UAC supervision requires exactly one case'}
    $case=$config.ui.cases[0]
    if($case.mode -notin @('cooperative','refusing','windowless','delayed') -or $case.signal -notin @('kill','terminate')){throw 'Invalid owned target action'}
    if($case.name -notmatch '^[a-z0-9-]+$'){throw 'Invalid case name'}
    if($case.fault -and $case.fault -ne 'target-exit-during-consent'){throw 'Unsupported observer fault'}
    if((Get-FileHash -LiteralPath $config.ui.binary -Algorithm SHA256).Hash.ToLower() -ne $config.ui.binary_sha256){throw 'Unexpected packaged binary'}
    if(@(Get-Process -Name system-pulse,consent -ErrorAction SilentlyContinue).Count){throw 'Another application or consent prompt prevents isolation'}
    $trace=[PulseProcessTrace]::new()
    if(!$config.ordinary_baseline) {
        $target=Start-Process -FilePath $config.ui.fixture -ArgumentList @($case.mode,('"'+$config.target_log+'"')) -PassThru
        $null=$target.Handle
        $record.target=@{pid=$target.Id;creation_ticks=[PulseProcessTrace]::Creation($target.Handle);elevated=[PulseProcessTrace]::Elevated($target.Handle);image=$config.ui.fixture}
        if(!$record.target.elevated){throw 'Disposable target did not start elevated'}
        $case|Add-Member -NotePropertyName target_pid -NotePropertyValue $target.Id -Force
        $case|Add-Member -NotePropertyName target_ticks -NotePropertyValue $record.target.creation_ticks -Force
    }
    $config.ui|ConvertTo-Json -Depth 30|Set-Content -LiteralPath $config.ui_configuration -Encoding UTF8
    $record.operator_action=$case.operator_action
    Save-Supervision
    Start-ScheduledTask -TaskName $config.ui_task
    $startedUi=$true
    $deadline=(Get-Date).AddSeconds(240)
    $uiStarted=$false
    do {
        Start-Sleep -Milliseconds 200
        $record.events=@($trace.Snapshot())
        if($case.fault -eq 'target-exit-during-consent' -and !$record.fault_applied) {
            $active=Read-UiRecord 'current-case.json'
            $consent=@($record.events|Where-Object {$_.kind -eq 'start' -and $_.name -ieq 'consent.exe'})
            if($active -and $active.name -eq $case.name -and $active.phase -eq 'confirming' -and $consent.Count -eq 1) {
                # The retained Process belongs to our own fixture. Never kill a PID
                # supplied by the unelevated UI observation or by a trace event.
                if($target.HasExited){throw 'Owned stale target exited before fault injection'}
                $target.Kill()
                if(!$target.WaitForExit(5000)){throw 'Owned stale target survived fault injection'}
                $record.fault_applied=@{kind=$case.fault;utc=(Get-Date).ToUniversalTime().ToString('o');pid=$target.Id;creation_ticks=$record.target.creation_ticks}
                Save-Supervision
            }
        }
        $info=Get-ScheduledTaskInfo -TaskName $config.ui_task
        $state=(Get-ScheduledTask -TaskName $config.ui_task).State
        if($info.LastRunTime.ToUniversalTime() -ge [DateTime]::Parse($record.started_utc).ToUniversalTime().AddSeconds(-1)){$uiStarted=$true}
        if($uiStarted -and $state -ne 'Running'){break}
    }while((Get-Date) -lt $deadline)
    if(!$uiStarted -or $state -eq 'Running'){throw 'Native UAC observation exceeded its deadline'}
    $record.ui_task_exit=$info.LastTaskResult
    $ui=Read-UiRecord 'result.json'
    if(!$ui -or $ui.status -ne 'PASS' -or $info.LastTaskResult -ne 0){throw 'Native UI action failed; inspect UI result'}
    if($target){$record.target_exited_before_cleanup=$target.HasExited}
    if($case.fault -and !$record.fault_applied){throw 'Requested stale-target fault was not observed'}
    $record.status='COLLECTED'
} catch {$record.error=$_.Exception.ToString()}
finally {
    if($target) {
        try {
            if(!$target.HasExited){$target.Kill()}
            $record.target_cleaned=$target.WaitForExit(5000)
            if(!$record.target_cleaned){throw 'Owned elevated fixture survived cleanup'}
        } catch {$record.status='FAIL';$record.cleanup_error=$_.Exception.ToString()}
        finally {$target.Dispose()}
    }
    if($startedUi -and (Get-ScheduledTask -TaskName $config.ui_task).State -eq 'Running') {
        # The UI runner has its own finally cleanup. Preserve its task and artifacts
        # after a timeout; do not kill unrelated processes or infer consent.
        $record.status='FAIL';$record.ui_still_running=$true
    }
    if($trace) {
        Start-Sleep -Seconds 2
        try {$trace.Dispose()}catch{$record.status='FAIL';$record.trace_cleanup_error=$_.Exception.ToString()}
        $record.events=@($trace.Snapshot())
    }
    $record.finished_utc=(Get-Date).ToUniversalTime().ToString('o')
    Save-Supervision
}
if($record.status -ne 'COLLECTED'){Write-Error $record.error;exit 1}
