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
- **When to revisit:** ~~When Tessera supports specific routing to reasoning models~~ — **this trigger fired.** As of **ADR-0002** (2026-06-26) Tessera routes by Claude effort tier (`CLAUDE_HAIKU/SONNET/OPUS`) at subagent/workflow dispatch. The routing precondition is now satisfied; the open part of *this* item — per-tier prompt-pattern templates (different prompt structures for opus-class vs haiku-class work) — is now **actionable but unbuilt**. Revisit if tier misrouting or tier-blind prompting proves to cost quality.
- **Resolution:** Routing built (ADR-0002); prompt-pattern templates deferred — current routing changes the *model*, not yet the *prompt structure* per tier.

### Capability registry / plugin system

- **Source:** Open GSD — `bin/lib/capability-registry.cjs`, `bin/lib/capability-loader.cjs`, ADR-1244 (theirs)
- **What it is:** Generated central registry of capabilities, with runtime overlay loading from `$GSD_HOME/.gsd/capabilities/` (global) and `<projectRoot>/.gsd/capabilities/` (project). Validated overlay system with first-party precedence, engines.gsd version gating, and per-capability command routing via command family modules. Their extension model.
- **Why it caught our attention:** More developed than our skills system. Allows third-party capability extensions with consent gates and confinement (path validation, realpath containment).
- **Status:** Watching
- **When to revisit:** If Tessera ever needs third-party extension support (currently solo use; not in scope). Or if our profile compositional mechanism proves insufficient and we need a more general extension system.
- **Resolution:** Skipped in ADR-0001 because different design philosophy (Tessera uses compositional profiles; GSD uses extensible capabilities).

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
- **Status:** Watching (narrowed)
- **When to revisit:** The remaining question is no longer "does a producer exist" but "does it **earn its keep**." Watch the first real dogfood: (1) does Claude reliably call the recorder, or does forgetting dominate (→ a Stop-hook transcript-scan backstop)? (2) does reviewing the gate journal in the dashboard surface real friction, or is the convention alone the whole feature? (3) does the mechanical/scored producer (option B) ever get pulled for — i.e. does anyone want precision/recall on live data? Close when the dogfood answers these.
- **Open question it feeds:** does a convention-only gate need a producer at all? Partly answered — built one for the dogfood's friction-finding purpose, not for production measurement. Whether it survives past the dogfood depends on the three watches above.

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

---

## Closing notes

This file is meant to be light-touch. Drop entries in when you notice something; promote to ADR when evidence justifies; close out when decided. Do not let it become a place that requires its own maintenance schedule — that defeats the purpose.

If an entry sits in "Investigating" for >6 months without being touched, that itself is evidence it doesn't matter. Either close it (move to a "Closed without action" section), or commit to a real decision.
