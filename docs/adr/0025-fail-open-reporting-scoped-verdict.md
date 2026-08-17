# ADR-0025: Spec 11's bar is met and the general claim is not — the mechanism is proven, the coverage is one component

- **Date:** 2026-08-17
- **Status:** Accepted
- **Executed:** 2026-08-17 — `docs/observatory.md` (the "Fail-open everywhere" entry is promoted and carries this ADR as its resolution). **Nothing is BUILT by this decision, deliberately** — see §Decision, point 4.
- **Decision driver:** Trigger fired. `docs/observatory.md` → "Fail-open everywhere — Tessera cannot tell you when it is broken" states *"Promote to an ADR once spec 11 ships and the bar is met."* Spec 11 shipped 2026-07-27. The bar's second clause — confirmation by an independent session — was satisfied 2026-08-17.

---

## Context

The entry this ADR closes is the one the observatory itself calls **"the most consequential entry in this file"**. It was written after the 2026-07-12 F-001/venv session, in which eight bugs were found and *not one announced itself*: every one surfaced because a human got suspicious or an adversarial verifier ran in a clean context. Its claim was about the framework as a whole — Tessera cannot report its own failure — and it named a precise closure bar:

> **Close when:** a deliberately-broken component (venv removed, guard corrupted, hook typo'd, `python3` pointed at 3.9) is detected by the framework *within one session, without a human asking* — and **confirmed by an independent session, not the one that built it.** That is the bar. Nothing today would have met it.

It has sat at `Investigating` for 36 days. Spec 11 shipped on 2026-07-27 — `tessera-degraded`, `tessera-watch` P13, and 11 chaos probes, the last three added by the A5b audit after it found that a hook can run perfectly while its *runner* is gone.

## Evidence

**1. The bar's mechanical half is met, and was verified independently.** `bin/tessera-chaos` returns 11/11 green, run 2026-08-17 in a session 21 days after the one that built the probes. All four failure modes the bar enumerates are covered. The probes were written and watched **RED before the mechanism existed**, which is what makes them instruments rather than mirrors.

**2. The wild corpus is one component and one failure mode.** All 16 `degraded` events ever written, across 47 session logs:

| n | component / reason | what they are |
|---|---|---|
| 6 | `standing-patterns / block-missing` (08-09, 08-10) | **Real accidents.** Authoring a new handoff section orphaned the standing-patterns block for ~90 seconds. Nobody was probing; the detector caught it, twice, in two separate sessions. |
| 8 | `standing-patterns / block-missing` (08-16) | A deliberate re-plant, verifying the first six. |
| 2 | `spend-guard / deny-list-bypassable` (07-27) | Deliberate. Both details begin **"Probed"**. |

So exactly **one** component has ever reported a genuine unplanned failure without being asked, from **one** cause, inside a two-day window. That is real evidence and it is not zero. It is also not "the framework reports its own failure."

**3. The measurement nearly went the other way, which is itself the argument.** The first query over the session logs returned **0 degraded events** — it keyed on `event` where `tessera-degraded` writes `type`. The only reason it was caught is that P13 had printed *"10 degraded event(s) in 7d"* at SessionStart minutes earlier, and the contradiction was believed over the query. That is F-001's shape (`empty ≠ unused`) recurring inside the audit of the mechanism built to defeat it — and it is a live demonstration that a reader can report "nothing is broken" while looking at the wrong field.

**4. P13 has no acknowledgment state, and 14 of 16 events are one noisy detector.** A fixed condition can only be waited out or snoozed, and snoozing blinds the predicate to *new* events. G-a fires on P13's streak with no right answer available. A channel that trains its reader to ignore it cannot carry an autonomy precondition.

## Decision

**1. The observatory entry is promoted and closed by this ADR — with a scoped claim, not a general one.**

**What is claimed:** the reporting *mechanism* exists, is wired into hook bail-outs, the `settings.json` trailing branch and three surfacers, and is verified against 11 deliberate breaks by a session that did not build it. A component that fails in one of the eleven probed ways will say so within one session.

**What is NOT claimed, and must not be quoted as if it were:** that Tessera reports its own failures generally. The probes establish that the *channel works when a known break is induced*. They do not establish coverage of unknown failure modes, and the wild corpus supporting that broader reading is one component, one cause, six events.

**2. The general claim keeps a named evidence bar of its own.** It is met when **three distinct components** have each reported a genuine unplanned failure — not a probe, not a re-plant — without a human asking. Today the count is **one**. This is deliberately a count of *components*, not of events: 8 events from one re-plant of one detector is the number that would otherwise make this look satisfied.

**3. ADR-0005's readiness assessment is formally due, and this ADR does not perform it.** ADR-0005 declared its preconditions met on 2026-07-12; the spend guard was subsequently found to fail open and the escalation backstop shipped with its fire-counter past its cap, disabled in every clone. Both are fixed. Whether that restores the readiness claim is a separate judgement with its own cadence (2026-10-09) and its own decision-maker, and folding it into a spec-11 verdict would repeat the error ADR-0005 is criticised for — declaring readiness from adjacent evidence.

**4. Nothing is built by this decision.** No new predicate, no P13 change. The verdict is the deliverable. Recorded explicitly because an ADR that records a finding and ships no artifact is exactly the shape `Executed: not yet` exists to make visible, and here the absence is intended rather than pending.

## Alternatives considered

- **Close the entry outright as satisfied.** Rejected on the corpus. The bar's words are met, but the entry's *subject* is the general claim, and closing on eleven self-induced probes would assert framework-wide reporting from evidence that covers one component. That is precisely the move ADR-0005 made in July — readiness declared from adjacent evidence — and this entry exists because that declaration was wrong.
- **Leave it at `Investigating` until three components report in the wild.** Rejected: the entry names a bar, the bar is met, and refusing to record that is its own dishonesty. It also leaves the *mechanism* question permanently open when it has a real answer, and buries the sharper unanswered question — coverage — inside a resolved one.
- **Build P13's acknowledgment state first, then adjudicate.** Tempting, and rejected on sequencing rather than merit. The noise is real and worth fixing, but a verdict withheld pending an unrelated build is how this entry accumulated 36 days. The noise is recorded here as a consequence and remains open.
- **Fold the ADR-0005 re-assessment into this ADR.** Rejected — see Decision point 3.

## Consequences

- **The framework may now say its reporting mechanism is verified. It may not say its coverage is.** Any artifact quoting this ADR — the promo page especially — carries the scope or misrepresents it.
- **The count of components with wild evidence is now a tracked figure (1 of 3)**, which is a claim that will drift if unmaintained. It is small and mechanical: `degraded` events whose detail is not a probe or re-plant, grouped by component.
- **P13's noise is unresolved and is the practical blocker.** 14 of 16 events are one detector, and the missing acknowledgment state means correct-but-spent fires cannot be cleared.
- **The A5b lesson stands and is the reason the probe count is 11 and not 8:** a hook can run perfectly while its runner is gone, and no code inside a hook can report that.

## Re-evaluate trigger conditions

- **Three distinct components have each reported a genuine unplanned failure, unprompted** → the general claim is supportable; write the ADR that makes it.
- **A real failure occurs that no probe covers and nothing reports it** → the scoped claim is too generous; this ADR is superseded, not amended.
- **P13 gains an acknowledgment state** → the noise consequence closes and the signal becomes usable as a precondition.
- **ADR-0005's cadence (2026-10-09)** → the readiness re-assessment this ADR defers.
- Next cadence review: 2026-11-15 (90 days).

---

## References

- `docs/observatory.md` → "Fail-open everywhere — Tessera cannot tell you when it is broken" — the entry this promotes; the evidence base and the bar
- `docs/postmortem-2026-07-12.md` — the eight-bug session that produced the claim
- `_project_specs/11-fail-open-detection.md` — the remedy's scope and ordering
- `docs/contracts/degraded-event.md` — "could not do my job" vs "nothing to do"
- `docs/adr/0005-autonomy-inflection.md` — the readiness assessment this ADR declines to perform
- `docs/adr/0006-instrumentation-not-control.md` — the charter this verdict is measured against
- `bin/tessera-chaos`, `bin/tessera-degraded`, `bin/tessera-watch` — the mechanism
