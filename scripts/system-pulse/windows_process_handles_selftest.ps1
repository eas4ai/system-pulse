# Verify the native counter against real opened/closed handles to our own child.
param(
    [Parameter(Mandatory=$true)][string]$Fixture,
    [Parameter(Mandatory=$true)][string]$HandlesSource,
    [Parameter(Mandatory=$true)][string]$FaultSource,
    [Parameter(Mandatory=$true)][string]$Output
)
$ErrorActionPreference='Stop'
Add-Type -Path $FaultSource
[PulseOwnedProcessFault]::RemoveObserverDebugPrivilege()
Add-Type -Path $HandlesSource
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class PulseOwnedHandleProbe {
    [DllImport("kernel32.dll",SetLastError=true)]
    public static extern IntPtr OpenProcess(uint access,bool inherit,int pid);
    [DllImport("kernel32.dll",SetLastError=true)]
    public static extern bool CloseHandle(IntPtr handle);
}
'@
$result=@{status='FAIL';observer_debug_privilege_removed=$true;checks=@();samples=@()}
$child=$null
$guard=$null
$probe=[IntPtr]::Zero
try {
    $log=Join-Path (Split-Path -Parent $Output) 'handle-fixture.log'
    $child=Start-Process $Fixture -ArgumentList @('windowless',('"'+$log+'"')) -PassThru
    $null=$child.Handle
    $guard=[PulseOwnedProcessFault]::new($child)
    $ids=[uint32[]]@($child.Id)
    foreach($access in @(0x100000,0x101000,0x101001)) {
        $before=[PulseProcessHandles]::Capture([IntPtr](-1),$ids)
        $probe=[PulseOwnedHandleProbe]::OpenProcess($access,$false,$child.Id)
        if($probe -eq [IntPtr]::Zero){throw 'Could not open an owned positive-control handle'}
        $open=[PulseProcessHandles]::Capture([IntPtr](-1),$ids)
        if($open.process_handles[0].count -ne $before.process_handles[0].count+1){throw 'Native snapshot missed the deliberately retained process handle'}
        $terminationDelta=$(if(($access -band 1) -ne 0){1}else{0})
        if($open.process_handles[0].termination_count -ne $before.process_handles[0].termination_count+$terminationDelta){throw 'Native snapshot misclassified termination rights'}
        if(![PulseOwnedHandleProbe]::CloseHandle($probe)){throw 'Positive-control handle did not close'}
        $probe=[IntPtr]::Zero
        $after=[PulseProcessHandles]::Capture([IntPtr](-1),$ids)
        if($after.process_handles[0].count -ne $before.process_handles[0].count){throw 'Native snapshot did not observe the closed process handle'}
        $result.samples+=@{access=$access;before=$before;open=$open;after=$after}
    }
    $result.checks+='sync-query-and-termination-handles-observed-open-and-closed'
    $result.foreign_snapshot=[PulseProcessHandles]::Capture($child.Handle,[uint32[]]@($PID))
    $result.checks+='owned-foreign-process-snapshot-released'
    $result.status='PASS'
} catch {$result.error=$_.Exception.ToString()}
finally {
    if($probe -ne [IntPtr]::Zero -and ![PulseOwnedHandleProbe]::CloseHandle($probe)){$result.status='FAIL';$result.cleanup_error='Positive-control handle cleanup failed'}
    if($guard){try{$guard.Dispose()}catch{$result.status='FAIL';$result.cleanup_error=$_.Exception.ToString()}}
    if($child){try{$result.target_cleaned=$child.WaitForExit(5000);if(!$result.target_cleaned){throw 'Owned child survived cleanup'}}catch{$result.status='FAIL';$result.cleanup_error=$_.Exception.ToString()}finally{$child.Dispose()}}
    $result|ConvertTo-Json -Depth 25|Set-Content -LiteralPath $Output -Encoding UTF8
}
if($result.status -ne 'PASS'){Write-Error $result.error;exit 1}
Write-Output 'PASS: native handle positive controls, released snapshots and owned child cleanup'
