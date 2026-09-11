# Windows thermal and energy execution

Current: driver/access decision approved; collector/helper and installer work in progress. Native candidate acceptance remains pending.

## Native observations

The retained capability probe ran through SSH with an elevated token. Standard
ACPI temperature queries returned Not supported, thermal performance counters and
battery temperature returned no instances. No PawnIO installation/driver or
LibreHardwareMonitor/OpenHardwareMonitor WMI provider was found. Storage
reliability reported SSD temperature 32 C; unelevated storage access has not yet
been established. The battery was full and online, with zero charge/discharge
rate. These are distinct scopes, not CPU package readings.

An enabled EMI interface identifies the i7-1250U. Both elevated and interactive
Limited probes opened it and read version 2, metadata and three current samples.
OEM Microsoft / model PPM exposes RAPL package, DRAM, PP0 and PP1 channels.
Package, PP0 and PP1 counters advanced. Unelevated package deltas correspond to
2.80 and 3.61 watts using the documented picowatt-hour/100ns units. DRAM remained
zero, which does not prove a supported DRAM counter. Full probes and raw bytes
are retained; these capability observations are not packaged acceptance or an
independent physical accuracy comparison.

The first EMI probe failed before opening the device because PowerShell 5.1
interpreted a hexadecimal access mask as signed. The corrected decimal value
produced the retained records. Limited scheduled tasks were stopped/unregistered.
No sensor driver was installed, no hardware register was written and no Windows
power setting was changed.

## Reference findings

- Cores 0.43 delegates Windows hardware monitoring to LibreHardwareMonitor.
- LibreHardwareMonitor 0.9.6 IntelCpu uses IntelMsr/PawnIO to read temperature target, core/package thermal status and RAPL energy registers. Its generic PawnIo Execute returns zero-filled output on failure; System Pulse must not copy that failure behavior.
- hwinfo-c-11 Windows CPU source supplies inventory/utilization/frequency, not an alternative CPU thermal/energy source.
- [PawnIO.Modules](https://github.com/namazso/PawnIO.Modules) provides signed modules. Reviewed IntelMSR source at 52a7e536dff3e53c96917a28caac5e0fa6510696: read allowlist includes 0x1a2, 0x19c and 0x1b1, while the module also exposes write functions. System Pulse must expose only fixed sensor reads.
- [PawnPP](https://github.com/namazso/PawnPP) is the C++ Pawn bytecode interpreter; it does not independently grant hardware access. No need to embed another interpreter in the application.
- PawnIO driver source at 9d52965895588b0ffa3703b72eec75ba19f4ccc0 has an INF security descriptor granting access to SYSTEM and administrators. Preserve this boundary; use an authorized restricted helper rather than elevating the dashboard or relaxing driver access.
- [Microsoft EMI documentation](https://learn.microsoft.com/en-us/windows-hardware/drivers/powermeter/energy-meter-interface) describes native energy metadata and readings. [Channel data](https://learn.microsoft.com/en-us/windows/win32/api/emi/ns-emi-emi_channel_measurement_data) specifies 100ns timestamps.
- [Official PawnIO integration guidance](https://github.com/namazso/PawnIO.Modules/wiki/Using-PawnIO-Modules) separates driver installation, modules and user library. Retain applicable source/notices for any distributed module.

## Reviewable installer

Official [PawnIO.Setup 2.2.0](https://github.com/namazso/PawnIO.Setup/releases/tag/2.2.0)
was downloaded and staged on the tablet for review only. SHA-256
1f519a22e47187f70a1379a48ca604981c4fcf694f4e65b734aaa74a9fba3032
matches the release asset digest. Windows Authenticode reports Valid, signer
namazso.eu, version 2.2.0.0. The retained installer-review record says executed
false. Use the official signed edition; do not disable Windows security settings.

Graph transport was unavailable; focused reference/source inspection used Tilth.

## Approved implementation and signing progress

The developer approved the official driver and restricted helper. The subsequent
pawnio-install.json records successful installation of the verified 2.2.0 setup
and a running demand-start driver. The earlier review-only and no-driver records
above describe the investigation before that approval.

The fixed-register probe returned valid Intel package temperature operands.
The same probe under an interactive Limited token failed with access denied (5),
confirming why the unelevated dashboard needs a separate authorized helper.
These are source capability observations, not acceptance of the production helper.

Winboat was started through its existing Docker Compose file. The guest API
responded, and the existing sign.cmd signed a copy of the previous GPU application
build. Authenticode and signtool verification both passed. The retained signing
probe identifies that older-build limitation; it does not prove the thermal
candidate or installer. The pinned Inno Setup 6.4.3 compiler was installed in the
user's SystemPulseBuildTools directory after hash and signature verification.

Independent thermal specification review found that a synchronous driver call
could outlive the dashboard. A helper watchdog fix and stalled-read demonstration
are required before native acceptance. See the current commitment review.
