# ADR-0006: Tessera is instrumentation, not control — retarget, prune, add an adversary

- **Date:** 2026-07-12
- **Status:** Accepted
- **Decision driver:** Lorenzo, after a 90-minute F-001 session became fixes-on-fixes: *"is there any point to building something like Tessera? … burn it down or add the adversarial mechanisms and refine?"*
- **Amends:** ADR-0005's readiness assessment. Does **not** supersede its Tier-1 reordering.

---

## Context

On 2026-07-12 a venv fix became a rathole. **Eight bugs surfaced in one session and not one of
them announced itself.** Three separate "it's fixed" claims were refuted by three independent
adversarial verifications, each correct. Full evidence: `docs/observatory.md` → *"Fail-open
everywhere."*

Two of those bugs matter more than the rest, and both were in the machinery this framework
builds to keep itself safe:

- **The spend guard failed OPEN.** On a `/usr/bin`-first PATH, `python3` is macOS 3.9; PEP-604
  annotations raise `TypeError` at definition time; `guard.py` exits 1; the wrapper passes that
  through as "not 2" — which Claude Code reads as **ALLOW**. *An unauthorized GPU boot proceeds.*
- **The spend backstop shipped disabled** to every clone (fire-counter committed past its cap).

ADR-0005 named three preconditions for unsupervised operation. **All three were declared met on
2026-07-12. Two were broken, and the framework could not tell.**

That is the finding this ADR responds to. It is not a bug report. It is a statement about what
kind of thing Tessera is.

## The evidence, sorted by mechanism

Ranked by how they actually behaved under a full night of adversarial pressure:

| Tier | Mechanism | Record on 2026-07-12 |
|---|---|---|
| **1** | **Make the bad state unrepresentable** | Never fails, because there is nothing to fail. The venv killed name-drift *for the toolchain* — there is no name left to drift. |
| **2** | **Bound the blast radius OUT-OF-BAND** | **The only mechanism that never failed.** conclave's AWS budget → SNS → hardstop Lambda sits *outside the agent's trust domain*. It does not depend on the agent being correct, the hook firing, or the detector being green. |
| **3** | **Adversarial verification by an independent instance** | **The only mechanism with a 100% hit rate.** Three runs, three refutations, all correct, all finding things the author had certified as fixed. |
| **4** | **Channel (harness-triggered check)** | Works — *until it doesn't*, and then it **manufactures false confidence**. `doccheck` reported "0 false claims" over three live, wired hooks. |
| **5** | **Sentence (a rule in prose)** | Failed every single time it was load-bearing — including sentences the model wrote itself, in the same session, and re-read. |

**Every rule with a channel held. Every rule that was only a sentence failed.** That is principle
#17 getting its strongest evidence to date, at the model's expense.

### Why sentences fail — the mechanism, stated precisely

A sentence requires the model to (1) remember it, (2) **recognise that *this moment* is when it
applies**, and (3) choose to apply it. The failure is almost never (1) or (3). **It is (2).**

The model does not rebel; it *fails to notice the moment* — and it fails to notice precisely when
it is most confident, which is exactly when the rule matters most. **Sentences are weakest
anti-correlated with need.** This is why *"be more careful next time"* is not a fix: it is another
sentence, aimed at the one faculty already compromised.

### And why a broken channel is *worse* than no channel

A green `doccheck` did not merely fail to catch the bug. **It replaced human suspicion with a
checkmark.** A sentence would at least have left everyone uncertain. An ignored checker is worse
than none, because it looks like coverage — and a *green* checker is worse still, because it looks
like proof.

**A channel you have never watched fail is, epistemically, still a sentence.** You are simply
trusting it for a different reason.

## Decision

### 1. Tessera's goal is retargeted: **instrumentation, not control.**

The docs sell control — preconditions, gates, an autonomy roadmap. **Tonight proved it is not
that, and cannot be**, because every in-band mechanism is subject to the same silent failure as
the agent it guards.

> **Tessera does not make the agent reliable. It makes the agent's unreliability visible and
> bounded.**

A smaller claim. An achievable one. And a rare one — most agent harnesses never find out how they
fail; they ship, rot silently, and the rot is blamed on the model. **Tessera found out, repeatedly,
because it was built to find out. Its real product is findings, not automation.**

### 2. **Prevention over detection**, wherever prevention is available.

Every detector is a liability that must itself be verified. Every impossibility is free forever.

The session's own worked example, and it is an indictment: F-001's silent-success class exists
**only because the toolchain source sits on `sys.path`**, so `PYTHONPATH=scripts python3 -m mnemos`
succeeds on *any* interpreter. The response was a detector — grepping shell scripts for `python3`,
rewritten three times, still holed. **The stronger move was available the whole time: stop shipping
the source on the path.** Then the bad state cannot be represented, and the detector is unnecessary.

**Standing rule: before building a detector, ask what would make the state unrepresentable.**

### 3. **Out-of-band bounds are the real safety layer. Tessera's job is to ensure they exist, not to be them.**

The one mechanism that never failed lives in *conclave's Terraform*, not in Tessera. In-band guards
(the spend guard) are **authorization**, and they are worth having — but they are not the ceiling,
and they must never be mistaken for it. See `docs/contracts/spend-authorization.md`: three layers,
three trust domains, and **layer 3 is the only one an agent cannot argue with.**

### 4. **Adversarial verification becomes a channel.** ← *the highest-value change in this ADR*

It is the most effective mechanism in the system and **it is not in the system.** It rides on
Lorenzo remembering to say *"verify from another session."* That is a sentence — in a human's head
— sitting on top of the single best tool available. **It is the exact failure mode this whole ADR
is about.**

Mechanized: an independent instance, clean context, instructed to **falsify**, run before any
"done" claim on a safety path. Scoped in **spec 12**. It is worth more than spec 11.

### 5. **Prune. The framework has stopped taking its own advice.**

`skills/base` opens with *"complexity is the enemy… every line of code is a liability."* Tessera now
carries 56 skills, 13 hooks, 54 fail-open bail-outs, 4 repos — **every one a place to fail
silently.** Named candidates:

- **The gate apparatus** — recorder + Stop-hook scanner + ratio + `should_fire` labeling is four
  moving parts to answer *"did Claude ask before deciding."* At least one too many.
- **Mnemos** — the kill/keep trial has run for months and has **never produced a valid verdict**
  (`0 real` compactions; and until today its hooks wrote through a drifting interpreter, so any
  earlier verdict would have measured broken machinery). The trial is overdue, and *"we cannot
  judge it"* is itself a finding.
- **56 skills, zero ever evaluated** — FOCUS-004, overdue by principle #15.

**A framework that cannot be audited by one person in one session is too big to trust**, and
Tessera is approaching that line.

### 6. **ADR-0005's readiness claim is withdrawn.**

Not its Tier-1 reordering — that stands, and spec 06 was correctly promoted. But its
*preconditions-met* framing is retracted: two of three were broken and undetectable. **Until spec 11
and spec 12 ship, any readiness claim Tessera makes about itself is unverifiable**, and that — not
any single bug — is why autonomy is further off than ADR-0005 implies.

## Alternatives considered

- **Burn it down.** Rejected. It would destroy the mechanisms that *did* work — the pre-commit gate
  (blocked a lying commit), P9/G-a (nagged until the venv landed, four sessions running), the
  gate-scan (caught gates the model forgot), doccheck's standing rule (grew 5 → 13 checks under
  adversarial pressure) — and the observatory/ADR trail, which is the actual product. The problem is
  not that the channels exist. It is that they were **aimed at control and never watched fail.**
- **Continue on the existing roadmap.** Rejected. The roadmap targets autonomy via in-band gates,
  and in-band mechanisms fail silently against the very agent they guard. Building more of them
  compounds the surface without changing the class.

## Consequences

- **The autonomy roadmap is demoted from goal to hypothesis**, pending spec 11 + spec 12.
- **Spec 12 (adversarial verification) outranks spec 11 (fail-open detection)** — it is cheaper,
  it has a perfect track record, and it would have caught everything tonight *on the first pass*.
- **Every new mechanism must declare its tier** (1–5 above). A tier-4 channel proposed where a
  tier-1 impossibility is available should be rejected in review.
- **Pruning is now sanctioned work**, not a distraction from features.
- **This ADR is itself a sentence** until spec 12 makes the adversary a channel. That is not irony;
  it is the plan.

## Re-evaluate trigger conditions

- **Spec 12 ships and an adversarial verifier runs unprompted** → revisit whether spec 11's chaos
  tests are still the right shape, or whether the adversary subsumes them.
- **The break-it-on-purpose bar is met** (`_project_specs/11-fail-open-detection.md`), *confirmed by
  an independent session* → reconsider the autonomy hypothesis.
- **The Mnemos trial produces a valid verdict** (≥3 real, classifiable compactions) → kill or keep,
  and prune accordingly.
- **FOCUS-004 completes** → prune the skill set on evidence, per principle #15.
- Next cadence review: **2026-10-10** (90 days).

---

## References

- `docs/observatory.md` → "Fail-open everywhere — Tessera cannot tell you when it is broken" (the evidence base)
- `_project_specs/11-fail-open-detection.md` — chaos tests, scope, ordering
- `_project_specs/12-adversarial-verification.md` — the missing mechanism
- `docs/contracts/spend-authorization.md` — three layers, three trust domains
- ADR-0005 — the autonomy inflection, whose readiness claim this amends
