# Spec 12: Adversarial verification — make the falsifier a channel

**Status:** shipped 2026-07-13 — criteria 2–5 evidenced live (see Shipped, below); criterion 1
(manual acceptance replay of the 2026-07-12 refutations) pending Lorenzo
**Priority:** Tier 1. Highest value-per-line in the framework.
**Effort:** Small. The mechanism already exists; it is simply not wired.
**Source:** ADR-0006 → decision 4

---

## The one-line case

**The most effective mechanism in this system is not in this system.**

On 2026-07-12, three independent adversarial verifications ran. **All three refuted claims the
author had already certified as fixed. All three were correct.** Nothing else in the framework —
not doccheck, not the watcher, not the gate-scan, not the test suite — came close to that record.

It ran because **Lorenzo remembered to ask.**

That is a **sentence, in a human's head**, sitting on top of the single best tool available. It is
precisely the failure mode of `docs/observatory.md` → *"Fail-open everywhere"*, applied to the very
thing that found it.

## Why it works, when everything else failed

Because it does not share the failure mode it is checking for.

Every other mechanism is **in-band**: it runs in the same context, on the same assumptions, and —
critically — **the agent that built the fix is the agent that certifies it.** That is how the same
mistake was made three times in one night:

> The detector was built. The fix was verified **with the detector that had the hole**. It reported
> green. Green was reported to the user. Repeat.

A clean-context falsifier breaks that loop structurally. It has **no investment in the fix being
correct**, no memory of the reasoning that produced it, and an explicit instruction to **attack, not
confirm**.

> **A detector you certify a fix with must be tested against that fix's own failure mode — or it is
> a mirror, not an instrument.** An independent adversary is the cheapest way to guarantee that.

## What it must do

Not "review the diff." **Falsify a claim.**

The prompt shape that worked (three for three):

- **State the claims explicitly** — "no code path invokes the toolchain by name", "the guard blocks
  unauthorized boots", "all suites green". A vague *"check my work"* produces vague agreement.
- **Instruct it to assume the claims are FALSE** until proven otherwise, by **running things**.
- **Say the comments are untrustworthy.** This repo's comments are eloquent and self-congratulatory;
  a verifier that reads them is reading marketing. *Only executed behaviour counts.*
- **Demand landmines.** "Plant a case the checker should catch. Does it?" That is how all seven
  detector holes were found — not by reading the regex, but by walking through it.
- **Require restoration.** It must leave the tree exactly as found.
- **Forbid fixing.** Report only. A verifier that fixes becomes an author, and inherits the bias.

## Scope

### 1. `tessera-verify` — the falsifier, invocable

A command that spawns an independent instance with a clean context, the claims, and the attack
instructions above. Returns CONFIRMED / REFUTED / PARTIAL per claim, each with the **exact command
and output** that proves it.

### 2. Wire it to a trigger — this is the part that matters

Invocable-but-forgotten is a sentence. It must fire without anyone remembering:

- **Stop hook**, on any session that touched a **safety path** (`scripts/spend/`, `.claude/scripts/`,
  `hooks/`, `install.sh`, `scripts/doccheck.py`) **and** made a "done"/"fixed"/"closed" claim.
- Or: **pre-push**, on the same paths.
- Fails **loud**, not open — an unverified safety change is exactly what we cannot afford to let
  through quietly. *(This is the one hook that should NOT fail open. See ADR-0006 tier 4.)*

### 3. Record the verdict

Append a `verification` event to `.tessera/logs/<session>.jsonl` (the channel already exists).
**A refuted claim is a finding, not a failure** — and the record of *how often the author was wrong*
is the single most valuable calibration datum this framework can collect.

> Tonight's number: **3 claims certified by the author, 3 refuted by an adversary. A 100% author
> error rate on "it's fixed."** That number should be tracked, and it should be published in the
> handoff, because it is the honest prior on any future "done".

## Success criteria

1. Replaying **2026-07-12** against `tessera-verify` reproduces all three refutations *without a
   human asking* — the spend-guard fail-open, the `-m`/multi-line-`-c` detector holes, and the
   `bin/*.sh`-matches-nothing scope hole.
2. It fires **unprompted** on a safety-path change.
3. It refuses to fix, and leaves the tree clean.
4. Its verdicts land in the event log, and the author-error rate is surfaced in the handoff.
5. **A green verify is never the last word on itself** — the verifier's own coverage is checked by
   planting a landmine it *should* catch. (Recursion stops here, deliberately: at some point a human
   looks. The point is to make that the *second* line of defence, not the first.)

## Why this outranks spec 11

Spec 11 builds **channels that report when a component breaks**. Good, necessary — and *tier 4*, the
tier that manufactured false confidence all night.

Spec 12 builds **a check on the checker**. It is *tier 3*, it is cheaper, and it has a perfect track
record. **It would have caught everything on 2026-07-12 on the first pass** — including spec 11's own
future holes.

**Build the adversary first. Then let it verify spec 11.**

## Where this ratholes

- **Making the verifier part of the same context.** Then it inherits the bias and is theatre. It must
  be a genuinely clean instance.
- **Letting it fix things.** It becomes an author.
- **Trusting a green verify.** See criterion 5. A verifier that has never been watched fail is —
  by ADR-0006's own argument — still a sentence.

## Depends on

- Nothing. Subagents, the event channel, and the Stop-hook surface all already exist.

---

## Shipped (2026-07-13)

- `bin/tessera-verify` — run / `skip --reason` / `stats` / `--self-test`. Verifier runs in a
  disposable git worktree (uncommitted + untracked state copied in), so tree restoration is
  **structural**, not an instruction. `NO_VERDICT` is never green.
- `scripts/verify/scan.py` + `.claude/scripts/tessera-verify-scan.sh` — Stop-hook trigger,
  **fail-LOUD** (the only Tessera hook that does), capped at 3 fires/session.
- Contract: `docs/contracts/verification-event.md`. Wiring checked by doccheck
  `verify-scan-is-wired`. Suite: 18 verify tests + 15 CLI tests, all API-free.
- **Criterion 2 evidence, unplanned and better than designed:** the hook fired unprompted on
  the very session that built it — mid-build, before wiring was announced — and the falsifier
  ran 4 claims: **4/4 CONFIRMED**, with landmines walked (scan.py moved aside → wrapper exit 2;
  `__future__` import stripped → reproduced the 3.9 TypeError; jq-less PATH → loud).
- **Criterion 5 evidence:** live `--self-test` REFUTED the planted zero-byte claim. PASS.
- Criterion 1 (replay the three 07-12 refutations) is deliberately manual: watch the channel
  fail/catch once before trusting it (ADR-0006). Not yet run.
