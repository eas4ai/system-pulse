# Application root membership differs from ordinary ancestry

The untraced run at `2f3429c5` passed initial cases, then failed before
Home/End input in initial navigation panel discovery. The original
eight-second batch deadline expired. [Retained runs and hashes](native-application-membership-failure.json).

A diagnostic logging only existing traversal/liveness calls showed seven
complete 927-node scans, each about 1.1 seconds, with no defunct results.
Membership validation rejected each completed scan. A second bounded
diagnostic recorded four failed-path observations: every ordinary link
matched, but the application root reported parent null and index -1
at the desktop boundary. Both diagnostic runs retain their failure
outcomes and are not acceptance evidence.

This matches pinned accesskit_unix 0.21.1: its application Accessible
interface returns null Parent and -1 GetIndexInParent, while bus setup
registers the application separately through Socket.Embed. The validator
incorrectly applied ordinary parent/index rules to that special boundary.

Preserve ordinary current parent-child validation through the application.
Prove the application itself by bounded current desktop-child enumeration,
exact accessible identity, liveness and PID. Keep complete final uniqueness
proof and all deadlines. Test the actual null-parent/-1-index case plus
missing, replaced, duplicate, wrong-PID and incomplete desktop observations.
Earlier unit fixtures modeled ordinary ancestry at this boundary; they
did not represent the adapter's actual behavior.
