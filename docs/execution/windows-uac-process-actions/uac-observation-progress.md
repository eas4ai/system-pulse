# Windows UAC observation progress

Nine current observations pass independent verification: ordinary, consent-force,
consent-cancel, consent-graceful, consent-refused, consent-stale, consent-delayed,
consent-denied and helper-crash. Their complete source/binary-bound receipts live
in `uac-native/`. Historical and failed attempts remain in `uac-native-attempts/`.

The helper-timeout run reported uncertainty and cleaned its owned processes but
failed a resource assertion. Source inspection found that sysinfo retains one
query-only handle to a still-live monitored process. The corrected snapshot records
granted access and SYNCHRONIZE counts. Only one exact collector query mask is
allowed for a still-live timeout helper; an action wait or termination handle
still fails. Native positive controls cover query-only, sync-only, query+sync and
termination+sync handles, plus closure and owned-process cleanup.

The nine earlier receipts prove zero helper handles, a stronger condition. The
verifier accepts only their exact reviewed 80f1cd41 harness or the current harness,
and rejects the old harness for timeout. The ownership review also covers the
vendored collector handle lifetime. The full Python suite passed 569 tests.
The corrected real timeout run and final commitment review remain pending.

The developer has requested Windows GPU discovery coverage matching Linux and
provided Cores, LibreHardwareMonitor and hwinfo references. That is the next named
commitment after the running UAC verification. Missing Windows energy and thermal
providers are also recorded. No hosted CI, push or publication has been performed.
