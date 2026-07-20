# 14 — should_fire follow-ons (backfill → auto-wire → override)

**Status:** STOP-LOSS (2026-07-20, same day as spec). Phase A ran and **failed its eyeball
acceptance**; all 74 classifier labels rolled back to null. Phases B and C **shelved**. See
"Outcome" at the end — the spec body below is kept as written for the trail.
**Motivation (superseded):** Producer built (#34/#35, `scripts/gate/label.py`); this spec is the
three follow-ons named in the 07-19 handoff, ordered.
**Motivation:** 73 of 102 gate events still `should_fire: null` (probe, 2026-07-20). The instrument
exists but has labeled almost nothing (3 classifier labels). Coverage is what feeds P10's precision
sample and un-blinds the dashboard's calibration matrix.

---

## Phase A — historical backfill (`--all`)

**Mechanism exists.** `label.py --all` already iterates every `.tessera/logs/*.jsonl`, timestamp-joins
each null gate to the user's disposition turn, classifies, writes back idempotently. Non-gate logs
no-op; sessions with no transcript skip cleanly (`skipped: no-transcript`).

**Work:**
1. Run `.venv/bin/python -m scripts.gate.label --all` (Ollama up, qwen3:8b).
2. Record the tally: labeled / no-transcript / no-disposition / still-null. Expect < 73 labeled —
   old sessions may lack transcripts under `~/.claude/projects/`.
3. **Eyeball pass (acceptance):** sample ~10 fresh classifier labels, check `should_fire_basis`
   (the disposition quote) supports the verdict. This is a smell-check, not the precision
   measurement — the real precision number is P10's job on the human-labeled fresh sample.
4. Note the new label counts in the observatory's should_fire entry.

**Flag:** the rubric was tuned on the same 26 human labels the eval uses (n=1 negative class).
Backfill labels are coverage-filler, `labeled_by: "classifier"`, never pooled with human anchors —
consumer discipline already documented in `docs/contracts/gate-event.md`.

## Phase B — Stop-hook auto-wire

New gates should label themselves the way new turns classify themselves (spec-13 pattern:
passive, at ingest, zero user burden).

- **Where:** a backgrounded step in the Stop chain, same `( … ) & disown` shape as
  `mnemos-stop-ingest.sh` — never blocks session exit. Own script
  (`.claude/scripts/tessera-gate-label.sh`) rather than folded into `tessera-gate-scan.sh`:
  scan is a *blocking* exit-2 gate, labeling is fire-and-forget; mixing their failure modes is
  the hazard. **[Decision D14-1]**
- **Cost:** `label.py` touches only null gates — per-Stop steady state is the handful of gates
  from that session. Idempotent, so double-fires are harmless.
- **Timing wrinkle:** at Stop time the *last* gate of the session may have no disposition yet
  (the user hasn't replied). It stays null and the next session's run picks it up — this is why
  the auto-wire labels **all logs' nulls cheaply**, not just the current session's.
- **Fail-open:** Ollama down → label.py already exits 0 with nulls intact. Nothing new needed.
- **Tests:** the hook script is glue; the labeling logic is already unit-tested (11 mocked tests).
  One addition: a test that a non-current-session log's nulls get picked up (the timing wrinkle).

## Phase C — human-override path

Today `_already_labeled` means a classifier label is permanent — a human who disagrees has no
defined move. Smallest honest fix:

- **CLI:** `label.py --override <session> --ts <event-ts> --value true|false --basis "<why>"` →
  sets `should_fire`, `labeled_by: "human"`, `labeled_ts`, keeps the classifier's verdict in
  `classifier_verdict` (one key, so the disagreement itself is data — these are exactly the
  events a rubric re-tune wants). **[Decision D14-2: field name + keeping the loser]**
- Human labels remain unoverwritable by the classifier (already true via `_already_labeled`).
- Contract (`gate-event.md`) gains the `labeled_by: "human"` value + override semantics.

## Order & sizing

A now (one sitting, mostly waiting on qwen). B after A's eyeball passes (~half session).
C when the first real disagreement shows up — build the door when someone knocks; the spec
records the shape so it's a mechanical add. **[Decision D14-3: C now vs on-demand]**

---

## Outcome — STOP-LOSS (2026-07-20)

Phase A ran: 71 labeled → verdict split 23 True / 51 False, vs ~90% True in the human anchor.
Eyeball sample showed the False class largely wrong, two causes:

1. **Retro join (structural, untunable).** Retro-logged gates (scan adjudication — a large share
   by design) carry adjudication-time `ts`; the disposition join grabbed unrelated wrap-up turns.
   ~24 events sat in <2-min bursts. No rubric can fix a wrong join, and pre-flag events are
   unmarked, so history is permanently unjoinable.
2. **Soft assents (rubric).** "i think that's okay for now" → labeled No. Invisible to the #35
   eval (negative class n=1).

**Disposition (adjudicated with Lorenzo, stop-loss over a 4th tuning cycle):**
- All 74 classifier labels rolled back to null; human anchor intact (26: 25 True / 1 False).
- The anchor already answers the instrument's question — the gate is **not over-firing**. Further
  classifier coverage refines a number whose decision-relevant reading is known.
- **Shipped as remedy:** `emit.py --retro` flag (adjudication logging now marks itself),
  `scan.py` exit-2 message requires it, `label.py` skips retro events. Forward events have clean
  provenance if labeling is ever revisited.
- **Shelved:** Phase B (auto-wire), Phase C (override). Resumption criteria in
  `docs/contracts/gate-event.md` → STOP-LOSS section (a consumer must actually need the coverage;
  retro-clean events only).
