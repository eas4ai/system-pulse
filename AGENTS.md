@/home/shawn/.codex/RTK.md
@/home/shawn/.codex/TILTH.md
@/home/shawn/.codex/PARTNERSHIP.md
@/home/shawn/.claude/BEST_PRACTICES.md

# System Pulse repository

The application belongs in `/home/shawn/workspace2/task-manager`. This is its source repository and publication home. Do not use the GPUI framework fork as the application's primary repository.

- `src/`, `assets/`, `package/`: application, bundled assets and package support.
- `crates/model/`, `crates/collectors/`: application model and host collectors.
- `crates/base/`, `crates/ui/`: patched GPUI Kit 0.6 libraries used by the application. Unmodified macros and icon assets come from Cargo dependencies.
- `vendor/`: retained native adapter patches and their license notices.
- `docs/feature-spec-dockable-system-monitor.md`: original product specification.
- `docs/spec/`, `docs/commitments/`, `docs/plans/`: current contract and execution state.
- `scripts/system-pulse/`: verification, native replay and packaging.
- `reference/`: local third-party design/reference snapshots; keep these separate from application source and preserve notices.

From this repository root, `cargo run --locked` runs System Pulse. Use `cargo test --locked -p system-pulse` for its tests and the documented application acceptance command for full native/package verification. Use rustfmt defaults, descriptive Rust names and the specification's monitor, sensor, meter, dock layout and preset terms.

Keep exactly one todo item in progress for multi-step work. Mark work complete only after its implementation and verification pass. Preserve unrelated local files and edits. Keep source, setup instructions and verification claims consistent.

# Working agreement

This repository runs under Cairn. The specification in docs/spec/ is
the contract, the roadmap names the current commitment, and the
referee, `cairn`, reads the repository and names the next action. This
file says what each party does when it is their turn.

## The agent

Wake. Before anything else, run `cairn wake`. Read the glossary, the
keystone, the roadmap, the current commitment, and the decision records
for what it names. Nothing you remember from an earlier session counts; the
repository does.

Act on the verdict, and only on it.

- Resolvable: do the one action named. Then run `cairn wake` again.
  Do not stop while the verdict is Resolvable.
- Escalate: present the escalation file to the developer, in its own
  words, and stop. Do nothing else until it is answered.
- Done: the commitment is complete. Report it, and stop. The next
  commitment is the developer's to name.

Before you change code, write `.cairn/in-progress`:

    action: implement | build-decision | run-mechanism | review
    target: <requirement, decision slug, or commitment slug>
    base: <commit identifier>
    started: <iso timestamp>

Remove it when the change is committed. On wake, an existing record is
reconciled before any new work: finish or abandon the action it names.

Commit before you check. `cairn check` records evidence only against a
committed tree and refuses a dirty declared input. Your own test runs
while editing are how you work; they are not evidence.

Decide by level. Routine: decide, no record. Judged and above: record
it with `cairn decide` before you build it. Blocking: `cairn escalate`,
then stop. Three attempts at a requirement without new passing evidence
make the next decision about it Blocking.

Out of scope is captured, never built. An idea outside the current
commitment goes to `cairn backlog --title ... --body ... --from <REQ>`.
It enters a commitment only when the developer writes it into the
specification and names it there.

Review before Done. When every requirement passes, examine the work for
what the mechanisms would miss, record what you attacked and what you
found in `.cairn/reviews/<slug>.md`, and change no code while you look.
A finding is resolved as its own work, after the review is recorded.

## The developer

An escalation awaits you in `.cairn/escalations/<slug>.md`. Answer it:

    cairn answer <slug> ok | instead <what> | ask <question>

A queued decision awaits you in `.cairn/queue/<slug>`; its record is in
docs/decisions/. The agent did not wait for you. Reading it and
removing the queue entry in a commit is the review; the commit's author
and date are the mark. To reverse it, have the agent supersede the
record with the cause named.

The next commitment is yours. Write the requirement into the
specification with its falsifier, name it in a commitment file, and
move the roadmap's Current: line.
