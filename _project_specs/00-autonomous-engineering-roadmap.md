# Autonomous Engineering Roadmap

A set of specs closing the gaps between claude-bootstrap's current code-intelligence stack (`codebase-memory-mcp` + `iCPG` + `Joern/CodeQL` + `Mnemos` + `code-deduplication`) and what an autonomous coding agent actually needs to ship changes without supervision.

## Why these?

Autonomous agents fail in 10 specific, repeatable ways (see [comparison doc in chat history — 2026-04-20](#)). Our current stack addresses 9 of them. The specs below close the remaining agent-observable gaps and add the two "frontier" capabilities (multimodal ingestion, verifiable contracts).

## Priority order

**Tier 1 — highest leverage, unlocks the rest:**

| # | Spec | Why it matters |
|---|---|---|
| 07 | [Human escalation protocol](07-human-escalation-protocol.md) | **STARTED 2026-07-11.** The suggestion-gate's *asynchronous* form. Principle #12 (Claude proposes, user disposes) structurally requires a human present; unsupervised there is no disposer, so a blocked agent must package and queue instead of compounding or exiting with an unactionable summary. |
| 03 | [Verifiable contracts](03-verifiable-contracts.md) | iCPG postconditions are currently natural-language. Generating property-based tests from them makes them machine-checkable. **Sequenced after 07 — see the P2 risk below.** |
| 01 | [Runtime observability](01-runtime-observability.md) | Drift detection is static — an agent that ships code needs a production feedback signal. **Gated on a downstream actually deploying to real users**; there is nothing to observe until then. |

> **Tier 1 reordered 2026-07-11 — the inflection point.** The original order (01 → 03 → 07)
> was written in April 2026. Three months of dogfood reorder it, on evidence:
>
> - **The human-in-the-loop phase was the on-ramp, not the destination.** The gates, the
>   gate log, the haze scores, the watcher fire-log — these are the *instruments you build
>   before you can trust an agent to run without you*. They are autonomy preconditions, not
>   alternatives to autonomy. That phase has now produced enough wiring to read.
> - **07 goes first because the gate machinery just became reliable.** The Stop-hook
>   gate-scan backstop (2026-07-11) made gate *recording* harness-triggered instead of
>   recall-triggered. Escalation is what that same gate becomes when nobody is there to
>   dispose of it. It was not buildable before the gate was trustworthy; it is now.
> - **Its trigger already fires organically.** The gate log contains
>   `"wire route-task: BLOCKED — no classifier on this machine (Ollama down)"` — an
>   escalation packet with nowhere to go, so it landed in the gate log instead. The event
>   shape exists; only the channel was missing.
> - **03 is sequenced *after* on the pilot's own evidence.** The observatory-watcher pilot
>   was meant to de-risk spec 03 and did — by finding the risk. **P2 fired correctly on a
>   proxy that tracked no real pain**, and the honest response was to fix the predicate, not
>   build what it flagged. Spec 03 wants to *auto-generate* property tests from prose
>   postconditions: that is P2-shaped failure at scale, and the blast radius inverts (P2 cost
>   one noisy session-start line; a bad generated contract costs a broken build or false
>   confidence in a green suite). It needs calibration data first.
> - **The calibration corpus is currently the wrong population, and we know it.** All 28 gate
>   events come from *framework development* — design-heavy meta-work, 54% `design` kind.
>   Autonomy will not run Tessera; it will run the downstreams. Gate distribution from a
>   downstream build session is the corpus that matters, and it does not exist yet.
> - **`should_fire` is null on all 28 events.** The contract left it nullable as the
>   ground-truth column, and it has never been labeled. Until it is, any escalation threshold
>   is guesswork — which is why v1 escalates only on *hard blocks* (unambiguous, needs no
>   threshold) and defers graded escalation.
>
> Much of the autonomy substrate already exists and this roadmap does not credit it:
> `polyphony` (container-isolated agents on independent branches), `subagent-route`,
> `tier-classify`. **The gap was never execution — it was the escalation channel.**

> **Entry point (2026-07-09).** If Tier 1 is taken up, spec 03's observatory pilot
> is the cheapest first move: it tests this tier's central premise — *prose
> conditions go silently unchecked* — on a corpus where a wrong predicate costs a
> noisy session-start line rather than a broken build. Evidence it isn't
> theoretical: on 2026-07-09, three observatory triggers were found at or past
> threshold, unnoticed, by running three shell commands. The observatory-watcher
> idea was folded here rather than into spec 01, which observes the *deployed
> product*, not the framework's own invariants.

**Tier 2 — valuable, not blocking:**

| # | Spec | Why it matters |
|---|---|---|
| 08 | [Auto CODE_INDEX](08-auto-code-index.md) | The capability index currently depends on humans maintaining it. Auto-derive from the graph. |
| 04 | [Multi-agent coordination](04-multi-agent-coordination.md) | When two agents touch the same area, we need locking / negotiation |
| 02 | [Rollback & recovery](02-rollback-and-recovery.md) | Drift flags a problem; we still need automated revert paths |

**Tier 3 — frontier / optional:**

| # | Spec | Why it matters |
|---|---|---|
| 05 | [Confidence calibration](05-confidence-calibration.md) | Reinforcement loop — learn from past agent actions which patterns fail |
| 06 | [Cost / budget awareness](06-cost-budget-awareness.md) | Agents stuck in loops burn real money. Hard budget stops. |
| 09 | [Multimodal ingestion](09-multimodal-ingestion.md) | Graphify-style. Only matters if your repos include docs/images/video. |

## What each spec contains

- **Context** — the failure mode being addressed
- **Goal** — one-sentence outcome
- **Approach** — concrete integration points with existing skills/scripts
- **Success criteria** — how we know it works
- **Effort** — rough size (small / medium / large)
- **Depends on** — other specs that should land first

## Implementation convention

When picking up a spec:

1. Create a feature branch `feat/spec-XX-<short-slug>`
2. Write good Conventional-Commit subjects — the CHANGELOG derives from them at
   release time via `bin/tessera-changelog` (subject-based, so commit trailers
   never reach the public file). No hand-maintained "Unreleased" section; the
   per-change manual step was dropped after it silently drifted two weeks.
3. Write the feature following TDD (as the rest of the project does)
4. Update the spec file's `Status` field when merged

Status values: `pending` · `in-progress` · `in-review` · `done` · `deferred`
