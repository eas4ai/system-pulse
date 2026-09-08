# Expand the process table with the window and keep search compact

Surfaced from: PERF-005
Captured: 2026-09-08T20:49:47.078Z

Developer reported the process table remains at a fixed width when enlarging the window and separately requested that the search input not expand. Allocate excess table width consistently between headers and virtualized rows while retaining narrow-window horizontal scrolling. Keep a compact search field. Verify actual bounds, column alignment and keyboard navigation after resizing.
