# 16 — live correction-pipe spot-check (dead-pipe suspicion)

**Status:** SPEC (2026-07-20). A probe, not a build — ~30 min; escalates into a watch predicate
only if the suspicion confirms.
**Motivation:** probe (2026-07-20): real-signal sessions stuck at **24/40** (P10 counter) — the
exact count at the 07-17 backfill — while total haze rows grew 24→43. All 19 sessions ingested
since score `correction_density = 0`. Plausible innocently (clean sessions exist; the spread was
0.00–0.35, zeros included). But the signature — *instrument reads clean because the instrument
silently stopped running* — is F-001's shape exactly (bare-python3 no-op'd checkpoints for weeks,
read as "unused" when it meant "unreachable"). Spec-13's own finding repeats it: the regex
detector read every session ~0 and was believed. A zero from this pipe is not yet
distinguishable from a dead pipe. Make it distinguishable.

---

## The question

Did the qwen classifier actually *run* at Stop-hook ingest on the 19 post-backfill sessions —
or did they all silently take the regex-only / disabled path?

Known silent-zero paths (all fail-open by design, none currently leave a per-session trace):
1. Ollama down at Stop time → regex fallback.
2. 3-consecutive-null disable trips early in the session's batch → regex-only for the rest.
3. Hook env differs from interactive shell (the "agent's shell is not your shell" observatory
   entry) → import or model-name failure → fallback.
4. Sessions genuinely clean → real zeros. (The innocent explanation.)

## Procedure

1. **Pick a known-dirty recent session:** from the last ~19, one where corrections definitely
   happened (any session with a `rule-over-read` style redirect; the 07-18/07-19 build sessions
   had several surfaced-and-corrected decisions).
2. **Re-run by hand against live qwen:**
   `.venv/bin/mnemos ingest-claude --reclassify --session <id>` → does density move off 0?
   - Moves → Stop-time run missed what a hand-run catches → pipe defect (paths 1–3). Bisect:
     check Ollama uptime pattern, then run the Stop hook script itself
     (`.claude/scripts/mnemos-stop-ingest.sh`) in a hook-like env and watch which path it takes.
   - Stays 0 → hand-label 10 user turns of that session; if any are real corrections the
     *classifier* is missing them (recall regression, different bug); if none, zeros are real.
3. **Check the disable counter's footprint:** did any ingest trip the 3-null disable? (If the
   counter state isn't observable after the fact, that is itself the finding — see remedy.)
4. **Verdict, one of:** `pipe-dead` / `recall-regression` / `zeros-real`. Written to the
   observatory entry either way — a confirmed-innocent zero is worth recording; it retires the
   suspicion instead of leaving it ambient.

## Remedy (only if not `zeros-real`)

Root-cause fix, plus the structural one: **fail-open must leave a trace** (spec-11's thesis,
first live application). Smallest version — ingest writes one line per session into the store or
a log: `classifier: ran|fallback-regex|disabled(reason)`. Then a `tessera-watch` predicate
(P11): *N consecutive ingests on fallback → surface*. A fail-open path with a heartbeat is
honest; without one it's F-001 waiting.

**[Decision D16-1]:** if the pipe is dead, does the trace+predicate remedy land in the same fix
PR (my lean — the probe already proved silent fallback costs weeks), or does spec 11 get built
properly first?

## Sizing

Probe: ~30 min. Remedy if triggered: ~half session (trace line + predicate + tests).
