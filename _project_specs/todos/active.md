# Active Focus

Declared current priority for Tessera framework dev. One focus at a time.

---

## Handoff — pick up here (last updated 2026-07-10)

**Just finished (big session):** the **observatory-watcher pilot is built** —
roadmap Tier 1 / spec-03 de-risking. `bin/tessera-watch` evaluates the
Observatory's silent+machine-checkable "When to revisit" triggers as predicates,
surfaced by a SessionStart hook (`tessera-watch-surface.sh`, now wired + in the
install payload). Substrate-only: predicate list + runner + append-only fire-log
(`.tessera/logs/watch.jsonl`) + `G-a` graduation predicate that reads the log so
the "graduate to a stateful engine" decision is itself channelized, not prose. 11
tests. On first run it caught **two real drifts** (a live hook missing from
`templates/`; a 167-line phantom `mnemos-compact-recovery.sh` contradicting its own
doc — both fixed). Also this session: FOCUS-003 closed, findings backlog cleared to
0 (howler F-002 transferred, tess-dashboard legacy `FINDINGS.md` renamed). **9
commits across tessera/howler/tess-dashboard, all pushed.**

**Do not re-litigate (decided this session):**
- **Substrate-only.** No snooze/hysteresis/prose-parsing/umbrella until a
  graduation predicate fires on real fire-log evidence. Building any of them now is
  the exact over-build the pilot exists to prevent.
- **P2 (tess-umbrella) declined + retired.** Verb count tracked no real friction —
  the `tessera-*` binaries are hook-invoked and callers name them directly, so an
  umbrella aliases without consolidating. Don't rebuild it; reopen only on a real
  hand-driven `tess` workflow. (observatory → Override entry #1.)
- **Mnemos compaction trial** unchanged: still event-triggered (≥3
  `compaction_fired`), now auto-watched by P3. Empty log = untested, not useless.

**Next — signal-gated, nothing to build cold:** the fire-log starts populating at
the *next* SessionStart (the hook wasn't live when this session began). No predicate
currently fires — watcher is green. Pick up when one fires: **P3** (Mnemos verdict),
**P1/P4/P5** (real drift/growth), or **G-a** (a predicate stuck ≥3 runs → decide its
remedy). The one *discussion* still parked: **broader roadmap Tier 1** + the 5 GSD
observatory cluster (below) — the pilot informs it but hasn't settled it.

---

## [FOCUS-001] Fix tier-classifier under-rating of decision/question prompts

**Status:** done (2026-07-08) — few-shot mitigation applied, 5/6 empirical; residual (context-blind lookup-shaped decisions) logged to observatory as mitigation #1, still open
**Priority:** high
**Source:** observatory "Tier classifier under-rates discussion-heavy prompts" (ADR-0002 open thread); observed live 2026-07-08 — "what's next for tessera?" classified HAIKU.

### Problem
`hooks/tier-classify-hook` classifies by task-type keywords on the bare prompt.
Short decision/strategy questions ("what's next?", "should we go global?") match
no keyword and fall through to HAIKU/SONNET — under-rating the most
reasoning-heavy turns exactly when stakes are highest. Sanctioned fix path:
ADR-0002 re-evaluate trigger ("misclassification costs quality → boundary
few-shot examples").

### Approach
Prompt-engineering the classifier (smallest diff, reversible): add a
"judge reasoning demanded, not prompt length" rule, extend OPUS to open
design/strategy decisions, and add balanced few-shot examples (short decision Q
→ OPUS; short trivial lookup → HAIKU) so length stops being the signal.

### Validation
Re-classify this session's real prompts (decision questions) — must land OPUS,
while a trivial lookup stays HAIKU. Empirical eval against local qwen, not hope.

---

## [FOCUS-002] Sweep the observatory (22 entries)

**Status:** done (2026-07-08)

Triaged all 22. Framework too young for the >6mo cull — nothing dead. Outcomes:
- **Promoted:** L217 convention-surfacing drift → **design principle #17** (3rd
  instance was this session's findings SessionStart hook).
- **Cluster cross-ref:** 5 GSD entries (byte-budget, `.planning` schema, domain
  probes, gate types, plan-drift) tied to the Tier 1 discussion — resolve together.
- **Near-due watch:** L174 Mnemos kill/keep clock resets ~2026-07-10 (drop signal
  if the fed layer still hasn't aided a real recovery).
- **Spawned:** FOCUS-003 (audit CLAUDE.md "surface X" against #17).
- Rest legitimately parked on external triggers. Duplicate hook copies
  (`hooks/` vs `.claude/scripts/`) noted — real F-003-shaped smell, folded into
  the ADR-0004 re-eval space, not urgent.

---

## [FOCUS-003] Audit CLAUDE.md "surface X" instructions against principle #17

**Status:** done (2026-07-10)
**Priority:** medium
**Source:** principle #17 (channel-not-convention); its own follow-on clause.

Sweep CLAUDE.md (framework + downstream templates) for instructions telling the
model to surface something to the user via convention alone ("surface X",
"flag Y", "tell the user Z"). Each is a silent-drift risk. For each: is there a
non-model channel (statusline / hook / harness tool), or does it rely on model
recall? Convert the high-value ones; document the rest as accepted-convention
with rationale.

### Outcome
Swept `CLAUDE.md`, `templates/tessera/CLAUDE.md.template`, `templates/CLAUDE.md`.
Six candidates; **one violation**, already tracked, no build needed.

- **Accepted conventions** (#17 exempts "shape how the model works" — no
  user-facing artifact whose value depends on being seen):
  - Push back on drift (L31), Name biases (L35), Flag confidence (L37). All
    introspective/reasoning behavior; no non-model channel is possible or wanted.
- **Already channelized** (N/A — the "announce" is cosmetic atop a real channel):
  - Announce `MNEMOS CHECKPOINT` (L56 → hook injection); Tier advisory (L60 →
    statusline).
- **The one #17 violation — surface-decisions → *also record it* (L33):** the
  *record* (`scripts/gate/emit.py` → `.tessera/logs/*.jsonl` → dashboard) is the
  user-facing friction journal; its trigger is pure model recall; **~85% miss**
  measured (observatory line 154). Already documented (observatory 147-157) with
  the fix queued: Stop-hook gate-scan backstop, gated on n≥2 dogfood reproduction.
  No new work — correctly deferred there.

**Audit's own contribution:** L33 *conflates two things* — gate-**surfacing**
(an accepted reasoning-convention) and gate-**recording** (the violation). The
same bundling is copied into `CLAUDE.md.template:23-24`, so every downstream
project inherits the ambiguity. **RESOLVED 2026-07-10:** reworded both files —
surfacing is now its own bullet (accepted convention, #17-permitted); recording is
a separate bullet honestly labelled a lossy convention with the ~85% miss and the
queued Stop-hook backstop stated inline. The convention half is no longer tarred
with the violation half.

---

## Backlog (triggered — do when the condition fires)

- **Mnemos compaction-recovery verdict.** Fires when `.mnemos/compaction-log.jsonl`
  records **≥3 `compaction_fired` events**. *Detection is now automated — the
  watcher's **P3** predicate surfaces this at session start; the manual tally is no
  longer the trigger.* When P3 fires, judge: did `restore_injected` follow each
  `compaction_fired`, and did the restored checkpoint let work resume without
  re-deriving? `compaction_fired` with no matching restore, or repeated
  `restore_missed_stale`, is a **failure** signal. An **empty or absent log is not
  a signal at all** — it means compaction hasn't fired. Scope: compaction-recovery
  layer only, never session-continuity.

- **Content-aware hook drift check.** *Partly resolved 2026-07-10 — the watcher's
  **P1** predicate now content-diffs `.claude/scripts/` ↔ `templates/` and fired on
  two real drifts.* `bin/tessera-hooks status` still only compares declared mode vs
  local-copy *count*, never content. **Remaining gap P1 does NOT cover:** the third
  layer, `~/.claude/templates/` (out-of-repo, so the in-repo watcher can't diff it),
  and making `templates/` generated rather than a hand-maintained copy. The
  bare-`python3` regression that sat ~2 weeks (observatory F-003, 2026-07-09) would
  now be caught by P1. **Trigger for the rest:** next `install.sh` rework — fold in a
  global-layer diff or generate `templates/`. Until then the global copy still needs
  a manual sync (in-repo pair is now watched).

- **Cut CHANGELOGs when repos go public.** conclave, tessera, tess-dashboard, and
  howler are all expected to go public at some point. None but tessera has a
  CHANGELOG yet — deliberately (premature until there's a public reader). When a
  repo goes public: `cd <repo> && tessera-changelog --since <ref> --version <v> --date <d>`
  (commits are already Conventional; verified plug-and-play on conclave). Keep the
  tool **single-source in `tessera/bin`, reached via PATH — do NOT copy it into
  each repo** (that's the F-003 drift trap). PATH the dir once per machine.

---

## Parked for discussion (not started)

- **Roadmap Tier 1** (runtime observability / verifiable contracts / human
  escalation, `_project_specs/00-autonomous-engineering-roadmap.md`). Build-more-
  framework vision; rationale dates to an April 2026 chat. Discuss whether current
  dogfood pull justifies it before committing — do NOT start speculatively.
  - **Now carries a concrete entry point (2026-07-09).** The observatory-watcher
    idea folded into **spec 03** (verifiable contracts) as its de-risking pilot —
    same conversion (prose condition → machine-checked predicate), on a corpus
    where a wrong predicate costs a noisy session-start line instead of a broken
    build. Deliberately *not* spec 01, which observes the deployed product.
  - **The dogfood pull is no longer hypothetical.** Three observatory triggers
    were found at or past threshold, unnoticed, on 2026-07-09: `tess`-verb count
    (4, trigger said 2), downstream project count (4, trigger said ~4–5), skill
    count (56, trigger said 60, entry claimed "~50"). Spec 03's premise —
    natural-language conditions go silently unchecked — is demonstrated, not
    argued.
  - **Do not build the watcher standalone.** It is the experiment that tests
    whether Tier 1's premise holds. Building it before the discussion spends the
    evidence it exists to produce.
  - Resolves together with the 5-entry GSD cluster (byte-budget, `.planning/`
    schema, domain probes, gate types, plan-drift guard) per the observatory
    cluster note.
  - **Discussion opened 2026-07-10. Resolved: substrate-only, hard-stop before
    stateful.** Verdict on starting: justified (4 self-surfaced instances of the
    drift class; #17 already doctrine). Smaller-vs-engine resolved on a reframe —
    the axis isn't small-vs-big but **shared-substrate vs speculative-requirements**:
    - **Build now (substrate):** flat declarative `name: predicate` list (≈ cost
      of inline greps, reads better) + generic runner + surfacing channel +
      append-only **fire-log** + written kill criterion.
    - **Defer HARD until a real fired trigger demands it (speculative):** snooze/
      ack state, hysteresis/damping, per-entry config, and NL-prose parsing (the
      actual spec-03 engine). Reshape is likely, kill is not — so don't cast
      predicate *shape* in engine-concrete before writing 5 real ones. The
      "second `tess` verb = spirit-not-letter" case already proves predicates are
      subtler than greps.
  - **Re-evaluation is itself channelized (the watcher watches itself).** The
    "build the engine now?" decision must not be a prose note — that's the drift
    being fixed. Graduation triggers = watcher predicates over its own fire-log:
    (a) same trigger fired ≥3 consecutive sessions → needs snooze/state; (b) any
    predicate flapped (fired→cleared→fired) in last 5 → needs hysteresis; (c) >10
    active predicates OR a trigger that can't be a one-liner → declarative/prose
    engine earns its slot. When one fires, reopen smaller-vs-engine in-channel.
    Fire-log earns its keep 3 ways: product function, kill decision, graduate
    decision.
  - **4 scope decisions — ALL SETTLED 2026-07-10. Ready to build.** (1) predicate
    set — DRAFTED, denominators settled, see below; (2) surface channel — SETTLED:
    **SessionStart hook + on-demand verb, both** (the `tessera-findings` shape —
    one `bin/tessera-watch` script, hook wraps it for auto-surface, runnable
    on-demand for deliberate checks; statusline rejected as too cramped for N
    lines); (3) kill criterion + (4) storage — both ride the shared append-only
    fire-log; kill and graduate are two faces of one self-monitor.
  - **Build shape (substrate-only, no stateful parts):** `bin/tessera-watch` runs
    the 5 predicates over on-disk state, prints fired ones, appends fired-set to
    the fire-log; SessionStart hook wraps it (silent when none fire). Graduation
    predicates a/b/c read the fire-log. NO snooze/hysteresis/prose-parsing until a
    graduation predicate fires.
  - **BUILT 2026-07-10.** `bin/tessera-watch` (5 predicates, `--json`/`--log`,
    exit 1 if any fire) + `.claude/scripts/tessera-watch-surface.sh` (SessionStart
    wrapper, `--log`, silent unless fired) synced to `templates/` + wired into
    `settings.json` SessionStart. Fire-log → `.tessera/logs/watch.jsonl`
    (gitignored). Tests `scripts/test_tessera_watch.py` — 8 pass (py3.13). Live: P2
    fires (5 verbs — tessera-watch became the 5th), P1/P3/P4/P5 green. Graduation
    predicates (a consecutive-fire / b flap / c count>10 or non-one-liner) NOT yet
    built — add when the fire-log has history to read.
  - **G-a BUILT 2026-07-10 — self-eval loop closed.** `g_a_consecutive` reads the
    fire-log; a core predicate firing ≥3 consecutive runs surfaces as its own fired
    predicate ("build remedy or add snooze"). Detector only — the remedy (snooze
    state) still waits until G-a fires. G-b (flap) / G-c (predicate-count scale)
    deferred, no signal. 12 tests pass. Observatory entry "…triggers are prose"
    updated to Piloting + kill criterion recorded. All committed + pushed.
  - **P2 RETIRED 2026-07-10 — pilot's first real lesson.** P2 (verb count → `tess`
    umbrella) fired on a proxy that tracks no friction: the `tessera-*` binaries are
    mostly hook-invoked and callers name them directly, so an umbrella adds an alias
    layer without consolidating. Declined the umbrella, retired P2 from the watcher.
    The watcher's value shown by *provoking scrutiny of a bad predicate*, not by
    compliance. Recorded in observatory override entry (#1 declined). Watcher now
    quiet — all green (only real signals fire). 11 tests pass.
  - **NEXT (signal-gated, nothing to build now):** no predicate currently fires.
    P3 fires when compaction hits 3 (Mnemos verdict); P1/P4/P5 on real drift/growth;
    G-a if any core predicate sticks ≥3 runs. G-b/G-c only if their pattern appears.
    Pilot substrate complete; further builds wait on the fire-log producing evidence.
  - **#1 predicate set DRAFTED (silent AND machine-checkable; 5 of 22 entries):**
    - **P1** F-003 hook drift: `templates/` vs `.claude/scripts/` per-hook diff
      → **FIRES NOW (1 drift)**.
    - **P2** override→`tess` CLI: `ls bin/tessera-* | wc -l` ≥2 → **FIRES NOW (4)**.
    - **P3** Mnemos trial: `grep -c compaction_fired .mnemos/compaction-log.jsonl`
      ≥3 → no (0, clean/untested). Same as the trial's re-arm trigger — folds in free.
    - **P4** F-003 project count: downstreams w/ frozen hooks ≥5 → no (3).
    - **P5** skill routing: `ls -d .claude/skills/*/ | wc -l` ≥60 → no (56).
    - Excluded: Tier-1-cluster entries (resolve with the decision), self-announcing
      triggers (sqlfluff etc.), and the gate-scan backstop (can't be a one-liner →
      it's graduation-signal-c, not a starter predicate).
    - **Denominators SETTLED 2026-07-10:** P2 → count `bin/tessera-*` binaries
      (spirit, not `tess <noun>` letter which reads 0), threshold ≥2, **fires now
      (4)**; stateless so it fires every session until umbrella built/snoozed →
      first exerciser of graduation-signal-a. P4 → downstream siblings EXCL.
      framework (tessera is `source`, not a drift victim), ≥5, no fire (3);
      frozen-only refinement deferred. P5 → `.claude/skills/*/` dirs, ≥60, no fire
      (56); plugin/duplication excluded until proven to dominate.
  - **P1 drift predicate caught + fixed a live bug (2026-07-10):**
    `tessera-findings-surface.sh` was a live SessionStart hook present in
    `.claude/scripts/` but **missing from `templates/` AND `~/.claude/templates/`**
    → fresh `install.sh` would not install it; findings backlog channel goes dark
    on a new machine. **FIXED** — synced to both layers; scripts→templates now clean.
  - **Phantom in install payload — DELETED 2026-07-10.**
    `templates/mnemos-compact-recovery.sh` (167 lines) was dead payload wired to
    nothing, its header naming the "SessionStart compact matcher" the 2026-07-09
    correction declared never existed. Removed from `templates/` (not in global).
    The accurate correction comment in `mnemos-post-compact-inject.sh:24` stays —
    that's the record, not stale.
