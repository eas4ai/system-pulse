# PawnIO 2.2.0 corresponding driver source

The optional Windows installer redistributes the unmodified official PawnIO.Setup
2.2.0 executable. Its driver is PawnIO 2.2.0 at revision
5cdf470831fdfff3f7f1d06363ca6b230f3bf35a. Its PawnPP submodule is pinned to
e64e4c37b2d8ba0d8ee57205faf8183aee12c438. Both complete source archives are
retained here; source-provenance.json records download URLs and SHA-256 hashes.

Extract PawnIO-source.tar.gz, then extract PawnPP-source.tar.gz into the resulting
driver tree's PawnPP directory, removing the tarball's top-level directory.
Follow the retained upstream README and CMake/build workflows with the Windows
SDK and WDK. System Pulse does not modify or rebuild the upstream driver.

PawnIO is GPL-2.0-or-later with the exception described in PawnIO-README.md;
see PawnIO-COPYING. PawnPP includes its own license in its source archive.
The signed installer is kept outside the repository and verified against its
pinned release SHA-256 before packaging. The module has separate provenance
under vendor/pawnio-intel-msr. All these materials are included in the application
source archive distributed with the Windows installer.
