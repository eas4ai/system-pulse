# Independent acceptance inventory

Read-only collector inventory by `prepare_live_acceptance`, against reviewed collector source through `c217818d`. This is verifier preparation and supporting host observation, not final acceptance. All paths below are relative to `examples/system_pulse/collectors/`.

## Captured inputs and source coverage

- CPU frequency: `core-N-frequency` uses original decimal kHz from `scaling_cur_freq` times 1000, or cpuinfo MHz times one million. Independently enumerate actual logical IDs. CPU temperature IDs retain canonical device path and physical label; original millidegrees times 0.001. See `src/host/proc.rs:321` and `:375`. This host exposes 32 frequency sources and 25 coretemp sensors.
- CPU load/uptime retain original decimals. Threads are the scheduling-entity total from loadavg; processes are numeric proc entries enumerated before individual row reads, not returned-row count. See `src/host/proc.rs:97` and `src/host/process.rs:174`.
- Memory retains named meminfo operands in kB. Used = total minus available; cache = Cached + SReclaimable - Shmem; other = total - free - cache - buffers. Multiply by 1024. Swap used = SwapTotal - SwapFree; preserve valid zero totals. Fault counters use pgfault/pgmajfault. See `src/host/proc.rs:174`.
- AMD scalar observations preserve the source number before conversion. Temperatures multiply by 0.001, power by 0.000001; hwmon frequencies are already Hz and fan readings RPM. VRAM retains integer used/total bytes. Independently discover vendor, unique ID/PCI path and readable fields. Both host cards expose average power; both instantaneous `power1_input` paths return ENOENT. See `src/host/devices.rs:9`.
- Process identity uses PID and stat field 22. Parse names between the first opening and final closing parenthesis. RSS is stat field 24 times system page size; threads are stat field 20. CPU excludes child ticks and divides by one core's measured elapsed clock ticks. IO uses its own observation windows. User is the real UID, optionally resolved through passwd. See `src/host/process.rs:12`. A controlled stable child allows independent PID/start/name/user comparison without pretending arbitrary changing rows share one instant.
- Filesystem capacity uses blocks minus **bfree**, never bavail, times fragment size. Decode mountinfo octal escapes. Ordinary IO mapping uses mountinfo major/minor; fuseblk must use the source block node's st_rdev. This host has fuseblk devices 259:4 and 259:10. Shared-device IO must retain its scope. See `src/host/devices.rs:333`.

Build expected capability sets from independent OS enumeration before joining descriptors. A readable attributable source without an implementation fails. Preserve actual read errno; existence alone does not prove availability. Independent host probes confirmed EACCES for process 1 IO and a sampled Docker overlay filesystem capacity. Empty interface addresses are an attribution limit; this host's enp11s0 and wlo1 have no addresses.

## Connection evidence finding and resolution

The original reviewed connection observations retained only the derived count. This cannot prove exact captured-input attribution. Add one shared optional snapshot record containing the captured interface/local-address map and TCP4/TCP6 local-address/state rows, each with query windows and errors. Preserve wildcard and non-established rows so the Python verifier independently filters established state, normalizes mapped IPv6, excludes unspecified addresses, and requires distinct-interface ownership. Do not retain ports, remote endpoints or socket owners. Individual readings can retain the existing counts.

Process raw observations already preserve PID/start ticks, but not original UID/passwd lookup results. Do not claim exact captured-input resolution for every arbitrary user string. The original collector README overstated passwd lookup failure preservation: a numeric UID fallback has no user_reason. The follow-up corrected that documentation.

The shared observation is implemented and independently spec/quality reviewed through `bbfc24905d5566d37e655be2412b105e9edab218`. See [attribution review](attribution-review.md). Structurally uncertain rows redact both retained tokens; malformed source content must not enter evidence errors. Independent Python recomputation passed 72 actual host count/status comparisons. Final acceptance must capture fresh inputs and retain this independent check.

## Adversarial cases

Corrupt kB, temperature, power or frequency factors; substitute free for available memory; omit Shmem subtraction; replace bfree with bavail; use mountinfo major zero for fuseblk; change process start ticks, RSS page size, CPU core normalization or elapsed interval; change connection state, wildcard/mapped address or ownership; omit one accessible descriptor. Every corruption must fail. Preserve valid zero swap/GPU clocks and negative Celsius. Named child tests must cover spaces/closing parentheses and process exit separately from permission denial.
