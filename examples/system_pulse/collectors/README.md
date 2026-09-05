# System Pulse host collectors

This GPL-3.0-or-later Rust crate owns blocking host collection and has no GPUI dependency. Linux reads procfs/sysfs directly where source errors, device identity, or counters matter. The common backend uses pinned sysinfo 0.37.2. NVIDIA support dynamically loads NVML through pinned nvml-wrapper 0.13.0; no NVIDIA library or driver is needed to start the app.

```sh
rtk cargo test -p system-pulse-collectors
rtk cargo clippy -p system-pulse-collectors --all-targets -- -D warnings
rtk cargo fmt -p system-pulse-collectors -- --check
rtk cargo run -p system-pulse-collectors --bin pulse-snapshot -- --count 3 --interval-ms 1000
```

The diagnostic writes one JSON snapshot per line. Count defaults to 3 and accepts 1–100000. Intervals accept 500/1000/2000/5000 ms and default to 1000 ms. Invalid or repeated options fail with exit status 2. `--help` lists usage. Redirect stdout to retain a capture; process command lines and environments are never collected.

## Public API

`HostCollector::new()` constructs an independent collector. `collect(&mut self) -> Snapshot` performs a blocking capture and returns owned serializable descriptors, readings, process rows, and diagnostics. `SamplingService::start(Duration) -> Result<SamplingService, String>` constructs the collector inside one worker, including NVML initialization. `set_interval(Duration)` interrupts its wait. `take_latest()` removes the single replaceable delivery slot. Dropping the service interrupts a wait and joins any in-flight collection. It cannot cancel an OS/driver call already in progress. Missed sample deadlines are skipped without overlapping work or catch-up bursts.

`Snapshot` exports `sequence`, capture start/end nanoseconds, `clock_anchor`, `monitors`, `sensors`, `readings`, `processes`, and backend `diagnostics`. Every monitor has a `summary_sensor_id`. Every sensor has a stable ID, monitor ID, title, kind, unit, source, semantic scope, and optional capacity scale. `Reading` keeps optional physical value/total, availability, reason, and raw observations. Enum JSON values use their Rust names (for example `Available`, `BytesPerSecond`, `Gpu`). Process fields are owned readings. `user_reason` preserves failures reading the real UID from `/proc/PID/status`; if that UID has no usable passwd name, `user` contains the truthful numeric UID and `user_reason` remains absent.

## Shared network attribution evidence

Linux snapshots contain one optional, serde-defaulted `network_attribution` record. Older JSON snapshots without the field and common-backend snapshots use `None` (`null` in JSON). This additive record contains `interface_addresses`, `tcp_v4`, and `tcp_v6`; it is not copied into individual readings or retained in a table history.

Each observation has a `query` record with `source`, `read_started_ns`, `captured_ns`, `availability`, and `errors`. The address observation stores an `interfaces` map from actual interface names to every local address returned by sysinfo, including duplicates. Its successful API return has no fabricated error status: sysinfo exposes no refresh error channel.

Each TCP observation records `address_family` (`Ipv4` or `Ipv6`), `word_byte_order` (`LittleEndian` or `BigEndian`), and `rows`. Each row contains only `line_number`, optional raw `local_address_hex`, and optional raw `state_hex`. IPv6 addresses consist of four native-endian 32-bit words. Both files are queried independently. Wildcard and non-established rows remain in the evidence. Parse errors preserve source/line/field context; ports, remote endpoints, inodes, and socket owners are never retained, including in errors.

Connection counts are derived from these captured objects: decode the declared word order, normalize mapped IPv6, retain established state `01`, exclude wildcard addresses, and require exactly one distinct owning interface. Duplicate copies of an address within one interface do not make it ambiguous. Missing/ambiguous addresses remain unavailable; failed tables prevent a successful count. A valid attributable interface with no matching established rows has a measured zero. The scalar count's raw observation references `Snapshot.network_attribution` and spans the three input query windows, allowing independent recomputation from the shared inputs.

## Time and arithmetic

All monotonic nanoseconds are relative to this collector's `Instant` origin. They are not Unix time or an OS-absolute monotonic clock. Every snapshot's optional `ClockAnchor` contains a `SystemTime` reading in Unix nanoseconds bracketed by `monotonic_before_ns` and `monotonic_after_ns`. External verifiers can pair their wall and monotonic clocks and retain this bracket's uncertainty; they must not equate the two monotonic origins. The anchor is absent only if system time cannot be represented as unsigned Unix nanoseconds.

`RawObservation.captured_ns` is the time an observation was recorded after its source query. `read_started_ns`, when present, bounds the source query together with that end time. Linux CPU, process CPU/I/O, interface counters, block counters, filesystem capacity and hwmon scalar reads retain these source windows. NVML records an individual query window after library initialization and enumeration. The common sysinfo backend brackets each CPU, memory, process, network, component, load, uptime, and disk query group separately; cached fields retain that group’s completion timestamp and read window. The CPU window also bounds sysinfo’s possible implicit CPU refresh during process collection. Other gauge observations are stamped after parsing and bounded by the enclosing snapshot. OS files and APIs need not supply atomic values across different fields.

Integer counters stay `u64` in raw observations, including values above the exact integer range of `f64`. Floating OS values stay floating, without integer truncation. Display values use `f64`. Derived readings carry both previous and current observations. Bytes/s and IOPS divide checked counter differences by measured elapsed seconds. A first sample, decreased counter, or nonpositive interval yields no measured value; a failed read discards its baseline. Missing identities are removed from all baseline maps after each capture.

CPU utilization is `100 * delta(user + nice + system + irq + softirq + steal) / delta(user + nice + system + idle + iowait + irq + softirq + steal)`. Guest counters are excluded because Linux already includes them in user/nice. Every logical CPU gets its own reading. Process CPU uses `100 * delta(utime + stime) / CLK_TCK / elapsed_seconds`, so a multithreaded process can exceed 100%. Process identities are PID plus `/proc/PID/stat` start ticks; the collector checks start ticks again after the other files to avoid joining fields from a reused PID.

## Linux capability report

The snapshot itself is a per-device capability report: each descriptor names the real source, units, scope, and current reading status/reason. This table explains the family contract.

| Family / fields | Source and physical definition | Availability and identity |
| --- | --- | --- |
| CPU overall / every logical core | `/proc/stat`; utilization formula above | Per-core keys use Linux CPU IDs. Read/parse failure invalidates the affected baseline. |
| CPU frequency | `cpuN/cpufreq/scaling_cur_freq` kHz ×1000; fallback `/proc/cpuinfo` cpu MHz ×1000000 | Hertz per logical CPU; scaling frequency may be a requested P-state. Missing both sources is explicit. |
| CPU temperature | CPU provider hwmon `temp*_input` millidegrees ×0.001 | Celsius; provider device path and original physical package/core label retained. Sparse physical labels are not reassigned to logical CPU indexes. |
| CPU load / uptime / counts | `/proc/loadavg`, `/proc/uptime`, numeric `/proc` entries, `/proc/loadavg` fourth-field total scheduling entities | Load1/5/15, seconds, process/thread counts. Thread count comes directly from the kernel and includes kernel threads; process count is the separately scoped procfs census. |
| RAM / composition | `/proc/meminfo`, kB ×1024 | Used = Total − Available. Disjoint composition: Free, Cache = Cached + SReclaimable − Shmem, Buffers, Other = Total − Free − Cache − Buffers. Available is a separate estimate, not another composition slice. |
| Swap / faults | `SwapTotal − SwapFree`, `/proc/vmstat` pgfault / pgmajfault | Bytes and cumulative fault counts. Missing fields retain a reason. |
| AMD utilization / VRAM | `gpu_busy_percent`, `mem_info_vram_used/total` | Percent and bytes. ID is `amdgpu:<unique_id>`, with PCI address fallback; no card/hwmon discovery index identity. |
| AMD temperatures | hwmon `temp1/2/3_input`, original labels | Edge/junction/memory Celsius, including valid subzero temperatures. |
| AMD power | `power1_average` µW ×0.000001; independent `power1_input` | Watts. Average SoC power is labeled separately from instantaneous power. A missing instantaneous source stays unavailable. |
| AMD clocks / fans | `freq1/2_input` Hz; `fan1_input` RPM | Graphics/memory clocks in hertz; sleeping zero clocks are valid. Fan revolutions per minute. |
| NVIDIA fields | NVML utilization %, memory bytes, temperature °C, power mW ×0.001, clocks MHz ×1000000; fan intended % and intended RPM queried separately | ID is `nvidia:GPU-UUID`. Per-field failures remain independent. Missing UUID produces a diagnostic, never an index identity. Missing library/driver, zero devices, lost devices, and reconnects leave other collectors running. |
| Filesystem capacity | `/proc/self/mountinfo` plus `statvfs` | `(blocks − free_blocks) × fragment_size`; total = blocks × fragment_size. Device filesystem UUID preferred, loop backing file next, source/root/mountpoint fallback. Kernel control and namespace pseudo-filesystems are excluded. |
| Filesystem backing I/O | `/sys/dev/block/major:minor/stat`; FUSE block source nodes are resolved separately | Read/write sectors ×512; IOPS = delta(read_ops + write_ops)/elapsed; mean latency = delta(read_ms + write_ms)/delta(read_ops + write_ops). No completed requests means undefined latency, not zero. Shared backing-device I/O is labeled, never claimed as per-volume. Memory/overlay/network filesystems without a direct block mapping report that scope limit. |
| Interface RX/TX / totals | `/sys/class/net/<name>/statistics/{rx,tx}_bytes` | Bytes/s and cumulative bytes; failures do not become zero. Stable hardware-parent path plus interface name; otherwise MAC plus interface name, or name alone. The interface discriminator is always included, so shared-parent/shared-MAC siblings remain distinct when one disappears. Renaming an interface changes its identity; a physical interface changing its configured MAC does not. Includes real virtual interfaces. |
| Interface connections | `/proc/net/tcp` and tcp6 established sockets, matched to sysinfo local interface addresses | Only uniquely owned non-wildcard local addresses are attributed. Wildcard and ambiguous addresses are excluded. No address or inaccessible connection table has a reason. |
| Processes | `/proc/PID/stat`, status Uid, io read_bytes/write_bytes; `/etc/passwd` user names | All current readable process rows; no row cap. CPU as above, RSS pages × page size, measured disk byte rates, threads, user. Access-denied `/proc/PID/io` stays absent with its exact error. No arguments or environment are read. |

## Platform and verification limits

Linux is the host-verified path. The common sysinfo path compiles and is smoke-tested on Linux, but native macOS/Windows accuracy remains unverified. It provides the fields exposed by sysinfo and explicitly reports source limitations for fields that API does not expose. Some sysinfo APIs provide numeric values without a per-field error channel; that limitation is recorded in the backend diagnostic. The common process identity start value uses sysinfo Unix start seconds rather than Linux boot ticks.

The development host has two AMD Radeon AI PRO R9700 devices. Its NVML initialization reports `DriverNotLoaded`; live NVIDIA numeric accuracy is unverified. Fake session tests exercise initialization/count/device failures, session reuse/reinitialization, UUID failure, field failures, ordering, conversion, query windows, and fan-unit separation. The installed kernel exposes both AMD devices' required utilization, VRAM, three temperatures, average SoC power, clocks, and fan RPM; it does not expose instantaneous `power1_input`.

Source references: [Linux procfs](https://docs.kernel.org/filesystems/proc.html), [block I/O statistics](https://docs.kernel.org/admin-guide/iostats.html), [AMD hwmon units](https://docs.kernel.org/gpu/amdgpu/thermal.html), [nvml-wrapper Device API](https://docs.rs/nvml-wrapper/0.13.0/nvml_wrapper/device/struct.Device.html), [NVML queries](https://docs.nvidia.com/deploy/nvml-api/group__nvmlDeviceQueries.html).
