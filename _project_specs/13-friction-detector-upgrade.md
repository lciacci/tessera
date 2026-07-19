# 13 — Friction-detector upgrade (Mnemos correction recall)

**Status:** Phase 1 BUILT + backtested (2026-07-17). **Phase 2 (typing) BUILT + verified (2026-07-18).**
Phase 3 deferred.
**Motivation:** `docs/observatory.md` → "Haziness's correction-detector has near-zero recall".

---

## Phase 1 — BUILT (2026-07-17)

**Result:** correction recall un-blinded. The heavy-redirection session `b6d7b6f5` went
`correction_density 0.000 → 0.219` (matches a 27-turn hand-labeled truth of 0.188); a clean
session (`b4344aae`, 372 turns) stays `0.000`. Old detector scored *every* session 0.00–0.06
(blind); new spread is 0.00–0.35 across the ~24 dogfood sessions. Backtest = acceptance, met.

**What shipped:**
- `scripts/mnemos/correction_detect.py` — `regex_match` (the old heuristic, now single-homed here)
  + `classify`/`CorrectionDetector` (qwen classifier, recall-leaning prompt, wall-clock budget,
  fail-open to regex). `scripts/model_routing.py:ollama_generate` — the missing Ollama POST
  (with `think` support). `claude_log.py` runs the classifier over eligible user turns the regex
  missed, at ingest. `--reclassify` CLI (+ `reclassify_session`) un-blinds history. `tessera-watch`
  **P10** self-fires the deferred band re-tune. Unit tests mock the boundary; no network in CI.

**Four things the build corrected in the original scope:**

1. **Model: qwen3:8b, NOT the 3B tier-classify model.** The 3B model is useless here — it *parrots
   whichever polarity the prompt ends on* (constant-yes on a recall prompt, constant-no on a tight
   one; it never discriminates). qwen3:8b lands prec/rec ~0.5 and a density matching the human count.
   **qwen3 is a reasoning model — it MUST run with `think=false`** or it spends the token budget on a
   hidden `<think>` block and returns empty. Override via `MNEMOS_CORRECTION_MODEL`. Fails open to
   regex if 8b is absent.

2. **Injected user turns were being counted** (a correctness bug independent of the classifier).
   Hook feedback (`isMeta: true`) and harness content like task-notifications
   (`promptSource: 'system'`) ride on `role='user'` events but are not the human. They now emit as
   `event_type='user-meta'`, excluded from BOTH the correction numerator and haziness's eligible
   denominator (which already filters `event_type=='user'`). See `_is_injected_user`.

3. **Latency/volume — was never a real problem.** (a) The Stop hook is `( … ) & disown` — ingest
   is backgrounded, so it *never* blocks session exit whatever the classifier costs. (b) Ingest is
   incremental (`last_line_offset`), so a live Stop classifies only the new turns since last Stop —
   a handful, not 900. (c) Even a full historical backfill is cheap: `--reclassify --all` over ~26
   sessions ran in **81s**; the single heaviest (1141 turns) in **~5s**. No pre-filter-for-speed,
   no batching, no cap needed — the incremental delta *is* the cap. (A pre-filter WAS added, but for
   *correctness*: a user turn can only correct an action that already happened, so eligibility
   requires a prior agent turn.)

4. **Precision is ~0.5, and that gates the band re-tune.** The classifier catches ~half the real
   corrections and ~half its positives are wrong (on the one labeled session). Recall-first (spec's
   stance) tolerates the false positives; the density still tracks truth in aggregate. But it is too
   noisy to re-tune haziness thresholds on yet — hence P10 fires a *precision spot-check first*, not
   an immediate re-tune.

**Deferred with a self-firing trigger (not a note):** the haziness band re-look. `tessera-watch`
**P10 haze-recalib** fires when ≥40 sessions carry real correction signal (24 at backfill → ~16
sessions of runway). At fire: spot-check detector precision on a fresh sample, THEN decide the bands
(clear/cloudy/hazy/lost at 0.25/0.50/0.75) and correction_density's 0.30 weight.

## The problem

Mnemos `correction_density` — the one instrument that could capture **action-divergence** (did the
agent do the opposite of / diverge from / overreach what was asked) — has **near-zero recall**.
`mnemos haze` reads 0.00–0.06 across every session on record; this session scored
`correction_density 0.000` despite heavy substantive redirection. Root cause: detection is a keyword
regex (`scripts/mnemos/claude_log.py`, `_CORRECTION_LEAD_RE`/`_CORRECTION_PHRASE_RE`) that fires only
when a turn *opens* with `no/wait/stop/actually/undo/revert/wrong/don't`. It misses probing questions,
reframes, "but that would require X" — the redirections that actually change the work.

**The pipe is right, only the detector is weak.** `claude_log.py` already ingests every transcript
passively and stores matched-phrase + redacted preview + timestamp per correction (ADR-0006 pattern,
zero user burden). The fix upgrades the detector on this pipe — it does **not** add manual labeling
(the `should_fire` dead backlog proves labeling-as-a-separate-act dies).

## Why this matters

Two disposition vectors: *asking* calibration (`should_fire`) and *doing* calibration
(action-divergence). The second is the more valuable one — it is what the framework's own postmortems
keep saying only a human catches ("every correction came from outside me", ADR-0007; the deletion-leap;
the 38% `tessera-verify` author-error-rate). Fixing correction recall is what makes it instrumentable.

## Phase 1 — recall fix (this spec's build target)

- **Mechanism:** a local-qwen classifier over the transcript delta at Stop-hook ingest, reusing the
  `tier-classify-hook` / `scripts/model_routing.py` Ollama infra. Question per user turn: *"did this
  turn redirect / challenge / correct / express dissatisfaction with the agent's prior action?"* → yes/no.
- **Recall-first:** a false "you corrected me" is cheap (a review flag); a missed one is today's failure.
  The prompt errs toward yes.
- **Fails open:** Ollama down → fall back to the existing regex (same pattern tier-classify uses to fall
  back to Sonnet). Never worse than today.
- **Local only:** the classifier is local qwen — transcript turns never leave the machine, consistent
  with the redact-before-store rule (`scripts/mnemos/redact.py`). Matches conclave's "local for routine".
- **Proof = backtest:** re-ingest THIS session (`b6d7b6f5`, known heavy redirection → must now score
  non-zero) vs a known-clean session (must stay ~0). That comparison is the acceptance test.
- **TDD:** the classifier call is a boundary — unit-test the detection logic with fixture turns
  (substantive-redirect → detected; neutral/agreement → not), mock the Ollama call.

## Build notes (sized 2026-07-16)

Estimate: **~1 focused session** (half-day plumbing + half-day prompt/recall tuning). Blast radius is
small — Mnemos internals, mostly `claude_log.py:409` (one swap point) + a new classifier fn + a backtest
script. Acceptance = the backtest.

Two things the initial scope under-named:

- **`model_routing.py` has no inference call yet.** It has `_ollama_up()` (probes `localhost:11434`) and
  model/availability config, but **not** a "call qwen for a completion". The classifier must add a
  `urllib` POST to Ollama `/api/generate` (stdlib, no deps; `_ollama_up` shows the pattern), with a
  timeout and fail-open to the existing regex.

- **Per-turn latency/volume — a real design decision, not free.** Classifying *every* user turn at
  Stop-hook ingest is N sequential Ollama calls (a long session is ~900 turns). That can make ingest slow.
  Phase 1 must pick a strategy — likely a combination:
  - **pre-filter** — only classify user turns that follow an agent action (skip standalone questions with
    no prior agent turn to have diverged from);
  - **batch** — classify M turns in one prompt instead of one call each;
  - **cap** — classify only the last K turns, or only the delta since `last_line_offset` (ingest is already
    incremental/idempotent, so steady-state is a handful of new turns per Stop, not 900 — the 900 is only
    the one-time backfill).
  The incremental-ingest point matters: **at steady state the cost is small** (new turns since last Stop);
  the volume problem is really just the historical backfill, which can be a one-off batched pass.

## Phase 2 — typing — BUILT (2026-07-18)

**What shipped:** `correction_detect.py` gained `classify_type` + `CorrectionDetector.correction_type`
(a second qwen prompt, single label from `TYPES = misunderstood/defied/overreached/wrong`), sharing
Phase 1's wall-clock budget and fail-open discipline. Typing runs **only on already-detected
corrections** (regex- or qwen-matched) — small N, not per-turn. Stored in a new nullable
`claude_turns.correction_type` column (idempotent `store._add_column` ADD-COLUMN migration for
pre-existing DBs). Surfaced in `mnemos haze --session --explain`: a `CORRECTION TYPES (N total) ...`
rollup + per-turn `CORRECT:<type>` markers. `--reclassify` backfills types through the same path.

**Design stance (held):** typing is a **diagnostic view — it does NOT feed the haziness composite.**
A null type (Ollama down / over budget / unparseable) never drops the correction, it just leaves it
untyped. Composite weight changes stay gated on P10.

**Verified end-to-end (2026-07-18):** `ingest-claude --reclassify --session b6d7b6f5` against live
qwen3:8b typed its 7 corrections `misunderstood=2, overreached=1, wrong=4`; `correction_density`
unchanged at 0.219 (composite untouched, as designed). Boundary + wiring unit-tested (mocked Ollama,
no network in CI): `test_correction_detect.py` (type parse + budget/disabled → None),
`test_correction.py` (`_emit_rows` types a matched correction; null type never drops it).

## Deferred — Phase 3

- **Phase 3 — action link + view:** tie each correction to the *action* it was about; a "divergence"
  surface. This is where it fully becomes the doing-calibration instrument.

## Flags for the build session

- **Recalibrates haziness.** Fixing recall makes scores jump from falsely-0 to real — correct, but the
  fatigue bands (COMPRESS/PRE-SLEEP/REM at 0.4/0.6/0.75) were tuned against a blind detector. Re-look at
  the bands and `correction_density`'s 0.30 weight once real signal flows.
- **Scope = Mnemos internals** (`claude_log.py` + `haziness.py`). The Mnemos trial fixing its own
  instrument — fits the "why isn't Mnemos capturing" thread.
- **Relation to `should_fire`:** same fix shape (passive extraction of the user's disposition from the
  response they already give). If Phase 1 lands, apply the same pattern to `should_fire` (extract the
  gate disposition from the in-session response, retire the dead dashboard-labeling path).
