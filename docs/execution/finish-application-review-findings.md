# Application review findings

Reviewed source: `e462f2e8bb1241d4c745dbfdabc55c92361b892f`.
Direct review by the implementing agent; no independent review is claimed.

## Developer preset omits live network monitors

`src/layout.rs` selects `interface:` and `volume:` monitor IDs for Developer.
Live collection publishes network IDs with `network:`. The fixture-only test
uses `interface:fixture-lan`, so it misses this mismatch. Developer therefore
omits the network monitors promised by the implementation plan.

Correction required: include live `network:` identities, preserve fixture and
saved-layout compatibility, and test both visibility and dock membership with
a live-form network ID. This does not change saved user workspaces.

## Native product wrapper waits on inherited service pipes

The full `final-acceptance-package-streams-20260907` run passed 918 preservation
tests, all fourteen native cases, ten input-focus tests and release packaging.
The packaged product replay wrote a PASS result, but its enclosing step timed
out at 300 seconds. This is an aggregate failure, not successful acceptance.

The retained `application-wrapper-observation.json` shows RTK PID 1134107
waiting with read pipes 345191736/345191737. Session-owned portal PID 1134418
and ksecretd PID 1134460 retained those same pipes as stdout/stderr after the
native replay, Xvfb and DBus launcher had exited. The external owner reaped
all remaining descendants after the timeout.

Correction required: redirect the private session's output to a retained file
before it reaches RTK, following the existing preservation replay's capture
pattern. Keep the command's exit status, original outer deadlines and external
descendant cleanup. Test a descendant that holds output open and a nonzero
command result. The separate installed smoke has not yet run in this aggregate.

## Review scope

The direct review also examined physical process sorting, pidfd/start-identity
binding, protected targets, preset mutation validation and durable publication,
first-launch initialization, theme/font application, memory composition, and
installer path/overwrite/removal handling. No further finding was identified in
those paths. Final review remains pending resolution and current acceptance.

Developer preset correction: the live-form network visibility assertion first failed, then passed after adding the `network:` prefix alongside existing identities. The regression also requires dock membership. All 85 application tests, formatting, strict all-target application Clippy and diff checks passed. The session-capture finding remains open.
