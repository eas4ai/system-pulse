# PawnIO IntelMSR module

Official signed IntelMSR.bin from PawnIO.Modules release 0.2.11.
Upstream: https://github.com/namazso/PawnIO.Modules/releases/tag/0.2.11
Source revision: 52a7e536dff3e53c96917a28caac5e0fa6510696
Archive SHA-256: 43608cb89bc84247fef1368a139013f7d043e17db6d6c8dfc9b46bf0905a81f4
Module SHA-256: d6ed85d65ab17a22f813ef98207d6d537155ee2ded5976a21cb48413c9b92e5f

Copyright (C) 2025 namazso. LGPL-2.1-or-later; see COPYING and retained
source/ with its include files. Module bytes and source are unmodified.
Building modules requires the upstream Pawn compiler/toolchain; consult the
pinned upstream repository and its _pawn submodule/build workflow. The official
driver accepts signed modules, so a locally changed module requires the upstream
signing/contribution process or a separately managed development environment.

The module runs in the separately installed official PawnIO driver. System Pulse
uses only fixed temperature-register reads, although the upstream module also
contains write operations. The app does not expose a general module interface.
The PawnIO installer and PawnPP interpreter are not embedded here.

The complete upstream source tree at the pinned revision, including build workflows
and submodule declarations, is retained as source-upstream.tar.gz. SHA-256:
f2199b1bac7daa1cc114c8dd28627771de74641797292e76dab974920c788932
