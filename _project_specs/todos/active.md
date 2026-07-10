# Active Focus

Declared current priority for Tessera framework dev. One focus at a time.

---

## Handoff — pick up here (last updated 2026-07-09)

**Just finished:** Mnemos compaction trial re-armed. It was due 2026-07-10 and
would have been decided on evidence the system never produced. Compaction has
never fired (max `token_utilization` 0.51 / 131 samples, ~83% trigger; fatigue
`flow` 131/131), and the marker was destroyed on consumption so nothing on disk
could show otherwise. Added `.mnemos/compaction-log.jsonl`; swapped the calendar
trigger for **≥3 recorded `compaction_fired` events**. Also corrected a ~6-week
doc error: `mnemos-compact-recovery.sh` never existed — Layer 2 is
`mnemos-session-start.sh` on an unmatched SessionStart. Commits `0f32d81`,
`6372237`.

**Do not re-litigate:** Mnemos's *session-continuity* layer is working and is
**not** on trial. Only *compaction-recovery* is. Conflating them is what almost
killed a working subsystem. An empty `compaction-log.jsonl` means **untested**,
never **useless**.

**Next, in order:**
1. **Roadmap Tier 1 discussion** (below, "Parked"). Was queued and not reached.
   Unblocks the 5-entry GSD observatory cluster. Discuss before building — the
   doc itself warns against starting it speculatively. **← only remaining item.**
2. ~~**FOCUS-003**~~ **DONE 2026-07-10.** Audited; one #17 violation
   (gate-recorder, already tracked); rest are accepted reasoning-conventions.
   Open follow-on: reword the surface-decisions bullet to split surfacing from
   recording (gate logged, awaiting approval).
3. ~~**Findings backlog**~~ **DONE 2026-07-10.** howler F-002 →
   `transferred:observatory "Reusable migration skill"`. tess-dashboard legacy
   `FINDINGS.md` → renamed `carry-forward.md`, fresh contract stub added. Scanner
   now reports 0 open across the fleet.

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
project inherits the ambiguity. **Open decision (gated, not executed):** reword
the surface-decisions bullet in both files to split surfacing from recording, so
the convention half isn't tarred with the violation half. Design change to a core
doc → surfaced for approval, not done silently.

---

## Backlog (triggered — do when the condition fires)

- **Mnemos compaction-recovery verdict.** Fires when `.mnemos/compaction-log.jsonl`
  records **≥3 `compaction_fired` events**. Tally with:
  `python3 -c "import json,collections;print(dict(collections.Counter(json.loads(l)['event'] for l in open('.mnemos/compaction-log.jsonl'))))"`
  Then judge: did `restore_injected` follow each `compaction_fired`, and did the
  restored checkpoint let work resume without re-deriving? `compaction_fired`
  with no matching restore, or repeated `restore_missed_stale`, is a **failure**
  signal. An **empty or absent log is not a signal at all** — it means compaction
  hasn't fired. Scope: compaction-recovery layer only, never session-continuity.

- **Content-aware hook drift check.** `bin/tessera-hooks status` compares declared
  mode vs local-copy *count*, never file *content* — so the three writable copies
  of each hook (`.claude/scripts/` → `templates/` → `~/.claude/templates/`) drift
  silently. This let a bare-`python3` regression sit in the install payload for
  ~2 weeks (see observatory F-003 update, 2026-07-09). Fix: diff the three layers
  by content, or make `templates/` generated rather than hand-maintained.
  **Trigger:** next hook edit, or next `install.sh` rework. Until then, every
  hook edit needs a manual three-way sync.

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
  - **NEXT (signal-gated, nothing to build now):** G-a fires after ~3 real sessions
    (P2 perpetual) → then decide P2: build `tess` umbrella CLI vs add snooze (first
    stateful piece). G-b/G-c only if their pattern appears. Pilot substrate is
    complete; further builds wait on the fire-log producing evidence.
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
