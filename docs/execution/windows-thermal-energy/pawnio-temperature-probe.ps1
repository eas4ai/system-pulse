$ErrorActionPreference = 'Stop'

Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Text;
using Microsoft.Win32.SafeHandles;

public static class ThermalProbe {
 private const uint RelationProcessorPackage = 3;

 [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
 public static extern SafeFileHandle CreateFile(string path, uint access, uint share,
  IntPtr security, uint creation, uint flags, IntPtr template);

 [DllImport("kernel32.dll", SetLastError=true)]
 public static extern bool DeviceIoControl(SafeFileHandle handle, uint code,
  byte[] input, uint inputSize, byte[] output, uint outputSize,
  out uint returned, IntPtr overlapped);

 [DllImport("kernel32.dll", EntryPoint="GetLogicalProcessorInformationEx",
  SetLastError=true)]
 private static extern bool GetLogicalProcessorInformationEx(uint relationship,
  IntPtr buffer, ref uint length);

 public static int Load(SafeFileHandle handle, byte[] module) {
  uint returned;
  return DeviceIoControl(handle, 0xA1B22084, module, (uint)module.Length,
   null, 0, out returned, IntPtr.Zero) ? 0 : Marshal.GetLastWin32Error();
 }

 public static uint PackageCount() {
  uint length = 0;
  bool complete = GetLogicalProcessorInformationEx(
   RelationProcessorPackage, IntPtr.Zero, ref length);
  int error = Marshal.GetLastWin32Error();
  if (complete || error != 122 || length < 8)
   throw new Win32Exception(error, "Could not size processor-package topology");
  IntPtr buffer = Marshal.AllocHGlobal(checked((int)length));
  try {
   if (!GetLogicalProcessorInformationEx(RelationProcessorPackage, buffer, ref length))
    throw new Win32Exception(Marshal.GetLastWin32Error(),
     "Could not read processor-package topology");
   uint count = 0;
   uint offset = 0;
   while (offset < length) {
    if (length - offset < 8)
     throw new InvalidOperationException("Truncated processor topology record");
    uint relationship = unchecked((uint)Marshal.ReadInt32(buffer, (int)offset));
    uint size = unchecked((uint)Marshal.ReadInt32(buffer, (int)offset + 4));
    if (size < 8 || size > length - offset)
     throw new InvalidOperationException("Invalid processor topology record size");
    if (relationship == RelationProcessorPackage) count++;
    offset += size;
   }
   return count;
  } finally { Marshal.FreeHGlobal(buffer); }
 }

 public static object ReadMsr(SafeFileHandle handle, uint register) {
  byte[] input = new byte[40];
  byte[] name = Encoding.ASCII.GetBytes("ioctl_read_msr\0");
  Array.Copy(name, input, name.Length);
  Array.Copy(BitConverter.GetBytes((ulong)register), 0, input, 32, 8);
  byte[] output = new byte[8];
  uint returned;
  bool ok = DeviceIoControl(handle, 0xA1B22104, input, 40, output, 8,
   out returned, IntPtr.Zero);
  int error = ok ? 0 : Marshal.GetLastWin32Error();
  return new {
   register = register, ok = ok, error = error, returned = returned,
   value = ok && returned == 8 ? (ulong?)BitConverter.ToUInt64(output, 0) : null
  };
 }

 public static object ReadAmdTemperature(SafeFileHandle handle) {
  const ulong TemperatureOffset = 0x59800;
  byte[] input = new byte[40];
  byte[] name = Encoding.ASCII.GetBytes("ioctl_read_smn\0");
  Array.Copy(name, input, name.Length);
  Array.Copy(BitConverter.GetBytes(TemperatureOffset), 0, input, 32, 8);
  byte[] output = new byte[8];
  uint returned;
  bool ok = DeviceIoControl(handle, 0xA1B22104, input, 40, output, 8,
   out returned, IntPtr.Zero);
  int error = ok ? 0 : Marshal.GetLastWin32Error();
  return new {
   offset = TemperatureOffset, ok = ok, error = error, returned = returned,
   value = ok && returned == 8 ? (ulong?)BitConverter.ToUInt64(output, 0) : null
  };
 }
}
'@

function Read-AmdTemperatureSample {
    param($Handle)
    $mutex = [Threading.Mutex]::new($false, 'Global\Access_PCI')
    $ownsMutex = $false
    try {
        try {
            $ownsMutex = $mutex.WaitOne(250)
        } catch [Threading.AbandonedMutexException] {
            $ownsMutex = $true
        }
        if (!$ownsMutex) { throw 'Timed out acquiring the bounded PawnIO PCI mutex' }
        $before = [Diagnostics.Stopwatch]::GetTimestamp()
        $read = [ThermalProbe]::ReadAmdTemperature($Handle)
        $after = [Diagnostics.Stopwatch]::GetTimestamp()
        return [ordered]@{
            amd_thm_tcon_cur_tmp = $read
            amd_reserved = [uint64]0
            query_before_qpc = $before
            query_after_qpc = $after
            query_qpc_frequency = [Diagnostics.Stopwatch]::Frequency
            observed_utc = [DateTime]::UtcNow.ToString('o')
        }
    } finally {
        if ($ownsMutex) { $mutex.ReleaseMutex() }
        $mutex.Dispose()
    }
}

function Read-IntelTemperatureSample {
    param($Handle)
    $before = [Diagnostics.Stopwatch]::GetTimestamp()
    $target = [ThermalProbe]::ReadMsr($Handle, 0x1A2)
    $core = [ThermalProbe]::ReadMsr($Handle, 0x19C)
    $package = [ThermalProbe]::ReadMsr($Handle, 0x1B1)
    $after = [Diagnostics.Stopwatch]::GetTimestamp()
    return [ordered]@{
        target = $target
        core = $core
        package = $package
        query_before_qpc = $before
        query_after_qpc = $after
        query_qpc_frequency = [Diagnostics.Stopwatch]::Frequency
        observed_utc = [DateTime]::UtcNow.ToString('o')
    }
}

$processors = @(Get-CimInstance Win32_Processor -ErrorAction Stop)
if ($processors.Count -ne 1) { throw 'Expected one Win32_Processor package' }
$manufacturer = ([string]$processors[0].Manufacturer).Trim().ToLowerInvariant()
$processorId = ([string]$processors[0].ProcessorId).Trim()
if ($processorId -notmatch '^[0-9a-fA-F]{16}$') {
    throw 'Win32_Processor did not return the 16-digit CPUID signature'
}
$signatures = @(foreach ($offset in @(0, 8)) {
    $eax = [Convert]::ToUInt32($processorId.Substring($offset, 8), 16)
    $baseFamily = [int](($eax -shr 8) -band 0xF)
    $family = if ($baseFamily -eq 0xF) {
        $baseFamily + [int](($eax -shr 20) -band 0xFF)
    } else { $baseFamily }
    $baseModel = [int](($eax -shr 4) -band 0xF)
    $model = if ($baseFamily -eq 0x6 -or $baseFamily -eq 0xF) {
        ([int](($eax -shr 16) -band 0xF) -shl 4) -bor $baseModel
    } else { $baseModel }
    [pscustomobject]@{ family = $family; model = $model }
})
$intelVendor = @('intel', 'genuineintel') -contains $manufacturer
$amdVendor = @('amd', 'authenticamd', 'advanced micro devices, inc.') -contains $manufacturer
if ($intelVendor) {
    $expectedFamily = 0x6
    $expectedModel = 0x9A
} elseif ($amdVendor) {
    $expectedFamily = 0x19
    $expectedModel = 0x21
} else {
    throw 'CPU vendor is not supported by this fixed thermal probe'
}
$matchingSignature = @($signatures | Where-Object {
    $_.family -eq $expectedFamily -and $_.model -eq $expectedModel
})
if ($matchingSignature.Count -ne 1) {
    throw 'CPUID signature is not one of the supported thermal CPU models'
}
$family = $matchingSignature[0].family
$model = $matchingSignature[0].model

if ($intelVendor -and $family -eq 0x6 -and $model -eq 0x9A) {
    $backend = 'intel'
    $module = Join-Path $PSScriptRoot '..\..\..\vendor\pawnio-intel-msr\IntelMSR.bin'
    $moduleHash = 'd6ed85d65ab17a22f813ef98207d6d537155ee2ded5976a21cb48413c9b92e5f'
    $source = 'PawnIO / Intel package digital thermal sensor / signed module 0.2.11'
} elseif ($amdVendor -and $family -eq 0x19 -and $model -eq 0x21) {
    $backend = 'amd_zen3'
    $module = Join-Path $PSScriptRoot '..\..\..\vendor\pawnio-amd-smn\AMDFamily17.bin'
    $moduleHash = 'dae74615761b78bdf064dfb3e136252ddcc6fc727d88f14738d0e5800d427a91'
    $source = 'PawnIO / AMD Zen 3 package Tctl/Tdie / signed module 0.2.11'
} else {
    throw 'CPU vendor, family or model is not supported by this fixed thermal probe'
}

$module = (Resolve-Path $module -ErrorAction Stop).Path
if ((Get-FileHash $module -Algorithm SHA256).Hash.ToLowerInvariant() -ne $moduleHash) {
    throw 'Signed PawnIO module hash mismatch'
}
$packageCount = [ThermalProbe]::PackageCount()
if ($packageCount -ne 1) {
    throw "Expected exactly one processor package; found $packageCount"
}
$elevated = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)
$result = [ordered]@{
    backend = $backend
    source = $source
    processor_family = $family
    processor_model = $model
    package_count = $packageCount
    module_sha256 = $moduleHash
    observed_utc = [DateTime]::UtcNow.ToString('o')
    elevated = $elevated
}
$handle = [ThermalProbe]::CreateFile('\\?\GLOBALROOT\Device\PawnIO', 3, 3,
    [IntPtr]::Zero, 3, 0, [IntPtr]::Zero)
$result['open_error'] = if ($handle.IsInvalid) {
    [Runtime.InteropServices.Marshal]::GetLastWin32Error()
} else { 0 }
try {
    if (!$handle.IsInvalid) {
        $result['load_error'] = [ThermalProbe]::Load($handle, [IO.File]::ReadAllBytes($module))
        if ($result['load_error'] -eq 0) {
            $result['samples'] = @(for ($i = 0; $i -lt 3; $i++) {
                if ($backend -eq 'intel') {
                    Read-IntelTemperatureSample $handle
                } else {
                    Read-AmdTemperatureSample $handle
                }
                Start-Sleep -Seconds 1
            })
        }
    }
} finally {
    $handle.Dispose()
}
$result | ConvertTo-Json -Depth 8
