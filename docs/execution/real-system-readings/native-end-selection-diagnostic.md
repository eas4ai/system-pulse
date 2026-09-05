# Native selection diagnostic capture

The diagnostic copied the failed run's frozen harness and added eight
cached-node observations around table entry, initial End, and its existing
selection acknowledgement. It added no keys, traversal, or sleeps, and
changed no budget constants. Observation overhead can alter timing, so this
is not acceptance evidence. [Artifacts and hashes](native-end-selection-diagnostic.json).

The initial End succeeded. The first selection poll still observed the
close button focused and first row selected; acknowledgement completion
observed the table body focused and expected last row selected. End to
acknowledgement took about 0.626 seconds. The earlier eight-second failure
was not reproduced; delayed initial focus alone does not explain it.

Later, the 64-Up burst's five-second acknowledgement expired inside the
Processes row walk. Read-only investigation is checking traversal cost
and live identity/index changes. No production correction follows merely
from the earlier 31 ms Tab-to-End interval. The app and transport were
reaped after failure, with no cleanup errors or forced transport kill.
