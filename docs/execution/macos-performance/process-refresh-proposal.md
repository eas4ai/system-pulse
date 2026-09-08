# Skip unrequested Mac process-argument reads

Status: proposal only; dependency change awaits a scope decision.

The complete paired comparison found 14.5% less Summary CPU and 21.7% less
tray-only CPU, below the required 50%. Native preservation and the other four
PERF requirements passed. The next optimization should address measured cost
without reducing sampling frequency or process coverage.

## Evidence

The isolated stage timing macro measured 35.612 ms of process-refresh CPU per
sample, versus 4.190 ms for temperature reads and 1.295 ms for account enumeration.
Instruments Time Profiler subsequently captured 1,271 ms of weighted running CPU
samples over 15.791 seconds. Of these, 1,016 ms belonged to the collector thread;
517 ms included process refresh and 287 ms included `get_process_infos`.
The latter is about 22.6% of all sampled CPU. Seventy milliseconds had no
backtrace and remain included in the total. Inclusive categories overlap.

The [summary](probes/instruments-tray-summary.json) is retained with the probe
evidence. The original Instruments bundle and exported samples are at
`task-manager-artifacts/macos-performance/cpu-profile-20260908T131200Z` on Linux,
and under the existing Mac performance artifact directory. The profile was
separate from scored acceptance observations and used the unchanged candidate.

In sysinfo 0.37.2, `src/unix/apple/macos/process.rs::update_process` calls
`get_process_infos` for each retained process. That function reads
`KERN_PROCARGS2` twice before examining which fields need updating. System Pulse
requests CPU, memory, disk usage, user and tasks; it does not request command
arguments, environment, working directory or executable path. A retained
process name is only assigned from these arguments when the name is empty.

## Proposed dependency change

Add an early return at the start of sysinfo's `get_process_infos`, before its
existing system calls:

```rust
if !process.name.is_empty()
    && !refresh_kind.exe().needs_update(|| process.exe.is_none())
    && !refresh_kind.cmd().needs_update(|| process.cmd.is_empty())
    && !refresh_kind.environ().needs_update(|| process.environ.is_empty())
{
    return true;
}
```

Keep all existing reads when the process name is empty or any requested field
needs refreshing. Keep PID/start-time checks, user refresh, CPU counters, memory,
disk I/O and process removal behavior. A fresh process, including PID reuse,
must still acquire its name. Validate the denied-read fallback and same-PID exec
behavior explicitly before considering this safe; the proposal is not proof.

Prefer an already corrected upstream version if a reviewed compatible release
contains this exact fix; otherwise use a narrowly documented local patch with
upstream source and license notices retained. No registry cache modification,
dependency upgrade or vendored implementation has been made for this proposal.

## Required verification

- Requested executable/command/environment fields still refresh for both
  `Always` and `OnlyIfNotSet`; `Never` does not trigger their reads.
- New names, PID reuse, process exit, denied reads and user changes retain
  truthful behavior and current coverage.
- The isolated timing probe demonstrates whether the guard actually saves CPU.
- Native/Linux collector and application tests, strict lint and package notices
  pass against the committed dependency change.
- Fresh complete paired observations and native preservation establish its
  actual benefit. Retain the current below-target set. This patch alone is not
  promised to meet the 50% target.

## Scope decision

The current commitment says: “Source changes belong in the application collector
and directly affected tests.” The proposed change is inside a third-party
dependency and needs the developer to extend that scope. This proposal makes
the next action reviewable without changing production behavior.
