# Verify retained Mac process user IDs follow account changes

Surfaced from: PERF-003
Captured: 2026-09-08T13:36:57.839Z

Inspection of upstream sysinfo 0.37.2 update_process found it refreshes BSD identity and parent but does not reassign existing process user IDs from the fresh BSD record. The approved argument-read guard does not alter this behavior. Native regression checks preserve initial user identity; they do not claim a live setuid transition test. Investigate separately before claiming retained UID changes are supported.
