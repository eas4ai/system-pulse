# Authenticate privileged process actions

Surfaced from: PERF-005
Captured: 2026-09-08T20:44:42.657Z

Developer confirmed a sudo-style password prompt for ending or force-quitting processes owned by root or another user. Scope authentication to the requested action, keep the application unprivileged, and do not store passwords. Platform authentication, cancellation, failure handling and process identity checks require specification and verification before implementation.
