# 13 — Friction-detector upgrade (Mnemos correction recall)

**Status:** Scoped, not built (2026-07-16). Build in a fresh session.
**Motivation:** `docs/observatory.md` → "Haziness's correction-detector has near-zero recall".

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

## Deferred — Phase 2 / 3

- **Phase 2 — typing:** classify each detected correction (misunderstood / defied / overreached / wrong).
  Fuzzy; do not gate the recall fix on it.
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
