# Initial native Windows build

Source: fd98c4704cb2d79b5625cb4b8d0a6817fade0046.
Cairn receipt: `.cairn/evidence/REL-001/20260910T023944916Z`.

The native x86_64 Windows test run passed all 219 applicable tests, with no
failures or ignored tests. The optimized application build passed. The first
test build took 20m40s and the first optimized build took 31m36s with two Cargo
jobs on the [Intel tablet](windows-host.json).

Tools: Rust/Cargo 1.98.0, Git 2.55.0.windows.3, CMake 4.4.3, Visual Studio Build
Tools 2022 17.14.40, MSVC 14.44.35207 and Windows SDK 10.0.26100.0.

Executable SHA256:
`8f462e175175a19cb02af11a69b1b16d38f6ddaa31c7ca89311388cfe3258da0`.

Four collector warnings concern unused Unix authentication helpers on Windows.
This build result does not establish native GUI behavior or full feature parity.
The complete command output is retained by the named Cairn receipt; the verifier
checks a committed source archive hash before building and checks Cargo.lock is
unchanged afterward.
