# Run in the logged-in user's limited interactive session. The runner supplies
# RunId, OutputDirectory, SourceCommit and ExpectedBinarySha256 before this file.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes,System.Drawing,System.Windows.Forms
Add-Type @'
using System;
using System.Runtime.InteropServices;
using System.Threading;
public static class PulseRuntimeNative {
    [DllImport("user32.dll")] public static extern IntPtr SetThreadDpiAwarenessContext(IntPtr context);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr window);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr window);
    [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr window,uint message,IntPtr w,IntPtr l);
    [DllImport("user32.dll",CharSet=CharSet.Unicode)] public static extern IntPtr FindWindow(string name,string title);
    [DllImport("user32.dll")] static extern bool SetCursorPos(int x,int y);
    [DllImport("user32.dll")] static extern void mouse_event(uint flags,uint x,uint y,uint data,UIntPtr extra);
    [DllImport("user32.dll")] static extern void keybd_event(byte key,byte scan,uint flags,UIntPtr extra);
    public static void Taskbar() {
        SetThreadDpiAwarenessContext(new IntPtr(-4));
        SetForegroundWindow(FindWindow("Shell_TrayWnd",null));
        keybd_event(27,0,0,UIntPtr.Zero); keybd_event(27,0,2,UIntPtr.Zero);
        Thread.Sleep(200);
        keybd_event(91,0,0,UIntPtr.Zero); keybd_event(84,0,0,UIntPtr.Zero);
        keybd_event(84,0,2,UIntPtr.Zero); keybd_event(91,0,2,UIntPtr.Zero);
    }
    public static void Click(int x,int y,bool right) {
        SetThreadDpiAwarenessContext(new IntPtr(-4));
        if(!SetCursorPos(x,y)) throw new InvalidOperationException("Cannot position pointer");
        Thread.Sleep(100);
        mouse_event(right ? 8u : 2u,0,0,0,UIntPtr.Zero);
        Thread.Sleep(100);
        mouse_event(right ? 16u : 4u,0,0,0,UIntPtr.Zero);
    }
}
'@

function Write-Record($name,$value) {
    [IO.File]::WriteAllText((Join-Path $OutputDirectory $name),($value | ConvertTo-Json -Depth 30))
}
function Descendants($element) {
    @($element.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition))
}
function Control($name,$role) {
    $found=@(Descendants $script:root | Where-Object {$_.Current.Name -eq $name -and $_.Current.ControlType.ProgrammaticName -eq $role})
    if($found.Count -ne 1) {throw "Expected one $role '$name', found $($found.Count)"}
    $found[0]
}
function Select-Screen($name) {
    $tab=Control $name 'ControlType.TabItem'
    $pattern=[System.Windows.Automation.SelectionItemPattern]$tab.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern)
    $pattern.Select(); Start-Sleep -Seconds 2
    if(!$pattern.Current.IsSelected) {throw "Screen did not select: $name"}
}
function Capture($name,$bounds) {
    [PulseRuntimeNative]::SetThreadDpiAwarenessContext([IntPtr](-4)) | Out-Null
    if($bounds.IsEmpty -or $bounds.Width -le 0 -or $bounds.Height -le 0) {throw 'Empty screenshot bounds'}
    $bitmap=New-Object System.Drawing.Bitmap ([int]$bounds.Width),([int]$bounds.Height)
    $graphics=[System.Drawing.Graphics]::FromImage($bitmap)
    try {
        $graphics.CopyFromScreen([int]$bounds.X,[int]$bounds.Y,0,0,$bitmap.Size)
        $bitmap.Save((Join-Path $OutputDirectory $name),[System.Drawing.Imaging.ImageFormat]::Png)
    } finally {$graphics.Dispose();$bitmap.Dispose()}
}
function Process-Rows {
    $tables=@(Descendants $script:root | Where-Object {$_.Current.ControlType.ProgrammaticName -eq 'ControlType.Table'})
    if($tables.Count -ne 1) {throw 'Expected one process table'}
    $rows=@(Descendants $tables[0] | Where-Object {$_.Current.ControlType.ProgrammaticName -eq 'ControlType.DataItem' -and $_.Current.Name -eq ''})
    $observed=@(foreach($row in $rows) {
        $cells=$row.FindAll([System.Windows.Automation.TreeScope]::Children,[System.Windows.Automation.Condition]::TrueCondition)
        if($cells.Count -eq 8 -and $cells[0].Current.Name -match '^\d+$') {
            @{pid=[int]$cells[0].Current.Name;name=$cells[1].Current.Name;cells=@($cells|ForEach-Object {$_.Current.Name})}
        }
    })
    if($observed.Count -eq 0) {throw 'No native process rows were observed'}
    $observed
}
function Set-Choice($name,$change) {
    $button=Control $name 'ControlType.Button'
    $pattern=[System.Windows.Automation.TogglePattern]$button.GetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern)
    if($change -and $pattern.Current.ToggleState -ne [System.Windows.Automation.ToggleState]::On) {
        $pattern.Toggle(); Start-Sleep -Seconds 1
        $button=Control $name 'ControlType.Button'
        $pattern=[System.Windows.Automation.TogglePattern]$button.GetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern)
    }
    if($pattern.Current.ToggleState -ne [System.Windows.Automation.ToggleState]::On) {throw "Setting was not retained: $name"}
}
function Open-Tray {
    [PulseRuntimeNative]::Taskbar(); Start-Sleep -Milliseconds 800
    $shell=[System.Windows.Automation.AutomationElement]::FromHandle([PulseRuntimeNative]::FindWindow('Shell_TrayWnd',$null))
    $overflow=@(Descendants $shell | Where-Object {$_.Current.Name -eq 'Show Hidden Icons'})
    if($overflow.Count -eq 1) {
        ([System.Windows.Automation.InvokePattern]$overflow[0].GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)).Invoke()
        Start-Sleep -Milliseconds 800
    }
    $icons=@(Descendants ([System.Windows.Automation.AutomationElement]::RootElement) | Where-Object {
        $_.Current.Name -like 'System Pulse*CPU*' -and $_.Current.ClassName -eq 'SystemTray.NormalButton' -and !$_.Current.IsOffscreen
    })
    if($icons.Count -ne 1 -or $icons[0].Current.BoundingRectangle.IsEmpty) {throw 'Expected one visible System Pulse tray icon'}
    $icons[0]
}
function Wait-Window {
    $deadline=(Get-Date).AddSeconds(30)
    do {Start-Sleep -Milliseconds 500;$script:app.Refresh()} while(!$script:app.HasExited -and $script:app.MainWindowHandle -eq 0 -and (Get-Date) -lt $deadline)
    if($script:app.HasExited -or $script:app.MainWindowHandle -eq 0) {throw 'No live application window'}
    $script:root=[System.Windows.Automation.AutomationElement]::FromHandle($script:app.MainWindowHandle)
    [PulseRuntimeNative]::SetForegroundWindow($script:app.MainWindowHandle) | Out-Null
    $deadline=(Get-Date).AddSeconds(10)
    do {
        $tabs=@(Descendants $script:root | Where-Object {$_.Current.ControlType.ProgrammaticName -eq 'ControlType.TabItem'})
        if($tabs.Count -eq 10) {return}
        Start-Sleep -Milliseconds 200
    } while((Get-Date) -lt $deadline)
    throw 'Application accessibility tree did not become ready'
}
function Start-App($diagnostics,$prefix) {
    if($diagnostics) {$env:SYSTEM_PULSE_DIAGNOSTICS_PATH=Join-Path $OutputDirectory 'latest.json'}
    else {Remove-Item Env:SYSTEM_PULSE_DIAGNOSTICS_PATH -ErrorAction SilentlyContinue}
    $script:app=Start-Process $script:binary -PassThru -RedirectStandardOutput (Join-Path $OutputDirectory ($prefix+'.stdout')) -RedirectStandardError (Join-Path $OutputDirectory ($prefix+'.stderr'))
    # Retain the native process handle before exit, so ExitCode remains available.
    $null=$script:app.Handle
    Wait-Window
    Start-Sleep -Seconds 5
}
function Quit-App($prefix) {
    $icon=Open-Tray
    $bounds=$icon.Current.BoundingRectangle
    [PulseRuntimeNative]::Click([int]($bounds.X+$bounds.Width/2),[int]($bounds.Y+$bounds.Height/2),$true)
    Start-Sleep -Milliseconds 800
    $handle=[PulseRuntimeNative]::FindWindow('#32768',$null)
    if($handle -eq 0) {throw 'Native tray menu did not open'}
    $menu=[System.Windows.Automation.AutomationElement]::FromHandle($handle)
    if($menu.Current.ProcessId -ne $script:app.Id) {throw 'Menu belongs to another application'}
    $menuOwner=$menu.Current.ProcessId
    $bounds=$menu.Current.BoundingRectangle
    if($bounds.IsEmpty -or $bounds.Height -lt 70 -or $bounds.Height -gt 150) {throw 'Unexpected tray menu geometry'}
    Capture ($prefix+'-menu.png') $bounds
    # The Windows menu exposes only a UIA Pane. Retain its screenshot for review.
    # The application's two-command menu places Quit beneath its separator.
    [PulseRuntimeNative]::Click([int]($bounds.X+$bounds.Width/2),[int]($bounds.Y+$bounds.Height*0.78),$false)
    if(!$script:app.WaitForExit(15000)) {throw 'Tray Quit did not exit within 15 seconds'}
    if($script:app.ExitCode -ne 0) {throw "Nonzero exit: $($script:app.ExitCode)"}
    @{pid=$script:app.Id;exit_code=$script:app.ExitCode;menu_owner=$menuOwner}
}

$script:app=$null
try {
    if($RunId -notmatch '^[a-f0-9]{32}$') {throw 'Invalid run identity'}
    New-Item -ItemType Directory -Path $OutputDirectory -ErrorAction Stop | Out-Null
    $principal=New-Object System.Security.Principal.WindowsPrincipal([System.Security.Principal.WindowsIdentity]::GetCurrent())
    if($principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)) {throw 'Runtime verification must not be elevated'}
    $script:binary=Join-Path $env:USERPROFILE 'workspace\system-pulse-build-target\release\system-pulse.exe'
    $hash=(Get-FileHash $script:binary -Algorithm SHA256).Hash.ToLower()
    if($hash -ne $ExpectedBinarySha256) {throw 'Runtime binary differs from verified Windows build'}
    if(@(Get-Process -Name system-pulse -ErrorAction SilentlyContinue).Count -ne 0) {throw 'Close existing System Pulse instances before verification'}
    $env:SYSTEM_PULSE_STATE_DIR=Join-Path $OutputDirectory 'state'
    $result=@{run_id=$RunId;source_commit=$SourceCommit;binary_sha256=$hash;elevated=$false;started_utc=(Get-Date).ToUniversalTime().ToString('o')}
    $os=Get-CimInstance Win32_OperatingSystem
    $result.host=@{os=$os.Caption;version=$os.Version;visible_memory_bytes=[uint64]$os.TotalVisibleMemorySize*1024;cpu=@(Get-CimInstance Win32_Processor|Select-Object Name,NumberOfCores,NumberOfLogicalProcessors);gpu=@(Get-CimInstance Win32_VideoController|Select-Object Name,DriverVersion)}
    Start-App $true 'diagnostic'
    $result.diagnostic_pid=$script:app.Id
    Copy-Item (Join-Path $OutputDirectory 'latest.json') (Join-Path $OutputDirectory 'initial.json')
    $screens=@()
    foreach($name in @('Summary','CPU','Memory','GPU','Disks','Network','Energy','Thermals','Processes','Settings')) {
        Select-Screen $name
        $screens+=@{screen=$name;selected=$true}
        if($name -in @('Summary','GPU','Thermals','Energy','Processes')) {Capture ($name.ToLower()+'.png') $script:root.Current.BoundingRectangle}
    }
    $result.screens=$screens
    Select-Screen 'Processes'
    $search=Control 'Search name, PID, or user…' 'ControlType.Edit'
    ([System.Windows.Automation.ValuePattern]$search.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)).SetValue('system-pulse.exe')
    Start-Sleep -Seconds 2
    $result.filtered_rows=@(Process-Rows)
    ([System.Windows.Automation.ValuePattern]$search.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)).SetValue('')
    Start-Sleep -Seconds 1
    $sort=@()
    foreach($step in 1,2) {
        $button=Control 'Sort by PID' 'ControlType.Button'
        ([System.Windows.Automation.InvokePattern]$button.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)).Invoke()
        Start-Sleep -Seconds 2
        $sort+=,@(Process-Rows)
    }
    $result.sorted_rows=$sort
    Select-Screen 'Settings'
    foreach($name in @('Light','IBM Plex Sans','IBM Plex Mono','2 s')) {Set-Choice $name $true}
    Start-Sleep -Seconds 2
    Copy-Item (Join-Path $env:SYSTEM_PULSE_STATE_DIR 'workspace.json') (Join-Path $OutputDirectory 'saved-state.json')
    $oldWindow=$script:app.MainWindowHandle
    if(![PulseRuntimeNative]::PostMessage($oldWindow,16,[IntPtr]::Zero,[IntPtr]::Zero)) {throw 'Cannot close dashboard'}
    Start-Sleep -Seconds 3
    $script:app.Refresh()
    if($script:app.HasExited -or [PulseRuntimeNative]::IsWindowVisible($oldWindow)) {throw 'Close did not retain only the tray'}
    $icon=Open-Tray
    ([System.Windows.Automation.InvokePattern]$icon.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)).Invoke()
    Wait-Window
    $result.reopen=@{pid=$script:app.Id;old_window=$oldWindow.ToInt64();new_window=$script:app.MainWindowHandle.ToInt64();hidden=$true;visible=[PulseRuntimeNative]::IsWindowVisible($script:app.MainWindowHandle)}
    foreach($name in @('Light','IBM Plex Sans','IBM Plex Mono','2 s')) {Set-Choice $name $false}
    Copy-Item (Join-Path $OutputDirectory 'latest.json') (Join-Path $OutputDirectory 'final.json')
    $result.diagnostic_quit=Quit-App 'diagnostic'
    $diagnosticHash=(Get-FileHash (Join-Path $OutputDirectory 'latest.json') -Algorithm SHA256).Hash
    Start-App $false 'normal'
    foreach($name in @('Light','IBM Plex Sans','IBM Plex Mono','2 s')) {Set-Choice $name $false}
    $result.normal=@{pid=$script:app.Id;diagnostics_enabled=$false;settings_restored=$true}
    Capture 'restored-settings.png' $script:root.Current.BoundingRectangle
    Select-Screen 'Processes'
    $result.normal.rows=@(Process-Rows)
    $status=@(Descendants $script:root|Where-Object {$_.Current.ControlType.ProgrammaticName -eq 'ControlType.StatusBar'})
    if($status.Count -ne 1) {throw 'Missing normal live status'}
    $result.normal.status=$status[0].Current.Name
    $result.normal.quit=Quit-App 'normal'
    if((Get-FileHash (Join-Path $OutputDirectory 'latest.json') -Algorithm SHA256).Hash -ne $diagnosticHash) {throw 'Normal run wrote diagnostics'}
    if((Get-FileHash $script:binary -Algorithm SHA256).Hash.ToLower() -ne $hash) {throw 'Binary changed during verification'}
    $result.status='PASS'
    $result.finished_utc=(Get-Date).ToUniversalTime().ToString('o')
    Write-Record 'result.json' $result
} catch {
    if(Test-Path $OutputDirectory) {Write-Record 'failure.json' @{run_id=$RunId;error=($_|Out-String)}}
    throw
} finally {
    # Only a process started by this run may be cleaned up after a failed check.
    if($null -ne $script:app -and !$script:app.HasExited) {Stop-Process -Id $script:app.Id -ErrorAction Continue}
}
