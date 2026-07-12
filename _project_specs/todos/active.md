# Active Focus

Declared current priority for Tessera framework dev. One focus at a time.

---

## Handoff — pick up here (last updated 2026-07-11)

**2026-07-11: gate-scan backstop BUILT — the last standing #17 violation is closed.**
The 07-10 session reproduced the under-logging (≥8 gate-shaped decisions, 3 logged),
hitting the n≥2 trigger the observatory had set. Built: Stop hook
`.claude/scripts/tessera-gate-scan.sh` → `scripts/gate/scan.py` — counts gate-shaped
turns in the transcript, diffs against the session's gate log, exits 2 on a gap so the
model must adjudicate before finishing. **Trigger is now the harness, not model recall.**
Detector is a recall net (over-counts by design); the model is the precision filter; it
cannot *forget*, which was the whole failure. Fires on gap ≥2 **or zero-logged** (the
zero-logged session leaves no file and was invisible to `ratio.py` — the case the
backstop exists to see). Loop-safe: honors `stop_hook_active`, caps at 3 fires/session,
fails open. 17 tests. Synced to `templates/` + both settings templates + the
`tessera-new-project` scaffold (a downstream getting `emit.py` without the scan gets the
broken half). Also fixed `ratio.py`'s untyped glob counting `watch.jsonl` as a phantom
session. **New watch #4 (observatory): does the logged-gate rate actually move after
2026-07-11? If not, the hook is ceremony — cut it, don't tune it.**

**2026-07-11 (same session): Tier 1 taken up. THE INFLECTION POINT.** Discussed and
decided — the human-in-the-loop phase was the *on-ramp to autonomy, not the destination*.
The gates/haze/fire-log are the instruments you build before you can trust an agent to run
unsupervised. Claude's first read (decline Tier 1) was **wrong** — it inferred a terminal
preference for supervision from the repo instead of asking; Lorenzo corrected it. Tier 1
**reordered 07 → 03 → 01** on evidence (rationale recorded in
`00-autonomous-engineering-roadmap.md`, not in a commit message).

**Spec 07 v1 SHIPPED:** `bin/tessera-escalate` (raise/list/resolve) +
`docs/contracts/escalation.md` + watcher predicate **P6**. Escalation = the gate's
*asynchronous* form (#12 needs a disposer; unsupervised there is none). Packets are
committed JSON under `.tessera/escalations/`. `--tried` required. Surfacing rides the
watcher, not a 4th SessionStart hook. Cut (with triggers, see the spec): 4 delivery
adapters, 4 of 5 auto-triggers (they depend on unbuilt specs 02/03/04/06), dedup, iCPG
nodes, graded severity routing. 9 tests. E2E verified: raise → P6 fires → resolve → clears.

**ADR-0005 RECORDED** — the inflection point, Tier 1 reorder, and **spec 06 (spend)
promoted Tier 3 → Tier 1**. That promotion is the day's biggest finding and came from the
data, not from reasoning: **50% of conclave's gates are `aws-launch`/`aws-teardown`/
`aws-spend`.** An unsupervised agent in conclave is an agent that boots GPUs on its own. The
autonomy boundary in real work is **spend and irreversible infrastructure, not design** — the
exact opposite of what Claude predicted. A hard budget stop is now a *precondition* of any
unsupervised downstream run, not an optimization.

**Escalation channel wired everywhere (end of day).** It had shipped tessera-only — which was
backwards, since 3 of the 4 organic escalations came from conclave. Fixed: `tessera/bin` is on
PATH (`~/.zshrc`), `install.sh` now *fails loudly* if it isn't (a channel the docs promise but
that cannot be invoked is worse than none), bridge copy at `scripts/tessera-escalate` in each
downstream for no-PATH machines, CLAUDE.md + scaffold + template all wired.

**The backstop fired on its own build session and was right.** 5 gate-shaped turns detected,
3 logged, zero false positives; the 3 missing were real (incl. the "what is Tessera for"
decision). Session went 3 → 6 gates. **First data point for observatory watch #4: the rate
moved.** It also named its own recall hole (see backlog: question-shaped detector misses
declarative gates → the 91%/61% miss rates are **floors, not ceilings**).

---

## [FOCUS-004] Skill audit — and the session that finally tests compaction

**Status:** queued (prepped 2026-07-11, not started)
**Priority:** high — overdue by our own doctrine, and it is the compaction test vehicle
**Estimate:** L (it is *meant* to be large — that is the point)

### Why this is two things at once

**1. It is overdue.** `CLAUDE.md` says the skill set is "a starting point per principle #15 —
trim or expand based on evidence in subsequent sessions." That never happened. We are at **56
skills**; watcher **P5** fires at 60. Nobody has ever evaluated whether they earn their slots.
Candidates for the chop on sight: `posthog-analytics`, `supabase-python`, `web-content`,
`user-journeys`, `build-in-public` — none of which have been touched in any dogfood session.

**2. It is the only honest way to reach compaction.** Measured 2026-07-11:

| Corpus | ~Tokens |
|---|---|
| **All 56 `SKILL.md` files** | **~208,000** |
| design-principles + observatory + ADRs + specs + contracts | ~82,000 |
| *Context window (Opus)* | *~200,000* |
| *Auto-compaction fires at ~83%* | *~166,000* |
| *Longest session ever recorded (token_util 0.51)* | *~102,000* |

**The skills alone exceed the entire context window.** Reading them blows through the
compaction threshold by ~25% with no padding and no artifice — the work is *genuinely*
read-heavy. Expect **1–2 auto-compactions**, which is exactly what the Mnemos trial needs
(P3 requires ≥3 *real* compaction_fired events; the counter is currently **0**).

**Do not pad a session to force compaction.** Pick work whose nature is token-heavy. This is
that work, and it is cheap to lose: reading and doc edits, no builds, no spend, nothing
irreversible. If the restore layer fails mid-audit, the cost is re-reading.

### Preconditions (do these first, in order)

1. **Manual `/compact` machinery check must pass first** (see below). The three-layer restore
   has **never executed**. Discovering it is broken 160k tokens into an audit is the expensive
   way to learn it. Last time we assumed Mnemos plumbing worked, it was broken three separate
   ways, silently — see observatory "Mnemos kill/keep test was confounded."
2. Trigger-tagging is **done** (`22f06b9`) — manual `/compact` is now safe and will not
   pollute P3.

### What "done" looks like

- Every skill: keep / trim / cut, with a one-line evidence-based reason (used in a real
  session? covered by another skill? never once loaded?).
- Cuts recorded in `docs/design-principles.md` (the framework-evaluation section is where
  skill-set changes get their reasoning, per CLAUDE.md).
- **Secondary payload — the docs↔code consistency audit.** On 2026-07-11 two docs were found
  silently lying (the ADR index omitted 0005; `gate-event.md` still claimed the recorder rode
  model recall) — and both were found *by luck*, when Lorenzo asked "all docs updated?" Nobody
  has ever checked the rest. Fold it in; it is the same read-heavy shape.

---

## Compaction test protocol (run at the START of the next session)

The compaction-recovery layer is Mnemos' largest untested surface: **`.mnemos/compaction-log.jsonl`
does not exist — compaction has never fired, once.** 171 fatigue samples, max token_utilization
**0.51**, state=`flow` in **171/171**. Every band above 0.4 (COMPRESS / PRE-SLEEP / REM /
EMERGENCY) and every action it gates is dead code by observation.

**Step 1 — machinery (cheap, ~30 seconds).** Type `/compact` by hand. Then verify:

```bash
cat .mnemos/compaction-log.jsonl          # expect: trigger "manual" (excluded from P3 ✓)
ls .mnemos/just-compacted                 # marker: written by PreCompact, consumed by restore
python3 -c "import json;print(json.load(open('.mnemos/checkpoint-latest.json'))['id'])"
tessera-watch                             # P3 must still read 0 real — a test is not evidence
```
Pass = a `CONTEXT RESTORED AFTER COMPACTION` block appears, the marker is consumed, and P3
still reads **0 real**. Fail = fix the restore layer *before* spending a long session on it.

**Step 2 — value (needs the real thing).** Only a genuine auto-compaction answers the question
the trial actually asks: *did the restored checkpoint let work resume without re-deriving?*
That is what FOCUS-004 above is for. It cannot be faked — a padded session produces a restore
judgment about work you were not really doing.

---

## Next session — pick up here

**Nothing is due cold.** Every open item is signal-gated; the watcher is green. Check
`tessera-watch` first — it now carries **P6** (open escalations) and **P7** (unlabeled
post-backstop gates ≥20 → time to label `should_fire`).

In rough priority when a signal fires or you want to push forward:

1. **Spec 06 (cost/budget) — now Tier 1, and it blocks unsupervised downstream work.** This
   is the real next build. Conclave is the target: hard budget stop, spend ceiling, no
   GPU boot without one. Not started.
2. **Fix the gate-scan recall hole** (declarative gates invisible) — fold in *before* any
   `should_fire` labeling pass, or the labeling calibrates on a known-biased sample.
3. **Spec 03** — only after calibration data exists. Its risk is P2-shaped.
4. **Escalation Stop-hook backstop** — trigger is the *first real unsupervised run*
   (a session that ends blocked without raising a packet is the failure to catch). The
   escalation producer is still model-invoked, which is the same #17 exposure the gate
   recorder had this morning. Known, stated, deferred on purpose.

**Standing caution for the autonomy push:** two of today's three real findings came from
Lorenzo pushing back, not from the machinery — the Tier 1 premise (supervision was the
on-ramp, not the destination) and the doc audit that found the escalation channel missing
downstream. Claude inferred instead of looking, twice. Under unsupervised runs that check is
absent by construction. Build accordingly.

---

## Backlog (triggered — do when the condition fires)

- **Gate-scan detector is question-shaped — it misses *declarative* gates.** Found
  2026-07-11 by the backstop's own first live fire: it flagged 5 turns, but a gate that WAS
  logged (the spec-07 scope cut — "here are the cuts… Building.") was never detected,
  because that turn ends in a statement, not a `?`. `_is_asking()` looks for a question mark
  in the last 300 chars. The "here's what I'd do, proceeding unless you object" gate — the
  ponytail-shaped one, used constantly — is **invisible** to it. **Consequence: the measured
  miss rates (howler 91%, conclave 61%) are FLOORS, not ceilings.** *Trigger:* fold the fix
  in when P7 fires (before labeling — a labeling pass on a corpus with a known recall hole
  calibrates on the wrong sample). *Do not* reach for NLP: the cheap move is to also treat a
  turn as asking when it ends on an explicit proposal marker, and to accept that some recall
  is unreachable — the model is still the precision filter, and a recall net with a named
  hole beats one with an unnamed one.

- **First live fire, 2026-07-11 — the backstop moved the rate.** Gates logged this session
  went 3 → 6 after the hook fired (5 detected, 3 logged, all 3 missing ones real, zero false
  positives). First data point for observatory **watch #4** ("does the logged-gate rate
  actually move? if not, the hook is ceremony — cut it, don't tune it"). It moved. n=1.

- **Label `should_fire` on the gate corpus. DEFERRED 2026-07-11 — and the deferral is a
  predicate, not this bullet.** `bin/tessera-watch` **P7** counts unlabeled gate events
  recorded *after* the backstop went live (across tessera + all downstreams) and fires at
  ≥20. When it fires, the corpus is both honest and big enough to be worth labeling.
  *Why deferred:* (1) the pre-backstop corpus is **61–91% truncated** (howler logged 4 of
  43 gate-shaped turns, conclave 22 of 57), so labeling it calibrates on a biased sample;
  (2) v1 escalation fires on **hard blocks only**, which need no threshold, so nothing is
  blocked on it. *Two things to get right when it fires:* **(a) the model must not label its
  own gates** — the contract requires a truth signal *independent of the gate's own
  decision*, and Claude filling in 29 nulls with its own opinion is self-assessment wearing
  calibration's clothes; **(b) `should_fire` ≠ "could an agent self-dispose this"** — they
  come apart exactly where it matters (an `aws-launch` gate *should* have fired for a human,
  yet an agent with a hard budget stop could safely self-dispose a $2 boot inside budget).
  Overloading one column with both meanings corrupts a contract four repos already write to.
  Add a distinct `can_self_dispose` label instead. See ADR-0005, `docs/contracts/gate-event.md`.

- **`pytest scripts/` cannot run as a whole suite — two modules both named `emit`.**
  `scripts/gate/emit.py` and `scripts/override/emit.py` collide in `sys.modules` (no
  packages, rootdir sys.path insertion), so whichever imports first wins and
  `scripts/override/test_override.py` fails collection with
  `ImportError: cannot import name 'Override' from 'emit'`. **Pre-existing** (reproduces two
  commits back), invisible because everyone runs per-suite; every suite is green alone (gate
  17, watch 11, escalate 9, override 13). F-003-shaped: two things, one name, no namespace.
  **Trigger:** next time anything needs a single green-suite command (CI, a pre-commit gate,
  or a downstream copying this test layout). Fix = namespace them, not `--import-mode`
  (tried; it makes it worse).

---

## Handoff — prior (2026-07-10)

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
