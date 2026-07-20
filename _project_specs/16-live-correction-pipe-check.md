# 16 — live correction-pipe spot-check (dead-pipe suspicion)

**Status:** CLOSED (2026-07-20, same day) — **verdict: `pipe-dead`, confirmed and fixed.** The
suspicion was right and worse than suspected: not classifier fallback — *ingest itself* crashed
on every Stop-hook run from 07-17 (#19 merge) to 07-20. See "Outcome" at the end.
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

---

## Outcome — `pipe-dead`, fixed (2026-07-20)

**Root cause (found in one hand-run, step 2 of the procedure):** spec-13 Phase 1's
`make_detector()` opens with `from scripts.model_routing import …` — an absolute import of a
**repo-root** module from inside the installed `mnemos` package. Under `python -m` from the repo
root, cwd is on `sys.path` and it resolves; under the **console script** (`.venv/bin/mnemos`) —
which is exactly what `mnemos-stop-ingest.sh` execs — it raises `ModuleNotFoundError`. The call
sits on the *first line* of `ingest_session`, **before every fail-open guard**, so the whole
ingest died with nothing written, and the hook swallows stderr (`>/dev/null 2>&1 … & disown`).
Every hook ingest since #19 merged (2026-07-17 08:14) was killed; every hand-run/backfill
(`python -m`, repo root) worked. **F-001's cousin, precisely:** silent no-op in the hook
environment, silent success in the interactive one — and P9 could not see it (it asserts the
interpreter imports the *toolchain*; this was the toolchain failing to import a *repo module*).

None of the four hypothesized silent-zero paths was it — the probe's premise ("19 new sessions
score density 0") was itself wrong: those sessions **were never ingested at all**. The P10
counter wasn't stuck at 24 from zeros; it was starved of rows.

**Fix (all in one PR, per D16-1's adjudicated lean):**
1. **Root cause** — `_import_routing()` resolves the repo root from `__file__` before the import;
   `make_detector()` now NEVER raises (any import failure → regex-only detector with
   `reason="import-error"`). Regression test runs the real interpreter from an outside cwd —
   the hook's exact condition.
2. **Trace** — `claude_sessions.classifier_status` (idempotent ADD-COLUMN), written per ingest:
   `ran` / `regex-only:<reason>` / `disabled-mid:consecutive-nulls` / `budget-exhausted`.
3. **Predicate** — `tessera-watch` **P11 ingest-pipe**, two shapes: (a) **DEAD** — recent
   transcripts (1h < age ≤ 7d, >10KB) with no `claude_sessions` row (the shape a status column
   cannot see, and the one that actually happened); (b) **DEGRADED** — last 3 ingests all
   `regex-only`/`disabled-mid` (`budget-exhausted` excluded: a bulk sweep shares one wall-clock
   budget, partial run ≠ silent death).
4. **Repair** — full `ingest-claude --all` re-run via the fixed console script (the fix's own
   verification): 72 missing sessions ingested, real-signal count 24 → **50**, **P10 now fires
   legitimately** (the band-recalib cue — separate next-work).

**Lesson recorded:** the F-001 rule generalizes — *"reach the toolchain by path, not name"* must
include *"a package's imports must not depend on the caller's cwd."* A fail-open path with no
trace reads as clean data; it cost three days of instrument blindness this time (F-001's was
weeks).
