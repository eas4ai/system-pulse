# Apple GUI pool investigation

Status: Two missing lifetime boundaries reproduced on 2026-09-06. Full application
correction and native revalidation remain pending. These probes do not clear
[F1 from the GUI preflight](apple-gui-preflight-findings.md).

## Reproduction and source inspection

The pinned GPUI source is Zed commit
`f66ed399cdde86092af8af3dc7b418abf45f37f8`. System Pulse's `main` calls
`gpui_platform::application()` before establishing an autorelease pool. The pinned
[Mac constructor](https://github.com/zed-industries/zed/blob/f66ed399cdde86092af8af3dc7b418abf45f37f8/crates/gpui_macos/src/platform.rs#L197)
performs native setup, including keyboard and pasteboard work. Its
[dispatcher trampoline](https://github.com/zed-industries/zed/blob/f66ed399cdde86092af8af3dc7b418abf45f37f8/crates/gpui_macos/src/dispatcher.rs#L166)
runs callbacks without a local autorelease pool.

Root compiled isolated probes outside the source checkout. The GPUI probe links
the existing native application dependency artifact; Cargo's recorded dependency
fingerprint selected `libgpui_platform-33568cd5005678c6.rlib`, avoiding an ambiguous
second test artifact. Each probe ran as an ordinary, bounded child process.
The source checkout and dependency cache were not modified.

| Native probe | Unpooled warnings | Explicit scoped pool warnings |
| --- | --- | --- |
| Foundation process-info call | 3 | 0 |
| Pinned GPUI application construction and drop | 24 | 0 |
| Foundation call dispatched through pinned GPUI background executor | 1 | 0 |

The Foundation warnings followed an `ENTERED_MAIN` marker. This experiment does
not support an unavoidable pre-main warning explanation. The GPUI callback probe
establishes that a pool on the main thread does not cover an executor thread.
Each command exited zero. These are diagnostic controls; they are not a modified
production application or evidence that every original warning shares one cause.

[Apple's pool guidance](https://developer.apple.com/library/archive/documentation/Cocoa/Conceptual/MemoryMgmt/Articles/mmAutoreleasePools.html)
requires thread-local pools around Cocoa work and recommends draining temporary
objects during long-running loops. AppKit event pools do not establish pool
coverage for application construction or arbitrary background callbacks.

## Retained failures and provenance

The first GPUI probe setup stopped before compilation because two candidate rlibs
were present. Root inspected Cargo fingerprints and selected the artifact used by
the built application. No arbitrary newest-file selection was used.

A prior bounded LLDB launch exited one because macOS could not obtain permission
to debug in a noninteractive SSH session. No target process launched. Its original
error log is retained; no debugger permission or access-control change was made.

The GPUI probe's compiler stage itself emitted seven pool warnings from PID 4624.
They remain in the original compiler stderr, separately from each probe's runtime
stderr and the full application's warnings. The Foundation probe compiler emitted
none. Neither compiler-stage result is substituted for application lifecycle proof.

The [machine-readable record](apple-gui-pool-investigation.json) contains sources,
rlib and executable hashes, exact commands, original log hashes and local paths.
Root verified transferred logs and source hashes. The full application's 551
warnings remain unresolved: a correction must cover native startup and actual
callback ownership, then pass a fresh unfiltered full-app diagnostic and native
workspace observations. Helper lifetime corrections alone cannot close F1.
