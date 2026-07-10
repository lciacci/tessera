# Pattern Observatory

A living inventory of concepts we have encountered but not yet decided on (or explicitly chosen not to pursue right now). Lighter-weight than an ADR. Junk drawer with structure.

## Purpose

The Observatory complements the ADR system:

- **ADR** = "We made a decision." Final until superseded.
- **Observatory entry** = "We noticed this." No commitment, recoverable trail.

Without the Observatory, the failure mode is: months from now you remember a pattern vaguely, can't find where you encountered it, and either rediscover it or skip it. The Observatory is the index of "things on our radar."

## Entry status values

- **Investigating** — we noticed it, want to think about it more
- **Pending eval** — we plan to run an ADR on this
- **Adopted** — link to the ADR that closed this
- **Rejected** — link to the ADR that closed this with reasoning
- **Watching** — explicitly deferred; condition named for re-opening

## Maintenance

When working on something and remembering a pattern, check the Observatory first. If a relevant entry exists, follow the source link back. If something earns its keep through real evidence, promote it to an ADR.

When an Observatory entry is closed (via ADR or explicit rejection), update its status with a link to the resolution. Do not delete — keep the trail.

---

## Entries

### Two-stage hierarchical skill routing (namespace meta-skills)

- **Source:** Open GSD — `gsd-core` v1.40, [#2792](https://github.com/open-gsd/gsd-core/issues/2792)
- **What it is:** Six namespace meta-skills (`gsd-workflow`, `gsd-project`, `gsd-quality`, `gsd-context`, `gsd-manage`, `gsd-ideate`) layered above ~61 concrete sub-skills. On runtimes with non-recursive skill loaders, the installer emits only the 6 namespace router bundles as top-level skills, nesting the concrete skills under each router. The model selects a namespace router, which routes to a concrete skill via embedded routing tables.
- **Why it caught our attention:** Cuts eager skill-listing token cost ~94% (from ~67 entries to ~6). Real engineering for token efficiency.
- **Status:** Watching
- **When to revisit:** If Tessera ever crosses 60+ skills and eager listing cost becomes meaningful. Currently at ~50 skills.
- **Resolution:** Skipped in ADR-0001 because premature at our skill count.

### Cross-runtime translation layer

- **Source:** Open GSD — bin/install.js architecture; 16+ runtime adapters
- **What it is:** Single source-of-truth (workflows/agents/commands written in Claude Code's native format), installer translates at install time per target runtime (Claude Code, OpenCode, Codex, Gemini CLI, Kimi CLI, Cursor, Windsurf, etc.). Each runtime has its own tool names, hook events, file conventions; translation handles all of it.
- **Why it caught our attention:** Real value when the user wants to try multiple agents. Substantial engineering — they support 16+ runtimes.
- **Status:** Watching
- **When to revisit:** If Lorenzo wants to use Codex, Gemini CLI, OpenCode, or another non-Claude-Code agent for real work.
- **Resolution:** Deferred in ADR-0001 per principle #15 (design-aware, don't build until needed).

### Wave execution with parallel-commit safety

- **Source:** Open GSD — `bin/lib/state.cjs` (STATE.md file locking with `O_EXCL`), executor agents with `--no-verify` parallel commits
- **What it is:** When multiple executors run within the same wave, parallel commit safety is handled by two mechanisms: (1) `--no-verify` on commits to skip pre-commit hooks (prevents build lock contention like cargo lock fights in Rust), (2) lockfile-based mutual exclusion on STATE.md writes (`STATE.md.lock` with `O_EXCL` atomic creation, 10s stale lock timeout, spin-wait with jitter).
- **Why it caught our attention:** Solves the read-modify-write race condition for parallel executors. We will need this when we build the orchestrator capability.
- **Status:** Watching
- **When to revisit:** When implementing the orchestrator capability (per ADR-0001's staged implementation plan). Look at GSD's exact mechanism then.
- **Resolution:** Skipped in ADR-0001 for now (no parallel executors yet); flagged for revisit during orchestrator capability implementation.

### Thinking-models-specific prompt patterns

- **Source:** Open GSD — `gsd-core/references/thinking-models-{debug,execution,planning,research,verification}.md`
- **What it is:** Separate prompt patterns for thinking-class models (o3, o4-mini, Gemini 2.5 Pro) across each workflow stage. Recognizes that reasoning models behave differently from non-reasoning models and benefit from different prompt structures.
- **Why it caught our attention:** We don't differentiate prompts by reasoning-model tier. If we ever route specific work to o3 or similar, having pattern templates for that mode would be valuable.
- **Status:** Watching → precondition met
- **When to revisit:** ~~When Tessera supports specific routing to reasoning models~~ — **this trigger fired.** As of **ADR-0002** (2026-06-26) Tessera routes by Claude effort tier (`CLAUDE_HAIKU/SONNET/OPUS`, later extended with `CLAUDE_FABLE`) at subagent/workflow dispatch. The routing precondition is now satisfied; the open part of *this* item — per-tier prompt-pattern templates (different prompt structures for opus-class vs haiku-class work) — is now **actionable but unbuilt**. Revisit if tier misrouting or tier-blind prompting proves to cost quality.
- **Resolution:** Routing built (ADR-0002); prompt-pattern templates deferred — current routing changes the *model*, not yet the *prompt structure* per tier.

### Capability registry / plugin system

- **Source:** Open GSD — `bin/lib/capability-registry.cjs`, `bin/lib/capability-loader.cjs`, ADR-1244 (theirs)
- **What it is:** Generated central registry of capabilities, with runtime overlay loading from `$GSD_HOME/.gsd/capabilities/` (global) and `<projectRoot>/.gsd/capabilities/` (project). Validated overlay system with first-party precedence, engines.gsd version gating, and per-capability command routing via command family modules. Their extension model.
- **Why it caught our attention:** More developed than our skills system. Allows third-party capability extensions with consent gates and confinement (path validation, realpath containment).
- **Status:** Watching
- **When to revisit:** If Tessera ever needs third-party extension support (currently solo use; not in scope). Or if our profile compositional mechanism proves insufficient and we need a more general extension system.
- **Resolution:** Skipped in ADR-0001 because different design philosophy (Tessera uses compositional profiles; GSD uses extensible capabilities).

> **Cluster note (2026-07-08 sweep):** the next five entries — byte-budget numbers,
> `.planning/` schema, domain probes, gate types, plan-drift guard — are all gated on
> an **unbuilt planning/orchestration layer** Tessera has not committed to. That's the
> same premise as roadmap **Tier 1** (`_project_specs/00-autonomous-engineering-roadmap.md`,
> parked for discussion in `_project_specs/todos/active.md`). They resolve *together* with
> that decision; don't action them independently before Tier 1 is decided.

### Byte-budget enforcement tier numbers (XL/LARGE/DEFAULT: 90000/54000/38000)

- **Source:** Open GSD — `gsd-core/workflows/*.md` size budget enforced by `tests/workflow-size-budget.test.cjs`
- **What it is:** Per-file byte limits enforced via test. Three tiers: XL (90k bytes, top-level orchestrators), LARGE (54k bytes, multi-step planners), DEFAULT (38k bytes, focused workflows). Ceilings track current high-water mark within a grace band (tighten-only ratchet). Specific reference: Codex truncates instruction docs past 32,768 bytes (`project_doc_max_bytes`).
- **Why it caught our attention:** The *concept* (size as proxy for attention budget) is adopted via ADR-0001. The specific tier numbers are their tuning, not ours.
- **Status:** Investigating
- **When to revisit:** When implementing byte-budget enforcement for Tessera. Use their numbers as a starting point but verify against our actual workflow sizes and target runtimes (Claude Code's specific token limits, no Codex-specific concern unless we add Codex support).
- **Resolution:** Concept adopted (ADR-0001); specific tier numbers deferred.

### `.planning/` exact schema (CONTEXT.md, PLAN.md, STATE.md, etc.)

- **Source:** Open GSD — `docs/ARCHITECTURE.md` File System Layout section, `gsd-core/templates/`
- **What it is:** Specific schema for project state artifacts: `PROJECT.md` (vision/constraints), `REQUIREMENTS.md` (scoped requirements with v1/v2/out-of-scope), `ROADMAP.md` (phase breakdown), `STATE.md` (living memory), `CONTEXT.md` (per-phase user preferences from Discuss), `RESEARCH.md` (per-phase ecosystem research), `PLAN.md` (per-plan execution), `SUMMARY.md` (per-plan outcomes), `VERIFICATION.md` (post-execution).
- **Why it caught our attention:** We're adopting the *concept* of file-based decision-and-output artifacts (ADR-0001). The specific schema is their design; ours will be Tessera-idiomatic, not direct port. But theirs is a reference point.
- **Status:** Investigating
- **When to revisit:** When designing Tessera's file-based decision artifact schema. Their CONTEXT.md/PLAN.md/STATE.md split has lessons; do not copy wholesale.

### Domain probes for discuss-phase

- **Source:** Open GSD — `gsd-core/references/domain-probes.md`
- **What it is:** Domain-specific probing questions for the discuss-phase. Different question patterns for different domain types (e.g., greenfield vs brownfield, frontend vs backend vs data).
- **Why it caught our attention:** Tessera doesn't have domain-specific question patterns at any phase. If we add a discuss-phase equivalent (currently we use the suggestion-gate and pipeline pattern), domain-aware questioning would be useful.
- **Status:** Investigating
- **When to revisit:** If we add a discuss-phase or equivalent structured-question step to Tessera. Not a current priority.

### Gate types (Confirm / Quality / Safety / Transition)

- **Source:** Open GSD — `gsd-core/references/gates.md`
- **What it is:** Four canonical gate types wired into plan-checker and verifier agents. Confirm gates (user approval), Quality gates (artifact correctness), Safety gates (e.g., supply-chain checks), Transition gates (phase boundaries).
- **Why it caught our attention:** Tessera has a single "suggestion-gate" concept (#12). GSD's four-type taxonomy might be too rigid for our purposes, or it might be a useful distinction we lack. Worth understanding before deciding.
- **Status:** Investigating
- **When to revisit:** When we encounter a real situation where our single gate concept feels insufficient. Possibly during dogfood.

### Plan drift guard (symbol verification)

- **Source:** Open GSD — ADR-22 (theirs), plan_review.source_grounding
- **What it is:** Verifies symbol references in generated plans against live source before execution. Catches hallucinated function names, type names, etc. at planning time rather than execution time.
- **Why it caught our attention:** Concept adopted via ADR-0001 as part of our pipeline pattern. Implementation deferred — need to decide on mechanism (AST parsing, grep-based, semantic search via embeddings).
- **Status:** Pending eval (concept adopted; implementation design open)
- **When to revisit:** When implementing the pipeline pattern's plan-validation step in real code. Probably during decibel meter dogfood or shortly after.

### Adaptive context enrichment (1M-token models)

- **Source:** Open GSD — `docs/ARCHITECTURE.md` Adaptive Context Enrichment section
- **What it is:** When the context window is 500K+ tokens (1M-class models), subagent prompts are automatically enriched with additional context (prior wave SUMMARY.md files, full phase CONTEXT.md/RESEARCH.md). For standard 200K windows, prompts use truncated versions.
- **Why it caught our attention:** Smart use of larger context windows when available. Currently not relevant because we have one main model (Claude); becomes relevant if we route specific work to 1M-token models.
- **Status:** Watching
- **When to revisit:** If we start routing to 1M-context models for specific work (Gemini 2.5 Pro, future Claude variants).

### Tessera hook activation in project-local config

- **Source:** Tessera Phase 4 install and dogfood prep, June 22 2026
- **What it was:** In the first dogfood session, Tessera's project-local `.claude/settings.json` hooks (PreCompact, PreToolUse, PostToolUse, Stop, SessionStart) appeared to silently skip. The Mnemos statusline didn't render and `.mnemos/` was never created.
- **Investigation arc:** Considered GSD interference (uninstalled — not the cause), workspace trust (researched as likely cause — not it either), plugin precedence (caveman + ponytail are intentional per design doc — not it), session-process retention. None were the actual issue.
- **Actual root cause:** A shell alias in `~/.zshrc` line 7 — `alias claude='cd /Users/lciacci/Claude; command claude'` — forced every `claude` invocation to first `cd` to the parent directory before launching. Claude Code's `cwd` was therefore always `/Users/lciacci/Claude`, never `/Users/lciacci/Claude/tessera`, so project-local `.claude/settings.json` from tessera/ was never loaded. The "Setting sources" line in `/status` showed only "User settings, Project local settings" rather than "Shared project settings" — diagnostic available all along, missed until late in the investigation.
- **Secondary finding:** Mnemos hooks fire and degrade gracefully when the Mnemos Python package isn't installed. Hook scripts create `.mnemos/` (always written by `mnemos-statusline.sh`) but `mnemos status`, checkpoints, and event logging require the `mnemos` CLI on PATH. Installation: `/opt/homebrew/bin/pip3.13 install --break-system-packages /tmp/mnemos-install` after restructuring the source layout to put modules under a `mnemos/` subdirectory.
- **Status:** Resolved
- **Lessons for the framework:**
  - Diagnostic discipline: when the same behavior persists across what should be different invocations, check the shell first. `type claude && which claude && alias | grep claude` would have surfaced the issue in 30 seconds.
  - The `/status` command in Claude Code shows the actual loaded Setting sources — run it early when project-local config isn't behaving as expected.
  - Framework structure can verify correct (CLAUDE.md, skills, design doc) while runtime behavior fails due to launch-environment issues. Test both layers explicitly.
  - The Mnemos source layout in maggy-main needs a fix: modules are at the package root, not under a `mnemos/` subdirectory. Setuptools flat-layout discovery rejects this. A small PR or a Tessera-side fork could address it.

### Suggestion-gate (#12) is a convention, not machinery

- **Source:** Tessera dogfood session, June 23 2026 — gate-event contract + correction_match work.
- **What it is:** Principle #12 (suggestion-gate: Claude proposes, user disposes) shaped the entire session — every "here's what I'd do, OK to proceed?" before a structural change, every numbered decision point. But it fired as a *behavioral convention* I followed from CLAUDE.md, **not** as machinery. No `suggestion_gate` hook ran; no event was emitted to `.tessera/logs/`; nothing gated anything. The dashboard's gate-calibration panel runs on a fixture precisely because the producer does not exist.
- **What machinery DID run:** Mnemos, passively — 56 tool signals logged, 4 Stop checkpoints, haze ingest, fatigue tracking. So "are we dogfooding Tessera?" splits: Mnemos layer = real machinery; suggestion-gate = convention only; caveman/ponytail = unrelated global plugins.
- **Why it caught our attention:** The gap is invisible until named. Convention-followed-perfectly *looks* like a working gate, so the missing producer never announces itself. We recommended building the gate-event producer next for unrelated reasons (unblocks 2 dashboard rows, validates the new canonical contract) — this is the same gap from the framework side: #12 has no emitter, so it can't be measured, calibrated, or audited. The canonical contract (`docs/contracts/gate-event.md`) is the consumer-facing half; the producer is the missing half.
- **Update, June 23 2026 — producer built (`dadb459`).** A model-emitted recorder (`scripts/gate/emit.py`) now appends `suggestion_gate` events per the canonical contract; wired into CLAUDE.md's surface-decisions convention (`2d9bbb2`), so tessera-dev sessions self-dogfood it. Built minimal: `should_fire` null (annotate post-hoc), `score`/`threshold` omitted (no scorer). The *machinery-absent* half of this entry is closed.
- **Update, 2026-06-27 — first real dogfood answers watch #1: forgetting dominates.** A full tessera-dev session (statusline tier-advisory work, install.sh hardening, go-global decision) surfaced ~6 gates — statusline design, run install.sh, partial-vs-full global, KMP rides-global, go-global decision, statusline fallback edit — and logged **1**. ~85% miss rate. The recorder depends on the model remembering to call it mid-flow, and under real work the model doesn't. This is the same failure mode as the "Convention-surfacing drift" entry below (the tier advisory failed identically) — model-compliance is not a reliable trigger. **Watch #1 is answered: a model-only producer under-captures badly; the Stop-hook transcript-scan backstop the entry named is now evidence-justified.** Not built yet — n=1; defer one more dogfood before building the scanner (ponytail: don't build a transcript parser on a single sample). Cheap interim signal if wanted: a Stop-hook that counts surfaced-vs-logged gates and prints the ratio.
- **Status:** Watching (narrowed) — watch #1 answered (forgetting dominates); #2 and #3 still open.
- **When to revisit:** Backstop trigger: **build the Stop-hook gate-scan after the next dogfood reproduces the under-logging** (n≥2). Still watching: (2) does reviewing the gate journal in the dashboard surface real friction, or is the convention alone the whole feature? (3) does the mechanical/scored producer (option B) ever get pulled for? Close when (2)/(3) resolve and the backstop ships.
- **Open question it feeds:** does a convention-only gate need a producer at all? The dogfood sharpens it — a model-only producer that captures 1-in-6 isn't a usable friction journal, so if the producer is to earn its keep it likely *must* have the hook backstop, not just the convention. Whether it survives past the dogfood depends on that and watches #2/#3.

### Downstream packaging mechanism (and: templates/ is NOT cruft)

- **Source:** Howler dogfood #1 scaffold, June 2026. Surfaced while hand-scaffolding the first real downstream project.
- **Anti-cruft note (read this before deleting anything in `templates/`):** the maggy-inherited `templates/` top-level and `commands/initialize-project.md` are **NOT cruft.** Per `design-principles.md` ("Skills — keep" / "What's Out"), Tessera intentionally keeps mnemos, icpg, polyphony, codex-review, etc.; the cut-list skills are already removed (`e4ae042`). `templates/*` is the **install payload** for kept subsystems; `initialize-project.md` is the inherited maggy **installer**. A 2026-06 scaffold-notes draft mislabeled these "cruft" — that was filename-based inference, corrected here so it doesn't become a recurring false drift point.
- **The actual open question — how does Tessera stand up / distribute a downstream project?** Three observed realities, no shared mechanism:
  - **tess-dashboard (#0)** and **Howler (#1)** were each **hand-rolled** into different shapes (numbered vs bulleted CLAUDE.md; `.tessera/` with vs without `project.yml`; gate recorder absent vs present). Divergence baseline.
  - **`bin/tessera-new-project`** (built during Howler) — minimal, harness-only, copies from a sibling tessera checkout. Converges new projects but doesn't distribute the skill/command layer and assumes adjacency.
  - **Maggy installer** (`initialize-project.md` + `templates/` + `~/.claude/.bootstrap-dir`) — fuller (installs skills/commands/hooks) but maggy-shaped and assumes a global bootstrap dir.
- **Scaffold half — DECIDED (2026-06-24).** `bin/tessera-new-project` is the default mechanism for standing up a new downstream project (harness layer). Recorded in `design-principles.md` → Dogfood Plan → "Downstream project scaffold." tess-dashboard + Howler grandfathered (tess-dashboard's `project.yml` retrofit). This entry now tracks only the packaging half below.
- **Status:** Investigating (packaging half only)
- **When to revisit:** When real distribution pressure appears — a second machine, another person, or skills diverging from the global install. Decide then: adapt the maggy installer, extend the scaffold to carry the skill/command layer, or layer both. Graduate to an ADR at that point.

### Override mechanism — deferred pieces

- **Source:** Override-mechanism hook integration build (2026-06-26, design-principles §593). Core shipped: annotation scanner + audit emitter + `override-event` contract + `report.py` + `tdd-loop-check.sh` wiring.
- **Deferred, tracked for follow-up:**
  1. **`tess` umbrella CLI** — the design names `tess overrides report --since 1w`. Shipped as a standalone `scripts/override/report.py` instead; the `tess` front-end doesn't exist yet. Revisit when a second `tess <noun>` subcommand is wanted (don't build a CLI framework for one verb).
  2. **Actual gate-bypass semantics** — v1 is **audit-only** (detect + log + review; native skip does the skipping). A mode where an annotation actively suppresses a specific failure was rejected (hard to scope from a whole-suite run; invites silent green). Revisit only if "log it" proves too weak in dogfood.
  3. **Healthcare compliance-review extension** (§54) — required-review-on-override for the healthcare layer. Out of scope until the healthcare layer activates.
- **Status:** Deferred (core built)
- **When to revisit:** #1 when a second `tess` verb appears; #2 if audit-only proves insufficient in dogfood; #3 with the healthcare layer.

### Mnemos kill/keep test was confounded — empty ≠ unused

- **Source:** Dashboard-validation session (2026-06-26). Verifying tess-dashboard captured metrics as intended.
- **What it was:** The Mnemos trial (design-principles.md line 97) set a drop signal: "if two weeks pass with zero compaction issues and Mnemos never fires, drop." Two dogfood projects in, the typed-graph layer read **0 nodes** — which looked like that signal firing.
- **Actual finding:** The graph was empty because **unfed and mis-plumbed, not unused.** Three independent breaks, all silent: (1) hooks invoked Mnemos via bare `python3` (homebrew 3.14) but the package was installed for 3.13 → `auto_nodes` import + checkpoint write no-op'd every call; (2) `fatigue_log` was only written by `mnemos fatigue`, which no hook calls; (3) the Goal/Constraint layer's two intended feeds were both dead — manual `mnemos add` (never happens) and `bridge-icpg` (no `.icpg/` to read). None of this is a usage signal. The kill/keep test silently assumed the plumbing worked; it didn't.
- **Resolution:** Fixed all three (hooks resolve a mnemos-capable interpreter via the console-script shebang; `cmd_checkpoint` logs fatigue; iCPG bootstrapped + idempotent `bridge-icpg` + new `extract_session_goals` feed both goal flavors). Layer now auto-captures: 21 goals (10 code-intent + 11 session-task), 53 constraints, 9 results — all idempotent. Commits: tessera `fix(mnemos): pin interpreter…`, `feat(mnemos): feed never-evicted goal/constraint layer…`; tess-dashboard `fix(gate): exclude unlabeled events…`.
- **Lesson for the framework:** A kill/keep test on *observed output* is only valid once the *input path is verified live*. "Feature never fired" must be disambiguated — unused vs unreachable — before it counts as evidence. The two-week clock should **restart from a fed baseline**, not from the broken one.
- **Update, 2026-07-09 — the clock was the wrong instrument, and the test was unfalsifiable.** Evidence pulled on the eve of the ≈07-10 deadline:
  - **Compaction never fired.** Across 131 `fatigue_log` samples since the fed baseline, max `token_utilization` = **0.51**; zero samples above 0.7 or 0.8. Compaction triggers ≈83%. `state` was `flow` in **131/131** — the COMPRESS / PRE-SLEEP / REM / EMERGENCY bands and every action they gate have never been exercised either.
  - So the drop signal ("still never aided a recovery") reads as satisfied and means nothing. This is a **third category** the entry above didn't name: not unused, not unreachable — **untriggered**. The event the feature exists to handle has not occurred. Turn count is not the driver (a 628-turn session peaked at 0.51); token volume is.
  - **Worse: the test could never have been answered.** `mnemos-post-compact-inject.sh` consumed the marker with `os.rename` → `os.unlink`, leaving zero trace, and `checkpoints` has no trigger/source column — a PreCompact emergency checkpoint is byte-indistinguishable from a routine Stop-hook one. Had compaction fired 20 times, no query on disk could have shown it. **The kill/keep criterion was set against evidence the system does not produce** — a principle #17 failure one level up: the *decision* rode on recall, not a channel.
- **Fixes landed 2026-07-09:** `.mnemos/compaction-log.jsonl` (gitignored, append-only) now records `compaction_fired` (PreCompact) and `restore_injected` / `restore_missed_stale` (PreToolUse). Both paths + the no-op fast path exercised in an isolated temp `.mnemos/`; the real log stayed clean. Separately, the docs' Layer 2 (`mnemos-compact-recovery.sh` via a SessionStart `"compact"` matcher) **never existed** — its role is played by the unmatched `mnemos-session-start.sh`. Coverage intact, naming corrected in the skill, both script headers, and `design-principles.md`.
- **Status:** Trial **re-armed on an event trigger** (calendar trigger retired)
- **When to revisit:** **Not on a date.** When `compaction-log.jsonl` records **≥3 `compaction_fired` events**, judge: did `restore_injected` follow each one, and did the restored checkpoint actually let work resume without re-deriving? Then keep or drop on evidence. A `compaction_fired` with no matching `restore_injected`, or repeated `restore_missed_stale`, is a **failure** signal — distinct from the **untested** signal of an empty log.
- **Standing caveat:** the trial is about the **compaction-recovery** layer. Mnemos's **session-continuity** layer (checkpoint written on Stop, reloaded on SessionStart) is separately and visibly working — 148 nodes, 134 checkpoints, restores every session. The two got conflated in the original framing. Session-continuity earns its keep on its own; do not let its success vouch for the untested layer, or its trial's failure condemn it.

### Mnemos/iCPG installed on homebrew system python — venv is the durable fix

- **Source:** Same 2026-06-26 session (the interpreter-mismatch root cause above).
- **What it is:** `mnemos`/`icpg`/`polyphony` are `pip install --break-system-packages` into homebrew's python (currently 3.13). When homebrew bumps the default `python3` (it moved to 3.14), bare `python3 -m mnemos` stops resolving the package — the break that silently emptied the Mnemos graph.
- **Mitigation in place:** hooks now resolve the package's interpreter from the `mnemos` console-script shebang, so the pipeline is version-agnostic regardless of which `python3` is default. The symptom is handled.
- **The deferred decision:** the *durable* fix is a dedicated venv (pins the interpreter, immune to homebrew bumps, no `--break-system-packages`). NOT doing it now — reinstalling for each new homebrew python is a treadmill, but a venv is a packaging/install change touching `install.sh` + the bin scaffold, larger than this session warranted. The console-script resolution holds until then.
- **Status:** Mitigated; venv deferred
- **When to revisit:** if `--break-system-packages` bites again (a homebrew bump the shebang-resolution doesn't absorb, or a second machine where the install layout differs), or when `install.sh` is next reworked — fold the venv in then.

---

### Downstream script drift (F-003) — local copies vs. global single-source

- **Source:** Tessera dogfood, 2026-06-27. A statusline patch (tier-advisory flag) landed in tessera but not in howler / tess-dashboard — three repos needed manual sync for one script change.
- **What it is:** Every downstream project scaffolds its own copies of the mnemos hook scripts into `.claude/scripts/`. When Tessera patches a script, downstream copies don't update — no sync mechanism. The hooks already resolve `.claude/scripts/X` (local) **OR** `$HOME/.claude/templates/X` (global fallback); local always wins, so local copies shadow the global one and drift independently.
- **State after 2026-06-27 session:** the global fallback is now **live** (`install.sh` run → `~/.claude/templates/` populated) and the statusline was given the same two-tier fallback its sibling hooks have (`eb21914`) — previously it was local-only, the literal root cause. So the *rail* for going global is laid; the *switch* is not flipped. Existing projects keep local copies (deliberate — Howler is shipping to Play Store and benefits from frozen, churn-immune hooks).
- **Correction + DECISION, 2026-06-30 (ADR-0004).** The "hooks already resolve local **OR** global fallback" claim above was **wrong at the hook-entry level.** Verified: every mnemos hook command (live settings, scaffold template, statusline) was `if [ -x .claude/scripts/X ]; then exec …; fi; exit 0` — **no `elif ~/.claude/templates/X`**, and no script resolved global siblings internally. `~/.claude/templates/` was an *install source*, not a *runtime fallback*: a project with no local copies would silently no-op every mnemos hook. Going global was never a config flip — the switch didn't exist. **ADR-0004 built it** (G1): fallback branch added to the 7 hooks + statusline in `settings.base.json`; `hook_distro: global|frozen|source` field; `tessera-new-project` defaults global; `bin/tessera-hooks freeze|thaw|status` for inflection. Existing 3 grandfathered — howler/dash `frozen`, tessera `source`, no mass migration.
- **KMP forcing-decision dissolved.** KMP (the named trigger) is an android→iOS port of Howler *in the howler repo* (KMP = one repo, shared + android + ios targets), not a new scaffold — so it doesn't exercise `tessera-new-project`. Howler stays `frozen` (now shipping two platforms). First real global scaffold validation deferred to the next genuinely-new project.
- **The two coherent end-states:** (A) **status quo** — local copies, self-contained (clone + go), drift on every script change; (B) **full global** — no local copies, single source in `~/.claude/templates/`, zero drift, but machine-coupled (needs `install.sh` per machine, not version-controlled per project, all projects change together). The scaffold currently does (A); going (B) means `tessera-new-project` stops copying scripts locally.
- **The hybrid the architecture enables:** decide per-project. A new project (KMP, imminent) can scaffold *without* local copies → rides global, zero drift from day one. Ship-critical projects (Howler) keep frozen local copies until safely live, then drop them.
- **Update, 2026-07-09 — a *fourth* copy exists, and it was the stale one: `templates/` (the install payload).** ADR-0004 reasoned about two runtime layers (project-local `.claude/scripts/` vs global `~/.claude/templates/`) and missed that the repo's own `templates/` is the **upstream of the global layer** — `install.sh` copies `templates/` → `~/.claude/templates/`. Found while syncing an unrelated hook edit:
  - `mnemos-post-tool.sh` and `mnemos-stop-checkpoint.sh` in `templates/` still called **bare `python3`**. That is the exact interpreter-mismatch bug the 2026-06-26 session fixed — the one that silently emptied the Mnemos graph and confounded the kill/keep trial (see "Mnemos kill/keep test was confounded" above). The fix reached `.claude/scripts/` and was hand-copied into `~/.claude/templates/` on 06-27, but **never landed in `templates/`**.
  - Consequence: **`install.sh` on a fresh machine would have overwritten the good global copies with the broken ones and reintroduced the bug the 06-26 investigation existed to kill.** `verify()` would not have caught it — it checks that the mnemos shebang resolves, not that the hooks *use* it. A latent regression armed in the install path.
  - `mnemos-statusline.sh` was drifted the other way (repo `templates/` 07-02 newer than global 06-27) — the tier-advisory patch `eb21914` never propagated outward.
  - Reconciled 2026-07-09: `.claude/scripts/` is canonical (this repo is `hook_distro: source`); `templates/` re-synced from it. The global layer refresh is a separate, out-of-repo action.
- **The lesson, which is F-003's own lesson recurring one layer up:** ADR-0004 fixed *runtime* resolution (local → global fallback) but left *authoring* propagation manual. Three writable copies of the same script, no mechanism keeping them in step, and the drift is silent because each copy is independently valid bash. `bin/tessera-hooks status` checks declared-mode vs local-copy-count; it does **not** diff content across layers. **A drift check that doesn't compare bytes isn't a drift check.**
- **Status:** Adopted → ADR-0004; **re-opened** on the authoring-propagation gap
- **When to revisit:** per ADR-0004's re-evaluate triggers — first real `thaw` of a grandfathered repo (build the settings auto-patch then), a `global` project found silently dead on a machine, or project count crossing ~4–5 with several still `frozen`. **Added trigger (now):** teach `bin/tessera-hooks status` to diff `.claude/scripts/` ↔ `templates/` ↔ `~/.claude/templates/` by content and report drift, or make `templates/` a symlink/generated artifact rather than a hand-maintained third copy. Until one of those lands, every hook edit needs a manual three-way sync — which is precisely the failure mode that produced this entry.

### New-machine bootstrap is tribal knowledge, not a script

- **Source:** Tessera dogfood, 2026-06-27. After a machine move, `install.sh` had never been run — the global layer (`~/.claude/{skills,commands,templates}`) was empty and nobody noticed because every project carried local copies.
- **What it is:** Standing up Tessera on a fresh machine takes four steps that live only in scattered docs / past findings, not one bootstrap: (1) `install.sh` (populate global layer); (2) mnemos pip install **pinned to arm64** (`/opt/homebrew/bin/pip3.13`) with a shebang-resolves check (**F-001** — a dead shebang silently disables every Mnemos hook); (3) ollama + `qwen2.5-coder:3b` pull (else routing fails open to Sonnet — degraded, not broken); (4) Claude transcript slug rename if migrating `.mnemos`/history (**F-002** — slug derives from realpath with on-disk casing).
- **Why it caught our attention:** the empty-global-layer state is a silent-success failure mode — everything works via local copies, so the missing `install.sh` is invisible until you rely on the global fallback. Same shape as the F-001 dead-shebang and the shell-alias/wrong-CWD bug: the framework appears installed while a layer is quietly absent.
- **Update, 2026-06-27 — `verify()` shipped (`51f9f26`).** install.sh now runs a post-install verify: hard-aborts (exit 1) if the global layer is empty, mnemos is off-PATH, the mnemos shebang is dead (F-001), or the scaffold settings.json is invalid; warns-only if ollama/qwen are absent (routing fails open). The silent-success mode is closed — install.sh now loudly fails when the machine isn't known-good. Fail + happy paths both tested.
- **Status:** Watching (narrowed)
- **What's still open:** install.sh **verifies** mnemos but does not **install** it — that remains the `docs/install.md` Step 2 manual workaround (copy maggy source into a nested layout, arm64-pinned pip) because the upstream `maggy/scripts/mnemos` flat-layout `pyproject.toml` can't be `pip install`ed directly. F-002 slug rename stays out of scope (migration, not fresh-install).
- **When to revisit:** when the mnemos packaging is fixed upstream — Step 2 collapses to a one-liner and install.sh could absorb the install, not just the check. Trigger is passive (external repo, no watcher); already recorded in `docs/install.md` "When this guide goes stale." Low consequence if missed — `verify()` catches a broken workaround, so the worst case is a longer install step, not a silent break.

### Convention-surfacing drift — model-compliance is not a reliable user-facing channel

- **Source:** Tessera dogfood, 2026-06-27. Two independent features failed the same way in one session.
- **What it is:** A recurring failure mode where a CLAUDE.md convention instructs the model to **surface something to the user**, the model drifts and forgets, and the user never sees it — silently. The convention looks like it works (it's followed *sometimes*), so the gap doesn't announce itself. Two confirmed instances:
  1. **Tier advisory.** CLAUDE.md said "when the suggested tier differs from your model, surface it in one line." Across many sessions the model only surfaced it *when the user asked* — the advisory was effectively invisible. Root cause: the only path to the user's screen was the model choosing to echo it. Fixed by wiring it to the **statusline** (`⚑tier:<model>`, commits `5c9ddc4`/`eb21914`), a channel that renders every turn with zero model action.
  2. **Suggestion-gate logging.** CLAUDE.md said "when you surface a gate, also record it via `emit.py`." Real dogfood: ~6 gates surfaced, 1 logged (~85% miss). See the suggestion-gate entry above. Fix candidate is the same shape: a **Stop-hook** backstop, not reliance on the model.
- **The pattern:** model-memory is a lossy, drifting trigger. Anything whose value depends on the user *seeing* it (advisories, friction logs, status) must ride a **non-model channel** — statusline (per-turn user-visible), a hook (deterministic on an event), or a tool the harness renders. CLAUDE.md conventions are fine for shaping *how the model works*; they're unreliable for *guaranteeing the user is informed*.
- **Decision heuristic for new features:** when adding anything the model is "supposed to tell the user," ask first — *what's the non-model channel?* If the answer is "the model will mention it," expect ~drift-rate loss. The statusline is the underused default surface (one line, every turn, free); a Stop/PreToolUse hook is the default for event-triggered capture.
- **3rd instance landed, 2026-07-08.** The downstream findings backlog: `tessera-findings` was built, then surfaced only via a "run it next time" note — a model/human-recall convention. Caught in dogfood ("a user shouldn't have to kick that over"), fixed with a **SessionStart hook** (non-model channel, fires every session). Same shape as the two above. Trigger fired → **promoted to design principle #17** (channel-not-convention for user-facing signals).
- **Status:** Adopted → design principle #17
- **When to revisit:** Closed as a pattern-on-the-radar. Follow-on audit (sweep existing CLAUDE.md "surface X" instructions against #17) tracked as FOCUS-003 in `_project_specs/todos/active.md`.

### Tier classifier under-rates discussion-heavy prompts

- **Source:** Tessera dogfood, 2026-06-27 — observed across a long tessera-dev session.
- **What it is:** The `tier-classify-hook` (qwen, ADR-0002) classified most of this session as **HAIKU**, including the go-global architecture decision, the install.sh-hardening design work, and the model-switch cache-cost reasoning — all clearly OPUS-tier work. The classifier judges *surface shape* (a short, conversational-looking prompt) rather than *intent* (the deep reasoning the prompt actually demands). Short prompts that open large reasoning tasks ("what do you reco on X?", "should we go global?") get under-rated.
- **Why it caught our attention:** The advisory is only useful if its tier tracks the work. Systematic under-rating of discussion/decision prompts means the flag points the wrong way exactly when the stakes are highest — architectural and design turns. It nudges toward a cheaper model for the most intelligence-sensitive work.
- **Mitigations (unbuilt):** (1) feed the classifier conversation context, not just the bare prompt — a decision prompt mid-architecture-thread reads differently than in isolation; (2) bias the classifier upward on decision/question framing; (3) accept it and lean on the human (the advisory is advisory — the cost is a wrong nudge, not a wrong action). Note the "Convention-surfacing drift" entry and the model-switch cost note (CLAUDE.md) both argue *against* acting on every flag anyway, which softens the impact.
- **Mitigation #2 applied, 2026-07-08 (FOCUS-001).** Took the boundary-few-shot path (ADR-0002 re-eval trigger). Added a "judge reasoning demanded, not prompt length" rule to `tier-classify-hook`, extended OPUS to open design/strategy decisions, and added balanced examples (short decision Q → OPUS, short trivial lookup → HAIKU) so length stops being the signal. Empirical eval on real session prompts (qwen2.5-coder:3b, temp 0): **5/6** — "what's next for tessera?" and "should we fold the dashboard?" now land OPUS (were HAIKU); trivial lookups correctly stay HAIKU. **Residual miss:** "is X in the memory file, or do you disagree?" → HAIKU — it opens as a yes/no lookup and its OPUS-ness lives in conversation context the bare-prompt classifier can't see. That's mitigation #1 (feed context) territory, still unbuilt.
- **Status:** Investigating — #2 (few-shot) done; #1 (context-aware) open for the residual
- **When to revisit:** When the residual (context-blind on lookup-shaped decision prompts) bites for real — enough wrong-nudge annoyance to justify feeding conversation context to the classifier (mitigation #1). Until then the few-shot fix covers the common case.

### sqlfluff — adopt when a downstream project has standalone SQL

- **Source:** Tessera tooling discussion, 2026-06-28.
- **What it is:** sqlfluff is a dialect-aware SQL linter + autoformatter (postgres/bigquery/snowflake/…, dbt/jinja templater support). Candidate quality-gate / skill for SQL-heavy projects.
- **Why deferred:** Tessera-the-framework has **0 `.sql` files and no dbt** — all SQL is inline string literals in Python (`scripts/{mnemos,icpg,polyphony}/store.py`, SQLite DDL). sqlfluff lints `.sql` files and templated SQL; it does **not** see SQL embedded as Python/TS string literals without extraction. Pointed at this repo today it finds nothing. Downstream projects so far (Howler = none, tess-dashboard = inline TS/SQLite) are the same shape.
- **Adopt-when trigger:** a downstream project introduces **standalone `.sql` files or dbt models**. Then add it as an **on-demand skill** (`paths: **/*.sql`) plus an optional pre-commit gate that **no-ops when no SQL is present** — not an eager default (principle #15). Worth a `/evaluate-framework sqlfluff` run at that point for a real ADR with verdict + re-evaluate triggers, rather than ad-hoc bolting.
- **Separate use — pr-arbiter (different repo, different rationale):** sqlfluff as a deterministic SQL pre-pass for the LLM reviewer — strips style-nit noise, validates parse, normalizes formatting so the model reviews clean SQL. **Caveat:** it does *not* address the SQLi/taint false-positives the dashboard pr-arbiter run hit (those are threat-model context — "discount request-derived-input findings unless a route threads user input", per `../tess-dashboard/docs/FINDINGS.md`). Two layers: sqlfluff = noise floor; reviewer-prompt threat-model = the false-positive fix. That work lives in `~/Claude/pr-arbiter`, not Tessera.
- **Status:** Watching
- **When to revisit:** first downstream `.sql`/dbt surface (Tessera side); pr-arbiter side is tracked in that repo.

### Cross-cutting rename guard — Kotlin/manifest greppable, JNI coupled by string convention

- **Source:** Howler dogfood F-004, 2026-06-30 — closed tester reported crash on open (Android 16).
- **What it is:** A package rename (`com.example.howler` → `com.houseofyeti.howler`) updated the Kotlin/namespace/manifest layer but left `audio_engine.cpp` exporting `Java_com_example_howler_...` symbols. JNI resolves natives by mangled FQCN, so `nativeStart()` threw `UnsatisfiedLinkError` and the app crashed on open — **with no build error** (the C++ compiles and links; the symbol is just orphaned). A cross-cutting refactor Tessera has no guard for: the Kotlin layer is IDE-refactorable, the native layer is coupled to it only by string convention.
- **Why it caught our attention:** Silent-at-build, crash-at-runtime is exactly the failure class a framework guard should catch. Two candidate guards: (1) a rename-checklist / lint that, for projects with an `externalNativeBuild`, greps `src/main/cpp` for `Java_<old_package_mangled>_` after an applicationId/namespace change; (2) a minimal JNI-load instrumented test in the NDK scaffold so symbol-name drift fails CI, not a tester's device. Secondary lesson (agent-behavior, not framework): pull the actual `logcat -b crash` stack *before* theorizing — anchoring on the 16KB-page theory cost time the stack trace would have saved.
- **Status:** Watching
- **When to revisit:** When iOS/KMP work starts (KMP moves the JNI boundary again) or any future rename touches native code. Narrow scope (NDK projects only) — not worth building until a second native-layer project exists. Howler is currently the only one.

### The Observatory's own triggers are prose, therefore unchecked

- **Source:** Tessera dogfood, 2026-07-09. Asked whether sqlfluff was worth adopting; the answer was "the entry already decided that — has its trigger fired?" Checking took three shell commands. Checking the *rest* of the entries took three more, and found trouble.
- **What it is:** every entry here carries a **"When to revisit"** condition. Nothing evaluates them. They fire when a human happens to re-read the entry. On 2026-07-09, three were at or past threshold with nobody aware:

  | Entry | Stated condition | Reality |
  |---|---|---|
  | Override mechanism — deferred pieces | "when a second `tess` verb appears" | four exist (`tessera-{changelog,findings,hooks,new-project}`) — though these are standalone binaries, not `tess <noun>` subcommands, so it is the spirit, not the letter |
  | Downstream script drift (F-003) | "project count crossing ~4–5" | exactly 4 |
  | Two-stage hierarchical skill routing | "60+ skills"; entry claims "currently at ~50" | 56 |

- **The pattern:** **a trigger written as a sentence can only be checked by someone who reads the sentence.** A trigger written as a predicate checks itself. This is design principle #17 turned on the Observatory itself — the file is a *compendium*, and its value depends on a human seeing a fired condition, which is precisely the model/human-recall channel #17 says drifts. The findings backlog had the identical shape until `bin/tessera-findings` + a SessionStart hook converted it from compendium to channel.
- **The sharp filter is silent vs. self-announcing, not checkable vs. not.** sqlfluff's trigger ("first `.sql` file") is trivially checkable and *worthless* to watch: the day you write SQL and want it linted, the need announces itself. Hook-layer content drift is checkable and **silent** — bare `python3` sat in `templates/` for two weeks with no symptom, because each copy was independently valid bash. Watch only what cannot announce itself. Roughly a third of entries are machine-checkable; about five are *also* silent, and every one of those five corresponds to a failure that already happened.
- **Three things were conflated in the original question** and are worth keeping apart: (a) a **compendium** — this file, durable record, no evaluation; (b) a **watcher over declared triggers** — perfect precision (the condition is stated), recall bounded by expressibility; (c) a **scanner outside the declared set** — discovery of conditions nobody wrote down, unbounded and low-precision. (c) is not worth building: FOCUS-002 swept all 22 entries manually and found nothing dead. Discovery doesn't need automating; it needs **scheduling**.
- **Status:** Pending eval — **folded into roadmap Tier 1, spec 03** (verifiable contracts) as its de-risking pilot. Same conversion (prose → predicate), ~2% of the risk: shell one-liners instead of property-based test generation. Deliberately *not* folded into spec 01, which observes the deployed product rather than the framework's own invariants.
- **When to revisit:** with the Tier 1 decision. See the cluster note above — this joins the five GSD entries that resolve together with it. **Do not build the watcher independently**; it is the pilot that tests whether spec 03's premise holds, and building it early spends the evidence it was meant to produce.
- **Honest bias note:** proposed at the end of a session spent finding drift bugs, by a party predisposed to want a drift-bug-finding tool. The five candidate checks all map to documented past failures rather than anticipated ones (principle #3), which is the strongest available answer to that objection — but the objection stands.

### Reusable migration skill (path-slug caveat is the seed)

- **Source:** Howler dogfood F-002, 2026-06-24 — restoring `claude-project.tgz` on a
  new machine. Transferred here 2026-07-10.
- **What it is:** moving a Claude project between machines requires renaming the
  unpacked transcript dir to match the new machine's path-slug. Each downstream
  ships its own `RESTORE.md` with this caveat. Candidate for a single reusable
  `tessera` migration skill instead of per-project prose that drifts and is
  re-derived each time.
- **The concrete detail that must survive the transfer:** the slug derives from the
  **realpath with on-disk casing**, not the cwd string. On case-insensitive macOS a
  lowercase path *looks* equivalent (`/Users/x/claude/...`) but the slug is literal —
  it takes the on-disk dir's actual case (`Claude`, capital C). In the F-002 case
  only the username segment changed (`lciacci` → `lorenzociacci`); the case did not.
  A migration skill's example must show casing-from-realpath, not just the cwd string,
  or it will mislead exactly when the FS casing and the typed path disagree.
- **Why it caught our attention:** small, but the kind of detail lost when it lives in
  N per-project RESTORE.md copies (same divergence class as the hook-drift and
  statusline-drift entries — one source vs. many hand-maintained copies).
- **Status:** Watching.
- **When to revisit:** when a second cross-machine migration happens, or the next
  project scaffold would benefit from a shared restore path. Not worth building the
  skill on n=1; the caveat is captured here so it is not re-derived.

## Closing notes

This file is meant to be light-touch. Drop entries in when you notice something; promote to ADR when evidence justifies; close out when decided. Do not let it become a place that requires its own maintenance schedule — that defeats the purpose.

If an entry sits in "Investigating" for >6 months without being touched, that itself is evidence it doesn't matter. Either close it (move to a "Closed without action" section), or commit to a real decision.
