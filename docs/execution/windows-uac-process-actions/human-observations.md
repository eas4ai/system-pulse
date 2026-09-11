# Human Windows UAC observations

These statements record the developer's responses during native collection on
2026-09-10 and 2026-09-11. They supplement the source-bound receipts and do not replace native
verification or complete the commitment.

- `consent-force`: the developer answered "yes" when asked whether they personally
  clicked Yes on the first System Pulse prompt and it showed "Unknown publisher".
  Historical receipt: `uac-native-attempts/consent-force-before-handle-checkpoint/receipt.json`; original run directory:
  `system-pulse-windows-uac-m459n9pu`. The independent single-run verifier passed.
- The developer identified `shawn` for account use. The observed dashboard uses
  `XPSTABLET\shawn` with a limited administrator token. The developer subsequently limited acceptance to administrator consent;
  standard-user credential entry is excluded.

- First `consent-cancel` attempt (`system-pulse-windows-uac-o44yoqv1`): the
  developer confirmed "I clicked yes" after clarification. The observed helper
  execution and target exit therefore agree with the human action. This attempt
  is not cancellation evidence; the cancellation case is being repeated.

## 2026-09-11 current-harness observations

The developer returned to the desktop and explicitly continued the work. They
reported clicking Yes for consent-force, consent-graceful, consent-refused,
consent-stale, consent-delayed, consent-denied and helper-crash, and No for
consent-cancel. Each corresponding current receipt passed independent verification.
For consent-stale, the developer waited for the observer's target-exited cue.
For consent-delayed, the native consent process lived 12.085 seconds and sampling
advanced during that interval.

The developer also approved the first helper-timeout attempt. The UI reported
uncertainty and owned-process cleanup passed, but its resource assertion rejected
a still-live helper handle. That failed attempt is retained separately. The
corrected counter distinguishes action wait handles from sysinfo query-only
handles; the actual timeout rerun remains pending.
