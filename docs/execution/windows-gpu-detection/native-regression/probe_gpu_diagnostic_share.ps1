$ErrorActionPreference='Stop'
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class RenameProbe {
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)]
 public static extern bool MoveFileExW(string source,string target,uint flags);
}
'@
$directory=Join-Path $env:TEMP ('pulse-gpu-share-'+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory $directory | Out-Null
$results=@()
try {
 foreach($share in @([IO.FileShare]::ReadWrite,([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))) {
  $target=Join-Path $directory 'latest.json'
  $source=Join-Path $directory 'latest.tmp'
  [IO.File]::WriteAllText($target,'old')
  [IO.File]::WriteAllText($source,'new')
  $reader=New-Object IO.FileStream($target,[IO.FileMode]::Open,[IO.FileAccess]::Read,$share)
  try {
   $success=[RenameProbe]::MoveFileExW($source,$target,1)
   $errorCode=[Runtime.InteropServices.Marshal]::GetLastWin32Error()
   $results+=@{share=[string]$share;rename=$success;error=$errorCode}
   $reader.Dispose()
   $success=[RenameProbe]::MoveFileExW($source,$target,1)
   $results+=@{share='closed';rename=$success;error=[Runtime.InteropServices.Marshal]::GetLastWin32Error()}
  } finally {$reader.Dispose()}
 }
 ConvertTo-Json -InputObject $results
} finally {Remove-Item -Recurse $directory}
