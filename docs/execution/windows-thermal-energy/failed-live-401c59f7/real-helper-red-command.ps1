$ErrorActionPreference='Stop'
$env:PATH=[Environment]::GetEnvironmentVariable('Path','Machine')+';'+[Environment]::GetEnvironmentVariable('Path','User')
$env:CARGO_TARGET_DIR=Join-Path $env:USERPROFILE 'workspace\system-pulse-build-target'
$env:CARGO_BUILD_JOBS='2'
$env:SYSTEM_PULSE_TEST_REAL_HELPER='1'
Set-Location (Join-Path $env:USERPROFILE 'workspace\system-pulse-d5ac44902e64-199a62ed')
& cargo test --locked -p system-pulse-collectors native_real_driver_helper_session --lib -- --nocapture
exit $LASTEXITCODE
