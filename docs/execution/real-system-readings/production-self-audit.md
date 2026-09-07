# Production self-audit: real system readings

Standard: machine `BEST_PRACTICES.md` version 1.1.0, 2026-09-01. No source
repository override exists. Reviewed implementation is the committed input set
at `bb87134b978f8c2400ff1cbed755ca5ee9615d28`; later acceptance documentation
and receipts do not change those inputs.

The [full acceptance](final-acceptance-pass.md) and its [retained record](final-acceptance-pass.json)
provide the verification below. Final independent review passed with no actionable findings. Cairn subsequently
returned Done with exit zero; the [completion record](completion.md) retains it.

| Rule | Review and evidence |
| --- | --- |
| 1. Understand before editing | The agreed LIVE contract, capability matrix, collector/integration boundaries, implementation plan and Judged records identify the real-reading outcome and preserved workspace behavior. |
| 2. Small coherent changes | Collector and presentation changes follow those boundaries. Native verifier corrections have retained failures and bounded decisions; the final correction changes one condition. No unrelated product feature was added. |
| 3. Maintainable ownership | Collection, physical model, presentation, persistence and verifier responsibilities have distinct modules. Independent implementation reviews inspected boundary/error paths. |
| 4. Boundary contracts | Typed physical values retain identity, source, units and availability. PID/start identity, backend errors, diagnostic-frame identity and saved-state validation have failure regressions and host/native evidence. |
| 5. Errors and secrets | Failed readings keep explicit reasons; failed captures keep actual outcomes. Process arguments and environments are not collected. No credentials or third-party messages are part of delivery. |
| 6. Security | Process source/identity joins reject substitution and PID reuse; malformed saved state remains protected. NVIDIA loading is an optional backend boundary; missing driver does not become a hardware-accuracy pass. |
| 7. Surviving state changes | Stable device/sensor choices survive discovery and restart. Invalid schema and malformed JSON recovery, preserved originals and missing saved-device restoration passed the complete native replay. |
| 8. Performance and reliability | Host collection runs outside UI updates through one bounded latest-only service. History keys are evicted for absent devices. Held input, scrolling, collapse and normal cleanup passed with active sampling; native observers and retries retain declared limits. |
| 9. Track multi-step work | The implementation plan and handoff now mark all authorized code and verification complete after actual review/Done gates passed. Historical failed work remains recorded. |
| 10. Verify what matters | 745 executed tests, formatting, strict Clippy, native build, independent host comparisons, sixteen controlled-child native comparisons and every full replay stage passed. Root checked all 154 declared artifact hashes, all command logs and 242 retained file hashes. |
| 11. Report honestly | Four independently explained ordinary-process counter gaps remain unverified. NVIDIA hardware accuracy, other native platforms, physical unplug and direct diagnostic access to every history point retain explicit limits. Historical failures were not relabeled. |
| 12. Technical partnership | The confirmed real-reading and NVIDIA scope, process-exit policy and preserved no-tab/collapse requirements govern delivery. Implementation/review proceeded without repeating settled permission questions. |
| 13. Release gate | Independent final review passed with no actionable finding and actual current Cairn Done was recorded with exit zero. |
| 14. Simple technical English | Current overview, glossary, acceptance report and handoff name observed behavior, actual checks and limits directly. Historical records retain their original scope and dates. |

The completed implementation and independent review satisfy the production rules.
No revision is needed. The final referee verdict and completion records are retained.
