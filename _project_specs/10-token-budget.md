# Spec 10: Token budget awareness

**Status:** pending
**Priority:** Tier 3 — frontier / optional
**Effort:** Small

> **Split out of spec 06 on 2026-07-12.** This was spec 06's original content. Spec 06 was
> promoted to Tier 1 by ADR-0005 on the strength of a finding about **AWS GPU spend** — but its
> mechanism was a **Claude token meter**, which cannot stop a `terraform apply`. The two are
> different problems with different mechanisms, and only one of them blocks unsupervised work.
>
> Spec 06 kept the Tier 1 problem (external spend authorization) and shipped. This spec keeps
> the Tier 3 problem — *"agents stuck in loops burn real money"* — at the tier it was correctly
> filed at in April.

## Context

An agent stuck in a loop burns Claude tokens. Mnemos's fatigue model (tokens, scatter,
re-reads, error density) is a *behavioral* proxy for "the agent is struggling", but it is not a
hard stop.

**This is real but bounded.** Token spend is linear, visible, and small next to a g6e.xlarge.
It is not irreversible in the way external spend is. That is why it is Tier 3 and spec 06 is
Tier 1.

## Goal

Per-task and per-session token limits, with a budget-aware fatigue state.

## Approach

### Step 1 — declare a budget on the intent

```yaml
budget:
  tokens: 100000
  api_calls: 50
  wall_clock_minutes: 30
```

All optional. No budget ⇒ no enforcement.

### Step 2 — track spend via hooks

PostToolUse accumulates tokens consumed (from `transcript_path`), tool-use count, and wall
clock since the intent started. Stored per intent.

### Step 3 — budget-aware fatigue

A 5th Mnemos fatigue dimension: `budget_burn_rate`. 70% of budget at 40% progress is a signal
to compress, consolidate, or hand off.

| Budget consumed | Action |
|---|---|
| <60% | Normal |
| 60–85% | COMPRESS forced |
| 85–100% | REM forced, agent warned to wrap up |
| >100% | Stop **writing**; checkpoint and hand off |

### Step 4 — graceful stop

Budget exhausted ⇒ write a Mnemos handoff checkpoint, flip intent status to
`deferred_budget`, exit. A human or a fresh-budget agent resumes from the checkpoint.

## The constraint this spec inherits from spec 06

> **A budget stop must never be able to block the exit.**

The original draft hard-stopped by *"rejecting further Edit/Write/Bash"*. **Teardown is a Bash
command.** An agent that blows its token budget while a GPU is running would be frozen and
unable to tear it down — the token budget would cause an unbounded *dollar* runaway. See
`docs/contracts/spend-authorization.md`.

If this spec is ever built: **never blanket-reject Bash.** Reject writes; leave the exit open.

## Open question — is this worth building at all?

Honest read as of 2026-07-12: **no evidence it is.** Twelve Mnemos-scored sessions, every one
in the `clear` band, max haze 0.09, including sessions of 628 turns. *The agent does not flail.*
The failure mode this spec guards against has not been observed once in three months of
dogfood.

**Trigger to build it:** a session that actually burns a pathological number of tokens without
progress — i.e. haze in the `hazy`/`lost` band, or a runaway subagent fan-out. Until then this
is a solution in search of its problem, and building it would be exactly the speculative
machinery principle #15 warns about.

## Depends on

- Mnemos fatigue model (exists)
