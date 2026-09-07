# Initial Mac performance investigation

Status: Observed 2026-09-07

The [reference release](baseline-build.json) used 2.57 CPU seconds in 20.022826375 elapsed seconds (12.835 percent of one CPU), measured without a profiler. The [isolated 30-second observations](recon-measurements.json) used Summary at 1280 by 880 with the one-second interval, followed by tray-only. Native accessibility confirmed one window then zero after close. The owned app and wake lock were cleaned up. These are preliminary observations, not final acceptance.

Process CPU came from macOS ps. Thread counters used the SDK proc_pidinfo PROC_PIDLISTTHREADS and PROC_PIDTHREADINFO definitions. Summed thread nanosecond deltas agree with process deltas within collection timing and ps rounding. The collector accounts for roughly 10 percentage points in both modes; the main thread accounts for about 2.33 points in Summary and 1.23 in tray-only.

A separate ten-second native sample includes component discovery, process refresh, account enumeration, disk discovery and UI layout/painting. Many inclusive samples are blocked Mach calls; they locate paths but do not establish their CPU shares. Original stack/AX captures remain in the Mac diagnostic artifacts.

The pinned sysinfo 0.37.2 source, src/unix/apple/macos/component/arm.rs, retains an IOHIDEventSystemClient in ComponentsInner (17-20), creates it only when absent (70-78), and refreshes individual temperatures through retained service handles (180-200). Failed event reads clear temperature (182-186).

The same dependency's src/unix/apple/disk.rs DiskInner::refresh_specifics (79-116) can retain old capacity fields after failed property reads and still return true. That boolean cannot prove fresh successful capacity. Disk reuse needs a separate safe strategy or the current path stays in place.
