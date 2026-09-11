# Run only in a limited interactive desktop. Configuration and targets belong to
# the verification harness; this file is never included in the helper entry path.
param(
    [Parameter(Mandatory=$true)][string]$Configuration
)
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes,System.Drawing,System.Windows.Forms
Add-Type @'
using System;
using System.Runtime.InteropServices;
using System.ComponentModel;
public static class PulseActionObservation {
    [DllImport("kernel32.dll",SetLastError=true)] static extern bool GetProcessTimes(IntPtr h,out long creation,out long exit,out long kernel,out long user);
    [DllImport("advapi32.dll",SetLastError=true)] static extern bool OpenProcessToken(IntPtr h,uint access,out IntPtr token);
    [DllImport("advapi32.dll",SetLastError=true)] static extern bool GetTokenInformation(IntPtr token,int kind,out int value,int size,out int length);
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);
    [DllImport("kernel32.dll",SetLastError=true)] static extern IntPtr OpenProcess(uint access,bool inherit,int pid);
    [DllImport("kernel32.dll")] static extern uint WaitForSingleObject(IntPtr h,uint milliseconds);
    [DllImport("kernel32.dll",SetLastError=true)] static extern bool GetProcessHandleCount(IntPtr h,out uint count);
    [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern bool QueryFullProcessImageName(IntPtr h,uint flags,System.Text.StringBuilder path,ref int size);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] static extern bool SetCursorPos(int x,int y);
    [DllImport("user32.dll")] static extern void mouse_event(uint flags,uint x,uint y,uint data,UIntPtr extra);
    [DllImport("user32.dll")] public static extern IntPtr SetThreadDpiAwarenessContext(IntPtr context);
    public static long Creation(IntPtr h) {
        long c,e,k,u; if(!GetProcessTimes(h,out c,out e,out k,out u)) throw new Win32Exception();
        return c;
    }
    public static IntPtr Observe(int pid) {
        IntPtr h=OpenProcess(0x101000,false,pid);
        if(h==IntPtr.Zero) throw new Win32Exception(); return h;
    }
    public static bool Exited(IntPtr h) {
        uint result=WaitForSingleObject(h,0);
        if(result==0) return true; if(result==258) return false; throw new Win32Exception();
    }
    public static void Release(IntPtr h) {if(!CloseHandle(h)) throw new Win32Exception();}
    public static uint HandleCount(IntPtr h) {
        uint count;if(!GetProcessHandleCount(h,out count)) throw new Win32Exception();return count;
    }
    public static int ForceAccessError(int pid) {
        IntPtr h=OpenProcess(0x101001,false,pid);
        if(h==IntPtr.Zero)return Marshal.GetLastWin32Error();
        Release(h);return 0;
    }
    public static string Image(IntPtr h) {
        var path=new System.Text.StringBuilder(32768);int size=path.Capacity;
        if(!QueryFullProcessImageName(h,0,path,ref size)) throw new Win32Exception();return path.ToString();
    }
    static int TokenValue(IntPtr h,int kind) {
        IntPtr token; if(!OpenProcessToken(h,8,out token)) throw new Win32Exception();
        try {int value,length; if(!GetTokenInformation(token,kind,out value,4,out length)) throw new Win32Exception(); return value;}
        finally {CloseHandle(token);}
    }
    public static bool Elevated(IntPtr h) {return TokenValue(h,20)!=0;}
    public static int ElevationType(IntPtr h) {return TokenValue(h,18);}
    public static void Click(int x,int y) {
        SetThreadDpiAwarenessContext(new IntPtr(-4));
        if(!SetCursorPos(x,y)) throw new Win32Exception();
        mouse_event(2,0,0,0,UIntPtr.Zero); mouse_event(4,0,0,0,UIntPtr.Zero);
    }
}
'@

function Save-Record($name,$value) {
    [IO.File]::WriteAllText((Join-Path $script:output $name),($value|ConvertTo-Json -Depth 30))
}
function Descendants {
    @($script:root.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition))
}
function Control($name,$role) {
    $items=@(Descendants | Where-Object {$_.Current.Name -eq $name -and $_.Current.ControlType.ProgrammaticName -eq $role})
    if($items.Count -ne 1){throw "Expected one $role '$name', found $($items.Count)"}
    $items[0]
}
function Control-Pattern($name,$role,$kind) {
    $deadline=(Get-Date).AddSeconds(2)
    do {
        $control=Control $name $role
        $pattern=$null
        try {
            if($control.TryGetCurrentPattern($kind,[ref]$pattern)){return $pattern}
        } catch [System.Windows.Automation.ElementNotAvailableException] {
            # The provider can replace a node between lookup and pattern access.
        }
        Start-Sleep -Milliseconds 100
    }while((Get-Date) -lt $deadline)
    throw "Native $role '$name' did not expose $kind before the deadline"
}
function Invoke-Button($name) {
    # Retry only read-only pattern acquisition. Never resubmit an action whose
    # Invoke/SetValue call may already have been delivered to the application.
    $invoke=Control-Pattern $name 'ControlType.Button' ([System.Windows.Automation.InvokePattern]::Pattern)
    ([System.Windows.Automation.InvokePattern]$invoke).Invoke()
}
function Read-SharedText($path) {
    # Allow atomic snapshot replacement while observing an older complete file.
    # Unlike Get-Content, this also returns text without provider/drive metadata.
    $stream=[IO.File]::Open($path,[IO.FileMode]::Open,[IO.FileAccess]::Read,([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
    try {
        $reader=[IO.StreamReader]::new($stream,[Text.Encoding]::UTF8)
        try {$reader.ReadToEnd()}finally{$reader.Dispose()}
    } finally {$stream.Dispose()}
}
function Read-Frame {
    Read-SharedText (Join-Path $script:output 'latest.json') | ConvertFrom-Json
}
function Status {
    $items=@(Descendants | Where-Object {$_.Current.AutomationId -eq 'process-action-status'})
    if($items.Count -eq 1){return $items[0].Current.Name}
    return ''
}
function Capture($name) {
    # A failure can occur while the human is entering UAC credentials. For UAC
    # runs, retain only application UIA observations and never copy screen pixels.
    if($config.uac_observation){return}
    [PulseActionObservation]::SetThreadDpiAwarenessContext([IntPtr](-4))|Out-Null
    $bounds=$script:root.Current.BoundingRectangle
    $bitmap=New-Object Drawing.Bitmap ([int]$bounds.Width),([int]$bounds.Height)
    $graphics=[Drawing.Graphics]::FromImage($bitmap)
    try {
        $graphics.CopyFromScreen([int]$bounds.X,[int]$bounds.Y,0,0,$bitmap.Size)
        $bitmap.Save((Join-Path $script:output $name),[Drawing.Imaging.ImageFormat]::Png)
    } finally {$graphics.Dispose();$bitmap.Dispose()}
}
function Prepare-Action($target,$signal) {
    $search=Control-Pattern 'Search name, PID, or user…' 'ControlType.Edit' ([System.Windows.Automation.ValuePattern]::Pattern)
    ([System.Windows.Automation.ValuePattern]$search).SetValue([string]$target.Id)
    Start-Sleep -Seconds 2
    $rows=@(Descendants | Where-Object {$_.Current.ControlType.ProgrammaticName -eq 'ControlType.DataItem' -and $_.Current.Name -eq ''})
    $selected=@(foreach($row in $rows) {
        $cells=$row.FindAll([System.Windows.Automation.TreeScope]::Children,[System.Windows.Automation.Condition]::TrueCondition)
        if($cells.Count -eq 8 -and $cells[0].Current.Name -eq [string]$target.Id){$row}
    })
    if($selected.Count -ne 1){throw 'Owned target is absent or ambiguous in the native table'}
    $bounds=$selected[0].Current.BoundingRectangle
    [PulseActionObservation]::SetForegroundWindow($script:app.MainWindowHandle)|Out-Null
    [PulseActionObservation]::Click([int]($bounds.X+20),[int]($bounds.Y+$bounds.Height/2))
    Start-Sleep -Milliseconds 300
    Invoke-Button $(if($signal -eq 'kill'){'Force quit…'}else{'End task…'})
    Start-Sleep -Milliseconds 300
    $text=@(Descendants | ForEach-Object {$_.Current.Name}) -join "`n"
    if($text -notmatch ('PID '+$target.Id+'\)\?')){throw 'Confirmation omitted the selected PID'}
    if($signal -eq 'kill' -and $text -notmatch 'Unsaved work may be lost'){throw 'Force quit omitted its warning'}
    if($signal -eq 'terminate' -and $text -notmatch 'Request graceful closure'){throw 'End task omitted its Windows semantics'}
    $text
}

$script:app=$null
$owned=New-Object Collections.Generic.List[System.Diagnostics.Process]
$observed=New-Object Collections.Generic.List[IntPtr]
$config=Get-Content -Raw -Encoding UTF8 $Configuration|ConvertFrom-Json
$script:output=$config.output
$result=@{status='FAIL';source_commit=$config.source_commit;cases=@();started_utc=(Get-Date).ToUniversalTime().ToString('o')}
$outputCreated=$false
try {
    New-Item -ItemType Directory -Path $script:output -ErrorAction Stop|Out-Null
    $outputCreated=$true
    $self=[Diagnostics.Process]::GetCurrentProcess()
    try {if([PulseActionObservation]::Elevated($self.Handle)){throw 'Action UI harness must be unelevated'}}finally{$self.Dispose()}
    if(@(Get-Process -Name system-pulse -ErrorAction SilentlyContinue).Count -ne 0){throw 'Existing System Pulse instance prevents isolated verification'}
    $hash=(Get-FileHash $config.binary -Algorithm SHA256).Hash.ToLower()
    if($hash -ne $config.binary_sha256){throw 'Action binary does not match configuration'}
    $result.binary_sha256=$hash
    $result.binary_path=$config.binary
    $result.signing_status=[string](Get-AuthenticodeSignature $config.binary).Status
    $result.os_version=[Environment]::OSVersion.VersionString
    $env:SYSTEM_PULSE_STATE_DIR=Join-Path $script:output 'state'
    $env:SYSTEM_PULSE_DIAGNOSTICS_PATH=Join-Path $script:output 'latest.json'
    $script:app=Start-Process $config.binary -PassThru -RedirectStandardOutput (Join-Path $script:output 'app.stdout') -RedirectStandardError (Join-Path $script:output 'app.stderr')
    $null=$script:app.Handle
    $deadline=(Get-Date).AddSeconds(30)
    do {Start-Sleep -Milliseconds 300;$script:app.Refresh()}while(!$script:app.HasExited -and $script:app.MainWindowHandle -eq 0 -and (Get-Date) -lt $deadline)
    if($script:app.HasExited -or $script:app.MainWindowHandle -eq 0){throw 'No live action dashboard'}
    $script:root=[System.Windows.Automation.AutomationElement]::FromHandle($script:app.MainWindowHandle)
    Start-Sleep -Seconds 3
    $tab=Control-Pattern 'Processes' 'ControlType.TabItem' ([System.Windows.Automation.SelectionItemPattern]::Pattern)
    ([System.Windows.Automation.SelectionItemPattern]$tab).Select()
    Start-Sleep -Seconds 2
    $result.dashboard=@{pid=$script:app.Id;creation_ticks=[PulseActionObservation]::Creation($script:app.Handle);elevated_before=[PulseActionObservation]::Elevated($script:app.Handle);elevation_type=[PulseActionObservation]::ElevationType($script:app.Handle);account=[Security.Principal.WindowsIdentity]::GetCurrent().Name}
    Save-Record 'result.json' $result
    $controlLog=Join-Path $script:output 'unrelated-control.target.log'
    $control=Start-Process $config.fixture -ArgumentList @('cooperative',('"'+$controlLog+'"')) -PassThru
    $owned.Add($control)
    $null=$control.Handle
    Start-Sleep -Seconds 1
    $result.unrelated_control=@{pid=$control.Id;creation_ticks=[PulseActionObservation]::Creation($control.Handle)}
    $result.helper_entry_checks=@()
    $request=@('--system-pulse-windows-process-action',[string]$control.Id,[string]$result.unrelated_control.creation_ticks,'kill',[string]$script:app.Id,[string]$result.dashboard.creation_ticks)
    foreach($probe in @(
        @{name='unelevated-helper';arguments=$request;expected_exit=29},
        @{name='extra-helper-argument';arguments=@($request)+@('extra');expected_exit=29},
        @{name='legacy-helper-mode';arguments=@('--system-pulse-process-action',[string]$control.Id,[string]$result.unrelated_control.creation_ticks,'kill');expected_exit=13}
    )) {
        $originalState=$env:SYSTEM_PULSE_STATE_DIR
        $originalDiagnostics=$env:SYSTEM_PULSE_DIAGNOSTICS_PATH
        try {
            $env:SYSTEM_PULSE_STATE_DIR=Join-Path $script:output ($probe.name+'-state')
            $env:SYSTEM_PULSE_DIAGNOSTICS_PATH=Join-Path $script:output ($probe.name+'-diagnostics.json')
            $helper=Start-Process $config.binary -ArgumentList $probe.arguments -PassThru
            $owned.Add($helper)
            $null=$helper.Handle
            if(!$helper.WaitForExit(5000)){throw 'Direct helper invocation did not exit promptly'}
            if($helper.ExitCode -ne $probe.expected_exit){throw 'Direct helper invocation returned the wrong refusal'}
            $control.Refresh()
            if($control.HasExited){throw 'An unelevated or malformed helper changed its target'}
            if((Test-Path $env:SYSTEM_PULSE_STATE_DIR) -or (Test-Path $env:SYSTEM_PULSE_DIAGNOSTICS_PATH)){throw 'A helper initialized application state or collection'}
            $result.helper_entry_checks+=@{name=$probe.name;pid=$helper.Id;exit_code=$helper.ExitCode;target_alive=$true;state_created=$false;diagnostics_created=$false}
        } finally {
            $env:SYSTEM_PULSE_STATE_DIR=$originalState
            $env:SYSTEM_PULSE_DIAGNOSTICS_PATH=$originalDiagnostics
        }
    }
    Save-Record 'result.json' $result
    foreach($case in $config.cases) {
        if($case.name -notmatch '^[a-z0-9-]+$'){throw 'Invalid case name'}
        $log=Join-Path $script:output ($case.name+'.target.log')
        if($case.target_pid) {
            # Externally owned elevated fixtures are cleaned by their supervisor.
            $target=Get-Process -Id $case.target_pid -ErrorAction Stop
        } else {
            $target=Start-Process $config.fixture -ArgumentList @($case.mode,('"'+$log+'"')) -PassThru
            $owned.Add($target)
        }
        $nativeHandle=[PulseActionObservation]::Observe($target.Id)
        $observed.Add($nativeHandle)
        if([IO.Path]::GetFullPath([PulseActionObservation]::Image($nativeHandle)) -ine [IO.Path]::GetFullPath($config.fixture)){throw 'Target executable is not the owned process fixture'}
        $ticks=[PulseActionObservation]::Creation($nativeHandle)
        if($case.target_ticks -and $ticks -ne [long]$case.target_ticks){throw 'Supervisor target identity changed'}
        Start-Sleep -Seconds 2
        $frame=Read-Frame
        $row=@($frame.snapshot.processes | Where-Object {$_.identity.pid -eq $target.Id})
        if($row.Count -ne 1 -or $row[0].identity.start_time_ticks -ne $ticks){throw 'Collected full creation identity differs from GetProcessTimes'}
        $observation=@{name=$case.name;pid=$target.Id;creation_ticks=$ticks;signal=$case.signal;mode=$case.mode;collected_creation_ticks=$row[0].identity.start_time_ticks;sequence_before=$frame.snapshot.sequence}
        if($config.uac_observation -and $case.target_pid -and $case.signal -eq 'kill') {
            $observation.ordinary_force_access_error=[PulseActionObservation]::ForceAccessError($target.Id)
            if($observation.ordinary_force_access_error -ne 5){throw ('Owned force fixture expected access denied; native error: '+$observation.ordinary_force_access_error)}
        }
        $observation.confirmation=Prepare-Action $target $case.signal
        $observation.dashboard_handles_before=[PulseActionObservation]::HandleCount($script:app.Handle)
        Capture ($case.name+'-confirmation.png')
        if($case.exit_before_confirm) {
            $target.Kill();if(!$target.WaitForExit(5000)){throw 'Owned stale fixture did not exit'}
        }
        if($case.cancel_confirmation) {
            Invoke-Button 'Cancel process action'
            Start-Sleep -Milliseconds 300
            if([PulseActionObservation]::Exited($nativeHandle)){throw 'Confirmation cancellation changed owned target'}
            $observation.status='confirmation cancelled'
        } else {
            Save-Record 'current-case.json' @{name=$case.name;phase='confirming';pid=$target.Id;expected_operator_action=$case.operator_action}
            $confirmName=$(if($case.signal -eq 'kill'){'Confirm force quit'}else{'Confirm end task'})
            $invoke=[System.Windows.Automation.InvokePattern](Control-Pattern $confirmName 'ControlType.Button' ([System.Windows.Automation.InvokePattern]::Pattern))
            $observation.submitted_utc=(Get-Date).ToUniversalTime().ToString('o')
            $invoke.Invoke()
            # Exercise an actual duplicate activation of the same native control.
            # It may already have left the accessibility tree, which is also inert.
            try {$invoke.Invoke();$observation.duplicate_activation='delivered'}
            catch [System.Windows.Automation.ElementNotAvailableException] {$observation.duplicate_activation='control removed'}
            catch [System.Windows.Automation.ElementNotEnabledException] {$observation.duplicate_activation='control disabled'}
            $pending=@()
            $deadline=(Get-Date).AddSeconds(180)
            do {
                Start-Sleep -Milliseconds 200
                $status=Status
                if($status -and $status -notlike 'Sending request*'){break}
                if($status -like 'Sending request*') {
                    if($case.verify_responsive -and $pending.Count -eq 0) {
                        $selected=@()
                        foreach($name in @('Summary','Processes')) {
                            $selection=[System.Windows.Automation.SelectionItemPattern](Control-Pattern $name 'ControlType.TabItem' ([System.Windows.Automation.SelectionItemPattern]::Pattern))
                            $selection.Select();Start-Sleep -Milliseconds 200
                            if(!$selection.Current.IsSelected){throw 'Dashboard did not respond during the pending action'}
                            $selected+=,$name
                        }
                        $observation.pending_screen_changes=$selected
                    }
                    $disabled=@(foreach($name in @('End task…','Force quit…')) {!(Control $name 'ControlType.Button').Current.IsEnabled})
                    if($disabled -contains $false) {
                        # UIA reads are separate observations; completion can fall
                        # between the pending status and the toolbar properties.
                        $status=Status
                        if($status -and $status -notlike 'Sending request*'){break}
                        throw 'Pending action allows another toolbar submission'
                    }
                    $pending+=@{sequence=(Read-Frame).snapshot.sequence;actions_disabled=$disabled;observed_utc=(Get-Date).ToUniversalTime().ToString('o')}
                }
            } while((Get-Date) -lt $deadline)
            if(!$status -or $status -like 'Sending request*'){throw 'Process action did not settle before the observation deadline'}
            $observation.status=$status
            $observation.settled_utc=(Get-Date).ToUniversalTime().ToString('o')
            $observation.pending_observations=$pending
            Save-Record ($case.name+'-action.json') $observation
            if($status -notmatch $case.expected_status){throw "Unexpected action result for $($case.name): $status"}
        }
        Start-Sleep -Seconds 1
        $observation.exited=[PulseActionObservation]::Exited($nativeHandle)
        if($observation.exited -ne [bool]$case.expected_exit){throw 'Observed target lifetime differs from expected action semantics'}
        $observation.sequence_after=(Read-Frame).snapshot.sequence
        $observation.dashboard_elevated_after=[PulseActionObservation]::Elevated($script:app.Handle)
        $observation.dashboard_handles_after=[PulseActionObservation]::HandleCount($script:app.Handle)
        if($observation.dashboard_elevated_after){throw 'Dashboard became elevated'}
        $control.Refresh()
        $controlMessages=Read-SharedText $controlLog
        if($control.HasExited -or $controlMessages -ne "ready`n"){throw 'An unrelated control target was affected'}
        $observation.unrelated_control_alive=$true
        $observation.unrelated_control_messages=$controlMessages
        Capture ($case.name+'-result.png')
        $result.cases+=,$observation
        Save-Record 'result.json' $result
        Save-Record 'current-case.json' @{name=$case.name;phase='complete';pid=$target.Id}
        if($config.observe_resources) {
            # Keep the dashboard alive until the independent native observer has
            # inspected its released helper handle. Never extend the action wait.
            $ackPath=Join-Path $script:output ($case.name+'-resources.json')
            $ackDeadline=(Get-Date).AddSeconds(15)
            do {Start-Sleep -Milliseconds 100}while(!(Test-Path -LiteralPath $ackPath) -and (Get-Date) -lt $ackDeadline)
            if(!(Test-Path -LiteralPath $ackPath)){throw 'Native resource observation was not acknowledged'}
            $ack=Read-SharedText $ackPath|ConvertFrom-Json
            if($ack.case -ne $case.name -or $ack.dashboard_creation_ticks -ne $result.dashboard.creation_ticks -or $ack.passed -ne $true){throw 'Resource acknowledgment does not match this dashboard and case'}
            $result.resources_acknowledged=$true
        }
        if($case.target_pid){$target.Dispose()}
    }
    if((Read-SharedText (Join-Path $script:output 'app.stderr')).Trim()) {
        throw 'Application reported an error; inspect app.stderr'
    }
    $result.status='PASS'
} catch {
    $result.error=$_.Exception.Message
    $result.error_stack=$_.ScriptStackTrace
    if($script:root -and $outputCreated) {
        try {
            Save-Record 'failure-tree.json' @(Descendants | ForEach-Object {@{name=$_.Current.Name;role=$_.Current.ControlType.ProgrammaticName;id=$_.Current.AutomationId;enabled=$_.Current.IsEnabled}})
            Capture 'failure.png'
        } catch {$result.capture_error=$_.Exception.Message}
    }
} finally {
    $cleanup=@()
    foreach($target in $owned) {
        try {
            $target.Refresh();if(!$target.HasExited){$target.Kill()}
            $exited=$target.WaitForExit(5000)
            $cleanup+=@{pid=$target.Id;exited=$exited}
            if(!$exited){$result.status='FAIL';$result.cleanup_error='Owned target survived cleanup'}
        } catch {$result.status='FAIL';$result.cleanup_error=$_.Exception.Message}
        finally {$target.Dispose()}
    }
    if($script:app) {
        try {
            # This harness measures process actions, not tray shutdown; the runtime
            # preservation harness separately exercises the native Quit command.
            if(!$script:app.HasExited){$script:app.Kill()}
            $result.dashboard_cleaned=$script:app.WaitForExit(5000)
            if(!$result.dashboard_cleaned){$result.status='FAIL'}
        } catch {$result.status='FAIL';$result.cleanup_error=$_.Exception.Message}
        finally {$script:app.Dispose()}
    }
    $result.owned_target_cleanup=$cleanup
    foreach($handle in $observed) {
        try {[PulseActionObservation]::Release($handle)}catch{$result.status='FAIL';$result.cleanup_error=$_.Exception.Message}
    }
    $result.finished_utc=(Get-Date).ToUniversalTime().ToString('o')
    if($outputCreated){Save-Record 'result.json' $result}
}
if($result.status -ne 'PASS'){Write-Error $result.error;exit 1}
