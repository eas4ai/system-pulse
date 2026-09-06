# Navigation observation replay: stale frame failure

The fresh focused replay against `57aec38298abdf84b04f31827b5f7d21f17c11c3` finished **FAIL**
with publication tracing disabled. It is supporting verification, not full
aggregate acceptance. The [record](native-navigation-observation-stale-failure.json)
retains the metadata, thirteen navigation observations and all 97 artifact hashes.
Artifacts: `/home/shawn/workspace2/task-manager-artifacts/tmp/pulse-navigation-observation-1rqv69wz/native`.

Launch, metrics, collapse, charts and inner scrolling passed. Held-input evidence
was retained but its enclosing case was not finally marked PASS. No controlled
child metric comparison or exit proof completed. The child was
`process:1205904:75143246`. Application PID 1198513 was terminated in cleanup and
no longer existed; transport PID 1198431 exited zero without forced kill. Binary
and running-executable SHA-256 both match `7dbcd3adfae54db64e3ed5f32cf728ee55684fd1429c95c1bbd1e72a770340e7`.

## Freshness failure

The reader rejected sequence 95/revision 94 at age 2.116767208 seconds against
the unchanged two-second limit. Read time was 4.030536 ms,
parse time 18.346280 ms and read-start through age check
22.652864 ms. The opened device/inode was
66318/222692849; pathname identity before the check was 66318/222692852. This
directly establishes replacement during the observation. It does not identify
the replacement's contents or the producer delay. Later retained frames are
sequence 96/revision 95 and sequence 97/revision 96; later inode reuse cannot
establish a replacement-content match at the earlier check.

## What navigation observations add

All thirteen observations were retained with no eviction. Earlier completed
selection scans took approximately 23–52 ms. They show previous instantiated
selection, one rejected publication bracket and temporary absence of instantiated
selection, followed by exact endpoint acknowledgements. Recovery blocking could
remain latched while an ordinary acknowledgement subsequently succeeded; that
does not establish that blocking caused the earlier diagnostic's timeout.

The last acknowledged endpoint was `process:4012042:74522983`. The failed batch
expected `process:4011980:74522958` at index 1414, issued two Up keys and retained
the same batch deadline. Observation 13 failed during its initial frame read,
before panel checks or a selection scan. This failure is freshness, not expiry
of the eight-second navigation deadline.

The matching baseline-stat journal timestamp is 751436879264901; the next batch
journal timestamp is 751438236313959, a gap of 1.357049058 seconds. These timestamps
alone do not identify whether journal writing, intervening preparation or
scheduling consumed the interval. Independent source/evidence diagnosis is recorded below. No performance remedy
or deadline relaxation is inferred.

The earlier traced publication run did not reproduce this freshness failure.
This run has navigation observations but no producer stage trace. All previous
failures remain failed; fresh full aggregate acceptance and final review remain
required.

## Independent diagnosis and next observation

Reviewer `review_publication_quality` confirmed the artifact arithmetic, all
thirteen observation records, exact prior acknowledgement, live baseline
validation and disabled publication tracing. Frozen driver, pending validator
and observation helper matched current source byte-for-byte. This read-only
review made no edits, builds or live runs.

The failing initial frame observation had approximately 6.439 seconds left in
its batch deadline. The recovery-blocked latch did not prevent the previous
exact acknowledgement or cause this next batch's stale read.

`journal()` samples its timestamp after acquiring its lock and opening the
append file. The 1.357-second interval includes the first record's serialization,
write, close and lock release; in-memory stat validation and pending/publication
construction; the next lock acquisition and file open; and possible scheduling
delays. There is no journal fsync or additional accessibility/procfs read in that
source interval. Existing timestamps cannot attribute its cost to one stage.

The next routine verification action is one combined diagnostic with the existing
publication tracing switch and bounded navigation observations. It changes no
source or acceptance policy and may not reproduce the failure. It cannot count
as acceptance. A performance remedy remains unsupported; fresh untraced full
aggregate acceptance and final review remain required.
