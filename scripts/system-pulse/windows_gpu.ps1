# The runner supplies runtime helper functions and a verified packaged binary.
function Write-GpuRecord($name,$value) {
    [IO.File]::WriteAllText((Join-Path $OutputDirectory $name),(ConvertTo-Json -InputObject $value -Depth 30))
}
$script:app=$null
try {
    New-Item -ItemType Directory -Path $OutputDirectory -ErrorAction Stop | Out-Null
    $principal=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    if($principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {throw 'GPU observation must remain unelevated'}
    if((Get-FileHash $script:binary -Algorithm SHA256).Hash.ToLower() -ne $ExpectedBinarySha256) {throw 'GPU binary hash mismatch'}
    if(@(Get-Process -Name system-pulse -ErrorAction SilentlyContinue).Count -ne 0) {throw 'Existing System Pulse instance prevents isolated observation'}
    $env:SYSTEM_PULSE_STATE_DIR=Join-Path $OutputDirectory 'state'
    $inventory=@(Get-CimInstance Win32_VideoController | Select-Object Name,PNPDeviceID,Status,DriverVersion)
    Write-GpuRecord 'inventory.json' $inventory
    Start-App $true 'gpu'
    Select-Screen 'GPU'
    $frames=@()
    $independent=@()
    $last=0
    foreach($iteration in 1..8) {
        $counter=Get-Counter -Counter '\GPU Adapter Memory(*)\Dedicated Usage','\GPU Adapter Memory(*)\Shared Usage','\GPU Engine(*)\Utilization Percentage' -SampleInterval 1 -MaxSamples 2 -ErrorAction Stop
        $independent+=@($counter | ForEach-Object {
            @{utc=$_.Timestamp.ToUniversalTime().ToString('o'); counters=@($_.CounterSamples | ForEach-Object {
                @{path=$_.Path;instance=$_.InstanceName;status=[uint32]$_.Status;value=$_.CookedValue}
            })}
        })
        $frame=Get-Content -Raw (Join-Path $OutputDirectory 'latest.json') | ConvertFrom-Json
        if($frame.application_pid -ne $script:app.Id) {throw 'Diagnostic frame belongs to another process'}
        if($frame.snapshot.sequence -le $last) {throw 'GPU sampling did not advance'}
        $last=$frame.snapshot.sequence
        $frames+=,$frame.snapshot
    }
    Write-GpuRecord 'frames.json' $frames
    Write-GpuRecord 'independent-readings.json' $independent
    $controls=@(Descendants $script:root | ForEach-Object {
        @{name=$_.Current.Name;role=$_.Current.ControlType.ProgrammaticName;offscreen=$_.Current.IsOffscreen}
    })
    Write-GpuRecord 'gpu-ui.json' @{pid=$script:app.Id;controls=$controls;selected_screen='GPU';sequence=$last}
    Capture 'gpu.png' $script:root.Current.BoundingRectangle
    Select-Screen 'Processes'
    $processRows=@(Process-Rows)
    $quit=Quit-App 'gpu'
    if((Get-FileHash $script:binary -Algorithm SHA256).Hash.ToLower() -ne $ExpectedBinarySha256) {throw 'GPU binary changed during observation'}
    $diagnosticHash=(Get-FileHash (Join-Path $OutputDirectory 'latest.json') -Algorithm SHA256).Hash
    Start-App $false 'normal'
    Select-Screen 'GPU'
    $normalControls=@(Descendants $script:root | ForEach-Object {
        @{name=$_.Current.Name;role=$_.Current.ControlType.ProgrammaticName;offscreen=$_.Current.IsOffscreen}
    })
    Capture 'normal-gpu.png' $script:root.Current.BoundingRectangle
    Select-Screen 'Processes'
    $normalRows=@(Process-Rows)
    $normalQuit=Quit-App 'normal'
    if((Get-FileHash (Join-Path $OutputDirectory 'latest.json') -Algorithm SHA256).Hash -ne $diagnosticHash) {throw 'Normal launch wrote diagnostics'}
    Write-GpuRecord 'preservation.json' @{diagnostics_enabled=$false;diagnostic_rows=$processRows;normal_rows=$normalRows;normal_gpu=@{selected_screen='GPU';pid=$normalQuit.pid;sequence=$last;controls=$normalControls};quit=$normalQuit}
    Write-GpuRecord 'result.json' @{status='PASS';run_id=$RunId;source_commit=$SourceCommit;binary_sha256=$ExpectedBinarySha256;elevated=$false;cleanup=$true;quit=$quit}
} catch {
    if(Test-Path $OutputDirectory) {Write-GpuRecord 'failure.json' @{error=($_|Out-String)}}
    throw
} finally {
    if($null -ne $script:app -and !$script:app.HasExited) {
        Stop-Process -Id $script:app.Id -ErrorAction Continue
        $script:app.WaitForExit(15000) | Out-Null
    }
}
