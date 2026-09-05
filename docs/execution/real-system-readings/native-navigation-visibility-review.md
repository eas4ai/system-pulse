# Navigation visibility recovery review

## First specification review

Candidate: `485c5129c2e95ddff27b2ec78fcdbcc8ff65a7cc`.

Status: open P1 finding. All 66 navigation tests passed, but an independent
probe showed recovery permission surviving a rejected pre-scroll frame.
An eligible expected index 2, original index 5, and instantiated span 5–7
set recovery active. Geometry inspection then published a frame restoring
the expected index to 5 and moving the span to 8–10. The mismatch rejected
that poll, yet the next poll scrolled and acknowledged success using the
old permission. Both eligibility guards were now false.

Re-establish fresh unique eligibility after any rejected observation before
the first physical recovery step. Freeze gesture eligibility only once
scrolling actually begins. Add the exact reproducer and preserve rejection
of incomplete geometry/membership under the same deadline. Corrective work
is separate from this read-only review. QUALITY has not begun.
