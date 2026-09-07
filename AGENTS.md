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
- `docs/feature-spec-dockable-system-monitor.md`: current tabbed-screen product specification.
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

Cairn is a discipline tool, not a security boundary. It checks recorded
results and freshness; it cannot judge whether a review is thorough or a
mechanism proves its requirements. A command that always succeeds can
produce passes without testing anything. The developer must challenge
unsound mechanisms, and the agent must demonstrate what makes them fail.

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

When wake says `reply <slug>`, read the developer's question and append
your explanation with `cairn answer <slug> "<explanation>"`. Run wake again
to return the decision to the developer. An `ask` answer authorizes only
an explanation; it does not authorize implementation.

Before you change code, write `.cairn/in-progress`:

    action: implement | build-decision | run-mechanism | review
    target: <requirement, decision slug, or commitment slug>
    base: <commit identifier>
    started: <iso timestamp>

Remove it when the change is committed. On wake, an existing record is
reconciled before any new work: finish or abandon the action it names.

Check execution has a separate working-tree lock. When wake names
`cairn-check.lock`, wait for a live owner. If the owner is dead or the
record is incomplete, inspect the command and any surviving children;
remove the named lock only after execution has stopped. Keep the agent's
in-progress record until its own action is finished or abandoned.

Commit before you check. `cairn check` records evidence only against a
committed tree and refuses a dirty declared input. Your own test runs
while editing are how you work; they are not evidence. Commit the new
evidence receipts and their output files after each check. Evidence
history is tracked; only .cairn/in-progress stays ignored.

Keep the candidate stable throughout a check. Cairn compares it with the
commit before execution and validates it again before recording evidence.
A changed candidate keeps its diagnostic output but gets no receipt.
Missing or damaged captured output needs a new check, never an edited
historical receipt.

When wake says `run <REQ>`, use `cairn check <REQ>`; Cairn selects its
mechanism for you. Declare every file that can affect the result, including
shared dependencies. Broad directories are easier to maintain but rerun
checks for unrelated edits. Narrow paths reduce reruns but need updating
when dependencies change. Do not omit a dependency just to shorten a run.

When wake says `review mechanism <REQ>`, compare the check with the
revised requirement and falsifier without changing code. Record what you
examined and any mismatch in the existing commitment review. Fix a
mismatch as a separate implementation action. Try a safe violating example
and the corrected case; record the results, or why that demonstration is
impractical. Add the exact `REQ sha256:...` entry wake prints to
the declaration's `reviewed:` list only after that review. Commit before
check. Copying the digest alone does not establish that the check works.
Apply the same failure demonstration when building a new check.

Decide by level. Routine: decide, no record. Judged and above: record
it with `cairn decide` before you build it. Blocking: `cairn escalate`,
then stop. Three attempts at a requirement without new passing evidence
make the next decision about it Blocking. An attempt is one distinct
digest of the mechanism's declared inputs among the failing checks
since the last pass; reruns, documentation changes, and a return to a
digest already tried add nothing, and the first check of a
requirement is its baseline, never an attempt. A failure no change
inside the footprint can address is not an attempt at all: it is an
escalation, and the wake names DEC-019 when it sees three runs at one
digest. A failing requirement every commitment inherits is repaired
under the current commitment; its mechanism's inputs are already in
the footprint, and a fix outside them means the declaration was
incomplete: declare, then fix.

Out of scope is captured, never built. An idea outside the current
commitment goes to `cairn backlog --title ... --body ... --from <REQ>`.
It enters a commitment only when the developer writes it into the
specification and names it there.

Review before Done. When every requirement passes, examine the work for
what the mechanisms would miss, record what you attacked and what you
found in `.cairn/reviews/<slug>.md`, and change no code while you look.
A finding is resolved as its own work, after the review is recorded.

## Writing for the developer

Write so the developer can understand the choice and its consequences
after one reading. Apply this to questions, specifications, records,
and progress reports.

- Name who does what and what changes for the user or system. Use
  familiar words, concrete examples, and short sentences.
- Match the explanation to the developer's knowledge. Explain an
  unfamiliar technical term when it matters to the decision. Keep
  technical detail that changes the answer; remove jargon that only
  makes the sentence sound authoritative.
- When asking for a decision, state the actual choice, your
  recommendation, why it helps, and what the alternative changes.
  Explain costs or risks in terms of what could happen. For an
  escalation, put this information in the existing fields.
- With a decision or agreement prompt, say: "If this isn't clear, ask
  me to explain it another way before you decide." For an escalation,
  put the invitation after the options on the existing Reply line.
- Distinguish what you observed from what you assume or do not know.
  Keep important limits visible when shortening an explanation.
- Before sending, ask whether the developer can tell what their answer
  would authorize without decoding internal names or abstract labels.
  Rewrite any sentence that hides that choice.
- If a reply shows a misunderstanding, explain the choice again before
  treating the reply as agreement. Silence alone is not confirmation.

For example: "Should the app save unfinished drafts so users can reopen
them later?" names the behavior the developer is deciding about.

## The developer

An escalation awaits you in `.cairn/escalations/<slug>.md`. Answer it:

    cairn answer <slug> ok | instead <what> | ask <question>

Use `ask <question>` whenever the explanation is unclear. The agent will
reply in the same file, then the decision returns to you. Answer `ok`,
`instead <what>`, or ask another question. Only `ok` or `instead` closes it.

A queued decision awaits you in `.cairn/queue/<slug>`; its record is in
docs/decisions/. The agent did not wait for you. Reading it and
removing the queue entry in a commit is the review; the commit's author
and date are the mark. To reverse it, have the agent supersede the
record with the cause named.

The next commitment is yours. Write the requirement into the
specification with its falsifier, name it in a commitment file, and
move the roadmap's Current: line.

Merge other branches with `git merge --no-ff` so their commits stay off
this loop's first-parent history. Cairn checks each of this loop's own
commits; reverting a change does not erase a footprint breach. Declare a
missing input when it belongs to the commitment. Otherwise capture the
work in the backlog and ask the developer to resolve its scope.
