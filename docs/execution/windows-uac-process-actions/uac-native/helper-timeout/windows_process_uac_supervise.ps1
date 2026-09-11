# One bounded native observation, run elevated by the test setup. Only the
# dashboard invokes runas. The operator answers that actual Windows UAC prompt.
param([Parameter(Mandatory=$true)][string]$Configuration)
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$config=Get-Content -Raw -Encoding UTF8 -LiteralPath $Configuration|ConvertFrom-Json
Add-Type -Path $config.trace_source -ReferencedAssemblies System.Management
Add-Type -Path $config.fault_source
Add-Type -Path $config.handles_source
[PulseOwnedProcessFault]::RemoveObserverDebugPrivilege()
$record=@{status='FAIL';started_utc=(Get-Date).ToUniversalTime().ToString('o');events=@()}
$record.observer_debug_privilege_removed=$true
$trace=$null
$target=$null
$targetFault=$null
$helper=$null
$helperFault=$null
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

function Observe-ReleasedHandles($case) {
    $active=Read-UiRecord 'current-case.json'
    if(!$active -or $active.phase -ne 'complete' -or $active.name -ne $case.name){return}
    $ui=Read-UiRecord 'result.json'
    if(!$ui -or @($ui.cases).Count -ne 1 -or $ui.cases[0].name -ne $case.name){throw 'Missing settled UI resource checkpoint'}
    $known=@($ui.dashboard.pid)+@($ui.helper_entry_checks|ForEach-Object {$_.pid})
    $starts=@($record.events|Where-Object {$_.kind -eq 'start' -and $_.name -ieq 'system-pulse.exe' -and $_.pid -notin $known})
    $expected=$(if($case.name -eq 'consent-cancel'){0}else{1})
    if($starts.Count -lt $expected){return} # The bounded UI checkpoint also bounds trace delivery.
    if($starts.Count -ne $expected){throw 'Unexpected helper count at the resource checkpoint'}
    $dashboard=[Diagnostics.Process]::GetProcessById($ui.dashboard.pid)
    try {
        $handle=$dashboard.Handle
        if($dashboard.HasExited -or [PulseProcessTrace]::Creation($handle) -ne [long]$ui.dashboard.creation_ticks){throw 'Dashboard identity changed before resource observation'}
        $live=[PulseProcessTrace]::Describe($dashboard.Id)
        if($live.live_observation_error -or $live.image -ine $config.ui.binary -or $live.elevated){throw 'Resource snapshot target is not the limited packaged dashboard'}
        $pids=@([uint32]$target.Id)+@($starts|ForEach-Object {[uint32]$_.pid})
        $snapshot=[PulseProcessHandles]::Capture($handle,[uint32[]]$pids)
        # Retain the native masks even when the assertions below fail.
        $record.resources=$snapshot
        Save-Supervision
        $targetHandles=@($snapshot.process_handles|Where-Object {$_.pid -eq $target.Id})
        $helperHandles=@($snapshot.process_handles|Where-Object {$_.pid -ne $target.Id})
        if($targetHandles.Count -ne 1 -or $targetHandles[0].termination_count -ne 0){throw 'Dashboard retained an owned termination handle'}
        foreach($row in $helperHandles) {
            if($row.count -eq 0){continue}
            # sysinfo retains one query-only handle while a process stays alive.
            # The action's WaitForSingleObject handle necessarily has SYNCHRONIZE.
            if($case.name -ne 'helper-timeout' -or !$helper -or $helper.HasExited -or
               $row.count -ne 1 -or $row.wait_count -ne 0 -or $row.termination_count -ne 0 -or
               @($row.granted_access).Count -ne 1 -or $row.granted_access[0] -notin @(0x1000,0x410,0x1410)) {
                throw 'Dashboard retained an elevated helper action handle'
            }
        }
        $snapshot['dashboard_creation_ticks']=$ui.dashboard.creation_ticks
        $snapshot['case']=$case.name
        $snapshot['passed']=$true
        $record.resources=$snapshot
        $ack=Join-Path $config.ui.output ($case.name+'-resources.json')
        [IO.File]::WriteAllText(($ack+'.tmp'),($snapshot|ConvertTo-Json -Depth 20))
        [IO.File]::Move(($ack+'.tmp'),$ack)
        Save-Supervision
    } finally {$dashboard.Dispose()}
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
    if($case.mode -notin @('cooperative','refusing','windowless','delayed','refusing-delayed') -or $case.signal -notin @('kill','terminate')){throw 'Invalid owned target action'}
    if($case.name -notmatch '^[a-z0-9-]+$'){throw 'Invalid case name'}
    if($case.fault -and $case.fault -notin @('target-exit-during-consent','deny-termination','helper-crash','helper-timeout')){throw 'Unsupported observer fault'}
    if((Get-FileHash -LiteralPath $config.ui.binary -Algorithm SHA256).Hash.ToLower() -ne $config.ui.binary_sha256){throw 'Unexpected packaged binary'}
    if(@(Get-Process -Name system-pulse,consent -ErrorAction SilentlyContinue).Count){throw 'Another application or consent prompt prevents isolation'}
    $trace=[PulseProcessTrace]::new()
    if(!$config.ordinary_baseline) {
        $target=Start-Process -FilePath $config.ui.fixture -ArgumentList @($case.mode,('"'+$config.target_log+'"')) -PassThru
        $null=$target.Handle
        $record.target=@{pid=$target.Id;creation_ticks=[PulseProcessTrace]::Creation($target.Handle);elevated=[PulseProcessTrace]::Elevated($target.Handle);image=$config.ui.fixture}
        if(!$record.target.elevated){throw 'Disposable target did not start elevated'}
        $targetFault=[PulseOwnedProcessFault]::new($target)
        $targetFault.RequireAdministratorForTermination()
        $record.target.administrator_termination_access_error=$targetFault.NewTerminationAccessError()
        if($record.target.administrator_termination_access_error -ne 0){throw 'Administrator cannot access the owned termination fixture'}
        $record.target.administrator_termination_dacl=$true
        if($case.fault -eq 'deny-termination') {
            $targetFault.DenyNewTerminationHandles()
            $denied=$targetFault.NewTerminationAccessError()
            if($denied -ne 5){throw 'Owned DACL fixture did not deny a new elevated termination handle'}
            $record.fault_applied=@{kind=$case.fault;utc=(Get-Date).ToUniversalTime().ToString('o');pid=$target.Id;creation_ticks=$record.target.creation_ticks;elevated_access_error=$denied}
        }
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
        if(!$config.ordinary_baseline -and !$record.resources){Observe-ReleasedHandles $case}
        if($case.fault -in @('helper-crash','helper-timeout') -and !$record.fault_applied) {
            $ui=Read-UiRecord 'result.json'
            if($ui -and $ui.dashboard) {
                $expected=@($config.ui.binary,'--system-pulse-windows-process-action',[string]$target.Id,[string]$record.target.creation_ticks,[string]$case.signal,[string]$ui.dashboard.pid,[string]$ui.dashboard.creation_ticks)
                $candidates=@($record.events|Where-Object {$_.kind -eq 'start' -and $_.name -ieq 'system-pulse.exe' -and $_.argv.Count -eq 7 -and $_.argv[2] -eq [string]$target.Id})
                if($candidates.Count -gt 1){throw 'More than one helper attempted the owned target'}
                if($candidates.Count -eq 1) {
                    $candidate=$candidates[0]
                    $helper=[Diagnostics.Process]::GetProcessById($candidate.pid)
                    $null=$helper.Handle
                    $live=[PulseProcessTrace]::Describe($candidate.pid)
                    if($helper.HasExited -or $live.live_observation_error -or $live.creation_ticks -ne $candidate.creation_ticks -or [PulseProcessTrace]::Creation($helper.Handle) -ne $candidate.creation_ticks){throw 'Helper identity changed before fault injection'}
                    if(!$live.elevated -or $live.image -ine $config.ui.binary -or $live.argv.Count -ne $expected.Count){throw 'Fault target is not the expected elevated helper'}
                    for($index=0;$index -lt $expected.Count;$index++) {
                        if($live.argv[$index] -cne $expected[$index]){throw 'Helper request differs from the owned target and dashboard'}
                    }
                    # Only now can the supervisor mutate this process. The job
                    # owns cleanup even if a suspended helper outlives the UI.
                    $helperFault=[PulseOwnedProcessFault]::new($helper)
                    $record.fault_applied=@{kind=$case.fault;utc=(Get-Date).ToUniversalTime().ToString('o');pid=$helper.Id;creation_ticks=$candidate.creation_ticks;image=$live.image;argv=$live.argv}
                    if($case.fault -eq 'helper-crash'){$helperFault.Crash()}
                    else {$record.fault_applied.suspended_threads=$helperFault.Suspend()}
                    Save-Supervision
                }
            }
        }
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
        # These two scheduler queries are not atomic. A previously read running
        # result (SCHED_S_TASK_RUNNING) must not become a terminal failure merely
        # because the subsequent state query observes completion.
        if($uiStarted -and $state -ne 'Running' -and $info.LastTaskResult -ne 0x41301){break}
    }while((Get-Date) -lt $deadline)
    if(!$uiStarted -or $state -eq 'Running' -or $info.LastTaskResult -eq 0x41301){throw 'Native UAC observation exceeded its deadline'}
    $record.ui_task_exit=$info.LastTaskResult
    $ui=Read-UiRecord 'result.json'
    if(!$ui -or $ui.status -ne 'PASS' -or $info.LastTaskResult -ne 0){throw 'Native UI action failed; inspect UI result'}
    if($target){$record.target_exited_before_cleanup=$target.HasExited}
    if($helper){$record.helper_exited_before_cleanup=$helper.HasExited}
    if($case.fault -and !$record.fault_applied){throw 'Requested stale-target fault was not observed'}
    $record.status='COLLECTED'
} catch {$record.error=$_.Exception.ToString()}
finally {
    if($helperFault) {
        try {$helperFault.Dispose();$record.helper_cleaned=$helper.WaitForExit(5000)}
        catch {$record.status='FAIL';$record.cleanup_error=$_.Exception.ToString()}
    }
    if($helper){$helper.Dispose()}
    if($targetFault) {
        try {$targetFault.Dispose()}
        catch {$record.status='FAIL';$record.cleanup_error=$_.Exception.ToString()}
    }
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
