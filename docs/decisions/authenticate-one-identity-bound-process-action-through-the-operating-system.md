# Authenticate one identity-bound process action through the operating system

Level: Consequential
Decided by: agent
Rests on: PROC-004 PROC-005
Would be wrong if: Authentication can change the target or signal, expose credentials to application data, leave the normal UI privileged, or allow a recycled PID to receive the request.

## Decision

Keep the UI unprivileged. Attempt ordinary identity-safe signaling first and request authentication only for a typed permission-denied result. Use the operating system authentication agent: pkexec with its internal terminal agent disabled on Linux, and a fixed AppleScript administrator-privileges command on macOS. Run a single-purpose mode of the same executable before UI initialization, with strictly parsed PID, start identity and one of two signal names; it never starts the UI or reads application state. Revalidate identity after authentication and signal using a Linux pidfd or a macOS audit token carrying the kernel PID version. Preserve microsecond macOS start identity from the existing BSD process observation; unknown identity and unavailable native support fail closed. The helper never requests authentication recursively. Pass no credentials through arguments, streams, environment, storage or diagnostics. Authentication cancellation and failure return visible errors and never trigger a numeric-PID fallback. Add boundary tests and native controlled-child verification for ordinary actions, denial, cancellation, successful privilege use and identity changes. OS-managed authorization caching is permitted; the application retains no password or authorization token.

## Realized by

(none yet: recorded, not built)
