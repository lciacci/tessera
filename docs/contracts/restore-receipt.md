# Contract: restore receipt (T2)

**Status:** live 2026-07-26 · **Decided by:** ADR-0015 · **Answers:** T2, the only question
that can produce a verdict on Mnemos's recovery half.

---

## The question

*After a context discontinuity, did the agent resume **without re-deriving** what it was doing?*

Discontinuities are not just compaction — the restore path runs on every session start
(`startup`, `resume`, `compact`; ~121 invocations vs ~3 compactions). See ADR-0015.

## Why a receipt, and not another counter

`restore_injected` was **a log line the hook wrote about itself.** The log showed four; the
model received nothing on all four, because a PreToolUse hook's stdout went to the debug log.
Thirty-seven days of trial evidence was one party certifying its own delivery.

Counting harder does not fix that. Going from 3 events to 121 gives 121 self-reports —
**volume does not fix provenance.** So the fix is structural: two parties who cannot mark
their own homework.

## The three events

All on the existing `.tessera/logs/<session>.jsonl` channel, alongside `suggestion_gate`,
`spend_denied`, `degraded`, `verification`.

| Event | Written by | Claims |
|---|---|---|
| `restore_offered` | **harness** — `mnemos-session-start.sh` → `scripts/restore/offer.py` | bytes, fields present, goal length. **Never delivery.** |
| `restore_receipt` | **model** — `scripts/restore/emit.py` | sufficient/insufficient + evidence |
| `restore_scan_fired` | **Stop hook** — `scripts/restore/scan.py` | the ask happened (auditable, and caps nagging) |

An offer with no receipt is a **detected miss**. That is the thing the old design could never
see: nothing independent recorded that a restore was owed, so a silent non-answer was
indistinguishable from no restore at all.

## Emitting

```bash
python3 scripts/restore/emit.py --sufficient \
    --used "goal + all 3 constraints; picked up the P14 work with no re-reading"

python3 scripts/restore/emit.py --insufficient --missing progress \
    --rederived "had the goal but not what was already done; re-read active.md"
```

`--missing` is a closed enum: `goal | constraints | progress | files | decisions`. Unknown
values exit 2, same fail-closed rule as `gate/emit.py --kind` (102 free-text gate events
produced 33 unusable values).

**Evidence is mandatory in both directions**, minimum 25 characters. `gate/emit.py` on pure
model recall missed ~85% of gates; a bare `--sufficient` flag would be worse, because it is
one keystroke. **A reflexively-typed "sufficient" is exactly as worthless as
`restore_injected`** — it rebuilds the bug one level up. Requiring the receipt to *name*
something is what makes the cheap path not the empty one. It is a speed bump, not a wall, and
is not trying to be.

## When to emit

**At the end of a session, or the moment you discover a gap. Never at the start.**

At session start, sufficiency is a *prediction*: the checkpoint looks fine until turn 20, when
you find you do not know why something was decided. A first-turn receipt records optimism.

## The backstop

`Stop` → `tessera-restore-scan.sh` → `scripts/restore/scan.py`, exit 2 on an unanswered offer,
so the model must adjudicate before finishing. Same division of labour `gate/scan.py` proved:
**the harness guarantees the turn happens; the model is the precision filter inside it.**
Nothing can guarantee the answer is honest.

It only fires on **substantive** sessions — `>= 1` file edit or `>= 20` assistant turns.
Every session restores, so an unconditional demand would tax all of them, and the failure
mode is not noise: it is that `--sufficient` becomes a reflex. A session that edited nothing
and ran a handful of turns never put the checkpoint under load and has no evidence to give.
Capped at 2 asks per session — a wedged hook gets ripped out, which helps nobody.

## Reading the data

`insufficient` is a **finding, not a failure**, and is the more useful result: it names which
field the checkpoint should have carried. A run of `--missing progress` is an instruction to
change what `write_checkpoint` captures, not a reason to kill Mnemos.

**No verdict is available from a single session.** T1 (P3, deliverability) is green today and
means only that the payload survives delivery.

## Known limits — stated so they are not mistaken for coverage

1. **The receipt is still self-reported.** The *obligation* is now independent; the *answer*
   is not. A determined filler defeats it. The upgrade path is a detector that corroborates
   from the transcript (did the model re-read, or ask what it was doing?) — deliberately not
   built yet, because the obvious version is confounded: reading the handoff at session start
   is normal and encouraged here. The non-confounded version compares checkpoint *contents*
   against what was re-derived.
2. **Downstream coverage is unproven.** `offer.py` resolves via `$PWD/scripts/restore/` in the
   ADR-0004 global tier, so a downstream project records offers only once `scripts/restore/`
   is synced there. The trial runs in this repo first.
3. **Zero receipts so far, and data arrives only as a BYPRODUCT of work.** The backstop fires
   only on a substantive session (≥1 edit or ≥20 assistant turns), so there is no way to
   "collect receipts" as an activity — you do the real next job and the receipt is owed at its
   Stop. **Verified 2026-07-26:** the session that built T2 was itself substantive (1,574
   assistant turns, 143 edits) yet produced **no** `restore_offered`, because it started before
   `offer.py` existed; `scan.py` correctly stayed silent, since no offer means nothing owed.
   That confirms the "nothing to do" branch on real data and puts **n=1 at the next session,
   not that one.** If a later substantive session *does* get an offer and the Stop hook still
   says nothing, that is the failure this contract exists to make visible.
