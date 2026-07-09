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
1. **Roadmap Tier 1 discussion** (below, "Parked"). Was queued for this session
   and not reached. Unblocks the 5-entry GSD observatory cluster. Discuss before
   building — the doc itself warns against starting it speculatively.
2. **FOCUS-003** (below) — still pending. Cheapest real win; closes #17's own
   follow-on clause. Note CLAUDE.md's gate-recorder instruction is itself a #17
   violation with a measured ~85% miss rate.
3. **Findings backlog** (surfaced by the SessionStart hook every session):
   howler F-002 wording, and tess-dashboard's `FINDINGS.md` in a legacy
   non-scannable format. Both small, both mechanical.

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

**Status:** pending
**Priority:** medium
**Source:** principle #17 (channel-not-convention); its own follow-on clause.

Sweep CLAUDE.md (framework + downstream templates) for instructions telling the
model to surface something to the user via convention alone ("surface X",
"flag Y", "tell the user Z"). Each is a silent-drift risk. For each: is there a
non-model channel (statusline / hook / harness tool), or does it rely on model
recall? Convert the high-value ones; document the rest as accepted-convention
with rationale.

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
