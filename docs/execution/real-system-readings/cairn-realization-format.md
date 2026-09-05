# Cairn realization record migration

Production Cairn advanced from `6879dde` to `1ea0cf7775fb018009636183d91cdd71619ee283`
during this work. Wake now requires each Realized by entry to include a
resolving commit identifier and its subject. Root added subjects obtained
from Git, removed obsolete duplicate empty Realized by sections, and
preserved the same implementing commits. Each change followed wake's
named decision. Wake now requests `run LIVE-001`. No requirement or
historical evidence result changed.
