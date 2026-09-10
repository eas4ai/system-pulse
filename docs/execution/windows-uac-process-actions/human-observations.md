# Human Windows UAC observations

These statements record the developer's responses during native collection on
2026-09-10. They supplement the source-bound receipts and do not replace native
verification or complete the commitment.

- `consent-force`: the developer answered "yes" when asked whether they personally
  clicked Yes on the first System Pulse prompt and it showed "Unknown publisher".
  Receipt: `uac-native/consent-force/receipt.json`; original run directory:
  `system-pulse-windows-uac-m459n9pu`. The independent single-run verifier passed.
- The developer identified `shawn` for account use. The observed dashboard uses
  `XPSTABLET\shawn` with a limited administrator token. A separate standard-user
  account has not yet been identified; credential-path evidence remains pending.
