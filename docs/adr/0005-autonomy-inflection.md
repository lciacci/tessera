# ADR-0005: The autonomy inflection — Tier 1 reordered, spend promoted to Tier 1

- **Date:** 2026-07-11
- **Status:** Accepted
- **Decision driver:** Project decision — "the framework was built human-in-the-loop first, deliberately. Is that phase over?" Raised by Lorenzo after the gate-recording backstop closed the last principle-#17 violation.

---

## Context

Tessera's doctrine is heavily supervised. Principle #12 (*Claude proposes, user disposes*),
the suggestion-gate convention, numbered decision points, the gate journal — the whole
posture assumes a human in the loop on every turn. On 2026-07-11 that posture got *tighter*:
a Stop-hook backstop (`0d93edf`) made gate recording harness-triggered rather than
recall-triggered, because the model was missing ~85% of gates.

Reading only the repo, the obvious inference is that supervision is the destination. **That
inference is wrong, and it was made in this session before being corrected.** The
human-in-the-loop phase was the **on-ramp**: the gates, the gate log, the haze scores, the
watcher fire-log are the *instruments you build before you can trust an agent to run without
you.* They are autonomy preconditions, not alternatives to autonomy.

Lorenzo's framing, verbatim in intent: *build the framework up with a human in the loop
before jumping to unsupervised work — and that time is now, because the friction is here and
the patterns are built up.*

The roadmap's Tier 1 (`_project_specs/00-autonomous-engineering-roadmap.md`) was written in
April 2026, before three months of dogfood. Its ordering no longer matches the evidence.

## Evidence

1. **The agent does not flail.** 12 Mnemos-scored sessions, every one in the `clear` band,
   max haze 0.09 — including sessions of 628, 567 and 562 turns. Baseline competence is not
   the blocker.
2. **Escalation's trigger already fires organically, four times, all the same category.**
   The gate logs contain four events that are not gates but *escalations with nowhere to go*:
   `route-task BLOCKED — Ollama down` (tessera); `v1 launch halted — spot
   InsufficientInstanceCapacity`, `Chunk 2 boot blocked — on-demand dry in all us-east-1
   AZs`, `Blocked on capacity, did offline prep` (conclave). All four are **an external
   resource was unavailable.** The taxonomy named itself; it was not designed.
3. **The real autonomy boundary is spend and irreversible infrastructure — not design.**
   The downstream gate corpus inverts the intuition. In conclave, **11 of 22 gates (50%) are
   `aws-launch` / `aws-teardown` / `aws-spend`** — booting g6e.xlarge GPUs, tearing them
   down, "~45min, ~$2–3". Framework-development gates, by contrast, are 54% `design` —
   abstractions an agent could plausibly learn to self-dispose. **An unsupervised agent in
   conclave is an agent that boots GPUs on its own.**
4. **Spec 03's pilot de-risked spec 03 by finding the risk.** The observatory-watcher's P2
   predicate fired *correctly on a proxy that tracked no real pain*; the honest response was
   to fix the predicate, not build what it flagged. Spec 03 wants to auto-generate property
   tests from prose postconditions — that is P2-shaped failure at scale, and the blast radius
   inverts (P2 cost one noisy session-start line; a bad generated contract costs a broken
   build, or false confidence in a green suite).

## Decision

**1. Tier 1 is reordered `07 → 03 → 01`.**

- **07 (escalation) first.** It is the suggestion-gate's *asynchronous* form: #12 structurally
  requires a human to dispose, and unsupervised there is none. It was not buildable until the
  gate itself became trustworthy — which happened the same day. v1 shipped (`f52407c`).
- **03 (verifiable contracts) second**, and only after calibration data exists, per the P2 risk.
- **01 (runtime observability) last**, gated on a downstream actually deploying to real users.
  There is nothing to observe until then.

**2. Spec 06 (cost/budget awareness) is promoted from Tier 3 to Tier 1.**

The roadmap files it under "frontier / optional" and justifies it as *"agents stuck in loops
burn real money."* The gate corpus says that framing is too weak. Spend is not a tail risk of
autonomy in this codebase — **it is the single largest category of gate in the flagship
downstream**, and it is the one class of decision that is irreversible in the way that
matters (money leaves; a wrong refactor can be reverted). A hard budget stop is therefore a
**precondition** of any unsupervised downstream run, not an optimization to add later.

**3. Graded escalation waits for calibration.** `should_fire` — the gate contract's
ground-truth column — is `null` on every event ever recorded. Until it is labeled, any
escalation *threshold* is guesswork. v1 therefore escalates only on **hard blocks**, which are
unambiguous and need no threshold.

## Alternatives considered

- **Decline Tier 1 as a program; keep harvesting the convention→channel pattern by hand.**
  Argued for in-session and **rejected on correction.** It rested on reading the supervised
  doctrine as a terminal preference rather than a staging strategy. The surviving fragment of
  it — that hand-built channels teach you things an engine hides (the watcher taught us P2 was
  a bad predicate; the gate-scan taught us its own last-block blind spot) — is why 03 is
  sequenced *behind* calibration rather than dropped.
- **Take Tier 1 in its original order (01 → 03 → 07).** Rejected: 01 has nothing to observe,
  and 03's central mechanism carries the P2 risk with no calibration data to mitigate it.

## Consequences

- **The escalation channel is model-invoked, which is a known #17 exposure** (the same shape
  as the gate recorder before its backstop). Accepted for now because a blocked agent cannot
  proceed — the failure mode is a bad summary, not silence. **Not survivable under autonomy.**
  Backstop trigger: the first real unsupervised run.
- **The calibration corpus is truncated.** Measured 2026-07-11 against the downstream
  transcripts: howler logged 4 of 43 gate-shaped turns (**91% unlogged**), conclave 22 of 57
  (**61%**). The backstop is now wired into both, so the corpus becomes trustworthy going
  forward — but everything logged *before* today is a biased sample, skewed toward gates the
  model thought notable enough to record.
- **Spec 06 has no implementation yet.** Promoting it to Tier 1 means unsupervised downstream
  work is *blocked on it*, which is the intended consequence — not a delay to route around.

## Re-evaluate trigger conditions

- **`should_fire` gets labeled** on a downstream corpus → revisit graded escalation, and
  revisit whether spec 03's auto-generation is safe to attempt.
- **First real unsupervised run** → build the escalation Stop-hook backstop (a session that
  ends blocked without raising a packet is the failure to catch).
- **A downstream deploys to real users** → spec 01 unblocks.
- **The gate corpus stops being spend-dominated** (e.g. a downstream with no infra cost
  becomes the primary autonomy target) → re-examine the spec 06 promotion; it is justified by
  *this* corpus, not by a general law.
- Next cadence review: 2026-10-09 (90 days).

---

## References

- `_project_specs/00-autonomous-engineering-roadmap.md` — Tier 1 reorder rationale
- `_project_specs/07-human-escalation-protocol.md` — v1 scope + what was cut, with triggers
- `docs/contracts/escalation.md` — the packet contract
- `docs/observatory.md` → "Suggestion-gate (#12) is a convention, not machinery" — the ~85%
  miss finding and its backstop
- `0d93edf` gate-scan backstop · `f52407c` spec 07 v1 · howler `bc0df98` · conclave `8a8a8c3`
