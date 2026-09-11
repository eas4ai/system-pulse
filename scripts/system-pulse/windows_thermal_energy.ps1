# The runner prepends the existing runtime UI helpers and verified run metadata.
# This script runs in a Limited interactive scheduled task, never elevated SSH.
function Save-Thermal($name,$value) {
    [IO.File]::WriteAllText((Join-Path $OutputDirectory $name),(ConvertTo-Json -InputObject $value -Depth 40))
}
function Request-Action($stage,$instruction,$details) {
    Save-Thermal 'request.json' @{run_id=$RunId;stage=$stage;instruction=$instruction;details=$details;requested_utc=[DateTime]::UtcNow.ToString('o');deadline_utc=[DateTime]::UtcNow.AddSeconds($GateTimeout).ToString('o')}
}
function App-Frame {
    $text=[IO.File]::ReadAllText((Join-Path $OutputDirectory 'latest.json'))
    $record=$text|ConvertFrom-Json
    if($record.application_pid -ne $script:app.Id) {throw 'Diagnostic frame belongs to another process'}
    if([ThermalToken]::Elevated($script:app.Id)) {throw 'Packaged dashboard is elevated'}
    @{application_pid=$script:app.Id;elevated=$false;observed_utc=[DateTime]::UtcNow.ToString('o');qpc=[Diagnostics.Stopwatch]::GetTimestamp();frequency=[Diagnostics.Stopwatch]::Frequency;snapshot=$record.snapshot}
}
function Package-Reading($frame) {
    $readings=@($frame.snapshot.readings|Where-Object {$_.sensor_id -eq 'cpu:host/windows-package-temperature'})
    if($readings.Count -ne 1) {throw 'Expected one CPU package temperature reading'}
    $readings[0]
}
function Wait-Reading($availability,$reasonPattern,$timeout) {
    $deadline=[DateTime]::UtcNow.AddSeconds($timeout)
    do {
        if($script:app.HasExited) {throw 'Packaged dashboard exited while awaiting thermal state'}
        $frame=App-Frame;$reading=Package-Reading $frame
        if($frame.snapshot.sequence -gt $script:lastSequence -and $reading.availability -eq $availability -and (!$reasonPattern -or $reading.reason -match $reasonPattern)) {
            $script:lastSequence=$frame.snapshot.sequence
            return $frame
        }
        Start-Sleep -Milliseconds 250
    } while([DateTime]::UtcNow -lt $deadline)
    throw "Thermal state timed out: $availability / $reasonPattern"
}
function Thermal-UI($screen) {
    @{selected_screen=$screen;pid=$script:app.Id;controls=@(Descendants $script:root|ForEach-Object {@{name=$_.Current.Name;role=$_.Current.ControlType.ProgrammaticName;offscreen=$_.Current.IsOffscreen}})}
}
function Add-Stage($name,$frames,$capture) {
    $ui=$null
    if($capture) {Start-Sleep -Seconds 1;$ui=Thermal-UI 'Thermals';Capture ($name+'.png') $script:root.Current.BoundingRectangle}
    $stage=@{name=$name;frames=@($frames);ui=$ui}
    $script:stages+=,$stage
    Save-Thermal 'stages.json' $script:stages
    $stage
}
function Invoke-Thermal($label) {
    $button=Control $label 'ControlType.Button'
    if(!$button.Current.IsEnabled) {throw "Thermal control disabled: $label"}
    ([System.Windows.Automation.InvokePattern]$button.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)).Invoke()
}
function Other-Helper {
    $helpers=@(Get-Process -Name system-pulse -ErrorAction SilentlyContinue|Where-Object {$_.Id -ne $script:app.Id})
    if($helpers.Count -ne 1) {throw 'Expected exactly one newly launched temperature helper'}
    [ThermalReadOnlyProcess]::new($helpers[0].Id,$script:binary)
}
Add-Type @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Text;
public static class ThermalToken {
 [DllImport("kernel32.dll",SetLastError=true)] static extern IntPtr OpenProcess(uint rights,bool inherit,int pid);
 [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);
 [DllImport("advapi32.dll",SetLastError=true)] static extern bool OpenProcessToken(IntPtr process,uint access,out IntPtr token);
 [DllImport("advapi32.dll",SetLastError=true)] static extern bool GetTokenInformation(IntPtr token,int kind,out int value,int size,out int used);
 public static bool Elevated(int pid) {
  IntPtr process=OpenProcess(0x1000,false,pid); if(process==IntPtr.Zero)throw new Win32Exception();
  IntPtr token=IntPtr.Zero;
  try {if(!OpenProcessToken(process,8,out token))throw new Win32Exception(); int value,used;
   if(!GetTokenInformation(token,20,out value,4,out used)||used!=4)throw new Win32Exception();return value!=0;
  } finally {if(token!=IntPtr.Zero)CloseHandle(token);CloseHandle(process);}
 }
}
public sealed class ThermalReadOnlyProcess : IDisposable {
 [DllImport("kernel32.dll",SetLastError=true)] static extern IntPtr OpenProcess(uint rights,bool inherit,int pid);
 [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);
 [DllImport("kernel32.dll")] static extern int GetProcessId(IntPtr h);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool GetProcessTimes(IntPtr h,out long created,out long exited,out long kernel,out long user);
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern bool QueryFullProcessImageName(IntPtr h,uint flags,StringBuilder path,ref int length);
 [DllImport("kernel32.dll",SetLastError=true)] static extern uint WaitForSingleObject(IntPtr h,uint milliseconds);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool GetExitCodeProcess(IntPtr h,out int code);
 IntPtr handle; public int Id {get;private set;} public long CreationTicks {get;private set;}
 public ThermalReadOnlyProcess(int pid,string expectedPath) {
  handle=OpenProcess(0x101000,false,pid);if(handle==IntPtr.Zero)throw new Win32Exception();
  try {Id=GetProcessId(handle);long created,exit,kernel,user;var path=new StringBuilder(32768);int length=path.Capacity;
   if(Id!=pid||!GetProcessTimes(handle,out created,out exit,out kernel,out user)||!QueryFullProcessImageName(handle,0,path,ref length))throw new Win32Exception();
   if(!String.Equals(System.IO.Path.GetFullPath(path.ToString()),System.IO.Path.GetFullPath(expectedPath),StringComparison.OrdinalIgnoreCase))throw new InvalidOperationException("Helper is a different executable");
   CreationTicks=created;if(WaitForExit(0))throw new InvalidOperationException("Helper already exited");
  } catch {Dispose();throw;}
 }
 public bool WaitForExit(int milliseconds) {uint code=WaitForSingleObject(handle,(uint)milliseconds);if(code==0)return true;if(code==258)return false;throw new Win32Exception();}
 public int ExitCode {get {int code;if(!GetExitCodeProcess(handle,out code))throw new Win32Exception();return code;}}
 public void Dispose() {if(handle!=IntPtr.Zero){CloseHandle(handle);handle=IntPtr.Zero;}GC.SuppressFinalize(this);}
 ~ThermalReadOnlyProcess(){Dispose();}
}
'@
$script:app=$null;$script:stages=@();$script:lastSequence=0;$helper=$null
try {
    New-Item -ItemType Directory -Path $OutputDirectory -ErrorAction Stop|Out-Null
    if([ThermalToken]::Elevated($PID)) {throw 'Thermal UI harness must run unelevated'}
    if((Get-FileHash $script:binary -Algorithm SHA256).Hash.ToLower() -ne $ExpectedBinarySha256) {throw 'Packaged binary hash mismatch'}
    $signature=Get-AuthenticodeSignature $script:binary
    if($signature.Status -ne 'Valid') {throw 'Packaged application signature is not valid'}
    if(@(Get-Process -Name system-pulse -ErrorAction SilentlyContinue).Count -ne 0) {throw 'Existing System Pulse process prevents isolated observation'}
    $started=[DateTime]::UtcNow.ToString('o')
    $env:SYSTEM_PULSE_STATE_DIR=Join-Path $OutputDirectory 'state'
    Save-Thermal 'inventory.json' @{cpu=@(Get-CimInstance Win32_Processor|Select-Object Name,Manufacturer,ProcessorId);gpu=@(Get-CimInstance Win32_VideoController|Select-Object Name,PNPDeviceID,Status,DriverVersion)}
    Start-App $true 'thermal'
    Select-Screen 'Energy';$energyUI=Thermal-UI 'Energy';Capture 'energy.png' $script:root.Current.BoundingRectangle
    Save-Thermal 'energy-ui.json' $energyUI
    Select-Screen 'Thermals'
    $frame=Wait-Reading 'Unavailable' 'off' 20
    $null=Add-Stage 'off' @($frame) $true
    Request-Action 'deny' 'Deny the forthcoming System Pulse CPU-temperature UAC request after the pending frame has been captured.' @{}
    Invoke-Thermal 'Enable CPU temperatures…'
    $pending=Wait-Reading 'WarmingUp' '' 15
    $null=Add-Stage 'pending' @($pending) $false
    Request-Action 'deny-ready' 'Pending frame captured. Deny the current Windows UAC request.' @{}
    $denied=Wait-Reading 'Failed' 'denied|cancelled' $GateTimeout
    $null=Add-Stage 'denied' @($denied) $true
    Request-Action 'approve' 'Approve the forthcoming System Pulse CPU-temperature UAC request.' @{}
    Invoke-Thermal 'Enable CPU temperatures…'
    $first=Wait-Reading 'Available' '' $GateTimeout
    $frames=@($first)
    Request-Action 'independent' 'Run the fresh independent EMI and PawnIO probes now. Write independent.json in this evidence directory with this run_id and UTC bounds. Existing historical probe output is not accepted.' @{output_directory=$OutputDirectory}
    $deadline=[DateTime]::UtcNow.AddSeconds($GateTimeout)
    do {
        Start-Sleep -Seconds 1
        $frames+=,(Wait-Reading 'Available' '' 10)
        if((Test-Path (Join-Path $OutputDirectory 'independent.json')) -and $frames.Count -ge 8) {break}
    } while([DateTime]::UtcNow -lt $deadline)
    if(!(Test-Path (Join-Path $OutputDirectory 'independent.json'))) {throw 'Contemporaneous independent probes were not supplied before deadline'}
    # Retain an app frame after the completed independent capture's timestamp.
    Start-Sleep -Seconds 1;$frames+=,(Wait-Reading 'Available' '' 10)
    $null=Add-Stage 'enabled' $frames $true
    $helper=Other-Helper
    Invoke-Thermal 'Disable CPU temperatures'
    $disabled=Wait-Reading 'Unavailable' 'off' 20
    if(!$helper.WaitForExit(10000)) {throw 'Temperature helper survived Disable'}
    $disabledStage=Add-Stage 'disabled' @($disabled) $true
    $disabledStage.helper=@{pid=$helper.Id;exited=$true}
    $helper.Dispose()
    Request-Action 'approve-retry' 'Approve the second CPU-temperature UAC request for the helper-exit test.' @{}
    Invoke-Thermal 'Enable CPU temperatures…'
    $beforeExit=Wait-Reading 'Available' '' $GateTimeout
    $helper=Other-Helper
    Request-Action 'helper-exit' 'Terminate only the retained temperature helper identified here, using the authorized elevated test session. Leave the dashboard alive.' @{pid=$helper.Id;creation_ticks=$helper.CreationTicks;dashboard_pid=$script:app.Id;binary_sha256=$ExpectedBinarySha256}
    if(!$helper.WaitForExit($GateTimeout*1000)) {throw 'Requested helper-exit test was not performed'}
    $exitFrame=Wait-Reading 'Failed' 'helper|stopped|pipe' 20
    $exitStage=Add-Stage 'helper-exit' @($exitFrame) $true
    $exitStage.before_exit=$beforeExit;$exitStage.helper=@{pid=$helper.Id;exited=$true;exit_code=$helper.ExitCode}
    $helper.Dispose()
    Save-Thermal 'stages.json' $script:stages
    Select-Screen 'GPU';$gpuUI=Thermal-UI 'GPU';Capture 'gpu.png' $script:root.Current.BoundingRectangle
    Select-Screen 'Processes';$rows=@(Process-Rows)
    $quit=Quit-App 'thermal'
    $diagnosticHash=(Get-FileHash (Join-Path $OutputDirectory 'latest.json') -Algorithm SHA256).Hash
    Start-App $false 'normal'
    if([ThermalToken]::Elevated($script:app.Id)) {throw 'Normal packaged dashboard is elevated'}
    Select-Screen 'Energy';$normalEnergy=Thermal-UI 'Energy';Capture 'normal-energy.png' $script:root.Current.BoundingRectangle
    Select-Screen 'Thermals';$normalThermals=Thermal-UI 'Thermals';Capture 'normal-thermals.png' $script:root.Current.BoundingRectangle
    Select-Screen 'GPU';$normalGpu=Thermal-UI 'GPU';Capture 'normal-gpu.png' $script:root.Current.BoundingRectangle
    Select-Screen 'Processes';$normalRows=@(Process-Rows)
    $normalQuit=Quit-App 'normal'
    if((Get-FileHash (Join-Path $OutputDirectory 'latest.json') -Algorithm SHA256).Hash -ne $diagnosticHash) {throw 'Normal launch wrote diagnostics'}
    if((Get-FileHash $script:binary -Algorithm SHA256).Hash.ToLower() -ne $ExpectedBinarySha256) {throw 'Application changed during capture'}
    Save-Thermal 'preservation.json' @{diagnostics_enabled=$false;elevated=$false;diagnostic_rows=$rows;normal_rows=$normalRows;gpu=$gpuUI;normal_gpu=$normalGpu;normal_energy=$normalEnergy;normal_thermals=$normalThermals;quit=$normalQuit}
    $remaining=@(Get-Process -Name system-pulse -ErrorAction SilentlyContinue)
    if($remaining.Count -ne 0) {throw 'Application/helper survived cleanup'}
    Save-Thermal 'result.json' @{status='PASS';run_id=$RunId;source_commit=$SourceCommit;binary_sha256=$ExpectedBinarySha256;elevated=$false;cleanup=$true;started_utc=$started;finished_utc=[DateTime]::UtcNow.ToString('o');quit=$quit;signature=@{status=$signature.Status.ToString();subject=$signature.SignerCertificate.Subject;thumbprint=$signature.SignerCertificate.Thumbprint}}
    Request-Action 'complete' 'Native observations complete; independent validator and visual review remain required.' @{}
} catch {
    if(Test-Path $OutputDirectory) {Save-Thermal 'failure.json' @{error=($_|Out-String);run_id=$RunId}}
    throw
} finally {
    if($null -ne $helper) {$helper.Dispose()}
    if($null -ne $script:app -and !$script:app.HasExited) {Stop-Process -Id $script:app.Id -ErrorAction Continue;$script:app.WaitForExit(15000)|Out-Null}
}
