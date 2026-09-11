$ErrorActionPreference='Stop'
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class GpuLuidProbe {
    [StructLayout(LayoutKind.Sequential)] public struct Open {public IntPtr name; public uint handle; public uint low; public int high;}
    [StructLayout(LayoutKind.Sequential)] public struct Close {public uint handle;}
    [DllImport("cfgmgr32.dll",CharSet=CharSet.Unicode)] public static extern uint CM_Get_Device_Interface_List_SizeW(out uint size,ref Guid guid,string device,uint flags);
    [DllImport("cfgmgr32.dll",CharSet=CharSet.Unicode)] public static extern uint CM_Get_Device_Interface_ListW(ref Guid guid,string device,[Out] char[] data,uint size,uint flags);
    [DllImport("gdi32.dll")] public static extern int D3DKMTOpenAdapterFromDeviceName(ref Open request);
    [DllImport("gdi32.dll")] public static extern int D3DKMTCloseAdapter(ref Close request);
}
'@
$guid=[Guid]'1ca05180-a699-450a-9a0c-de4fbe3ddd89'
$records=@()
foreach($device in @(Get-CimInstance Win32_VideoController)) {
    [uint32]$size=0
    $status=[GpuLuidProbe]::CM_Get_Device_Interface_List_SizeW([ref]$size,[ref]$guid,$device.PNPDeviceID,0)
    if($status -ne 0 -or $size -gt 65536){throw "CM size failed $status / $size"}
    $buffer=New-Object char[] $size
    $status=[GpuLuidProbe]::CM_Get_Device_Interface_ListW([ref]$guid,$device.PNPDeviceID,$buffer,$size,0)
    if($status -ne 0){throw "CM list failed $status"}
    foreach($name in ((-join $buffer).Split([char]0) | Where-Object {$_})) {
        $request=New-Object GpuLuidProbe+Open
        $request.name=[Runtime.InteropServices.Marshal]::StringToHGlobalUni($name)
        try {
            $status=[GpuLuidProbe]::D3DKMTOpenAdapterFromDeviceName([ref]$request)
            $record=@{pnp=$device.PNPDeviceID;interface=$name;open_status=$status;luid_low=$request.low;luid_high=$request.high}
            if($status -ge 0) {
                $close=New-Object GpuLuidProbe+Close
                $close.handle=$request.handle
                $record.close_status=[GpuLuidProbe]::D3DKMTCloseAdapter([ref]$close)
            }
            $records+=,$record
        } finally {[Runtime.InteropServices.Marshal]::FreeHGlobal($request.name)}
    }
}
ConvertTo-Json -InputObject $records -Depth 4
