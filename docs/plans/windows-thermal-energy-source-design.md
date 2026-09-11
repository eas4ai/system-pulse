# Proposed Windows thermal and energy sources

The confirmed commitment is [WTE-001](../spec/windows-thermal-energy.md).
The source investigation and raw observations are [retained](../execution/windows-thermal-energy/status.md).

## Recommended approach

Use native Windows EMI for energy and derived power. Discover interfaces with
SetupAPI and retain device plus channel identity. Parse versioned metadata with
strict bounds and units; preserve raw integer observations. Derive watts from
counter differences and source timestamps. Reset on failure, removal, changed
metadata or counter rollback. Never add package and component domains together.
A zero-only unsupported domain must not become a verified measured channel.

For Intel CPU temperature, use the official signed PawnIO driver and a pinned
official IntelMSR module through a separate opt-in helper. The app remains
unelevated. The helper accepts only a fixed sensor-sampling operation, never
arbitrary registers, module paths, IOCTL names or writes. Authenticate its caller,
bound output and lifetime, terminate collection when the requesting app exits,
and reject malformed/partial replies. Retain raw temperature status and target,
validate support and validity bits and restore processor affinity. Verify the
helper and pinned module provenance before use. No automatic startup service
or weakened driver permissions is proposed.

Battery energy/rate and available storage temperatures retain their own device
labels and availability; establish normal-user access before promising those
readings in the unelevated app. Existing Energy/Thermals pages receive real
sensors and explicit missing-source reasons. Keep Linux/macOS and Windows
GPU/process behavior unchanged.

## Alternatives

1. Native sources only: implement EMI and supported battery/storage sources, but leave CPU temperatures unavailable. Smaller deployment; does not fill CPU thermal monitoring.
2. Use an external LibreHardwareMonitor provider: requires another running application/service and its sensor-access setup, adds .NET/process/provider lifetime dependencies. It is not present on this tablet.
3. Recommended: native EMI plus the narrow PawnIO temperature helper. Adds a signed kernel driver and a privileged helper to install, maintain and test, but provides the intended CPU temperature path without elevating the dashboard.

## Verification before completion

Unit tests cover metadata sizes, units, duplicate/channel identities, counter
resets, unsupported data and thermal validity. Helper tests must reject malformed
requests and establish caller/provenance, bounded lifetime and absence of write
operations. Native package observations compare independent readings, normal
and denied helper access, sampling progress and screen availability. Run platform
preservation and record actual failure demonstrations before Cairn acceptance.

## Decision needed

Authorize installation of the staged official signed PawnIO 2.2.0 on the tablet
and implementation/native testing of the restricted temperature helper, alongside
the already confirmed native energy work. Installation adds kernel-mode code;
a driver fault can affect Windows stability. The module itself has broader
capabilities than this application's read-only interface. No unsigned edition,
security-setting changes, arbitrary register access, persistent service, hosted
CI or publication is included.
