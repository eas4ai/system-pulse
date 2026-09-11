# Windows thermal and energy collection

Status: Agreed 2026-09-11
Prefix: WTE

The developer confirmed Windows thermal and energy collection as the next
commitment after Windows GPU detection. Investigate the supplied hardware-monitor
references and actual sources on the i7-1250U/Iris Xe tablet, then implement and
verify supported real readings. Driver installation requires a separate decision.

[WTE-001] Windows MUST expose supported real thermal and energy/power readings on the available tablet through identified native sources, with explicit units, device scope, stable sensor identity and availability. Unsupported sources MUST explain their absence and MUST NOT produce fabricated zeros or mislabeled quantities. The implementation MUST preserve unelevated dashboard operation, Windows GPU and process controls, and Linux/macOS collection.
Falsifier: an independently observable supported reading is omitted without explanation; a value has the wrong unit, device scope or freshness; an unavailable source is represented as measured zero; a required privilege or driver is introduced without a separate decision; or preserved collection/process behavior regresses.
Mechanism: investigate native capabilities and the supplied Cores, LibreHardwareMonitor and hwinfo references; compare supported readings with independent native observations; test unit conversion, identity, unsupported/error and refresh boundaries; inspect the packaged Energy and Thermals screens and run platform preservation checks. If access requires a driver or no trustworthy source is available, record a concrete decision before implementation proceeds. Unsupported-only output does not establish successful sensor collection.

Temperature means an identified sensor's physical temperature, not an arbitrary
ACPI zone relabeled as CPU package temperature. Power is a rate in watts; energy
is an accumulated quantity in joules or another explicitly converted energy unit.
Battery discharge and CPU package power are different scopes and must remain so.

No sensor driver installation, hosted CI or release publication is authorized by
this commitment. Keep third-party reference source and license notices separate.
