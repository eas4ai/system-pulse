# PawnIO AMDFamily17 SMN module

Official signed `AMDFamily17.bin` from the PawnIO.Modules 0.2.11 release.

- Upstream release: https://github.com/namazso/PawnIO.Modules/releases/tag/0.2.11
- Source revision: `52a7e536dff3e53c96917a28caac5e0fa6510696`
- Release archive: `release_0_2_11.zip`
- Release archive SHA-256: `43608cb89bc84247fef1368a139013f7d043e17db6d6c8dfc9b46bf0905a81f4`
- Module SHA-256: `dae74615761b78bdf064dfb3e136252ddcc6fc727d88f14738d0e5800d427a91`
- License: LGPL-2.1-or-later; reuse `../pawnio-intel-msr/COPYING`.
- Copyright: (C) 2025 namazso, as retained in the pinned module source.
- Pinned source: `../pawnio-intel-msr/source-upstream.tar.gz`, SHA-256
  `f2199b1bac7daa1cc114c8dd28627771de74641797292e76dab974920c788932`.

The bundled module is the unmodified signed release binary. Its source exposes
additional MSR reads and writes, but System Pulse calls only `ioctl_read_smn` with the
fixed temperature register `0x59800`; it does not expose arbitrary SMN offsets,
MSR operations, or tuning. Each SMN read takes the bounded `Global\Access_PCI`
mutex required by the module source and releases it through an RAII guard.

PawnIO is installed and managed separately. The dashboard does not install or
start the driver; the existing Windows installer offers the optional official
prerequisite. Local hardware access is unverified when PawnIO is absent.
