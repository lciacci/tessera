# ADR-0015: The Mnemos trial was scoped to the wrong event — re-scope to restore integrity

- **Date:** 2026-07-26
- **Status:** Accepted
- **Decision driver:** The first `/compact` observed through a working channel (2026-07-26) found
  two defects and, in diagnosing them, invalidated the trial's founding premise. Supersedes the
  framing of `tessera-watch` **P3** (`p3_compaction`) and the "compaction vehicle" observatory
  entry. Retires `COMPACTION_MIN` as a verdict threshold.

> Internal architecture decision, so it uses the classic form (Context / Decision /
> Alternatives / Consequences / Re-evaluate) like ADR-0002 / 0003 / 0004.

**Governs:** `bin/tessera-watch` (the P3 predicate), `scripts/mnemos/checkpoint.py` (what the
restore payload contains), `.claude/scripts/mnemos-session-start.sh` (Layer 2, the restore that
actually runs), `.claude/scripts/mnemos-post-compact-inject.sh` (Layer 3, on notice).

---

## Context

P3 asked: *has compaction fired ≥3 times (non-manual)? If so, judge the compaction-recovery
half of Mnemos.* It never fired in 37 days, and each investigation found the machinery broken in
a new place. The question flapped repeatedly between "kill it, it never ran" and "it never had an
honest run."

**The premise was false.** The restore path is not compaction-specific.
`.claude/scripts/mnemos-session-start.sh` line 30 reads:

```
if [ -f ".mnemos/checkpoint-latest.json" ]; then … mnemos resume
```

No source gating. It runs identically on `startup`, `resume`, and `compact`. Compaction is one
**trigger** among several for a mechanism whose job is *recovery across any context
discontinuity* — compaction, session end → new session, crash, `/clear`, machine restart.

```
checkpoints written        541
sessions ingested          121
compaction_fired (all)     ~3        ← what P3 counted
span                       2026-06-26 → 2026-07-27
```

**The mechanism did not fire 3 times. It fired on the order of 121 times.** P3 counted the
rarest trigger — roughly 2% of invocations — and concluded the mechanism was untested. This is
standing pattern #3 in its purest form, and worse than the usual case: a proxy normally
*correlates* with the pain. This one measured a trigger responsible for a fiftieth of it.

The consequence is not academic. The defect found on 2026-07-26 — `checkpoint.py` joining every
active GoalNode unbounded, 11,119 chars, overflowing the SessionStart output limit so the harness
delivered a 2KB preview instead of the checkpoint — **was degrading all ~121 restores**, not 3
compactions. It was found via compaction only by accident. A trial scoped to the real event would
have surfaced it in the first week.

### The deeper problem, which the re-scope does not by itself solve

`restore_injected` is **a log line the hook writes about itself.** It is not evidence the model
received anything. The log shows `restore_injected` four times; on all four the model received
nothing, because a PreToolUse hook's stdout goes to the debug log. The trial has been reading a
self-report and calling it data — standing pattern #9. Re-scoping to 121 events instead of 3 gives
121 self-reports. **Volume does not fix provenance.**

---

## Decision

**Split what was one trial into three questions with different evidence, venues, and verdicts.**

**T1 — Restore integrity (mechanical; guarded here, now).** *Does the restore payload actually
survive delivery, with its sections intact?* This is the failure that occurred, it is checkable
without a model or a compaction, and it applies to every session start. **This becomes P3.** It is
a **guard, not the trial's verdict** — it asserts a precondition for restore working, and calling
it the verdict would mint proxy #5.

**T2 — Restore sufficiency (the actual question; instrument NOT yet built).** *After a
discontinuity, does the agent resume without re-deriving what it was doing?* Only the model can
report this, so it takes the **gate-event shape**: model-emitted, audited, backstopped by a Stop
hook that diffs claimed against detected. Unbuilt, and named here so it is not mistaken for done.
**Until T2 exists, no verdict on Mnemos's recovery half is available** — not "keep", not "kill".

**T3 — Compaction frequency (blocked, and now largely moot).** *Does auto-compaction fire often
enough to matter?* Unanswerable on this harness: the PreCompact payload is empty
(`payload_probe {"len": 2, "keys": []}`), so `trigger` is permanently `unknown`. **Demoted from
blocking to informational** — once compaction is one trigger among several rather than the sole
consumer, its frequency stops gating the mechanism's fate.

**Layer 3 is judged separately and on its own thin merits.** The two layers are not two
implementations of one thing:

| | Layer 2 — `mnemos resume` (SessionStart) | Layer 3 — `format_for_post_compact_injection` (PreToolUse) |
|---|---|---|
| Triggers | startup, resume, **and** compact | compaction only |
| Invocations | ~121 | ~3 |
| Deliveries to a model | many; confirmed on `source=compact` 2026-07-26 | **zero, ever** |
| Unique job | the restore | cover the case where Layer 2's output is dropped |

Layer 3 is a fallback for a failure mode never observed, and it caused both defects found on
2026-07-26. It is **retained but on notice**, and its removal is a live option under T2.

### What P3 becomes

`p3_restore_integrity`: assert `.mnemos/checkpoint-latest.json` is under a delivery budget and
carries its required fields. Checkpoint JSON tracks delivered bytes ~1:1 (8,508 → 8,206 rendered;
pre-fix ≈18,755 → 18,248, **which spilled**), so a stdlib size check on the file is a direct
measure, not a stand-in. Budget **12,000 bytes** — clearly under the observed failure point, with
headroom over the current 8,508.

`COMPACTION_MIN` is retired as a threshold. Compaction counts are still *reported* by P3, because
they remain the only evidence about T3 and the `unknown`-classification alarm must stay reachable.

---

## Alternatives considered

- **Keep P3, relocate the trial to a real Claude Code CLI session.** Rejected: it preserves the
  category error. Relocating gets auto-compaction events, which answers T3 — the question that
  matters least — while the ~121 restores stay unmeasured in either venue.
- **Make P3 the sufficiency check directly (model-emitted receipt).** Rejected *for now*: it is
  T2 and it is real work. Shipping it as a stub would put an unbuilt instrument in the watcher's
  green column, which is the failure this repo keeps finding.
- **Kill Mnemos's recovery half outright.** Rejected: the verdict rests on a self-report channel
  now known to have been broken for the whole trial, and killing it also deletes the
  session-continuity half, which is demonstrably alive. ADR-0007 — never subtract from a knowledge
  artifact you have not read; the same restraint applies to a mechanism you have not measured.
- **Retire P3 with no replacement.** Rejected: the 2026-07-26 defect would silently return. A
  regression guard is cheap and mechanical even while the verdict question is open.

---

## Consequences

- The trial's evidence base **resets to zero and this is the intended outcome** — every prior
  observation measured a mechanism with a 300s staleness gate and a self-truncating checkpoint.
  It is the first time the instrument is sound.
- P3 stops being a verdict gate. Nothing now claims Mnemos's recovery half has been judged,
  because it has not been.
- T2 is the sole blocker on a real verdict, and it is named, unbuilt, and owned.
- **A trap this ADR must not set:** T1 going green must never be read as "restore works." It means
  the payload is deliverable. Every doc stating the bar must say which question it answers.

---

## Re-evaluate when

- **T2 ships** — then a verdict on the recovery half is available for the first time, and this
  ADR's three-way split should be re-read against real sufficiency data.
- **Layer 3 delivers to a model even once** — it never has; a single confirmed delivery changes
  its cost/benefit and the "retained but on notice" call.
- **A restore is observed failing while P3 is green** — that means the budget-and-fields guard is
  itself a proxy, and T1 needs to name a different pain (standing pattern #3, applied to this ADR).
- **The harness begins sending a PreCompact payload** (`payload_probe` shows any keys) — T3
  becomes answerable here and can be re-promoted if anyone still wants it.
