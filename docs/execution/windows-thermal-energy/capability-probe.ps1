
$report = [ordered]@{observed_utc=[DateTime]::UtcNow.ToString('o')}
$report['elevated'] = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
foreach ($query in @(
 @{name='thermal_acpi';ns='root/wmi';class='MSAcpi_ThermalZoneTemperature'},
 @{name='thermal_perf';ns='root/cimv2';class='Win32_PerfFormattedData_Counters_ThermalZoneInformation'},
 @{name='battery_status';ns='root/wmi';class='BatteryStatus'},
 @{name='battery_capacity';ns='root/wmi';class='BatteryFullChargedCapacity'},
 @{name='battery_temperature';ns='root/wmi';class='BatteryTemperature'},
 @{name='power_meter';ns='root/cimv2/power';class='Win32_PowerMeter'},
 @{name='lhm_sensors';ns='root/LibreHardwareMonitor';class='Sensor'},
 @{name='ohm_sensors';ns='root/OpenHardwareMonitor';class='Sensor'})) {
 try { $report[$query.name] = @(Get-CimInstance -Namespace $query.ns -ClassName $query.class -ErrorAction Stop | Select-Object * -ExcludeProperty CimClass,CimInstanceProperties,CimSystemProperties,PSComputerName) }
 catch { $report[$query.name] = @{error=$_.Exception.Message} }
}
$report['drivers'] = @(Get-CimInstance Win32_SystemDriver | Where-Object {$_.Name -match 'Pawn|WinRing|Libre|OpenHardware|HWiNFO|Energy|Dptf|Esif'} | Select-Object Name,State,StartMode,PathName)
$report['pawn_install'] = Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\PawnIO'
try { $report['disk_reliability'] = @(Get-PhysicalDisk | Get-StorageReliabilityCounter -ErrorAction Stop | Select-Object DeviceId,Temperature,TemperatureMax) }
catch { $report['disk_reliability'] = @{error=$_.Exception.Message} }
$report['emi_interfaces'] = (& pnputil.exe /enum-interfaces /enabled /class '{45BD8344-7ED6-49cf-A440-C276C933B053}' 2>&1 | Out-String)
$report['thermal_devices'] = @(Get-PnpDevice -PresentOnly | Where-Object {$_.FriendlyName -match 'Thermal|Dynamic Tuning|Innovation Platform|Energy'} | Select-Object Class,FriendlyName,InstanceId,Status)
$report | ConvertTo-Json -Depth 6
