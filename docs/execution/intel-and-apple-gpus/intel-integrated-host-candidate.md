# Local Intel integrated GPU candidate

Status: Potential native host identified on 2026-09-06; enablement and acceptance
remain pending. The developer noted that the workstation CPU has integrated Intel
graphics that could be enabled in BIOS. Read-only host inspection confirmed an
Intel Core i9-13900K on MSI MEG Z790 GODLIKE (MS-7D85), board version 1.0.
Intel lists [UHD Graphics 770 for this CPU](https://www.intel.com/content/www/us/en/products/sku/230496/intel-core-i913900k-processor-36m-cache-up-to-5-80-ghz/specifications.html).

Linux currently enumerates two display-class functions, both AMD `1002:7551` using
`amdgpu`, at `0000:03:00.0` and `0000:06:00.0`. No Intel display PCI function is
present. This does not by itself prove a particular BIOS setting. The exact local
observations and primary source URLs are retained in the
[structured record](intel-integrated-host-candidate.json) and externally at
`gpu-recon/local-intel-igpu-candidate-20260906/observation.json`.

The [MSI Intel 700 BIOS guide](https://download.msi.com/manual/mb/Intel700BIOS.pdf),
pages 19–20, documents Settings → Advanced → Integrated Graphics Configuration.
`IGD Multi-Monitor = Enabled` permits integrated graphics alongside the discrete
card; `Initiate Graphic Adapter = PEG` selects the PCIe card for primary boot
display. The exact available menus depend on installed firmware. The agent has
changed no BIOS setting and performed no reboot.

After developer enablement and reboot, enumerate the actual PCI identity, driver,
DRM/render nodes and native provider capabilities before capturing acceptance.
Preserve the prior AMD evidence and verify device/restoration behavior with the
new inventory. This candidate could supply Intel integrated Linux coverage; it
cannot substitute for the separate discrete Intel hardware class.
