# Process table improvements

Status: Agreed 2026-09-08
Prefix: PROC

The developer requested these changes while Mac performance verification was
running, then agreed to stop optimization and move to this work. The original
requests are retained in the process-table and privileged-action backlog records.
The application remains native GPUI, with existing one-second collection, stable
process identities, sorting, selection and process navigation preserved.

[PROC-001] The process table MUST expand with the available window width and keep headers aligned with virtualized rows.
Falsifier: enlarging the window leaves unused table width beside fixed-width columns, header and row boundaries disagree, or narrow windows lose access to columns through horizontal scrolling.
Mechanism: focused layout tests and native Linux and Mac resize observations at ordinary, enlarged and minimum supported window sizes.

[PROC-002] The process search input MUST remain compact when the window grows.
Falsifier: excess window width stretches the search input, filtering stops working, or the toolbar clips at the minimum supported window size.
Mechanism: focused toolbar tests and native resize, search and clear observations on Linux and Mac.

[PROC-003] The macOS process table MUST hide the Threads column while Linux retains it.
Falsifier: macOS exposes a Threads header, cell or sorting choice, Linux loses its existing column, or column counts, accessibility, sorting and keyboard navigation disagree with the visible layout.
Mechanism: platform column tests and native table, sorting and keyboard navigation observations on Linux and Mac.

[PROC-004] End and Force Quit MUST support action-scoped system password authentication when a process requires administrative permission.
Falsifier: the application runs its normal UI as root, stores or receives a password itself, executes a different action or process identity after authentication, signals after cancellation or identity change, hides authentication failure, or cannot complete a permitted privileged action.
Mechanism: process-control boundary and failure tests plus native system-authentication, cancellation and controlled-process observations. Password entry belongs to the operating system, not application storage or diagnostic output.

[PROC-005] The changes MUST preserve process selection, sorting, filtering, identity checks and ordinary unprivileged process controls.
Falsifier: resizing or platform columns change selected identity or sort meaning, recycled PIDs can receive an action intended for the prior process, or ordinary End/Force Quit and their confirmation/error states regress.
Mechanism: existing and affected model/application/collector tests, native process-table replay and applicable package validation.
