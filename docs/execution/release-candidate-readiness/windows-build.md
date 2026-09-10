# Native Windows builds

## Refreshed release candidate

Source: `2801d26df53b79c25f35edf9016a6408f9de62f9`.
Cairn receipt: `.cairn/evidence/REL-001/20260910T041317512Z`.

All 219 applicable tests passed again after the CI compiler compatibility
changes. The optimized build passed in 9m24s, with the same native tools below
and an unchanged Cargo.lock. The unused Unix authentication warnings were fixed.
The [runtime check](windows-runtime.md) uses this executable.

Executable SHA256:
`17f989fdeb08fa4ec02fa6169992ba2b618c035e6e74fc658dcfde7dca9370d0`.

## Initial build

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
