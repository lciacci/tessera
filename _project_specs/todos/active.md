# Active Focus

Declared current priority for Tessera framework dev. One focus at a time.

**Read this top section, run `tessera-watch`, and you are caught up.**

---

## ═══ SESSION 2026-07-17 — Phase 1 + cohesion contract + skill removals (9/10) + template alignment ═══

**ALL MERGED to `main` (#19–#23). Suite green, doccheck 17/17, `tessera-watch` quiet (P7 snoozed). No branches in flight. Skills 57 → 48.**

### What shipped

**A. Friction-detector Phase 1 (spec 13) — #19.** correction recall un-blinded: keyword regex →
local **qwen3:8b** classifier on the passive ingest pipe. Heavy session `b6d7b6f5` went
`correction_density 0.000 → 0.219` (hand-labeled truth 0.188); clean sessions stay 0; spread across
~24 dogfood sessions is now 0.00–0.35 (was 0.00–0.06, blind). Three scope corrections found while building:
- **3B tier-classify model is USELESS here** — it parrots the prompt's ending polarity (constant-yes/no).
  Needs **qwen3:8b + `think=false`** (reasoning model; without it burns num_predict on a hidden `<think>`).
  Fails open to regex. Override: `MNEMOS_CORRECTION_MODEL`.
- **Injected user turns were counted as corrections** — hook feedback (`isMeta`) + task-notifications
  (`promptSource=system`) now tagged `user-meta`, excluded from numerator AND haziness denominator.
- **Latency was never real** — Stop hook is backgrounded (`& disown`) + incremental, so a live Stop
  classifies only new turns; full `--reclassify --all` backfill of ~26 sessions = 81s. No batch/cap needed.
- Review fix: disable the classifier after **3 consecutive** nulls, not the first (one blip was silently
  regex-only'ing the rest of a backfill).
- **`tessera-watch` P10** self-fires the deferred haziness band re-tune at ≥40 real-signal sessions
  (24 now → ~16 runway) → spot-check precision first, THEN decide bands + the 0.30 weight.

**B. Three-project cohesion contract — #20.** `docs/contracts/three-project-cohesion.md` — canonical
map of the **substrate/pattern/policy** stack: Conclave (serving + `divergence.py` instrument) /
pr-arbiter (multi-role union-recall review) / Tessera (governance + routing decisions). Tessera hosts as
coordinator; **hosting ≠ ownership**; runtime peers; lane-change needs that project's sign-off. Contains
layering table, 5 seams w/ owners, sequence (live/parked/ADR-gated), the **4 anti-conflation guards
verbatim**, Open decisions **D1–D4**. A coordination MAP, not an ADR — decisions surfaced, deferred.
- Resolved `council-review`'s pending roster/config decision → points at the contract (D1), flagged its
  **plan-validation** path is *select-best* → NOT shielded by guard (a) (unlike union-recall PR-review).
- Peer stubs point here: `../conclave/docs/INTEGRATION.md` (existed), `../pr-arbiter/docs/INTEGRATION.md`
  (authored this session, committed via a pr-arbiter session).

**C. Skill removals — 9 of 10 (ADR-0008) — #22.** HARVEST-before-CUT. Cut: `session-management`,
`code-deduplication`, `agent-teams`, `cross-agent-delegation` (ideas in design-principles Fossil lineage /
polyphony / icpg); `codex-review` + `gemini-review` (patterns → observatory convergence note);
`autonomous-testing` (→ observatory radar note); `ai-models` (skip-with-rationale); `build-in-public`
(corpus skill only — live plugin infra kept). **#10 `code-review` bulk still gated on D3.** `build-in-public`
writing-guidance harvest handed off for the plugin repo.

**D. Template/init alignment (ADR-0008/0009) — #23.** Dropped only `polyphony` from the downstream eager
block (kept `iterative-development`+`security` eager — they *fit* a downstream app, unlike framework-Tessera;
`@eager` ≠ "available"). Rewrote `initialize-project.md` Step 2/4 from the copy model → ADR-0009 selector.

**E. A FRICTION lesson, and its remedy — #22.** The `agent-teams` cut deleted 6 role files a KEPT command
(`spawn-team`, polyphony's) depended on — Lorenzo caught it, no check did. Root cause named: **rule-over-read**
(apply a documented rule by pattern-match instead of reading the specific artifact + checking its premise
holds here). Remedies landed: doccheck **`template-skill-refs-exist`** (17th check — catches `@`/`~/` skill
paths to deleted skills), observatory FRICTION finding, and a widened **`rule-over-read` memory**. The
eager-block over-application (D) was the same pattern, caught the same way. **Carry forward: skill/knowledge
decisions get read-first, single-decision, no batching.**

**F. Doc hygiene (end of session).** Promo HTML mosaic (dropped 6 cut skills, fixed eager flags to match
base+mnemos); `claude-bootstrap-reference` disclaimer (audit done, corpus now 48); this handoff.

### NEXT (in order) — nothing here is started
1. **D2 — the union-recall divergence metric** (contract seam S2). **The one genuinely-unblocked
   high-value lever:** needs no prerequisites (not Phase 3, not a standing fleet), and it's what validates
   pr-arbiter's thin headline (guard (d)) so the whole three-project integration can start moving. Design
   + build the scoring variant of `divergence.py` (oracle = union of true findings vs a labeled defect set).
2. **Delivery-entangled trims** — `python` TRIM, `ui-testing` MERGE (small). *(Read-first, per the
   rule-over-read lesson — these are the same shape that went soupy.)*
3. **Refine `skill-profiles.json`** vs the full KEEP set (low-stakes).
4. **Friction-detector Phase 2/3** — type corrections (misunderstood/defied/overreached/wrong), then
   action-link + divergence surface. The natural follow-on once Phase 1's signal is trusted.

*(The "10 removals" are 9-done — #22. Only `code-review` bulk remains, gated on D3. `workspace` +
`team-coordination` were never in the 10; they're separate removal candidates.)*

### Deferred with their own triggers (not "next")
- **Three-project ADR — D1/D3/D4** — evidence-gated: D3 needs pr-arbiter **Phase 3** (8–15h annotator
  pilot) + a **standing conclave fleet**; D4 (pr-arbiter adopts `.tessera/`) trips `tessera-watch` P4 at 5
  downstreams. D1 (routing home) firms with D2's result. See the contract's Open decisions.
- **P10 haze-recalib** — self-fires at 40 real-signal sessions → precision spot-check + band re-tune.
- **`should_fire` passive extraction** — apply spec-13's pattern to retire the dead labeling path.
- **Team-spawning feature seam** *(needs a call — read-first)* — ship it downstream (wire `install.sh` +
  activate polyphony) or retire (cut spawn-team + the `templates/agents/` roles). See observatory.
- **Canonical setup entry point** *(needs a call)* — `/initialize-project` (interactive) vs
  `bin/tessera-new-project` (greenfield); `install.sh`/`GETTING_STARTED` advertise only the former.
- **`code-review` bulk removal (#10)** — gated on D3. `templates/codex-auto-review.sh` deferred there too.
- **De-dup the registry / Listing-budget floor / P7 (snoozed 2026-08-31) / Mnemos compaction-recovery
  (→ real CLI venue)** — carried from prior sessions; own venues.

---

## ═══ SESSION 2026-07-16 — delivery reframe shipped, + a deep friction-instrumentation thread ═══

**ALL MERGED to `main` (12 PRs). Suite green, doccheck 16/16, `tessera-watch` quiet. No branches in flight.**

### What shipped, by arc

**A. FOCUS-004 delivery (the headline).** #4 (audit + ADR-0008 + adr-gate), #5 (safe bucket: fossil
harvests → `design-principles.md`, `base` 532→122, `icpg` 327→246), **#9** (*was #6*; ADR-0009 + scaffold).
- **ADR-0009 refines ADR-0008's mechanism:** Claude Code unions global+project skills, so downstream
  *already sees every skill* — never *undelivered*, just *un-curated*. Fix = a **selector**
  (`skillOverrides` off per profile), NOT a copier. `bin/tessera-new-project` writes it from the
  composable map `templates/tessera/skill-profiles.json` via `scripts/skill_overrides.py`. Verified
  end-to-end (47 off/9 on). Reviewed; fail-loud + universal-inviolable hardening applied.

**B. Eager-load cleanup — DONE.** #8 (`security` ADAPT — de-eager OWASP, keep the secrets floor) + **#11**
(`iterative-development` de-eager). **Eager set is now just `base` + `mnemos`** — the genuinely-universal,
framework-native two. The full skills stay in the registry, on-demand, shipped downstream via curation.

**C. Mnemos trial — SORTED.** #7. Fatigue is LIVE (token-util 0.27, not degraded — 07-15 all-None was
transient). Compaction DOES fire here, but via the harness-summarization path with no `{trigger}` (→
`unknown`); instrumented with a key-only `payload_probe`. **DECISION: compaction-recovery verdict → real
Claude Code CLI venue** (P3 can't reach 3 real `auto` events here); fatigue stays here. (`docs/observatory.md`
→ "Mnemos compaction vehicle", 07-16.)

**D. Infra hygiene.** #13 (P1 hook↔template drift, root-caused: an edit wrote the live hook not the
template, and P1 was a SessionStart advisory with no commit block — added doccheck `hooks-match-templates`,
**now uncommittable**). #16 (**`tessera-watch` snooze mechanism** — the G-a-earned remedy; tracked+expiring
+ reason-required; G-a snooze-aware. **Applied to P7, 45d.**).

**E. Design threads SEEDED (noted, not built).** #12 (conclave/pr-arbiter convergence), #14 (haziness
finding), #15 (spec 13). See the friction thread below.

### The friction-instrumentation thread (P7 → should_fire → action-divergence → haziness)
Started from P7's nag; went deep and it paid. Conclusions:
- **should_fire is SOUND** (user-disposition ground truth, real dashboard consumer) — I was wrong to want
  it retired. But its **backlog is dead data** (52 unlabeled across 19 sessions won't be hand-labeled), so
  **P7 is snoozed** (#16), not resolved by labeling.
- **The valuable vector is action-divergence** (did the agent do the *opposite* of what was asked) — the
  friction the framework keeps admitting only a human catches. Its one instrument, Mnemos
  `correction_density`, has **near-zero recall** (#14): a keyword regex that missed *this* session's heavy
  redirection entirely (`correction_density 0.000`). The *pipe* is right (passive, stores evidence); the
  *detector* is blind.
- **The fix for both is passive extraction, never manual labeling.** Scoped: **`_project_specs/13-friction-detector-upgrade.md`**
  (Phase 1 = local-qwen recall detector + backtest; typing/action-linking deferred).

### NEXT (in order) — nothing here is started
> **SUPERSEDED by the 2026-07-17 section above.** Item 1 (Phase 1) shipped as #19; the queue was
> re-ordered (D2 is now the unblocked lead). Kept for the trail.
1. **Friction-detector Phase 1** (`_project_specs/13`) — the highest-value build; instruments the
   action-divergence friction. Recalibrates haziness bands as a side effect (flagged in the spec).
2. **The 10 removals** — HARVEST-first; `codex`/`gemini-review` harvests now have a home (the conclave note,
   #12). `ai-models`→URL pointers, `autonomous-testing`→pipeline note, `build-in-public`→plugin docs. The 3
   Maggy skills (`agent-teams`, `autonomous-testing`, `workspace`) all live here → 0 Maggy after.
3. **Remaining delivery-entangled trims** — `python` TRIM, `ui-testing` MERGE.
4. **Refine `skill-profiles.json`** vs the full KEEP set (starter map; low-stakes).
5. **Conclave design session** (needs Lorenzo) — ADR-0008's open thread; seeded in `docs/observatory.md`
   → "Tessera ↔ Conclave ↔ pr-arbiter". Firms up with a review-flavored divergence measurement + pr-arbiter
   Phase 3. Gates the `code-review` bulk removal.

### Still deferred (own venues)
- **De-dup the registry (D)** — ADR-0009 further deferred it (global stays authoritative). Observatory.
- **Listing-budget floor ("Goal B")** — settings can't zero a skill's listing name; `/doctor`-measure
  before any physical partitioning. YAGNI.
- **P7 gate-labels — SNOOZED to 2026-08-31** (#16). Resurfaces then if the detector upgrade (spec 13)
  hasn't superseded the whole should_fire-labeling approach by making it passive.

---

## Handoff — 2026-07-13 (FOCUS-004 / the skill audit, and what it actually found)

**`docs/adr/0007-skill-corpus-prune.md` (Proposed) is the record. Read it before touching skills.**
Per-skill ledger with evidence: `_project_specs/todos/focus-004-audit.md`.

### The audit did its job, but the findings were NOT in the skills

- **6 skill invocations from the 56-skill corpus, ever** (171 transcripts, 34,636 events) — all
  `code-review`. The other 4 invocations machine-wide are skills *Anthropic ships*. **The
  inherited corpus has contributed exactly one skill, ever.** 22 skills declare `paths:` globs
  that match 0 files here and cannot fire.
- **Two byte-identical registries both load** (`tessera/skills/` + `~/.claude/skills/`), so every
  skill is listed twice. **Tessera is the only project with a local skills dir**; all 20+ others
  use the global one — which means *cutting `tessera/skills/` would not reduce Tessera's context
  at all.*

### What was actually broken — and it was NOT skill debt

1. **`bin/validate-plan` manufactured verdicts out of its own brokenness.** FIXED (`7a725f7`).
   It returned a confident `CHANGES_NEEDED 0/3` because a **missing backend was counted as a
   reviewer voting NO**. Three states now: voted / unavailable / **broken**. Zero usable
   reviewers → **exit 2, no verdict**. `scripts/test_council.py`.
2. **The entire multi-model stack had never run.** FIXED (`ec041d3`). Five `bin/` scripts
   `import httpx`; **httpx is installed nowhere**. `build-in-public-status` would not even
   *compile*. Ported to stdlib `urllib`.
3. **The F-001 detector was a blacklist** — `{mnemos, icpg, polyphony, skill_lint, pytest, yaml,
   requests}`. `httpx` simply was not on it. New check `bin-scripts-are-stdlib-only` names
   nothing and tests by execution: *every module `bin/` imports must be findable by the
   interpreter it actually runs on.* **15 doccheck checks** *(16 as of 2026-07-16 — added `hooks-match-templates`).*

### THE LESSON — and it cost three wrong conclusions

> **I audited whether files sat at the paths the docs claimed, and never once RAN the thing I was
> condemning.** `~/bin/deepseek` was absent, so I called the subsystem dead. It meant the *path*
> was wrong — `deepseek` was on PATH the whole time. **That is F-001's exact confusion:
> `unreachable` misread as `unused`,** which `CLAUDE.md` warns about in those words. Then I said
> "the stack works" because `command -v` found the files — **existence is not function.**
>
> **Every correction came from outside me:** the spec-12 adversary refuted 2 of 4 claims; Lorenzo
> caught the deletion momentum ("what are we short-shrifting?") and stopped me deleting a
> subsystem over a path typo; the *real run* caught a half-fix the tests called green.
> **`tessera-verify stats`: author error rate 38%.**

### ⚠️ THE AUDIT WAS NOT RUN. What ran was a reachability sweep.

**Caught by Lorenzo at the end of the session** — *"rather than reading through the skills there
was a leap to unnecessary and deletion."* **Correct, and it is the same error a fourth time.**

~31 of the 56 verdicts were reached **without reading the skill's body**, on two signals: *its
`paths:` can't match in Tessera* and *it was never invoked*. **Neither judges the skill.** Both
measure **reachability**. Those verdicts are **VOID** (ADR-0007, "The third correction").

- **The invocation argument is circular:** there are **6 invocations machine-wide across ALL
  skills, including Anthropic's own.** That indicts the *discovery mechanism*, not any skill.
- **The frame was wrong:** these live in the **global** `~/.claude/skills/`, serving **20+ repos**.
  **`flutter` SHOULD be inert in Tessera.** That says nothing about its worth to the Flutter repos.
- **So the `paths:`-match scan is the WRONG next step** — more reachability evidence for a
  question reachability cannot answer. **It was previously listed here as item 2. It is not.**

**And this restores the compaction premise.** I declared it falsified ("the audit didn't need the
205k read") — but only because I'd swapped a cheap proxy for the real judgment. **The real content
audit IS read-heavy, exactly as the spec said. FOCUS-004 is still the P3 compaction vehicle.**

**AND THE FLOOR OF IT: USAGE IS NOT EVIDENCE — not a CUT, not even a DEFER.** An earlier draft
said "never fires → DEFER". That still smuggled the signal in; **DEFER is suspicion, and suspicion
is a verdict.** Zero usage carries **zero information**, because the audit *already found what
fully explains it*: **`tessera-new-project` ships ZERO skills** (no delivery path downstream) and
**6 invocations machine-wide across every skill including Anthropic's own** (discovery barely
works). *Once a cause fully explains an observation, the observation is not evidence for anything
else.* The audit wrote both causes down and spent the number anyway.

**It is the same argument that saved the multi-model stack an hour earlier** — *never ran,
directional, framework hasn't got there yet, KEEP*. Accepted for `bin/`, refused for `skills/`.
**That is not a principle, it is a mood.**

> **The 6-invocation finding indicts the FRAMEWORK's distribution and discovery — not the skills.
> It was the audit's headline and it was aimed at the wrong target.**

**The rubric is in `_project_specs/todos/focus-004-audit.md`.** Only *is it true / is it superseded
/ is the guidance good* can CUT. A fourth question — *is it on the path we are building?* — can
only **KEEP**. **If a future session reaches for an invocation count to justify a cut, that is
drift. Challenge it.**

### Where to pick up

0. ~~**RUN THE ACTUAL AUDIT.**~~ **DONE (2026-07-14).** All 56 bodies read in the main thread, judged
   on the 5 admissible questions only. **Record: `focus-004-audit.md` → "═══ FINAL TALLY — REAL AUDIT ═══".**
   Headline: it **near-inverts the void table** — ~44 keep-in-some-form, **10 removals**, every one on
   stale/superseded/foreign-product/vendor-manual grounds, **zero on reachability**. Three verdicts flipped
   from reading current state (council-review CUT→FIX, iterative-development CUT→KEEP, cpg-analysis CUT→KEEP).
   **The real finding stands and is now content-confirmed:** the corpus is mostly *good, current,
   downstream-applicable* — but undeliverable, because `bin/tessera-new-project` ships **zero** skills.
---

## ═══ FOCUS-004 EXECUTION STATUS + POSTURE (2026-07-15) — read this to resume ═══

**Record of decisions:** ADR-0008 (supersedes 0007). **Per-skill ledger + harvest manifest:**
`focus-004-audit.md` → "REAL AUDIT" + "FINAL TALLY". **Verdict: keep 46, remove 10** (all removals
on stale/superseded/foreign-product grounds — **never** on reachability).

### The working method (agreed with Lorenzo 2026-07-15)

The 56-body audit already answered *"is each skill good"* (in the ledger). What execution adds is the
**forward-posture pass** — every destructive item resolves to ONE of three, and **the design note is
written BEFORE the cut, not after**:

1. **CUT CLEAN** — genuinely don't need the capability. *(e.g. `ai-models` — native `claude-api` covers it.)*
2. **ROLL OUR OWN → write the design-note/spec stub FIRST, then cut.** We want the capability, this
   version is wrong. *(e.g. `agent-teams`' step-enforcement → capture as Stop-hook kin before deleting;
   `code-review` multi-engine → conclave note before the bulk goes.)*
3. **LOG TO OBSERVATORY** — might want it later, not now. *(e.g. `autonomous-testing`'s pipeline shape.)*

This is *harvest-before-cut* **plus** *replacement-posture-before-cut*. It is the antidote to "cut
something we need in two months."

### Buckets (by risk, not by phase)

- **Mechanical, zero corpus risk (do anytime):** the FIXes + the *safe half* of D.
- **Low-stakes judgment (nothing leaves the corpus):** TRIM `base`/`python`/`icpg`, ADAPT `security`,
  MERGE `ui-testing` → decide *what within* survives; wrong = re-add, not lost.
- **Judgment-heavy, forward-posture protocol, don't rush:** the harvests + the 10 removals (A/B).
- **Design sessions (need Lorenzo):** delivery mechanism, skill instrumentation, Tessera↔conclave.

### DONE

- ✅ Audit + ADR-0008 + `adr-gate` split (#8) + `supabase-python` glob FIX → **PR #4** (10 commits).
- ✅ **FIX `council-review`** (2026-07-15): paths `~/bin/`→`bin/`; dropped the Maggy-dashboard ref;
  flagged the design-blocked parts (absent `council.yaml`, no `claude-fable-5` wrapper, `codex` absent)
  as *illustrative pending the conclave design* — **not rewritten** (conclave session reshapes it).
- ✅ **FIX `code-graph`** (2026-07-15): corrected the config claims — backend is live (MCP tools exposed)
  but configured **globally**, not via a committed `.mcp.json`; `install-graph-tools.sh` absent.

### DEFERRED / NEEDS-DESIGN — and WHY (this is the "don't lose it" part)

- ⏸ **D · de-dup the skill registry → BLOCKED on the delivery-source decision (E).** The two copies
  (`tessera/skills/` 57, global `~/.claude/skills/` 56) **have now DIVERGED** — this session added
  `adr-gate` + FIXes to the tessera copy only. So de-dup is no longer "delete the identical copy"; it
  *is* the question "which registry is authoritative for downstream delivery." **Do not delete either
  until delivery is designed.** → Observatory: "Skill registry — which copy is source-of-truth."
- 🎨 **D · the `skill-declared-backends-exist` doccheck check → NEEDS DESIGN, do not implement naively.**
  A literal "every binary a skill names must exist here" check **re-commits the exact reachability error
  the audit was about** — it would flag every downstream stack skill (`vercel`, `gh`, `supabase`…). The
  *correct* check lints the **fail-open PATTERN** (imperative "do not skip / mandatory / 0-of-3 → revise"
  gating language tied to an external backend), repo-local, no binary-existence. That's a design task.
  → Observatory: "Fail-open skill lint (the check council-review earns)."

### NEXT (in order)

1. **Low-stakes judgment bucket** — TRIM/ADAPT/MERGE (safe, nothing leaves).
2. **Harvests** (fossils→design-doc, `ai-models` pointers, `build-in-public`→plugin, vendor→conclave note)
   via the posture protocol.
3. **Then the 10 removals** — each already has its posture in the ledger's harvest manifest.
4. **Build the delivery path** — `bin/tessera-new-project` ships the KEEP set, profile-gated. **The fix
   the whole audit points at, and the gate on de-dup.** *(Design session — needs Lorenzo.)*

*(The numbered items below predate ADR-0008. **Superseded/done:** old #2 paths-scan (the content audit
replaced it), old #3 "22 authorized cuts" (audit says keep most), old #5 supabase-python (FIXed).
**Still live:** old #1 conclave = E above; old #4 `bin/kimi` broken.)*

---

## ═══ MNEMOS TRIAL — side-mission result (2026-07-15) ═══

> **⚠️ SUPERSEDED 2026-07-16 (#7) — kept for the trail.** Both gaps below were re-checked and the
> reading corrected: fatigue is LIVE (not degraded); compaction DOES fire here (via the no-`{trigger}`
> harness path). See the "Mnemos trial — RESOLVED this session" block at the top and `docs/observatory.md`
> → "Mnemos compaction vehicle" (07-16 update). The "NEXT SESSION" items below are done.

**This FOCUS-004 session was deliberately run long (side mission) to overfill context and test Mnemos's
compaction-recovery. RESULT: auto-compaction did NOT fire — a ~200k-token overfill produced zero
Mnemos-visible `compaction_fired` events dated this session.** Full finding + hypothesis + next-session
checks: **`docs/observatory.md` → "Mnemos compaction vehicle — does Claude Code auto-`/compact` even
happen in this harness?"**

- **Likely cause:** this harness manages context via its *own summarization* (system-prompt-stated), a
  different mechanism from Claude Code `/compact` — the only thing Mnemos's PreCompact hook instruments.
  So Mnemos may be watching a door this harness never opens. **Filling more won't help** — we already
  massively overfilled.
- **Second gap:** `fatigue.json` is all `None` — fatigue runs *degraded*, not dark. The statusline isn't
  writing token metrics, so the token-util dimension (0.40 weight) is blind; the behavioral dims still
  compute (a forced checkpoint scored **0.29**). Narrow fix: the statusline→`fatigue.json` token write.
- **What worked:** SessionStart restore (loaded at startup) + Stop-hook checkpoint (`941b43b7` today).
  Resume-across-*sessions* works; recovery-across-*compaction* stays untested (trigger never occurred).
- **NEXT SESSION — pick up:** (1) confirm whether this harness ever invokes `/compact`, or point Mnemos
  at the signal that *does* fire (or evaluate the recovery layer on a real Claude Code CLI session);
  (2) fix why `fatigue.json` isn't being written; (3) P3 consequence — if auto-compaction can't fire
  here structurally, the compaction-half of the Mnemos verdict needs a different venue.

---

## Housekeeping — deferred to next session (2026-07-15, context too full to do now)

> **⚠️ SUPERSEDED 2026-07-16 (#16).** P7 is **snoozed to 2026-08-31**, not labeled — the backlog is dead
> data and the real fix is the passive detector upgrade (spec 13). The note below is kept for the trail.

- **P7 gate-labels: ~45 unlabeled post-backstop gates.** `tessera-watch` flags it (≥20 threshold).
  Byproduct of a heavy-decision session (9 gates logged). The friction-journal review that tunes the
  #17 backstop precision — label each `should_fire` true/false (genuine gate vs noise). Distinct
  maintenance pass; nothing else depends on it. Resolve or snooze via the dashboard / observatory.

1. **The Tessera ↔ conclave design session.** *(ADR-0007, "NOT decided".)* The stack is a
   **directional keep** — more local models coming, Tailscale + AWS-hosted, **council/ensemble
   review is the path**. conclave is itself a multi-model stack. Shared council / isolated /
   one fronts the other = **ADR-weight, and deliberately not decided in a prune ADR.**
   *Now unblocked: the stack RUNS and FAILS HONESTLY, so this can be designed against a working
   mechanism instead of a phantom.*
2. **The `paths:`-match scan across all 20 repos.** The measurement that decides the **22
   deferred stack skills** (`flutter`, `supabase*`, `react-*`, `android-*`, …). They are dead
   *in Tessera* and **unmeasured elsewhere** — an invocation count is structurally blind to a
   `paths:` auto-load. **Cutting them without this scan is drift; challenge it.**
3. **Execute the 22 authorized cuts** — the Maggy corpses and stale/superseded skills. Safe,
   mechanical, evidence in the ledger.
4. **`bin/kimi` is broken** — it `exec`s `~/.local/bin/kimi`, which does not exist. Recorded,
   not fixed; it matters to item 1.
5. **`supabase-python` is misfiring** — its `**/*.py` glob matches 123 Python files here. It
   surfaced itself, live, during this very session when a `.py` file was written.

### What NOT to do

**Do not cut the multi-model stack.** It was condemned in the first draft of ADR-0007 and that was
wrong. It is kept on purpose. **Do not re-litigate it without the design session.**

---

## Handoff — pick up here (2026-07-12, end of the F-001 session)

**Full accounting: `docs/postmortem-2026-07-12.md`.** One document, the whole story — what
happened, the ten bugs, why each rule failed, the mechanism ranking, the numbers, and the
direction. Start there. The formal decision is `docs/adr/0006-instrumentation-not-control.md`;
the evidence base is `docs/observatory.md` → "Fail-open everywhere".

### What actually happened

A venv fix became a 90-minute rathole of fixes-on-fixes. Three rounds of "it's closed" were
each refuted by an **independent session** verifying from a clean context. Every refutation was
correct.

**The rathole was not about Python.** It was that *nothing in Tessera reports its own failure*,
so every fix required a fresh adversarial read to find the next silent thing. Eight bugs in one
session; **not one announced itself.** See the observatory table.

### The two that actually mattered

1. **THE SPEND GUARD WAS FAILING OPEN.** On a `/usr/bin`-first PATH, `python3` is macOS 3.9;
   PEP-604 annotations raise `TypeError` at definition time; `guard.py` exits 1; the wrapper
   passes that through as "not 2" — which Claude Code reads as **ALLOW**. *An unauthorized GPU
   boot proceeded.* This is **the** precondition for unsupervised spend, and it was broken.
   Fixed (`from __future__ import annotations`) + checked (`safety-scripts-run-on-system-python`,
   which **executes** on 3.9 — `ast.parse` passes, PEP-604 only explodes when *evaluated*).
2. **The spend backstop shipped DISABLED to every clone.** `.spend-backstop-fires` was committed
   holding **5** against a `MAX_FIRES` of **3**. It would never have fired, anywhere, ever.

**Both were caused by me, both were invisible to the framework, and both were found only because
Lorenzo asked for independent verification.**

### The rule that broke, and the one that replaced it

The worst bug was **built by a carve-out I wrote**: *"the gate/spend hooks may use bare `python3`
— they're stdlib-only and must survive a broken venv."* That sentence is the bug. **Stdlib-only
is NOT version-independent:** when the interpreter NAME drifts, the VERSION drifts with it.

> **New standing rule: a carve-out from a safety invariant must ship with a check that the
> carve-out holds.** And: **a mechanism that fails OPEN needs a paired detector that fails LOUD.**

### Where to pick up — in this order, in SEPARATE sessions

0. **READ `docs/adr/0006-instrumentation-not-control.md` FIRST.** It retargets the framework:
   *Tessera does not make the agent reliable — it makes the agent's unreliability visible and
   bounded.* It ranks the five mechanism tiers by their actual record under a full night of
   adversarial pressure, withdraws ADR-0005's readiness claim, and sanctions pruning. **Every
   item below is downstream of it.**

1. ~~**Adversarial verification — `_project_specs/12-adversarial-verification.md`. BUILD THIS
   FIRST, BEFORE SPEC 11.**~~ **SHIPPED 2026-07-13** — `bin/tessera-verify` + fail-LOUD Stop-hook
   trigger + `verification` event contract + doccheck `verify-scan-is-wired`. The hook fired
   unprompted on the session that built it (criterion 2, live); the falsifier confirmed 4/4
   claims with landmines walked; `--self-test` refuted its planted landmine (criterion 5).
   **Remaining: criterion 1 — Lorenzo's manual acceptance replay of the three 2026-07-12
   refutations, deliberately human-witnessed (ADR-0006: watch a channel fail before trusting
   it).** Spec's "Shipped" section has the full evidence.

2. **PRUNE — and FOCUS-004 *is* the prune. One item, not two.** *(ADR-0006 §5, sanctioned work.)*

   **Why this outranks spec 11, by ADR-0006's own ranking:** pruning is **tier 1** (make the bad
   state unrepresentable — *deleted machinery cannot fail silently*). Spec 11 is **tier 4**
   (detect the failure of machinery we chose to keep). **Prevention beats detection, and the ADR
   says so.** Practical consequence: spec 11 scopes five components — **if the prune kills one,
   you will have instrumented a corpse.** Prune first, and it tells spec 11 what is actually
   worth watching.

   - **FOCUS-004 — 56 skills, zero ever evaluated**, overdue by principle #15. Still the only
     honest path to a real `auto` compaction: **205,085 tokens measured** across the corpus vs a
     ~166k threshold (verified, not repeated). **The Mnemos trial counter is genuinely 0** — and
     P3 was silently counting an *unclassifiable* compaction as evidence until it was fixed on
     2026-07-12.
   - **The gate apparatus** — recorder + Stop-hook scanner + ratio + `should_fire` labeling is
     four moving parts to answer *"did Claude ask before deciding."* At least one too many.
   - **Mnemos itself.** The kill/keep trial has run for **months** and has **never produced a
     valid verdict**. Until 2026-07-12 its hooks wrote through a *drifting interpreter*, so any
     earlier verdict would have measured broken machinery. *"We cannot judge it"* is itself a
     finding, and the trial is long overdue.

   **Two disciplines, both learned the hard way:** (a) **audit, do not repair** — recording a
   broken skill is the job; fixing it is how tonight became a rathole. (b) **I must not certify
   the compaction restore myself** — that is the "verify with the instrument under test" failure,
   three times over. The verdict comes from the compaction log + P3, or from spec 12's adversary.

3. **Fail-open detection — `_project_specs/11-fail-open-detection.md`. SCOPE AND ORDERING ARE
   WRITTEN DOWN THERE. Read it before starting.** *And scope it to what SURVIVES the prune.*
   Five components (spend guard, spend backstop, gate-scan, Mnemos hooks, doccheck) — **not** the
   54 bail-out sites. Mechanism is ~35 lines (`tessera-degraded` + watcher P10); the substance is
   the chaos tests and the classification.
   **THE ORDERING IS THE POINT: write the break-it-on-purpose tests FIRST and watch them all
   fail.** The 2026-07-12 session built a detector and then verified the fix *with the detector
   that had the hole* — three times, reporting green each time. If a future session proposes
   building the mechanism first, **push back and point at spec 11.**
   **Bar for done (binary): break a component on purpose → Tessera says so within one session,
   with no human asking.** Nothing on 2026-07-12 would have met it.

4. **Ship the portable doccheck core downstream.** 7 of 13 checks are portable
   (`no-bare-python3-with-toolchain-import`, `safety-scripts-run-on-system-python`,
   `runtime-state-is-not-tracked`, `test-command-is-not-a-bare-interpreter`,
   `ignored-test-suites-are-run`, `spend-guard-is-wired`, `spend-backstop-is-wired`); 6 are
   Tessera-only. **`bin/tessera-new-project` mentions doccheck zero times**, so conclave, howler
   and tess-dashboard have the spend guard and the backstop but **not the checker that verifies
   either is wired**. That violates the "ship both halves or neither" rule written in
   `tessera-new-project`'s own comment. Bounded: ~one session.

5. ~~**Re-open ADR-0005's readiness claim.**~~ **DONE — ADR-0006 withdraws it.** Its Tier-1
   reordering stands; its *preconditions-met* framing is retracted. Two of three were broken and
   undetectable.

### Session findings 2026-07-13 (P7 labeling session)

- **P7 resolved:** 40 of 44 post-backstop gates labeled inline (`should_fire` +
  `should_fire_basis` + `labeled_ts`), 4 honestly null. Rubric: user's recorded disposition,
  verbatim quotes. Adversary sample-check: 2 CONFIRMED, 1 PARTIAL — caught a typo-corrected
  composite quote, fixed to verbatim, rule added to gate-event.md. Notable calibration hit:
  heaviside `voicing-defaults` was **held and should have fired** (user pushback followed).
- **BUG FIXED same session: `hooks/subagent-route-hook` broke ALL Agent tool calls** whenever
  a CLAUDE_* tier was cached and no explicit model set — `updatedInput` REPLACES tool input
  wholesale, and the hook emitted `{model}` alone, stripping `prompt`/`description`. Fixed by
  merging (`.tool_input + {model}`), guarded for null/empty/non-object `tool_input` and
  multi-document stdin — the null-input guard exists because the **first adversary run REFUTED
  the fix** (jq's `null + {model}` re-opened the bug through a side door). Verified: live spawn
  green, `tessera-verify` CONFIRMED merge + explicit-model-wins + fail-open across 14 degenerate
  shapes.

> **Ordering note, recorded because it drifted once already.** FOCUS-004 sat at #4, was argued up
> to "defensibly second", then **sank to last by accretion** when ADR-0006 added three items above
> it — with no decision and no announcement. Lorenzo caught it. It is now #2 **on principle, not
> position**: pruning is tier 1, spec 11 is tier 4, and ADR-0006 ranks prevention over detection.
> **If a future session finds FOCUS-004 drifting down the list again, that is drift, not a
> decision — challenge it.**

### What NOT to do next

**Do not keep fixing.** The rathole instinct was right. Everything is committed, pushed, green,
and the one live safety hole is closed. The next move is *design*, not repair.

---

## Handoff — 2026-07-12 (spec 06 / escalation backstop / venv, chronological)

**Spec 06 shipped — but not the spec that was written. It was retargeted first, and that was
the whole job.**

### The spec did not solve the problem it was promoted for

ADR-0005 promoted spec 06 to Tier 1 on one finding: *an unsupervised agent in conclave is an
agent that boots GPUs on its own.* But spec 06's mechanism, written in April under its old
Tier 3 framing, was a **Claude token meter** — declare `tokens`/`api_calls`, accumulate from
the transcript, hard-stop. **A token budget cannot stop `terraform apply enable_gpu=true`.** The
agent commits hundreds of dollars inside a few thousand tokens. All five of its success
criteria were token-denominated; none mentioned cloud spend. **Built as written, it would have
shipped green with the GPU boot path wide open.**

Worse — its Step 4 hard-stopped by *"rejecting further Edit/Write/Bash."* **Teardown is a Bash
command.** It would have frozen an agent with a live GPU and blocked its own teardown, *causing
the runaway it existed to prevent.* That produced the invariant the guard is now built around:
**a spend gate must never be able to block the exit.**

The token budget is real but minor, and it is a different mechanism. Split out to **spec 10**,
Tier 3, with an honest note that there is *no evidence it is worth building* (12 sessions, all
`clear`, max haze 0.09 — the agent does not flail).

### What shipped

- **`bin/tessera-authorize`** — a human grants a run-scoped envelope (`--usd 20 --ttl 4h`).
  **This is the piece that converts conclave from supervisable-only to unsupervised:** it
  collapses 14 synchronous boot gates into one up-front authorization.
- **`scripts/spend/guard.py`** + PreToolUse(Bash) hook — deny-by-default on spend-committing
  commands. **Teardown always allowed, unconditionally.** Denied → spec 07 escalation.
- **The TTL is enforced; the dollar figure is not.** Tessera cannot meter dollars; AWS can, and
  does. Tessera gates *authorization*, AWS meters *spend*. Three layers, three trust domains —
  don't collapse them.
- **We did not rebuild the ceiling.** conclave already had one (`budget.tf` → SNS →
  `hardstop.tf` lambda; `gpu.tf` idle-stop; tag chain verified end to end). It is *out-of-band*,
  outside the agent's trust domain, and strictly stronger than a hook. What it lacked was
  per-run *authorization* — a monthly cap bounds blast radius, it doesn't decide if the boot
  should happen.
- Wired into tessera + conclave + `templates/` + `bin/tessera-new-project`, each **verified by
  invoking it**, not by checking that files copied.

### Three things live-fire found that reasoning did not

Every one came from *running* the guard. None from reading the design.

1. **A live hole in the flagship downstream.** `conclave/scripts/sweep-gpu-capacity.sh:23` runs
   `terraform apply -auto-approve` — it boots g6e GPUs, it's the AZ-sweep from the gate log, and
   the guard saw only the wrapper's *name*. **A classifier that reads the command but not what
   the command runs is checking the wrong text.** Now reads local scripts one level down.
2. **The guard blocked its own wiring commit — and I misread the result.** The install command
   quoted a boot command in a test string, so the guard blocked the *whole* Bash call and
   **none of the wiring ran**. The probe that followed reported `allowed` for a GPU boot,
   because the wrapper fails open when the guard is absent. *It looked like a working guard
   saying yes. It was a missing guard saying nothing.* Caught only by checking disk.
3. **The guard blocked `cp guard.py test_guard.py`** — it followed the `.py` token, opened the
   *test file*, and found a boot command quoted in a fixture. **Naming a script is not invoking
   it.** Scripts are now followed only in *command position*. `git add`, `cat`, `vim`, `cp` on a
   script are no longer boots.

### The false-positive posture changed — v1's noise was buying less than it looked like

v1 classified raw text, so a *mention* read as an *invocation*. It produced **four false
positives against its own author in one session** (a test heredoc, the conclave install command,
the commit message describing the guard, the gate-log entry describing the false positive).

The defence of that noise was "stripping quotes opens `bash -c` as a bypass." **Checked rather
than trusted: the no-evasion property was already only partly true** — `echo "…" | bash` splits
to a bare, neutral `bash` segment either way. So quoted text and heredoc bodies are now data,
*unless the command is wrapper-led* (`bash -c`, `python3 -c`, `eval`, heredoc→shell), where they
are code. **Wrapper-ness is global, never per-segment** — `python3 -c "a; b"` splits on the `;`
inside its own quotes; judging that fragment alone reopens the bypass. That mistake was made and
caught by tests before shipping.

**Residual, deliberate:** `echo "…" | bash`, cloud-SDK calls, and script-calls-script are not
caught. This guard stops an agent booting a GPU *by mistake or without authorization*; it is not
built to defeat one actively evading it, which has easier routes. Layer 3 bounds those.

### A finding about the checker itself

`doccheck` gained **`ignored-test-suites-are-run`**, and it is a finding, not just a check. The
2026-07-11 *"test command ran 6 of 12 files and reported green"* bug was fixed **without leaving
a check behind** — which is the one thing doccheck's standing rule forbids. The rule was
violated by the commit that fixed the bug the rule exists for. Adding `scripts/spend/` to the
`--ignore` list nearly repeated it. Now: `--ignore` a suite without running it → doccheck fails.

Also added: `spend-guard-is-wired` (the doc claims a hook; is it in settings.json?) and
`spend-auth-is-not-tracked` (a committed grant would authorize spend on every clone, forever,
past its own TTL). **8 checks, 0 false claims.**

### The escalation backstop — spec 06 falsified the reason it was deferred

`docs/contracts/escalation.md` deferred the backstop on this premise: *"a blocked agent cannot
proceed, so the failure mode is not silence but a summary that isn't a packet."* **Spec 06 made
that false.** The guard denies **one tool call** — the agent can do other work, take an offline
path, or just move on, and the denial vanishes with it. The trigger was never really "the first
unsupervised run"; it was **the moment a block stops halting the agent**, and spec 06 was that
moment. I shipped a mechanism whose deny path ended in *prose* ("raise a packet"), i.e. model
recall — the exact trigger that missed ~85% of gates.

**BUILT.** Stop hook → `scripts/spend/backstop.py`. A denial must end in a grant (supervised) or
a packet (unsupervised); **neither → exit 2**. A grant *before* the denial doesn't count — an
expired envelope is what caused it. Better-conditioned than the gate-scan: `spend_denied` is a
*logged event*, not a text heuristic, so there is nothing to adjudicate away. The one quiet
disposition it invites is *"that was a guard false-positive"* — **a backstop that forces a bogus
packet is worse than none.**

### The suite was manufacturing the evidence

Found by reading the log the backstop was about to fire on: `guard.main()` → `_log_denial()` →
`emit()` keys on `CLAUDE_CODE_SESSION_ID`, **which is set under a real session** — so every hook
test wrote a *real* `spend_denied` to the production log. **26 of this session's 31 denials were
made by pytest.** An 84%-polluted friction journal, and a backstop poised to fire on its own
tests.

This is the P3 trigger-tagging lesson in a new costume: **a test must never become evidence about
the thing it tests.** There, a hand-run `/compact` could have delivered the Mnemos verdict on
manufactured data. Here, pytest was manufacturing the spend journal. Fixed at the root
(`scripts/spend/conftest.py` strips the session id suite-wide, so `emit()` is inert by
construction) and pinned by a test, so no future test can pollute by forgetting to mock.

**Today's log still contains that test noise — it was not rewritten.** Treat spend-denial counts
before 2026-07-12 as unusable; the journal is honest from here.

### The venv landed — F-001 is closed, and it bit me *during the fix*

Opened 2026-06-26. Resolved 2026-07-12 on a **uv-managed** interpreter (`.python-version`
tracked, base under `~/.local/share/uv/python/`, brew cannot touch it). Toolchain removed from
Homebrew's python entirely; console scripts symlinked into `~/.local/bin`, which **precedes**
`/opt/homebrew/bin` — `tessera/bin` does **not** (position ~17, behind brew), so a symlink there
would have been silently shadowed while everything *looked* fixed.

**My first recommendation was a brew-based venv, and it was wrong.** Reflex ("don't add a
dependency") applied without checking whether the cheap option met the *requirement*. It didn't:
the requirement is *never again suffer a silent interpreter break*, our hooks all **fail open**,
so a broken base degrades into **silence** — F-001 exactly. `uv` is a build-time tool with no
runtime coupling; the anti-dependency rule never applied to it. Corrected on Lorenzo's pushback.

**F-001 recurred live, inside the session fixing it.** `uv python install` shimmed the *name*
`python3.13` into `~/.local/bin`, ahead of Homebrew. A `pip uninstall` and its verification both
silently addressed **uv's** interpreter instead of brew's — **and reported success.**
`run-tests.sh`'s `python3.13` pin became a different interpreter with no pytest.

> **An interpreter is a path, not a name.** A name is a lookup through a mutable, ordered PATH
> that four package managers write to. There is no fallback to `python3` anywhere anymore — a
> silent fallback to a toolchain-less interpreter is *how F-001 stayed invisible for six weeks.*

**Two detector bugs found, both by testing the failure and not just the fix:**

1. **P9 could never have gone green.** Its predicate was *"bare `python3` can import mnemos"* —
   which post-venv is **false, and correctly so**. It would have fired forever, G-a would have
   escalated forever, and the only exit was snoozing our own detector. The pre-commit lesson
   inverted: **a detector that cannot go green teaches you to ignore the watcher.** Rewritten to
   assert the invariant F-001 actually violated: *the interpreter the consumer resolves must
   import what it imports*, and its base must not be a package manager's.
2. **P9 was silent on the worst case.** With `.venv` gone the symlink dangles, `which` returns
   None, and it said *"nothing to drift from"* — quiet while the toolchain was **entirely
   missing** and every hook was failing open. Absence is the loudest drift there is. Found by
   parking `.venv`; fixed; re-tested.

**And a shipped bug of my own, caught on the way past.** `.tessera/.spend-backstop-fires` — the
backstop's fire counter — **was committed, holding 5, against a `MAX_FIRES` of 3.** Every fresh
clone and downstream would have inherited a backstop **already past its cap: born disabled,
silently.** The guard would deny a GPU boot and nothing would ever catch the denial going
undispositioned. I gitignored `spend-auth.json` correctly one hour earlier and *the lesson did
not generalize to the sibling file on its own.* Now a rule, with a check:
`runtime-state-is-not-tracked`.

**The venv is the mechanism; the guardrail is a check.** A venv does not stop anyone typing
`python3` in a new script tomorrow. `doccheck`'s **`no-bare-python3-with-toolchain-import`**
fails if any hook invokes bare `python3` on code importing a venv-only module. The
stdlib/toolchain split was the de facto design for months and had **never once been enforced**.

**G-a still fires** — it intersects the last 3 logged runs and P9 genuinely did fire in all
three. It clears on its own as green runs accumulate. Deliberately *not* spamming `tessera-watch`
to force it quiet: that is gaming a detector, same species as a hand-run `/compact` contaminating
the Mnemos trial.

### Next

**All three preconditions to an unsupervised run are now met** (spec 06, the escalation backstop,
the venv). The blocker is gone.

1. **FOCUS-004 — the skill audit.** Now the front of the queue, and unchanged in shape: 56 skills,
   zero ever evaluated, and it is still **the only honest path to a real `auto` compaction** — the
   Mnemos trial's counter is *still 0* and its clock has never started. Must run in the **main
   thread**, its own session; the ~208k of reading has to land in the real context or the trial
   gets nothing.
2. **Gate-scan recall holes** — before any `should_fire` labeling pass. Two known: the
   question-shaped detector misses declarative gates, and it cannot see the gate in the turn that
   fires it (*last-block → last-turn*).
3. **Spec 03** — after calibration data.
4. ~~**Prune the inherited Maggy docs.**~~ **DONE 2026-07-12** — 18 files, 5,538 lines, during
   the pre-public provenance audit. It was *bigger than this item stated*: all **14** phase specs
   were Maggy's roadmap, not just the two with "maggy" in the filename, plus `benchmark-results.md`
   and `mwp.md`. Note how the item was scoped — from filenames, without opening the files. Reading
   them took a minute and doubled the set. **`commands/maggy.md`, `commands/maggy-init.md` and
   `bin/maggy-usage` also pruned** (2026-07-12) — the commands launched a dashboard absent from this
   repo, and `maggy-usage` read `~/.claude/routing-log.jsonl`, which only the *unwired*
   `route-task-hook` writes: it reported `$0.00` forever, by construction.
5. **The multi-provider harness is still shipped, and it is entangled — needs a decision (ADR-level).**
   `bin/{deepseek,kimi,qwen3,grok,gemini-api,gemini-cli}`, `hooks/route-task-hook`,
   `hooks/usage-summary-hook`, `commands/usage-summary.md`. **ADR-0003 §3 says Tessera does NOT own
   this** — "the full DeepSeek/Gemini/MiniMax/Kimi stack is maggy's reason to exist"; Tessera keeps
   only the Claude-tier sliver (`tier-classify-hook`/`subagent-route-hook`, both wired). But the
   wrappers are *consumed* by `bin/research`, `bin/review`, `bin/validate-plan` and by three live
   skills (`cross-agent-delegation`, `autonomous-testing`, `polyphony`). So this is not cleanup:
   deleting them decides whether Tessera keeps cross-agent delegation at all. **Do it with FOCUS-004,
   not before.** Note `install.sh` copies `bin/`, `hooks/` and `commands/` into `~/.claude/`, so
   whatever survives here is installed globally on every downstream machine.
2. **FOCUS-004 skill audit** — unblocked, and still the only honest path to a real `auto`
   compaction (the Mnemos trial's counter is still **0**). Deliberately not run concurrently
   with this session: the audit's 208k of reading must land in the *main thread* or the trial
   gets nothing.
3. **Gate-scan recall hole** — before any `should_fire` labeling pass. **Grew a second head on
   2026-07-12: the scan cannot see the gate in the turn that fires it** (the transcript it reads
   does not yet contain the turn in flight). Observed twice in one session. It is the last-block
   bug one level up — *last-block → last-turn* — and the miss is not random: it is always the
   *freshest* gate, i.e. the one most likely still unlogged. See observatory.
4. **Spec 03** — after calibration data.

**Standing caution, reinforced.** Every finding above came from *running the thing*, not from
reading it. The spec's flaw was visible in its own text for three months. The sweep-script hole
was live in conclave. Both surfaced within minutes of invocation. Under unsupervised runs
nobody is there to invoke and look — **build the instruments accordingly.**

---

## Handoff — 2026-07-11

Two sessions today. **25 commits across four repos, all pushed, all clean.**

### Session A — the autonomy inflection

- **Gate-scan backstop BUILT** — the last standing #17 violation is closed. Stop hook
  `.claude/scripts/tessera-gate-scan.sh` → `scripts/gate/scan.py` counts gate-shaped turns in
  the transcript, diffs against the session's gate log, exits 2 on a gap so the model must
  adjudicate before finishing. **The trigger is now the harness, not model recall.** The
  detector is a recall net (over-counts on purpose); the model is the precision filter; it
  cannot *forget*, which was the whole failure. Fires on gap ≥2 **or zero-logged**. Loop-safe,
  caps at 3 fires/session, fails open. Wired into all downstreams.
- **THE INFLECTION POINT — Tier 1 taken up.** Decided: the human-in-the-loop phase was the
  *on-ramp to autonomy, not the destination*. Claude's first read (decline Tier 1) was **wrong**
  — it inferred a terminal preference for supervision from the repo instead of asking. Lorenzo
  corrected it. Tier 1 reordered **07 → 03 → 01**.
- **Spec 07 v1 SHIPPED:** `bin/tessera-escalate` + `docs/contracts/escalation.md` + watcher
  **P6**. Escalation is the suggestion-gate's *asynchronous* form (#12 needs a disposer;
  unsupervised there is none).
- **ADR-0005 RECORDED**, and it carries the day's biggest finding — one that came from data,
  not reasoning: **50% of conclave's gates are `aws-launch` / `aws-teardown` / `aws-spend`.**
  An unsupervised agent in conclave is an agent that boots GPUs on its own. **The autonomy
  boundary in real work is spend and irreversible infrastructure, not design** — the exact
  opposite of what Claude predicted. Spec 06 promoted Tier 3 → **Tier 1**. A hard budget stop
  is now a *precondition* of any unsupervised run, not an optimization.

### Session B — the machinery started catching *Claude's* mistakes

- **COMPACTION FIRED FOR THE FIRST TIME EVER** (hand-run `/compact`). All four machinery
  checks passed. **Layer 2 delivered** — goal, constraints, and a fresh checkpoint landed in
  post-compaction context with no re-derivation. The trigger-tagging fix worked on its first
  live exercise: **P3 correctly read `0 real (1 manual test excluded)`.** A test did not become
  evidence. *Layer 3's injection remains unproven* (see backlog). **The trial's clock has NOT
  started** — a real `auto` compaction has still never happened.
- **`scripts/doccheck.py` + watcher P8 + a pre-commit gate.** Six doc-drift bugs had been found
  in three days — *every one* because Lorenzo got suspicious and asked "all docs updated?", and
  every one fixed without leaving a check behind. **The human was the detector.** Now
  mechanical: doccheck asserts the checkable claims docs make about the repo, `.githooks/pre-commit`
  **blocks** a lying commit, P8 surfaces red at session start. See `docs/contracts/doc-claims.md`.
- **`.tessera/config.yml` built — bottom-up, not as the profile-override layer the design doc
  imagined.** One key (`test:`), one live consumer (`bin/tessera-test`), zero speculative knobs.
  An agent must never have to *guess the test command*. Wired into all three downstreams, each
  command **verified by running it**, not inferred from the manifest.
- **`tessera-watch` P9 — interpreter-drift.** The F-001 detector we never had. Fires every
  session until the venv lands (see backlog). This is the "clean up the python fun" reminder,
  made mechanical — *a note is what gets dropped on the floor.*

### The thread that ties Session B together — read this before building anything

**Five separate bugs today, one root cause: we validated against the environment we were
standing in, not the one the code runs in.**

| Bug | It existed… | …but not where it mattered |
|---|---|---|
| **F-001** (historical) | `python3` on my PATH | not the one the *hook* resolved |
| **`.tessera/config.yml`** | on disk, in 4 repos | **gitignored** — untracked, would vanish on clone |
| **PATH export** | in `~/.zshrc` | **interactive-only** — invisible to the *agent's* shell |
| **pre-commit hook** | would have been in `.git/hooks/` | **not tracked** — no gate in any other clone |
| **`test:` command** | ran and reported "57 passed" | **6 of 12 files** — gate + override + mnemos silently skipped |

Three of these were **shipped by Claude today, inside the very machinery built to catch that
class**, and were caught by the tooling rather than by Lorenzo. That is the system working —
but the lesson generalizes and should be applied *before* the autonomy work, not after:

> **Existence is a local fact. Reachable-by-the-consumer is the shared one.** Before trusting
> any capability, invoke it the way the consumer will: `zsh -c` not `which`; `git ls-files`
> not `ls`; run the suite, don't count the files.

---

## State of the machinery (verified 2026-07-12, end of session)

```
toolchain       .venv/ — uv-managed python (NOT homebrew). `./install.sh` builds + verifies it,
                idempotently; rebuilt from scratch to prove the fresh-machine path.
                AN INTERPRETER IS A PATH, NOT A NAME. No fallback to `python3`, anywhere.
tessera-test    194 green   (80 top-level + 17 gate + 13 override + 84 spend + 3 mnemos)
doccheck        11 checks, 0 false claims  (+no-bare-python3-with-toolchain-import,
                                             +runtime-state-is-not-tracked)
spend guard     LIVE in tessera + conclave + templates + tessera-new-project
                live-fired in all four; a fresh scaffold blocks a boot and allows a teardown
spend backstop  LIVE — Stop hook; a denial must end in a grant or a packet, or exit 2
pre-commit      wired + live-fire verified (a lying commit was refused)
tessera-watch   P9 GREEN — F-001 CLOSED (was firing every session since 2026-07-11)
                G-a still firing: trailing indicator on P9's 3-run streak; clears itself
                P1/P3/P4/P5/P6/P7/P8 green
repos           tessera, conclave, howler, tess-dashboard
```

**P9 is the only thing firing, and it is meant to.** It nags every session until the venv
lands; G-a escalates it after 3 consecutive runs.

---

## Next session — priorities

Nothing is due *cold*; everything is signal-gated. **Run `tessera-watch` first.** In priority
order when you want to push forward:

1. **Spec 06 (cost/budget) — Tier 1, and it BLOCKS unsupervised downstream work.** This is the
   real next build. Conclave is the target: hard budget stop, spend ceiling, no GPU boot
   without one. **Not started.** The evidence is in ADR-0005 — half of conclave's gates are
   spend gates. Until this exists, "let the agent run unsupervised in conclave" means "let the
   agent boot GPUs unsupervised."

2. **The venv (P9 is firing).** Kills the dual-Homebrew Python split. **Hard trigger: before
   the first unsupervised run.** A silent interpreter break with no human watching *is* F-001 —
   and F-001 was invisible for weeks and confounded the entire Mnemos trial. Details in backlog.

3. **FOCUS-004 — the skill audit.** Now **unblocked** (both preconditions met). 56 skills,
   never once evaluated despite principle #15 saying they're a starting point. It is also the
   only realistic way to produce a **real `auto` compaction** (~208k tokens of reading, ~25%
   past the auto-compact threshold) — which is what the Mnemos trial actually needs. Two birds.

4. **Fix the gate-scan recall hole** *before* any `should_fire` labeling pass, or the labeling
   calibrates on a knowingly biased sample. See backlog.

5. **Spec 03** — only after calibration data exists. Its risk is P2-shaped.

**Standing caution for the autonomy push.** Across today, the findings that most changed
direction came from *Lorenzo pushing back*, not from the machinery: the Tier 1 premise, the
downstream doc audit, "actually do the config.yml", and "we should have a note to clean up the
python fun." Claude inferred instead of looking, repeatedly. **Under unsupervised runs that
check is absent by construction.** Build the instruments accordingly — that is the entire
argument for spec 06 and the escalation backstop.

---

## [FOCUS-004] Skill audit — and the session that finally tests compaction

**Status:** queued, unblocked
**Priority:** high — overdue by our own doctrine, and it is the compaction test vehicle

### Why this is two things at once

**1. It is overdue.** `CLAUDE.md` says the skill set is "a starting point per principle #15 —
trim or expand based on evidence in subsequent sessions." **56 skills. Zero have ever been
evaluated.** No evidence has ever been gathered. The doctrine was written and never executed.

**2. It is the only honest way to reach compaction.** Measured 2026-07-11:

| | tokens |
|---|---|
| all 56 `SKILL.md` files | **~208,000** |
| *context window* | *~200,000* |
| *auto-compaction fires at ~83%* | *~166,000* |

Reading the corpus to audit it overshoots the auto-compaction threshold by ~25% **with no
padding and no artifice** — the work is *genuinely* read-heavy. Expect **1–2 auto-compactions**,
which is exactly what the Mnemos trial needs (P3 requires ≥3 *non-manual* `compaction_fired`;
the counter is **0**).

**Do not pad a session to force compaction.** Pick work whose nature is token-heavy. A padded
session produces a restore judgment about work you were not really doing.

### Preconditions — both MET (2026-07-11)

1. ~~Manual `/compact` machinery check must pass first.~~ **PASSED** — see below.
2. Trigger-tagging **done** (`22f06b9`) — manual `/compact` cannot pollute P3. Verified live.

### What "done" looks like

- Every skill: keep / trim / cut, with a one-line evidence-based reason (used in a real
  session? covered by another skill? never once loaded?).
- Cuts recorded in `docs/design-principles.md` (the framework-evaluation section is where
  skill-set changes get their reasoning, per CLAUDE.md).
- **Secondary payload — the docs↔code consistency audit.** Partly mechanized now (`doccheck`),
  but doccheck covers only the ~60–70% that is machine-checkable. The prose 30% still needs
  eyes, and it bit twice today (design-principles said config.yml was "not built" 30 minutes
  after it was built). Same read-heavy shape; fold it in.

---

## Compaction test protocol — Step 1 RUN, PASSED (2026-07-11)

For 171 fatigue samples (max token_utilization **0.51**, `flow` in **171/171**) compaction had
**never fired, once**. Every band above 0.4 (COMPRESS / PRE-SLEEP / REM / EMERGENCY) was dead
code by observation.

**Step 1 — machinery. Done. All four checks green.**

| Check | Result |
|---|---|
| `compaction-log.jsonl` exists | ✅ first entry ever, `trigger: "manual"` |
| marker consumed, not orphaned | ✅ absent; `restore_injected` logged |
| restore block reached the model | ✅ **Layer 2** (`MNEMOS SESSION RESUME`) |
| P3 still reads `0 real` | ✅ `0 real (1 manual test(s) excluded)` |

The summarizer also honored the PreCompact preservation block. **The trigger-tagging fix worked
on its first live exercise: a test did not become evidence.**

**Caveat, recorded honestly.** Layer 3 (`mnemos-post-compact-inject.sh`) logged `restore_injected`
and consumed the marker, but its `CONTEXT RESTORED AFTER COMPACTION` text was never *observed*
arriving in context. Plumbing confirmed; injection unconfirmed. Moot while Layer 2 fires — but
**do not record Layer 3 as proven.**

**Step 2 — value. STILL OPEN.** `trigger: auto` has never happened. Only a genuine
auto-compaction answers what the trial asks: *did the restored checkpoint let work resume
without re-deriving?* That is FOCUS-004's job. **P3 remains at 0 real.**

---

## Backlog (triggered — do when the condition fires)

- **Kill the dual-Homebrew Python split — do the venv.** *Decided 2026-07-11 (1a/2b): venv is
  the right fix, deliberately deferred.* **`tessera-watch` P9 fires every session until this
  lands**, so it cannot be quietly dropped; G-a escalates after 3 consecutive runs.
  - **Measured, and it closes the obvious escape hatch:** `python@3.14` is
    `installed_on_request: **False**` — a brew **dependency** of awscli/httpie/mlx/mlx-c/**ollama**
    (the tier-classifier's engine). **Not removable**, and it owns the `python3` name with
    *nothing installed in it*. `python@3.13` is `installed_on_request: **True**`, nothing in brew
    depends on it, and it holds the **entire** toolchain. *The removable one is the one we use.*
  - **Why not just migrate to 3.14:** Homebrew re-points `python3` whenever a *dependent* formula
    moves. 3.14 arrived because ollama wanted it; 3.15 will do the same and orphan the toolchain
    again. **Migration resets the clock, it does not stop it.**
  - **Hard trigger: before the first unsupervised downstream run (ADR-0005).**
  - Scope: `install.sh` + the bin scaffold. Interim pin (`python3.13`, PATH-relative) works.

- **Namespace `scripts/gate/` and `scripts/override/` — the trigger already FIRED.** Both dirs
  contain an `emit.py` *and* a `scan.py`; with no packages, pytest binds `import emit` to
  whichever collected first and the other suite fails collection. The backlog said the trigger
  was *"next time anything needs a single green-suite command (CI, **a pre-commit gate**, ...)"* —
  **a pre-commit gate was built on 2026-07-11 and the trigger was not noticed.** Worse, the
  workaround (enumerating test files in `config.yml`) **silently ran 6 of 12 files while
  reporting green.** *Mitigated same day:* `scripts/run-tests.sh` runs each suite in a separate
  process (separate `sys.modules`, no collision) — all 87 tests now run. **Still open:** proper
  namespacing. *Deferred because* `python3 scripts/gate/emit.py` is the invocation documented in
  four repos' CLAUDE.md and in the gate-event contract; packagifying breaks that bare same-dir
  import contract. That is a real migration. *Trigger:* CI, or the next time the contract is
  being touched anyway.

- **Gate-scan detector is question-shaped — it misses *declarative* gates.** Found by the
  backstop's own first live fire. `_is_asking()` looks for a `?` in the last 300 chars, so the
  "here's what I'd do, proceeding unless you object" gate — the one used constantly — is
  **invisible**. **Consequence: the measured miss rates (howler 91%, conclave 61%) are FLOORS,
  not ceilings.** *Trigger:* fold in when P7 fires, **before** labeling. *Do not reach for NLP*:
  also treat a turn as asking when it ends on an explicit proposal marker, and accept that some
  recall is unreachable — a recall net with a **named** hole beats one with an unnamed one.

- **Label `should_fire` on the gate corpus. DEFERRED — and the deferral is watcher P7, not a
  note.** Fires at ≥20 unlabeled post-backstop gates. *Two things to get right when it fires:*
  **(a) the model must not label its own gates** — the contract needs a truth signal independent
  of the gate's own decision, and Claude filling in nulls with its own opinion is self-assessment
  wearing calibration's clothes; **(b) `should_fire` ≠ "could an agent self-dispose this"** — they
  come apart exactly where it matters (an `aws-launch` gate *should* have fired for a human, yet
  an agent with a hard budget stop could safely self-dispose a $2 boot inside budget). Add a
  distinct `can_self_dispose` label. See ADR-0005, `docs/contracts/gate-event.md`.

- **Prove Layer 3 (`mnemos-post-compact-inject.sh`) actually injects.** Its `restore_injected`
  line and marker consumption were confirmed 2026-07-11, but its text was never observed
  reaching the model — PreToolUse stdout may not surface. Moot while Layer 2 fires, but **Layer 3
  is the only net when a post-compaction turn has no SessionStart.** Cheap check first: does
  PreToolUse stdout reach the model at all?

- **Mnemos compaction-recovery verdict.** Fires at **≥3 non-manual `compaction_fired`**
  (currently **0 real**; one `manual` test, correctly excluded). Watcher **P3**. When it fires:
  did `restore_injected` follow each one, and did the restored checkpoint let work resume
  without re-deriving? An **empty log is not a signal** (untested ≠ useless), and a
  **`trigger: manual` entry is not a signal either** (a test of the layer, not evidence about
  it). Scope: compaction-recovery only, never session-continuity.

- **`design-principles.md` promises two files that were never built.** *(`.tessera/config.yml`
  was the third — it **graduated**: built 2026-07-11 with a live consumer. That is what a
  `PLANNED_PATHS` entry is *for*.)* Remaining, parked in doccheck's `PLANNED_PATHS` so the debt
  stays legible: `.tessera/third-party-scope.yml` (**build its consumer first** — the Data
  Handling review category does not exist; a data file with no reader is ceremony) and
  `.tessera/project.yml.template` (**deletion candidate**, not a build candidate — all repos are
  private, so the profile field leaks nothing).

- **The profile model has no consumer.** `profile: standard` is read by **nothing**; no
  `profiles/` dir exists; `healthcare` is named throughout design-principles and is zero bytes
  on disk. Same shape as the retired P2 — a mechanism whose value is *assumed*, never
  exercised. Observatory entry opened 2026-07-11 with an **event trigger**: *a second profile
  becoming real.* If one never arrives, that is the answer — a one-valued enum is a constant,
  and a constant does not need a model. **Do not let a verdict on the model condemn
  `.tessera/project.yml` as a marker file** — that demonstrably works and is how every tool
  discovers downstreams.

- **Content-aware hook drift, remaining gap.** Watcher **P1** now content-diffs
  `.claude/scripts/` ↔ `templates/`. **Not covered:** the third layer, `~/.claude/templates/`
  (out-of-repo), and making `templates/` generated rather than hand-copied. *Trigger:* next
  `install.sh` rework.

- **Cut CHANGELOGs when repos go public.** All four are expected to go public eventually. Only
  tessera has one — deliberately (premature until there is a public reader). When a repo goes
  public: `tessera-changelog --since <ref> --version <v> --date <d>` (commits are already
  Conventional). Keep the tool **single-source in `tessera/bin`, reached via PATH — do NOT copy
  it into each repo** (the F-003 drift trap).

---

## Parked for discussion (not started)

- **The 5-entry GSD observatory cluster** (byte-budget, `.planning` schema, domain probes, gate
  types, plan-drift). Tied to the Tier 1 discussion — resolve together, not piecemeal.

- **Roadmap Tiers 2–3.** Tier 1 is now taken up (ADR-0005), so the old "does Tier 1 earn its
  keep" question is settled. The successor question — how far past Tier 1 to go — is *not* open
  yet and should not be until spec 06 ships.

---

## Archive

### Handoff — 2026-07-10

**Observatory-watcher pilot built** — roadmap Tier 1 / spec-03 de-risking. `bin/tessera-watch`
evaluates the Observatory's silent+machine-checkable "When to revisit" triggers as predicates,
surfaced by a SessionStart hook. Substrate-only: predicate list + runner + append-only fire-log
+ `G-a` graduation predicate that reads the log, so "graduate to a stateful engine" is itself
channelized, not prose. On first run it caught **two real drifts** (a live hook missing from
`templates/`; a 167-line phantom `mnemos-compact-recovery.sh` contradicting its own doc).
FOCUS-003 closed; findings backlog cleared to 0.

**Do not re-litigate:**
- **Substrate-only.** No snooze/hysteresis/prose-parsing/umbrella until a graduation predicate
  fires on real fire-log evidence. Building any of them now is the exact over-build the pilot
  exists to prevent.
- **P2 (tess-umbrella) declined + RETIRED.** Verb count tracked no real friction — the
  `tessera-*` binaries are hook-invoked and callers name them directly, so an umbrella aliases
  without consolidating. Don't rebuild it. **P2 is now the canonical name for the failure mode
  "a predicate that fires correctly on a proxy tracking no real pain"** — it gets cited a lot.

### [FOCUS-001] Tier-classifier under-rating — **done (2026-07-08)**

Short decision/strategy prompts ("what's next?") matched no keyword and fell through to
HAIKU/SONNET — under-rating the most reasoning-heavy turns exactly when stakes were highest.
Fixed by prompt-engineering the classifier (judge *reasoning demanded*, not prompt length;
balanced few-shot). 5/6 empirical. Residual (context-blind lookup-shaped decisions) logged to
observatory as mitigation #1, still open.

### [FOCUS-002] Observatory sweep, 22 entries — **done (2026-07-08)**

Framework too young for a >6mo cull; nothing dead. **Promoted:** convention-surfacing drift →
**design principle #17**. Spawned FOCUS-003. Flagged the 5-entry GSD cluster (still parked, above).

### [FOCUS-003] Audit CLAUDE.md "surface X" against #17 — **done (2026-07-10)**

Six candidates, **one real violation**. The audit's own contribution: the instruction
*conflated* gate-**surfacing** (an accepted reasoning-convention, which #17 explicitly permits)
with gate-**recording** (the violation — a user-facing artifact riding pure model recall, ~85%
miss). Both files reworded so the convention half is no longer tarred with the violation half.
**The violation itself was then closed 2026-07-11 by the gate-scan backstop.**
