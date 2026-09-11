
$ErrorActionPreference='Stop'
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
public static class ThermalProbe {
 [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
 public static extern SafeFileHandle CreateFile(string p,uint access,uint share,IntPtr security,uint creation,uint flags,IntPtr template);
 [DllImport("kernel32.dll", SetLastError=true)]
 public static extern bool DeviceIoControl(SafeFileHandle h,uint code,byte[] input,uint inputSize,byte[] output,uint size,out uint returned,IntPtr overlapped);
 public static int Load(SafeFileHandle h,byte[] module) {
  uint returned;
  return DeviceIoControl(h,0xA1B22084,module,(uint)module.Length,null,0,out returned,IntPtr.Zero)?0:Marshal.GetLastWin32Error();
 }
 public static object Read(SafeFileHandle h,uint register) {
  byte[] input=new byte[40]; byte[] name=System.Text.Encoding.ASCII.GetBytes("ioctl_read_msr");Array.Copy(name,input,name.Length);
  Array.Copy(BitConverter.GetBytes((ulong)register),0,input,32,8);
  byte[] output=new byte[8];uint returned;
  bool ok=DeviceIoControl(h,0xA1B22104,input,40,output,8,out returned,IntPtr.Zero);
  int error=ok?0:Marshal.GetLastWin32Error();
  return new {register=register,ok=ok,error=error,returned=returned,value=ok&&returned==8?(ulong?)BitConverter.ToUInt64(output,0):null};
 }
}
'@
$module='C:\Users\shawn\workspace\IntelMSR-0.2.11.bin'
if((Get-FileHash $module -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'd6ed85d65ab17a22f813ef98207d6d537155ee2ded5976a21cb48413c9b92e5f'){throw 'Module hash mismatch'}
$r=[ordered]@{observed_utc=[DateTime]::UtcNow.ToString('o');elevated=([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)}
$h=[ThermalProbe]::CreateFile('\\?\GLOBALROOT\Device\PawnIO',3,3,[IntPtr]::Zero,3,0,[IntPtr]::Zero)
$r['open_error']=if($h.IsInvalid){[Runtime.InteropServices.Marshal]::GetLastWin32Error()}else{0}
try{
 if(!$h.IsInvalid){
  $r['load_error']=[ThermalProbe]::Load($h,[IO.File]::ReadAllBytes($module))
  if($r['load_error'] -eq 0){$r['samples']=@(for($i=0;$i -lt 3;$i++){@{target=[ThermalProbe]::Read($h,418);core=[ThermalProbe]::Read($h,412);package=[ThermalProbe]::Read($h,433)};Start-Sleep -Seconds 1})}
 }
}finally{$h.Dispose()}
$r | ConvertTo-Json -Depth 6
