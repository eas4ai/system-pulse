# Native process navigation freeze

Status: root cause reproduced; a focused fix and eight native regressions pass. Source commit `88d92e6c8a77c3a3f2ff1879831f662fdaf22e8c` awaits independent spec and quality reviews. Final native acceptance remains pending.

## Candidate and evidence

App source through `9c6034b456a0a50d6a8b7a708d36dddd8d6cbd4b`; native binary SHA256 `4250ff6c302a0a4f0a6e92936ee7f4420168132ae9bf6a8783e6efaf8b3b31a5`. App/model tests and integration reviews passed before the longer native probe found this runtime failure.

The cached visible CPU metric proof succeeded: `CPU · Overall utilization · 6.8 %` matched the same sequence 23 / render revision 22, accepted age 0.598 seconds, with a 2.156 ms native query. That equality does not independently prove arithmetic or formatting. Evidence: `/tmp/system-pulse-native-prep-3WGkPz/run2/metric-match.json` and `visible-exact-metric.png`.

During subsequent native process navigation, accepted data stopped at sequence 182 / revision 181 while the app remained busy at roughly one CPU core. A terminated real child remained in the frozen data beyond the five-second bound. Normal window close did not exit within ten seconds. The preparing agent preserved the frame, screenshots, logs and exact available command journal, then verified cleanup of both apps/probes. Handoff and reproduction notes: `/tmp/system-pulse-native-prep-3WGkPz/HANDOFF.md` and `REPRODUCTION.md`.

## Reproduction and investigation

A separate debugger reproduced the failure in its first isolated run: focus the panel-local Hide Processes control, Tab into the table viewport, End, then up to 64 Up events spaced 25 ms. Its data stopped at sequence 16 and the app remained busy. This first reproduction used aggressive input; the ordinary held-key control below establishes the practical application defect.

Attaching gdb to the existing private process was denied by the OS ptrace policy. The debugger subsequently enabled same-user tracing only for the private test app through its temporary launcher and captured stacks. No global ptrace settings changed. Production source remained unchanged during root-cause investigation. No full native acceptance or completion is claimed.

## Confirmed finite backlog

The debugger captured the main thread inside Taffy layout, reached through `X11Client::process_x11_events` → event handling → `Window::dispatch_key_event` → synchronous drawing. The X11 client drains events until the queue is empty. Process navigation requests a refresh for every key. The experimental navigator sent another 64-key batch while only about 9–10 prior selection changes had appeared; thirteen batches were journaled in 30 seconds. The UI remained near one full CPU core while the collector continued normal timed waits.

Native selected-row progress continued while accepted diagnostics stayed at sequence 82. After 196.28 seconds, delivery recovered without intervention to sequence 278, age 0.885 seconds. This proves finite queued-input starvation rather than an infinite loop or stopped collector. Stack and recovery evidence: `/tmp/system-pulse-freeze-investigation/run2/frozen-main-unbounded.txt` and `backlog-recovery.jsonl`.

## Ordinary key repeat and correction

Holding Up for 3.0036 seconds with unmodified Xvfb repeat settings (660 ms delay, 25 Hz) left sequence 380 stale for 14.514 seconds before sequence 395 arrived. This establishes an application defect under ordinary input, independently of the aggressive harness. Condition-paced navigation acknowledged twelve individual keys in 0.269–0.488 seconds each while samples advanced from 339 to 344. A bounded four-key probe acknowledged seven batches while sample age remained at most 1.358 seconds; its temporary driver then failed on a null accessibility ID, so it is partial evidence only.

The narrow fix will preserve every immediate selection and scroll movement while requesting one repaint through `Context::on_next_frame` per owning view. This API queues a frame without dirtying the current key event. Cover vertical and horizontal process navigation and outer Alt navigation. Tests must prove accumulated movement and one pending repaint; native held-key checks must prove fresh delivery and normal shutdown. Final automation must wait for actual selection acknowledgement and handle null or defunct accessibility nodes within the original deadline.

Full read-only report: `/tmp/system-pulse-freeze-investigation/REPORT.md`. Ordinary-repeat artifacts: `run2/held-key.json`, `held-freshness.jsonl`, and `xset-query.txt`. All private test processes exited or were reaped; the report records cleanup. No native acceptance pass is claimed.

## Candidate repaint correction

The app implementer has a narrow pending-frame correction in `panel.rs` and `workspace.rs`, with burst regressions in `native_tests.rs`. Three new regressions failed on the prior implementation; the candidate passed 44 app tests, 24 model tests, scoped formatting/strict Clippy and native build. Candidate binary SHA256: `c419281e6618155e31abfd5b1f4492698848ffa3bdec5e3f505b5604091dc76f`. Source is committed as `88d92e6c8a77c3a3f2ff1879831f662fdaf22e8c`; independent reviews are pending.

The original-size 1440×1000 native held-Up replay passed: 3.000521-second hold at unchanged 25 Hz, 69 independent freshness observations, maximum accepted age 1.358890228 seconds, sequences 231→235. Selection changed and Processes panel bounds remained `[8,250,1424,280]`. A stable native/diagnostic summary comparison completed in 57.214 ms at sequence 235/revision 234. Root inspected `/tmp/system-pulse-repaint-fix/native-held2/original-size-after-up.png`; the header is visible while the inner table remains horizontally scrolled from earlier checks. This is not an all-fields process or final accuracy proof. Exact case data: `/tmp/system-pulse-repaint-fix/native-original/held-up.json`.

The first held case used a 640-pixel-wide window around a 1424-pixel panel; its existing outer-reveal behavior moved the oversized panel horizontally, so that result proves freshness but not visible metric acceptance. Its 67 observations and 1.340-second maximum age remain in the replay journal; the standard case filename was overwritten by the full-size run. Later artifacts must use unique case paths. Initial whole-tree rescans and transient selected-row assumptions also caused harness setup failures before held input. The corrected transport caches/scopes nodes, selects a stable long-lived row before horizontal checks, and retains the original deadlines. Remaining native cases and clean shutdown are pending.

The bounded burst also passed: exactly 64 Up keys in 1.587819 seconds, then no additional input until the predicted PID/start identity was acknowledged. Forty freshness observations had a maximum accepted age of 1.429978066 seconds; the outer panel stayed fixed. Exact native/diagnostic summary comparison took 53.770 ms. Evidence: `/tmp/system-pulse-repaint-fix/native-burst/burst-64-up.json`. Root inspected that artifact; this is a passing bounded-input regression, not final native acceptance.

## Completed focused replay

All eight final cases passed on the same binary: original-size held Up, exactly 64 Up taps, held Left/Right, and held Alt+Left/Right/PageUp/PageDown. Maximum accepted age across those passing cases was 1.530683060 seconds, below the declared two seconds. Horizontal cases retained native PID/start `1:31`; outer vertical cases observed signed 15,900-pixel panel motion and explicitly did not observe offscreen selected rows. The deterministic outer test proves no selection mutation. Failed boundary/setup and offscreen-row lookup attempts remain separate and were not counted as passes.

Normal WM_DELETE_WINDOW shutdown returned zero in 0.402581 seconds; parent confirmation and cleanup recorded the private app, driver and DBus PIDs absent. Final evidence: `/tmp/system-pulse-repaint-fix/native-final-results.json`, `verification.md`, and `native-held2/shutdown.json`. Root read the final results and verification report. The source change adds two per-view pending flags and next-frame helpers; the remaining additions are focused regression coverage. Both independent reviews must pass before Task 3 source work begins.
