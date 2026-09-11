
$ErrorActionPreference='Stop'
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
public static class EmiProbe {
 [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
 public static extern SafeFileHandle CreateFile(string p,uint access,uint share,IntPtr security,uint creation,uint flags,IntPtr template);
 [DllImport("kernel32.dll", SetLastError=true)]
 public static extern bool DeviceIoControl(SafeFileHandle h,uint code,IntPtr input,uint inputSize,byte[] output,uint size,out uint returned,IntPtr overlapped);
 public static object Read(SafeFileHandle h,uint code,int size) {
  byte[] bytes=new byte[size]; uint returned;
  bool ok=DeviceIoControl(h,code,IntPtr.Zero,0,bytes,(uint)size,out returned,IntPtr.Zero);
  int error=ok?0:Marshal.GetLastWin32Error();
  if(returned>bytes.Length) throw new Exception("invalid return length");
  Array.Resize(ref bytes,(int)returned);
  return new {ok=ok,error=error,returned=returned,hex=BitConverter.ToString(bytes)};
 }
}
'@
$path='\\?\ACPI#GenuineIntel_-_Intel64_Family_6_Model_154_-_12th_Gen_Intel(R)_Core(TM)_i7-1250U#0#{45bd8344-7ed6-49cf-a440-c276c933b053}'
$r=[ordered]@{elevated=([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator);path=$path}
$h=[EmiProbe]::CreateFile($path,2147483648,3,[IntPtr]::Zero,3,0,[IntPtr]::Zero)
$r['open_error']=if($h.IsInvalid){[Runtime.InteropServices.Marshal]::GetLastWin32Error()}else{0}
try {
 if(!$h.IsInvalid) {
  $r['version']=[EmiProbe]::Read($h,2244608,2)
  $r['metadata_size']=[EmiProbe]::Read($h,2244612,4)
  $r['metadata']=[EmiProbe]::Read($h,2244616,65536)
  $r['samples']=@(for($i=0;$i -lt 3;$i++){[EmiProbe]::Read($h,2244620,256);Start-Sleep -Milliseconds 1000})
 }
} finally {$h.Dispose()}
$r | ConvertTo-Json -Depth 6
