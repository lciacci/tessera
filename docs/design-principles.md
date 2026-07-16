# Tessera (Tess) — Design Principles & Plan

*Each skill is a tessera; the whole framework is the mosaic.*

*Living document. Captures decisions made before reading and pruning begins. Expect to revise as the dogfood reveals reality.*

---

## Vision

**Tessera** is a personal agentic coding framework, forked from [alinaqi/maggy](https://github.com/alinaqi/maggy), pruned and rebuilt around three concerns: (1) what's actually useful for solo dogfooding, (2) what extends cleanly via project-specific profiles (healthcare is one example, others may emerge), (3) what could later survive as a shared tool for collaborators or a team. The dogfood phase comes first; everything else is downstream.

Long arc: a thoughtful Claude Code framework with verification gates, a YAGNI discipline, and per-project profile extensions (healthcare profile being one substantial example). Recognizable IP, not just an upstream-tracked fork.

---

## Philosophy

Four convergent influences, deliberately balanced:

- **Maggy** — *structure compounds*. Selectively true. Keep the TDD Stop hook, the read-only reviewer pipeline, the conditional-rules layer. Reject the maximalist scaffolding.
- **Boris / Arpan** — *master the primitives*. Short CLAUDE.md, mistake-driven rules, native commands first. The dominant philosophy for dogfood.
- **Ponytail** — *YAGNI ladder*. Climb the smallest-thing-that-works ladder before reaching for the heavier abstraction. Applies to code *and* to tooling decisions.
- **Trask** — *ensembling is a tool, not a default*. Real ML principle, real value for discrete decisions, overhyped for agentic coding work. Use where it wins.

**Core stance:** lean Boris/Arpan for the dogfood phase. Keep selective Maggy structure where native primitives don't cover the gap. Ponytail discipline as a compounding rule. Ensembling reserved for consequential decisions.

---

## Compounding Design Principles

These are the rules that should outlive any specific implementation choice. Add to this list as the dogfood teaches us new ones.

1. **Native primitives first.** Don't reach for a heavier custom thing if a native command (`/rewind`, `/goal`, `/batch`, `/insights`) covers it adequately.
2. **YAGNI ladder.** Stdlib → native platform → installed dependency → one line → only then custom code.
3. **Short, mistake-driven CLAUDE.md.** "Would removing this line cause a mistake? If not, cut it." Rules grow from real mistakes, not anticipated ones.
4. **`CLAUDE.local.md` for private feedback.** Gitignored. Personal corrections, PR feedback, and habits-to-correct accumulate here without polluting shared config.
5. **Ensembling is a tool, not a default.** `/arbiter` for consequential decisions; default single-model for normal flow.
6. **Direct integrations only.** No aggregators or middlemen (no OpenRouter). Trust and habit-building matter, especially with healthcare in the longer arc.
7. **Data handling is a first-class concern.** Tessera has a sensitive-data awareness layer that activates based on project profile. Healthcare profiles add HIPAA-specific defaults; other profiles may add other patterns. Even the standard profile treats audit trails and secrets handling as baseline concerns.
8. **Verifiability over ceremony.** TDD Stop hook earns its keep; a 10-stage agent pipeline does not, for solo use.
9. **Read-only reviewers.** Reviewers with write access defend their own edits. (Maggy enforces this; the reasoning is what matters when thinning the pipeline.)
10. **Single-harness focus.** Adapter sprawl is a cost, not a feature.
11. **Just-in-time provider addition.** With LiteLLM as abstraction, adding providers is near-free — but each one is still cognitive load. Add when a use case earns the slot, not pre-emptively.
12. **Heavy machinery is suggested, not silent.** Tessera proposes loops, multi-agent ceremonies, and other heavyweight workflows; the human accepts, declines, or modifies. Auto-invocation removes agency and is rejected as a default pattern.
13. **Reviewers operate read-only.** When Claude is in a review role (code review, security scan, spec review, etc.), it operates without write tools — regardless of whether multi-agent orchestration is active. Reviewers with write access defend their own edits.
14. **Once a pipeline is invoked, no internal skipping.** Heavy machinery is opt-in (per #12), but once opted in, the pipeline runs all stages as defined. Stages can produce "no findings" or "not applicable" results — that's still a stage running. *Agent judgment about whether a stage is "meaningful" is exactly what the pipeline is insuring against, so the agent doesn't get to decide to skip.* Human can `--abort` mid-pipeline; agent cannot.
15. **Skill defaults are starting points, not prescriptions.** Stack and tooling choices follow the project's needs first; skills inform but don't decide. When a skill recommends Next.js but Vite fits the project better, pick Vite — and don't feel like you're fighting the framework. The framework is a starting point, not a cage.
16. **Evaluate the ecosystem on a cadence; document the verdict.** Frameworks drift — the world changes, new tools emerge, existing tools evolve. Tessera has a `framework-evaluation` skill and ADR convention that turns ad-hoc "should we use this?" questions into structured decisions with named re-evaluate triggers. Don't ossify. Don't chase shiny. Document why you chose what you chose, and when you'd reconsider.
17. **Channel, not convention, for user-facing signals.** Anything whose value depends on the *user seeing it* — advisories, friction logs, backlogs, status — must ride a non-model channel: the statusline (renders every turn, free), a hook (deterministic on an event), or a harness-rendered tool. A CLAUDE.md instruction to "surface X" relies on model memory, which drifts and silently loses a fraction of the time — the gap doesn't announce itself, because the convention *is* followed sometimes. Conventions shape *how the model works*; they don't *guarantee the user is informed*. Confirmed across three instances: the tier advisory (→ statusline), suggestion-gate logging (→ Stop-hook), and the downstream findings backlog (→ SessionStart hook). When adding anything the model is "supposed to tell the user," ask first: what's the non-model channel? Source: observatory "Convention-surfacing drift."

---

## Architecture Decisions

### Provenance

- Clone Maggy locally, `git remote rename origin upstream`, push to a new repo: `lciacci/tessera`.
- Name committed: **Tessera** (Tess for short). Each skill is a tessera; the whole framework is the mosaic.
- License: MIT, matching upstream.

### Primary harness

- Claude Code as the only driver.
- Strip secondary harness adapters from upstream (Pi, Cursor, OpenCode CLI, Codex CLI-as-harness, etc.).
- Codex stays available as a *model provider* via LiteLLM, not as a separate harness.

### Model abstraction layer

- **LiteLLM as the unified multi-provider abstraction.** Direct provider calls from the local machine; no aggregator in the middle.
- Providers behind it:
  - **Claude** (primary, via Claude Code's own transport for normal flow; via LiteLLM for `/arbiter` and routing).
  - **Ollama** (local, already installed).
  - **Qwen** (local via Ollama; Qwen3:8b already running for the meeting transcription pipeline — joins the routing pool with known characteristics).
  - **Codex** (optional, primarily for auto-review hook — decide after first weeks).
  - **Kimi and others** added just-in-time when a specific use case earns the slot (e.g., 300-file analysis tasks), not pre-emptively.

### Routing

- Routing implemented as **a rule, not a service.** No dashboard, no daemon, no port 8080.
- Default: Claude.
- *Required* local (Ollama): PHI markers in context, sensitive personal data (financial, EAR, job-search internals).
- *Preferred* local: bulk mechanical transformations, offline work.
- `/arbiter` command for consequential decisions only (architecture choices, vendor evaluations, hard trade-offs). Not for normal flow.

### Memory & code-knowledge layers (on trial)

Two distinct concerns that Maggy tangles together — separating them clarifies the trial:

**Session / project memory** — multiple layers with distinct roles, not a single winner:

- **Native compaction** — baseline; the unreliable thing Mnemos exists to insure against.
- **Mnemos** (Maggy) — *compaction/crash recovery*, not general memory. Per Maggy v3.3.1 release notes: "two-layer post-compaction task restoration — guaranteed context recovery when Claude Code's compaction fires, crashes, or doesn't run. Typed memory graph (goals never evicted)." Hook-driven (PreCompact, PreToolUse, PostToolUse). Narrow but potentially valuable.
- **`_project_specs/session/` markdown** (base.md pattern) — lightweight project knowledge: `current-state.md`, `decisions.md`, `code-landmarks.md`. Human-readable, git-friendly.
- **Obsidian three-tier vault** (Arpan pattern) — richer persistent project knowledge. Lorenzo already runs this at `/Users/lciacci/Claude/obsidian`; Tessera should integrate, not replace.
- **Instinct + confidence scoring** (ECC pattern, not the ECC install) — pattern extraction with confidence scores; a third axis if pursued later.

**Revised trial question:** these aren't alternatives — they solve different problems. The trial is "do I need all of these, and which drop out?" *Mnemos handles the failure-mode recovery layer; Obsidian handles persistent project knowledge.* Specific test for Mnemos: does it catch real compaction/crash failures during dogfood and save your place? If yes, keep. ~~If two weeks pass with zero compaction issues and Mnemos never fires, drop.~~ **(2026-06-26 update:** the early "0 nodes" reading was a plumbing bug, not a usage signal — the graph was unfed/mis-plumbed, not unused. Fixed; trial clock reset to a fed baseline.**)**

**(2026-07-09 update — the calendar trigger is retired.)** Compaction has *never fired* since the fed baseline: max `token_utilization` 0.51 across 131 samples, never within reach of the ≈83% threshold; fatigue `flow` in 131/131. "Never aided a recovery" is therefore **untriggered**, not disconfirming — a third category beyond the unused/unreachable split the 06-26 correction drew. And the criterion was unfalsifiable as instrumented: the compaction marker was deleted on consumption and `checkpoints` carries no trigger column, so no query could distinguish "compaction never happened" from "happened twenty times." Fixed by `.mnemos/compaction-log.jsonl`. ~~**The trial is now event-triggered: judge after ≥3 recorded `compaction_fired` events, not after N days.**~~ Note also that this trial governs the *compaction-recovery* layer only — the *session-continuity* layer (Stop-hook checkpoint, SessionStart reload) is independently demonstrated and is not on trial. See observatory → "Mnemos kill/keep test was confounded — empty ≠ unused."

**(2026-07-11 update — the criterion needed one more qualifier, and the layer finally ran.)** The 07-09 criterion was still gameable: a hand-run `/compact` writes a `compaction_fired` event indistinguishable from a real one, so **three deliberate tests of the recovery layer would have delivered the trial's verdict on evidence we manufactured** — the same shape as the retired P2 predicate (firing correctly on a proxy that tracks no real pain). PreCompact now records the hook's `trigger` field, and the criterion is: **judge after ≥3 _non-manual_ `compaction_fired` events.** A `trigger: manual` entry is a *test* of the layer, never evidence about it; `tessera-watch` P3 enforces the exclusion. Separately, the layer executed for the first time ever on 2026-07-11 (manual): the machinery passed all four checks and Layer 2 (`mnemos-session-start.sh` on `source=compact`) put goal, constraints, and a fresh checkpoint back into context with no re-derivation. Layer 3's *injection* remains unproven — its log line fires, but its text was never observed arriving. **The trial's clock has still not started: 0 real events.**

**Code structural and intent knowledge** — three distinct invocation patterns, not parallel always-loaded layers:

- **Code-graph** (Maggy's `code-graph.md`) — *continuously-loaded structural layer for active development on familiar code.* Auto-fresh via file watcher + session-start + post-commit hook. Sub-millisecond queries via the `codebase-memory-mcp` MCP server. 14 tools, 64 languages. This is the always-on workshop view of code you're actively writing. *Tessera's default for active projects.*
- **iCPG** (Maggy) — *continuously-loaded intent layer, if the dogfood trial earns it.* Tracks ReasonNodes (intent), constraints/risk, drift detection. Three canonical pre-task queries fire automatically. Layers on top of code-graph rather than competing with it.
- **GitNexus** ([abhigyanpatwari/GitNexus](https://github.com/abhigyanpatwari/GitNexus)) — *evaluation tool for unfamiliar codebases, invoked at the start of work on code you didn't write.* Strong fit for onboarding to a new repo, due-diligence audits, vendor codebase review, legacy codebase rescue, forensic analysis. Not a daily-workflow tool; reach for it when the situation calls for it. License: PolyForm Noncommercial — for personal exploration of external code, no concern. Only the commercial license question fires when using on paid client or employer work.
- **Native** (grep, AST tools, agent's own exploration) as baseline.

**Reframed pattern:** Code-graph handles *active development on familiar code* (continuous, auto-fresh, low context cost). GitNexus handles *evaluation of unfamiliar code* (episodic, deeper queries, justified context weight). They cover different temporal phases of work, not the same problem. iCPG is the intent layer on top of whichever structural tool is appropriate.

**Hybrid case worth flagging:** PR review on someone else's contribution to your code = unfamiliar diff in a familiar repo. Code-graph + its `detect_changes` tool likely covers this; GitNexus only adds value for unusually large or structurally complex PRs. Pr-arbiter leans on this pattern when it graduates.

### Verification

- **Keep** Maggy's TDD Stop hook. This is the single most valuable piece of upstream.
- **Keep** the read-only reviewer pattern.
- **Thin** the 10-stage agent pipeline for solo dogfood; reconstitute for org rollout. Decide which agents stay after reading `agent-teams.md` (pass 1).
- Codex auto-review hook: deferred decision.

---

## What's In for Dogfood

### Skills — keep

- **Core skills** (with Mnemos marked as *on trial for crash/compaction recovery*, iCPG as *on trial as continuously-loaded intent layer*, code-graph as *on trial vs GitNexus for structural knowledge*): `base`, `iterative-development`, `mnemos*`, `icpg*`, `code-review`, `codex-review`, `gemini-review`, `workspace`, `commit-hygiene`, `code-deduplication`, `agent-teams`, `ticket-craft`, `team-coordination`, `code-graph*`, `cpg-analysis`, `security`, `credentials`, `session-management`, `project-tooling`, `existing-repo`, `cross-agent-delegation`, `polyphony` *(kept-but-not-activated — see Polyphony note below)*.
- **All 8 language/framework skills:** Python, TypeScript, Node backend, React web, React Native, Android Java, Android Kotlin, Flutter. (Android-then-port-to-iOS plan keeps the mobile cluster relevant.)
- **All 6 UI skills:** `ui-web`, `ui-mobile`, `ui-testing`, `playwright-testing`, `user-journeys`, `pwa-development`.
- **All 10 DB/backend skills:** `database-schema` *(dormant; activates on schema/migration/model file paths)*, Supabase x4, Firebase, Cloudflare D1, AWS Aurora, AWS DynamoDB, Azure Cosmos DB. (Agnostic-stack philosophy; Supabase is actively used.)
- **All 3 AI/agentic skills:** `agentic-development`, `llm-patterns`, `ai-models`.
- **PostHog analytics.**
- **`site-architecture`** — kept with **tightened path globs** (`**/robots.txt`, `**/sitemap*` only; drop `**/*.html` and `public/**` to prevent spurious activation on internal Vite projects like Tess dashboard).
- **`web-content`** — kept with tightened activation, same treatment as `site-architecture` (drop blanket HTML/public globs).

### Skills — cut

- `aeo-optimization`, `web-payments`
- `reddit-api`, `reddit-ads`
- `ms-teams-apps`
- `shopify-apps`, `woocommerce`, `medusa`, `klaviyo`
- **`maggy` skill** — references `maggy serve` and the localhost:8080 dashboard infrastructure we explicitly decided not to run. Including it would inject confusing references to features that don't exist in Tessera.
- **`external-model-delegation`** — UserPromptSubmit hook + 6-tier classification + delegation scripts. Superseded by the LiteLLM abstraction + `/arbiter` suggestion-gate design.
- **`model-routing`** — 9-tier classification routing with cascading fallback. Same shape as `external-model-delegation`; same supersession.
- **`visual-validation`** — Maggy-coupled enough that adaptation is more work than rewriting later. Peekaboo (the underlying tool) is good and worth manual tire-kicking during Tess dashboard work, but the skill itself doesn't fit Tessera. If the visual-regression workflow earns its keep during dashboard work, write a Tessera-aligned skill from scratch.

Can re-add from upstream later if a use case appears. Costs nothing to remove for now.

### Add-ons (separate from Maggy itself)

- **Ponytail plugin** — install standalone via `/plugin install ponytail@ponytail`. Run at `full` mode for the dogfood phase. After two weeks, decide: keep as plugin, lift into config, or write a healthcare YAGNI variant.
- **AgentShield** — install standalone via `npx ecc-agentshield scan`. Run as required pre-release hygiene. The one clear win from the ECC repo.
- **GitNexus** — **not part of default dogfood install.** Install when the first "I need to understand this unfamiliar codebase" task arises: onboarding to a new repo, due-diligence on a vendor codebase, evaluating an open-source project, legacy codebase rescue, forensic analysis. Code-graph handles familiar/active code; GitNexus handles unfamiliar/evaluation code. `npx gitnexus analyze` when needed. License: PolyForm Noncommercial — personal exploration is fine; commercial license from akonlabs.com required for paid client or employer work.
- **LiteLLM** — Python library, used by `/arbiter` and any routing logic that needs multi-provider access.

### Settings

- `CLAUDE_CODE_AUTO_COMPACT_WINDOW=400000` — force earlier compaction; quality degrades on long-context models past ~300-400k tokens.
- Short CLAUDE.md per the Boris discipline.
- `CLAUDE.local.md` gitignored.

---

## What's Out

- **Maggy command center / dashboard.** Don't run `maggy serve`. The bootstrap layer is the value; the dashboard is operational burden without a use case yet.
- **Secondary harness adapters.** Pi, Cursor, OpenCode, etc.
- **OpenRouter and any hosted aggregator.** Wrong direction for trust, privacy, and habit-building.
- **ECC as a framework.** Specific components borrowed (AgentShield, pattern references); the rest pushes in exactly the wrong direction.
- **Most e-commerce and marketing-content skills** (the cut list above).

### Kept-but-not-activated

- **Polyphony.** Container orchestration earns its weight for *headless background work* (auto-review hooks running on commit, scheduled refactor agents, A/B implementation comparisons) and *strong isolation guarantees*. During dogfood, interactive context-switching is covered by terminal tabs + `git worktree`. Skill stays in the fork; activate when the first headless use case appears (likely when the auto-review hook gets wired up).
- **`council-review`.** Multi-model validation council for plans/architecture/PRs. Overlaps with our `/arbiter` + multi-engine review via suggestion-gate. Skill stays for reference; activate if the suggestion-gate's multi-engine path proves underweight for genuinely consequential changes.
- **`autonomous-testing`.** Auto-discovers/generates/executes/fixes tests. Exactly the heavy machinery the suggestion-gate exists to gate. Don't auto-run; offer through the suggestion-gate as one of the options when testing work comes up. Trial activation during dogfood if a test-generation moment surfaces.

---

## Project Profiles

Profiles are how Tessera adapts to different kinds of projects without forcing one shape on all of them. A project declares its profile in `.tessera/project.yml`; Tessera reads the file at session start and activates the relevant extensions. Non-matching projects pay none of the overhead.

### Profiles available initially

- **`standard` (default)** — baseline Tessera. No specialized activations. Most projects sit here.
- **`healthcare`** — adds the substantive HIPAA-aware extensions (PHI marker detection, hard-gate behavior on PHI-touching code, bumped encryption defaults, healthcare-specific incident response templates, BAA scope tracking).
- Additional profiles may emerge: `financial` (PCI/SOX patterns), `client-work` (stricter audit defaults), etc. Profiles are additive bundles of extensions; new ones can be added without disrupting existing projects.

### Activation mechanism

- **First-session prompt at project incept.** When Tessera opens a project with no `.tessera/project.yml`, it suggests a profile based on lightweight signals (e.g., FHIR/HL7 libraries → healthcare suggestion). Single-keystroke pick from the list. Tessera writes the file; no manual YAML editing required.
- **Profile switching via command:** `tess profile show`, `tess profile switch healthcare`, `tess profile list-extensions`. The file is updated by Tessera, not by hand.
- **`.tessera/project.yml` checked in by default.** Reasons: reproducibility across machines, team coordination if the project is ever shared, audit trail via git for free, PR review visibility into what gates were in force. For sensitive open-source-bound projects, a `.tessera/project.yml.template` pattern (like `.env.example`) *would be* the opt-in. **Not built** — every project is private, so the profile field leaks nothing. Deletion candidate, not a build candidate.
- **Tuning values live separately in `.tessera/config.yml`.** **Built 2026-07-11**, but *not* as the profile-override layer this doc originally imagined — there is still only one profile, so there is nothing to override. It was built bottom-up from one observed failure: an agent must never have to **guess the test command**. On this machine bare `python3` is Homebrew 3.14, which has no pytest (F-001's interpreter split); a human guesses wrong once and recovers, an unsupervised agent (ADR-0005) concludes the suite is broken and acts on it. One key (`test:`), one consumer (`bin/tessera-test`), zero speculative knobs. **Committed, not gitignored** — a test command that vanishes on a fresh clone is useless to the agent it exists for. The template that preceded it shipped six knobs and every one was dead; see observatory → "The profile model has no consumer."

### Audit asymmetry

Whether profile changes are audited depends on the profile itself, not a global setting:

- **`standard` profile changes:** not audited. No overhead for hobby/exploratory work where you're flipping things around freely.
- **`healthcare` profile changes:** audited (entry written to structured log: timestamp, from-profile, to-profile, reason if provided).
- **Asymmetric friction.** Going *up* a tier (standard → healthcare) is frictionless — you're adding constraints. Going *down* (healthcare → standard) produces a warning and requires confirmation — you don't accidentally downgrade out of a stricter posture.

### Detection-as-suggestion

Tessera may detect signals at incept (FHIR/HL7 libraries, "patient" or "PHI" in `_project_specs/`, healthcare-specific dependencies) and *suggest* a healthcare profile rather than the standard default. Detection guides the suggestion; it doesn't decide. The user always picks.

### The healthcare profile, in summary

Substantive enough to count as original IP. Activates the specific behaviors detailed in **Pass 4.5 — Healthcare Profile (Additive Extensions)**. Skim there for the full inventory.

---

## Framework Evaluation as Ongoing Practice

A framework that never reckons with the outside world ossifies. Tessera has a structured mechanism for evaluating external tools, frameworks, libraries, and patterns — and for documenting the results so the trail of reasoning survives.

### The mechanism

Three artifacts work together:

- **`skills/framework-evaluation/SKILL.md`** — the methodology. Six dimensions, ~20 questions. Identity & maturity, problem-space overlap, integration cost, pattern-vs-implementation, lock-in & maintenance, decision. Explicit anti-patterns (confirmation bias, sunk-cost protection, excitement bias, familiarity bias, single-dimension judgment, skipping the re-evaluate trigger).
- **`/evaluate-framework <target>`** — slash command that invokes the methodology. Target can be a repo URL, project name, pattern/concept, or prior ADR for re-evaluation.
- **`docs/adr/`** — Architecture Decision Records following the template at `_template.md`. Each ADR is numbered sequentially, dated, and committed. Once accepted, ADRs are not edited — superseded by new ones if decisions change.

### When evaluations fire

- **Cadence-based:** quarterly review of the agentic coding landscape (or whenever the prompt comes up)
- **Contact-based:** new tool, framework, or pattern enters awareness
- **Trigger-based:** a prior ADR's re-evaluate condition has fired
- **Decision-based:** a new project raises the question of which tool to use

### Status values for ADRs

- **Proposed** — being drafted; not yet committed
- **Accepted** — decision is settled, 90-day default cadence to next review
- **Watching** — explicitly deferred; "watching for" condition named; 60-day default cadence to next check
- **Superseded by ADR-NNNN** — a later ADR changed this decision
- **Deprecated** — no longer relevant (rare)

"Watching" is the realistic default for many evaluations. The world rarely produces clean yes/no answers. "Watching with named condition" is more honest than forcing premature commitment.

### Why this matters

Three benefits worth being explicit about:

1. **Decisions get documented.** When you ask "why didn't we use X?" six months from now, you have an artifact: *"Evaluated X on date Y. Decided not to adopt because [reasons]. Would re-evaluate if [conditions]."* You don't relitigate the question every time.
2. **The methodology forces honesty.** Building the skill *before* running it on a target means committing to the questions upfront. If a target passes the questions and Tessera doesn't, the skill surfaces that. You can still decide to continue with Tessera, but it's a deliberate choice rather than momentum.
3. **Re-evaluate triggers are real.** A decision without trigger conditions becomes a decision made forever. Naming what would change your mind keeps the framework honest about its own evolution.

### The Observatory complements ADRs

ADRs capture decisions made. The Observatory (`docs/observatory.md`) captures things on the radar that haven't been decided. Lighter than an ADR — a junk drawer with structure.

- **Observatory entry** = "We noticed this pattern, want to remember it exists, no commitment."
- **ADR** = "We made a decision about this. Final until superseded."

Without the Observatory, the failure mode is: months from now you vaguely remember "GSD had a thing about drift detection" but no record of where, and you either rediscover it or skip it. The Observatory is the index of "things on our radar."

Entry status values: Investigating / Pending eval / Adopted (link to ADR) / Rejected (link to ADR) / Watching. Entries flow Observatory → Pending eval → ADR when evidence justifies. Or stay in the Observatory indefinitely, which is also fine.

### First worked example: ADR-0001 (Open GSD)

The first ADR is the evaluation of **Open GSD** (gsd-core), which surfaced during install when the existing global `~/.claude/` setup turned out to contain GSD's hook infrastructure.

**Verdict: Adopt patterns (substantial), keep Tessera as the host framework.** See `docs/adr/0001-gsd-evaluation.md` for the full evaluation.

**Concepts adopted (with implementation notes):**

- **Thin-orchestrator with fresh-subagent isolation, as a Tessera capability gated by suggestion-gate (#12).** Heavy work flows through orchestrator with clean per-task contexts. Light work stays in main session. Implementation is staged — ship dogfood with current design first, layer in orchestrator capability if evidence justifies (~5-6 core agent types).
- **File-based decision-and-output artifacts** augmenting the existing audit log. Capture decisions and outputs as durable structured artifacts (CONTEXT-style per phase), not just events.
- **Package Legitimacy Gate** as Tessera baseline (not healthcare-only), using slopcheck (MIT, pip-installable). Real attack surface — slopsquatting affects any AI-assisted project, ~20% of AI-generated package references are hallucinated.
- **Plan Drift Guard** concept for the pipeline pattern — verify symbol references in generated plans against live source before execution.
- **Byte-budget concept** for workflows and skills as protection against attention degradation.

**Concepts deferred to Observatory:** Two-stage hierarchical routing, cross-runtime translation layer, parallel-commit safety patterns, thinking-models-specific prompts, capability registry pattern. Each has a "watching for" condition recorded.

---

## Pass Decisions (as we read)

Decisions made when reading specific skills. Adopt/adapt/reject calls and the reasoning behind them.

### Pass 1.1 — `base.md`

**Adopt verbatim:**
- Core principle: complexity is the enemy.
- Functional core / imperative shell architecture.
- Anti-patterns list (global state, magic numbers, deep nesting, dead code, large PRs, mixing refactoring with features).
- TDD four-phase workflow: RED → GREEN → VALIDATE → COMPLETE.
- Bug-fix discipline: write a failing regression test before fixing.
- Fail-fast error handling, parameterized queries, secret hygiene, pre-commit hooks.

**Adapt:**
- **Simplicity rules become guidelines, not gates.** "Target 20 lines per function, 200 per file; if significantly over, ask whether decomposition helps." Drop the "STOP and split" enforcement language.
- **Atomic todo format simplified for solo work.** Title, description, acceptance criteria, validation. TDD execution log table available when running formal loops, not required per todo.
- **`_project_specs/` directory layout is recommended, not enforced.** Lorenzo's existing Obsidian vault may serve the same role; structure should fit existing patterns.
- **80% coverage as default target, not hard gate.** Project-aware — config and glue may not need 80%; business logic may want 95%+.

**Reject:**
- **Ralph Wiggum auto-loop as default.** Heavy iterative ceremony for "any non-trivial task" is exactly the ceremony Tessera rejects. Replaced with the suggestion-gate pattern below.
- **Auto-transformation of user requests.** Silently wrapping "add forgot password" in a 25-iteration Ralph prompt removes agency.
- **Mandatory multi-phase bug fix ceremony for every bug.** Sometimes a bug is one line + one test; DIAGNOSE/RED/GREEN/VALIDATE phase logging is theater for trivial fixes. Keep the *discipline* (regression test before fix); drop the *ceremony*.

**New / replaces upstream:** **Suggestion-gate for heavy machinery.** Replaces auto-Ralph. Claude evaluates whether iterative-loop machinery would help, surfaces a brief recommendation (what the loop would do, completion criterion, estimated iteration count), and waits for accept/decline/modify. Three configurable knobs:
- `suggest_threshold: high | medium | low | off` (default: medium)
- `max_iterations_default: 20`
- `auto_accept_for: []` — patterns where suggestion is skipped and loop runs directly (probably empty for dogfood; useful for org rollout)

**Observation worth carrying forward:** the `_project_specs/session/` structure in base.md is itself markdown-based session memory. Mnemos and the Obsidian-vault approach may be closer cousins than the design doc framed — possibly "Mnemos's typed graph layer on top of vault" vs "vault alone." Confirm when reading `mnemos.md` in pass 1.4.

### Pass 1.2 — `iterative-development.md`

The Ralph machinery itself is well-designed; pass 1.1's adaptation (suggestion-gate, not auto-invoke) preserved everything valuable. Most of this skill adopts cleanly.

**Adopt as-is:**
- The Ralph mechanic: Stop hook + same-prompt feedback + completion-promise/max-iterations exit. Simple and clever.
- All four prompt templates (feature development, bug fix, refactor, API). These become the *content* offered by the suggestion-gate.
- Prompt-writing rules: clear completion criteria, max iterations, TDD discipline, break into phases, include fallback behavior.
- The "When to use / not good for" calibration table. Encodes the suggestion-gate's threshold logic.
- Anti-patterns list, including "lying to exit."
- Monitoring/control commands and state file location.

**Promote (generalize beyond Ralph):**
- **Error classification.** Distinguish what the agent can fix (code, type, test errors → continue) from what only the human can fix (access, permission, environment, network → stop and report). This pattern applies anywhere Claude works autonomously, not just inside Ralph loops. Promote from "Ralph-only" to a Tessera-wide pattern.
- **Blocker report format.** Same generalization — any autonomous work that hits a human-required blocker uses this format to hand off cleanly.

**New / Tessera enhancement:**
- **Post-promise verification.** After `<promise>DONE</promise>` is detected, run an independent verification step (tests + lint + coverage) before declaring the loop complete. Closes the "lying to exit" anti-pattern that upstream names but doesn't solve. Don't trust the promise; verify.

**Light adaptation:**
- Section "Integration with Claude Bootstrap" → "Integration with Tessera."
- "Todo integration" subsection slims down to match the simplified atomic-todo format from pass 1.1 (drop the TDD execution log table requirement; keep it available for formal loops).

**Integration with the suggestion-gate (pass 1.1):** the four templates here *are* the suggestion-gate's offered content. When the gate fires, the suggestion references one of these directly — *"This looks like a feature-dev task; I'd use the feature template with these completion criteria. Estimate ~15-20 iterations. Run it, modify, or keep going interactively?"* The templates and the gate are designed for each other.

### Pass 1.3 — `agent-teams.md`

This is org-rollout machinery. The 10-stage pipeline (spec → spec-review → tests → RED-verify → implement → GREEN-verify → validate → code-review → security → branch+PR) and 6-agent roster (team-lead, quality, security, review, merger, feature-x per feature) are designed for parallel feature development at team scale. For solo dogfood, the patterns survive but the multi-agent orchestration doesn't.

**External context:** Anthropic released native Agent Teams with Claude Opus 4.6 (Feb 2026, `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`). When Tessera reconstitutes multi-agent flows for org rollout, use the native primitive as foundation; Maggy's role definitions layer on top. Don't reimplement multi-agent orchestration in markdown.

**For dogfood — adopt the patterns, not the orchestration:**

- **10-stage pipeline as a suggestion-gate-offered template.** When the gate detects a feature-scale task, offer "run through the feature pipeline? Spec → tests → RED verify → implement → GREEN verify → validate → review → security → branch+PR. Single Claude session, you can stop or modify at any stage." Accept/decline/modify.
- **Single session runs the pipeline as a structured prompt sequence.** No agent spawning during dogfood. The TDD Stop hook already enforces RED/GREEN; the other stages run as explicit prompt steps.
- **Read-only reviewer enforcement becomes a Tessera-wide pattern** (added as compounding principle #13). When Claude is in review mode — code review, security scan, spec review — it operates without write tools. Generalizes beyond multi-agent context.
- **Merger discipline as rules, not an agent.** "Never `git add -A`" (always stage by file). "Never merge automatically" (always create PR for human merge). "One branch per feature." Apply whenever Claude does git operations.
- **Multi-engine code review (Claude/Codex/Gemini) is suggestion-gate-offered, not default.** "This change looks consequential — want a multi-engine review pass?" Connects naturally to the `/arbiter` command design.
- **Preserve the "spec completeness review" stage even in solo mode.** A reviewer pass on the spec before tests get written catches ambiguity before it becomes wasted code. Cheap and valuable.

**Pipeline enforcement spec (implementing principle #14):**

When the suggestion-gate offers a pipeline and the user accepts, the pipeline runs all stages without the agent deciding to skip. Implementation:

- **Each stage produces a named artifact** at a known location (e.g., `.tessera/pipeline/<feature>/01-spec.md`, `02-spec-review.md`, `03-tests.md`, etc.).
- **The next stage's prompt only loads if the previous stage's artifact exists** and contains valid output (not an error or empty file). This is structural enforcement — the agent literally can't see the next stage's prompt until the previous artifact is written.
- **"No findings" and "not applicable" are valid stage results,** but they still produce an artifact. `02-spec-review.md` saying "reviewed the spec, no issues, proceed" is a valid completion. Skipping the file entirely is not.
- **Verification step at the end** confirms all expected artifacts exist before declaring the pipeline complete. Missing artifacts = pipeline failed, no completion promise emitted (closes the post-promise verification gap from pass 1.2).
- **Explicit human escape: `--abort` flag** stops the pipeline at any stage. The agent has no equivalent. If something is going wrong, the human decides; the agent doesn't get to.
- **Pipeline state is persistable.** If a session crashes mid-pipeline, the artifacts already written tell Tessera where to resume. Connects naturally to whatever wins the Mnemos trial.

**For org rollout — deferred but planned:**

- Use Anthropic's native Agent Teams when activating multi-agent flows. Maggy role definitions become a layer on top of the native primitive.
- The structural-ordering-via-task-dependencies pattern is the most valuable org-scale idea here. Preserve carefully when reconstituting — *deviation made impossible by capability* is stronger than *deviation discouraged by rule*.

**Rejected:**

- **"This is the default workflow, not optional."** Same auto-invocation pattern rejected in pass 1.1. Opt-in via suggestion-gate.
- **"No step can be skipped" as hard enforcement for solo work.** Guidance for solo, structural enforcement only when multi-agent orchestration is active.

**Pass-forward observation — meaningful revision to the GitNexus/iCPG trial:**
The agent-teams skill describes iCPG as tracking *ReasonNodes* (intent), *constraints/risk* (queried by feature agents), and *drift* (checked by quality agent). This is broader than "code structural knowledge." **iCPG and GitNexus may be complementary, not alternatives.** GitNexus excels at structural knowledge (calls, imports, blast radius); iCPG appears to add an *intent* layer on top. Revising the design doc: don't pre-rule against iCPG; read `icpg.md` in pass 1.5 with fresh eyes and see whether the intent-tracking is the real value or vapor.

### Pass 1.4 — `mnemos.md` (re-read after fetching actual file)

**The actual skill is stronger than the synthesis indicated.** Walking back several skepticism flags.

**What Mnemos actually does:**
- **Typed MnemoGraph with per-type eviction policies.** GoalNodes and ConstraintNodes never evicted; ResultNodes compressed before eviction; ContextNodes evictable when activation drops; CheckpointNodes persist to disk. Deliberate design — different node types have different value density.
- **Three-layer post-compaction defense.** PreCompact writes marker + preservation instructions inline → SessionStart "compact" hook is the primary re-injection path → PreToolUse fallback handles the edge case where SessionStart doesn't fire. Honest acknowledgment that Claude Code's compaction is unreliable enough to warrant fallback-to-fallback.
  - **Correction (2026-07-09).** Three layers do exist, but Layer 2 is not what this note (or the skill) said. There is no `mnemos-compact-recovery.sh` and no SessionStart `"compact"` matcher — neither has ever existed in this repo or in `~/.claude/templates/`. Layer 2's role is played by `mnemos-session-start.sh`, wired to an *unmatched* SessionStart, which therefore fires on `compact` along with `startup`/`resume`. Coverage is intact; the naming was wrong. Verified while gathering evidence for the Mnemos kill/keep trial.
- **Fatigue model with concrete signals.** Token utilization (40%), scope scatter (25%), re-read ratio (20%), error density (15%). Five fatigue bands (FLOW / COMPRESS / PRE-SLEEP / REM / EMERGENCY) trigger different actions (micro-consolidation, checkpoint, emergency handoff). The labels are cute; the underlying mechanism is *measure four behavioral signals, act on accumulation*. Reasonable engineering — walk back the earlier "kooky" framing.
- **Claude transcript ingestion + haziness scoring.** Ingests `~/.claude/projects/` JSONL transcripts on Stop hook. Stores only structural fields and 200-char redacted previews; secrets redacted before disk. Composite score over five dimensions (correction_density, redo_ratio, first_try_error_rate, orphan_tool_use_rate, backtrack_norm) maps to bands (clear/cloudy/hazy/lost). **This is exactly the kind of session-quality signal Tessera wants for dogfood evaluation.** Missed in the synthesis.
- **Storage is local + gitignored.** `.mnemos/mnemo.db` (SQLite) + supporting files. Per-project opt-out via `touch .mnemos/claude-log.disabled`.

**Revised decisions:**

- **Adopt Mnemos for dogfood with high confidence.** The earlier "narrow trial" framing was too cautious — this is more sophisticated than indicated, and the haziness scoring alone could be worth the install.
- **Trial criteria during dogfood:**
  - Does it fire and recover on real compaction events?
  - Do the haziness scores correlate with sessions that actually felt rough? (Honest test of whether the metric is useful.)
  - Does the fatigue-triggered consolidation/checkpoint behavior produce useful interventions or annoying interruptions?
- **The haziness scoring becomes a Tessera-wide signal**, not just Mnemos-internal. Use it to evaluate trial decisions across all of pass 1 ("did the suggestion-gate calibration produce clearer sessions? Did the read-only reviewer principle reduce haziness?"). Real measurement, not impression.
- **iCPG bridge is real and concrete.** `mnemos bridge-icpg` imports active ReasonNodes as GoalNodes, postconditions/invariants become ConstraintNodes. Two-way integration — Mnemos holds session state, iCPG holds code intent, they reference each other.

**Crowded-landscape note:** the persistent-memory-for-Claude-Code space has exploded. Multiple unrelated tools named "Mnemos" exist (a Go binary, a PyPI package `mnemos-memory`, an `mnemos-os/mnemos` GitHub org), plus Engram, Ori-Mnemos, claude-mem, claude-brain, claude-graph-memory, and native Claude Code memory features. **For org rollout, evaluate Maggy's Mnemos against at least one external alternative.** For dogfood, Maggy's Mnemos is fine since it's already in the stack.

### Pass 1.5 — `icpg.md` and `code-graph.md` (re-read after fetching actual files)

**Biggest correction of the whole pass.** iCPG is more concrete and rigorous than the synthesis suggested. Walking back significant skepticism.

**What iCPG actually is:**
- **Architecture is explicit.** iCPG = AST + CFG + PDG + RG (Reason Graph). The first three are standard code property graph layers; the Reason Graph is the novel addition. Not a replacement for code structure — a layer *on top of* it.
- **The 6 drift dimensions are all named with detection mechanisms:**
  - *Spec drift* (symbol checksum changed without a MODIFIES edge)
  - *Decision drift* (postconditions no longer hold)
  - *Ownership drift* (>3 owners without coherent oversight)
  - *Test drift* (VALIDATED_BY tests missing/failing)
  - *Usage drift* (symbol used outside original scope)
  - *Dependency drift* (downstream REQUIRES reasons have drifted)
  - All concrete, all detectable. Walk back "over-engineered" framing.
- **The 3 canonical pre-task queries are real CLI commands:** `icpg query prior` (duplicate detection), `icpg query constraints <file>` (invariants for files about to be touched), `icpg query risk <symbol>` (fragility profile including drift history). Concrete, not vague.
- **ReasonNode schema is well-defined.** UUID, goal, decision_type (business_goal/arch_decision/task/workaround/constraint/patch), scope, owner, status, source, plus a formal Design-by-Contract trio (preconditions, postconditions, invariants).
- **Contract predicates have actual types.** `file_exists("path")`, `test_exists("path")`, `symbol_count("dir") <= 15`, `function_signature("name") == "..."`. Evaluable, not hand-wavy. Three authoring tiers: hand-authored for high-risk intents, LLM-inferred via `icpg create --infer-contracts`, or heuristic (scope → file_exists, test → test_exists).
- **Six edge types:** CREATES, MODIFIES, REQUIRES, DUPLICATES, VALIDATED_BY, DRIFTS_FROM.
- **Bootstrap from git history exists** for existing codebases (`icpg bootstrap --days 90`), with honest epistemic posture — inferred intents get `confidence: 0.6-0.8`, marked for manual promotion.
- **Storage is local + SQLite, zero-deps install possible.** `.icpg/reason.db`. Optional ChromaDB for vector duplicate detection; TF-IDF fallback otherwise.
- **Hook integration is concrete.** PreToolUse on Edit/Write shows intent + constraints + preservation guidance before every edit. Stop hook auto-records symbols after tests pass.

**What code-graph actually is:**
- Maggy's structural-knowledge layer, via `codebase-memory-mcp` MCP server. **14 MCP tools, 64 languages, sub-ms queries, auto-fresh via file watcher + session-start auto-index + post-commit hook.**
- Tools include: `search_graph`, `search_code`, `get_code_snippet`, `query_graph`, `trace_call_path`, `detect_changes`, `get_architecture`, plus indexing/management. ~99% fewer tokens for navigation vs brute-force file reads.
- **"Graph first, file second" is the operating principle** — only read files when modifying or needing context beyond what the graph provides. This matches Trask's "use the right neurons not all neurons" principle applied locally.
- **Auto-update is genuinely polished** — three layers keep the graph fresh without manual intervention.

**Revised decisions:**

- **Adopt iCPG for dogfood with higher confidence than before.** The earlier skepticism was largely misplaced. The remaining open questions are *behavioral* not *conceptual* — does the agent actually populate ReasonNodes and contracts well in practice? Does drift detection catch things grep wouldn't? Real questions, answered by dogfood, not by skepticism.
- **Adopt code-graph as the continuously-loaded structural layer for active development on familiar code.** Auto-fresh via three-layer sync. This is the workshop view for code you're actively writing.
- **GitNexus is reserved for unfamiliar-codebase evaluation, not default install.** Strong fit for onboarding, vendor due diligence, legacy rescue, forensic analysis. Install when first such task arises, not preemptively. Code-graph and GitNexus serve different temporal phases of work (active development vs evaluation), not the same problem.
- **The "Workflow: Before Any Code Change" sequence from iCPG.md becomes a Tessera principle:** *Intent → Dedup → Constraints → Risk → Locate → Change → Record → Drift-check → Verify.* This is the actual procedural value of having iCPG — a defined sequence that prevents duplicate work and unintended drift.
- **The "Workflow: Before Any Code Change" from code-graph.md complements it:** *Plan → Locate → Understand → Blast → Trace → Change → Verify.* Tessera's planning step queries both layers — code-graph for structure, iCPG for intent.
- **Telos / IFS scoring stays opt-in via suggestion-gate.** Re-read of the skills didn't include Telos directly; per Maggy README it's the measurement layer on top. Multiplicative scoring still feels brittle as a continuous signal. Reserve for explicit invocation, not default.

---

## Pass 1 Wrap-up: Cross-Cutting Patterns

Five skills read (`base`, `iterative-development`, `agent-teams`, `mnemos`, `icpg`). Patterns that emerged across the pass, worth carrying forward into pass 2 (rules layer) and beyond.

**1. The framework's core values land; the execution often over-reaches.** TDD discipline, complexity-as-enemy, anti-patterns, fail-fast — all good. But hard line limits, mandatory pipelines, "this is not optional" framing, and auto-invocation are the consistent failure modes. The pattern: keep the values, reject the rigidity.

**2. Auto-invocation is the recurring anti-pattern.** Mandatory Ralph for "any non-trivial task." "This is the default workflow, not optional." Same shape across multiple skills. The **suggestion-gate (principle #12)** is the cross-cutting answer — Tessera proposes heavy machinery; the user disposes.

**3. Native primitives have caught up.** Anthropic Agent Teams (Feb 2026) covers much of Maggy's agent-teams. Native compaction + `/rewind` covers some of what Mnemos insures against. `/goal` and `/batch` cover lighter versions of Ralph and Polyphony. Maggy was prescient when conceived but the underlying tool has evolved. *Default to native; reach for Maggy's machinery when it earns its keep.*

**4. The "alternatives" framing kept being wrong.** Three times in pass 1 I framed something as A vs B and it turned out to be A + B addressing different problems:
- iCPG vs GitNexus → structural + intent (complementary)
- Mnemos vs Obsidian → crash recovery + human-readable knowledge (complementary)
- Agent teams vs single-Claude → org-scale + solo (modes, not alternatives)

The pattern: when in doubt, ask "are these solving the same problem or different problems?" before assuming a trial-and-pick.

**5. The lifecycle hooks are infrastructure, not features.** PreCompact / PreToolUse / PostToolUse are useful for many concerns beyond memory — audit logging, PHI detection, compliance gating, healthcare audit trails. Mnemos uses them for one purpose; Tessera should treat them as reusable infrastructure.

**6. Two new compounding principles emerged:**
- **#12 — Heavy machinery is suggested, not silent.**
- **#13 — Reviewers operate read-only.**

Both are now baked into the principles list and apply across passes 2-6.

**7. Honest limitations.** Two skills (`mnemos.md`, `icpg.md`) couldn't be fetched in full at first read. Decisions revised in passes 1.4 and 1.5 after the actual files arrived — synthesis from indirect sources had missed real specifics. *Lesson carried forward: when synthesis is the only option, flag it loudly and revisit when the actual files are available.*

---

## Pass 2 — Rules Layer

The rules are far smaller and tighter than the pass 1 skills — ~80 lines total across six files. They're declarative, path-glob-targeted via frontmatter, almost entirely advisory in tone. **Most adopt as-is**, with one structural addition Tessera needs (override mechanism) and a few healthcare-layer augmentations that extend rather than modify.

### Pass 2.1 — `quality-gates.md`

Six-row table of hard limits (20 lines/function, 3 params, 2 nesting levels, 200 lines/file, 10 functions/file, 80% coverage). The rigid framing from pass 1.1's base.md analysis appears in its purest form here ("split or decompose immediately"). Apply the same adaptation:

- **Reframe as targets, not gates**, with judgment guidance. Numbers stay; enforcement language softens.
- **80% coverage stays as project-aware default**, not universal hard gate (per pass 1.1).

### Pass 2.2 — `tdd-workflow.md`

Five lines plus header. RED-GREEN-VALIDATE three-phase (drops base.md's fourth COMPLETE phase — fine, completion tracking belongs in todo management). The principle distilled: *"Tests must fail first to prove they validate the requirement. No code ships without a test that failed first."*

**Cleanest expression of TDD discipline in the entire framework. Adopt almost verbatim.** The only addition is post-promise verification from pass 1.2 — independent check that tests actually pass, not just that completion was claimed.

### Pass 2.3 — `security.md`

Seven non-negotiables (no secrets in code, no client-exposed secret env vars, `.env` gitignored, parameterized queries, bcrypt 12+/argon2, validate at boundaries with Zod/Pydantic, `.env.example` with no values).

**Adopt as baseline. Healthcare layer extends purely additively** — no existing rule needs revision. Additions when healthcare layer activates:
- PHI marker detection patterns
- Compliance routing rule ("PHI markers → local model")
- Audit logging requirement (ties to Logging & Auditability section)
- HIPAA-specific identifier pattern matching
- bcrypt rounds bumped to 13-14 for healthcare contexts

### Pass 2.4 — Language rules (`typescript.md`, `python.md`, `nodejs-backend.md`)

Short bullet lists of stack-specific conventions. All sensible defaults:
- **TS:** strict mode, interfaces over type aliases, discriminated unions, no `any`, Zod for runtime, `const`/`let` (never `var`)
- **Python:** type hints, Pydantic, pytest, ruff, mypy, dataclasses/Pydantic over dicts, pathlib over os.path
- **Node backend:** Express/Fastify with typed handlers, repository pattern, Zod at routes, structured logging (pino/winston), async error middleware

**Adopt all three as-is.** Healthcare-layer additions when activated: nodejs-backend gets audit logging on data-access operations; python gets PHI redaction in log statements. Both additive, not modifications.

### Pass 2.5 — `react.md`

Same shape as the other language rules. Six bullets: functional components with hooks, React Query / TanStack Query for server state, Zustand or context for client state, colocated tests (`ComponentName.test.tsx`), extract custom hooks when logic is reused, avoid prop drilling beyond 2 levels (use context or composition).

**Adopt as-is.** No surprises; matches the pattern. The 2-level prop-drilling guideline is a nice concrete number — most "avoid prop drilling" advice is hand-wavy. Healthcare layer doesn't add anything React-specific (PHI handling lives in the backend rule, not the React rule).

### New Tessera Pattern — Rule Override Mechanism

Upstream rules have no override path. Hard rules with no exceptions is a stricter posture than most production codebases, and the exceptions get made anyway — they just get hidden in PR discussions instead of stated in code. Tessera adds an honest mechanism:

- **Inline annotations:** `// tessera:quality-gates-ignore-line`, `// tessera:security-skip-reason="legacy migration to ORM"`, `# tessera:tdd-skip-reason="dependency injection scaffolding"`
- **Audit-logged when used.** Every override fires an event in Tessera's structured log: rule, file, line, reason, timestamp, session-id. Connects to Logging & Auditability section.
- **Periodic review.** `tess overrides report --since 1w` surfaces all overrides used recently. Healthcare layer extends this to required compliance review.
- **No bypass for security-critical rules.** Some rules (no secrets in code, parameterized queries) cannot be overridden inline — those require explicit configuration in a `.tessera/security-exceptions.yml` file with named owner and review date. Stricter path for stricter invariants.

### Cross-cutting observations from pass 2

- **Rules don't need the suggestion-gate.** Rules are *invariants* that fire silently; suggestion-gate is for *heavy machinery* deciding what to do. Different layers, no integration needed.
- **Coverage threshold (80%) appears in both `quality-gates.md` and `tdd-workflow.md`** — different roles, not redundancy. Quality-gates defines *what* the threshold is; tdd-workflow defines *when* it's checked. Tessera keeps both, explicit about the relationship.
- **Healthcare layer is purely additive across all rules.** No existing rule needs revision for HIPAA. Cleaner than hoped.
- **The rules layer is smaller than the suggestion-gate spec.** ~80 lines of rules vs the multi-section suggestion-gate design. Worth keeping in mind for Tessera's overall shape — small focused files, principles that bridge them.

### Pass 2 Wrap-up: handoff to pass 3

Pass 2 lands cleanly because rules are the simplest layer of the framework. Three things worth flagging for pass 3 (hook scripts):

1. **The hook scripts implement the rules.** TDD Stop hook implements `tdd-workflow.md` enforcement. PreCompact/SessionStart-compact hooks implement Mnemos's compaction recovery. PreToolUse hooks inject iCPG context and check fatigue. *The hook layer is where the abstractions become real behavior.*
2. **Quality of upstream hook code matters more than quality of skill prose.** Skills and rules are markdown — easy to read, easy to adapt. Hooks are bash/Python — harder to read, but they're what actually runs. If hooks are buggy, the whole framework is buggy regardless of how clean the prose is.
3. **The override mechanism we just designed needs hook integration.** Annotation parsing and audit logging will live in hooks. Pass 3 is where that becomes concrete.

---

## Pass 3 — Hooks Layer

**Bottom line: hook code quality is good.** Defensive, async where appropriate, graceful degradation, atomic file operations where needed. Not toy code — pragmatic engineering. A few real concerns for Tessera adaptation, but no "this is broken" red flags.

### Pass 3.1 — Settings.json orchestration

The Stop hook chain has **5 hooks in sequence**, totaling ~3 minutes potential post-processing per Claude turn (most runs much faster):
1. `tdd-loop-check.sh` (60s timeout)
2. `codex-auto-review.sh` (120s, conditional on codex installed — returns instantly if not)
3. `icpg-stop-record.sh` (5s)
4. `mnemos-stop-checkpoint.sh` (5s)
5. `mnemos-stop-ingest.sh` (10s, fire-and-forget with `disown`)

PreCompact has 1 hook (Mnemos preservation), PreToolUse has 2 (post-compact inject fallback + Edit|Write fatigue/intent check), PostToolUse has 1 (signal logging), SessionStart has 1 (Mnemos recovery).

**Permissions section is well-designed:** allow list for safe commands (tests, lint, typecheck, gh CLI, all icpg/mnemos/polyphony tools); deny list for dangerous patterns (`rm -rf`, `git push --force`, `git reset --hard`, all `.env` writes/edits). Tight and correct.

**Hook lookup pattern is graceful:** project-local `.claude/scripts/` → global `$HOME/.claude/templates/` → stderr warning + exit 0. Never silent fail, never block user.

### Pass 3.2 — Architectural strengths to adopt

**Mnemos three-layer compaction defense is real engineering.** The cleverest piece: PreCompact's stdout becomes *summarizer instructions*. The hook literally writes prompts like "INCLUDE THIS VERBATIM" and the compaction summarizer obeys. This is the operational mechanism behind the typed-node eviction policies — implementation matches documentation.

> **Correction (2026-07-09).** "Implementation matches documentation" was wrong, and wrong in the direction this pass was least equipped to catch: the docs named a Layer 2 script (`mnemos-compact-recovery.sh`) that does not exist. Reading hook *prose* cannot verify hook *wiring* — a pass-3 read of the scripts confirmed the mechanism but never checked that every named file was on disk. The defense-in-depth is real; one of its three layers was misattributed for ~6 weeks. Lesson: when a doc claims N layers, `ls` all N.

**Fatigue data pipeline is well-structured:**
- statusline hook → `fatigue.json` (token data, 40% of fatigue model)
- pre-edit hook → `signals.jsonl` (scope scatter 25% + re-read ratio 20%)
- post-tool hook → `signals.jsonl` (error density 15%)
- `compute_fatigue()` reads both, produces composite, drives hook decisions (checkpoint at pre_sleep+, consolidate at compress+)

**Reusable patterns Tessera adopts as infrastructure:**
- **Marker file + atomic rename** for cross-event coordination
- **Fast-path/slow-path split** — existence check is ~5ms; full work only when needed
- **Fire-and-forget background** for non-blocking Stop hooks (`&` + `disown`)
- **Graceful degradation chain** — binary → module → fallback → no-op
- **Hook lookup with fallback** — project-local → global → stderr warning + exit 0

The `tdd-loop-check.sh` **25-iteration safety cap** is the smartest single bit. Without it, an agent that keeps failing tests gets trapped (Stop hook feeds failure back, Claude tries again, infinite loop). The counter breaks it after 25 iterations.

### Pass 3.3 — Concerns for Tessera adaptation

**Hard-coded toolchain assumptions in `tdd-loop-check.sh`:**
- npm-only for Node (no yarn/pnpm/bun detection)
- `npm test` as fixed command (no script name override)
- `tsc --noEmit` for typecheck only
- **Trivial bug:** no `command -v pytest` check in Python branch (fails confusingly if pytest missing)

**Tessera version generalizations:**
- Package manager detection (npm/yarn/pnpm/bun)
- Test/lint/typecheck commands configurable via `.tessera/config.yml` *(`test:` built 2026-07-11 and read by `bin/tessera-test`; lint/typecheck not built — no consumer yet)*
- Per-project timeout override
- Monorepo support via workspace patterns

**Embedded Python in bash is fragile.** `mnemos-pre-compact.sh` writes Python heredocs to temp files because bash + Python f-string + JSON quoting is a nightmare. Maintenance-hostile. **Tessera lifts these into separate `.py` files called from bash.**

**Two parallel iCPG pre-edit hooks exist** (`templates/icpg-pre-edit.sh` standalone, plus iCPG-section inside `templates/mnemos-pre-edit.sh`). They use *different input conventions* (env var vs stdin). The settings.json wires the integrated version. **Tessera unifies these** — one hook, one input convention, no dead-code confusion.

**Tight schema coupling to internal JSON.** Hooks parse `.mnemos/checkpoint-latest.json` directly with specific field names. If Mnemos changes its schema, hooks break silently. **Tessera version uses versioned schema with explicit validation.**

**No structured logging output.** Everything goes to stderr/stdout. **Tessera wires hooks into the structured event log** from the Logging & Auditability section. Each hook emits JSON Lines events to `.tessera/logs/<session-id>.jsonl` capturing: event type, source, structured data.

**Override mechanism (pass 2) needs hook integration.** Annotation parsing for `// tessera:tdd-skip-reason=...` needs to be added to `tdd-loop-check.sh`. Audit-log entry on every override use. — **DONE (2026-06-26).** `scripts/override/{scan,emit,report}.py` + `docs/contracts/override-event.md`; `tdd-loop-check.sh` calls the scanner on its green path. Semantics are **audit-only** (detect + log + review; the native skip does the skipping). Generic scanner covers all three rules (tdd / quality-gates / security). Deferred: the `tess overrides report` front-end (standalone `report.py` for now) and the healthcare compliance-review extension — tracked in the observatory.

### Pass 3.4 — The hidden hooks directory

Separate `hooks/` directory (vs `templates/`) contains *opt-in hooks not wired by default*:
- `auto-review-hook` — Stop hook asking qwen3 whether multi-model review is warranted (interesting pattern: small model gates expensive review)
- `route-task-hook` (12KB, biggest hook) — model routing logic; classifies each prompt into a tier (incl. `CLAUDE_HAIKU/SONNET/OPUS`) and caches it to `~/.claude/routing-cache.json`
- `subagent-route-hook` — PreToolUse (`Task|Agent`) companion to `route-task-hook`: reads the cached Claude tier and rewrites a spawned subagent's `model` via `updatedInput`, so the tier becomes real dispatch (advisory→applied). Explicit model on the call always wins; non-Claude tiers are a no-op
- `tier-classify-hook` — UserPromptSubmit, cache-only Claude-tier classifier (combo B). Classifies each prompt into `CLAUDE_HAIKU/SONNET/OPUS` via local qwen (Ollama, `qwen2.5-coder:3b`, few-shot + token-only + temp 0) and writes `~/.claude/routing-cache.json` — **without** route-task-hook's cross-provider delegation or minimax pre-analysis, so framework-dev sessions get live tiers with no hijack. Wired into Tessera's own `.claude/settings.json` alongside `subagent-route-hook` (dogfooding). Fails open to `CLAUDE_SONNET`
- `polyphony-auto-isolate` — Polyphony container isolation
- `mid-task-escalation` — interesting; deserves a read at install
- `post-commit-graph` — touches code-graph `.needs-update` marker
- `pre-push` — git pre-push gate
- `usage-summary-hook` — usage tracking

**This vindicates our "kept-but-not-activated" framing for Polyphony.** Polyphony hooks exist; they just don't fire unless Polyphony is activated. Maggy already has the architectural pattern Tessera wants — opt-in hooks for opt-in features, separated from default install.

**Worth reading at install:** `auto-review-hook` (small-model-gates-expensive-review pattern is genuinely clever); `mid-task-escalation` (unclear what this does without reading it).

### Pass 3.5 — Tessera enforcement design becomes concrete

The hook layer is where several Tessera design decisions need to land as actual code:

**TDD enforcement (from pass 2.2):** Adopt `tdd-loop-check.sh` structure. Generalize toolchain. Add override annotation parsing. Wire to structured log. Keep 25-iteration safety cap.

**Pipeline artifact-gating (from pass 1.3 / principle #14):** When the suggestion-gate fires a pipeline, each stage produces an artifact at a known location. Stop hook variant checks for the expected artifact before allowing pipeline completion promise. Closes the "post-promise verification" gap from pass 1.2.

**Override audit logging (from pass 2):** Annotation parsing happens in PreToolUse hook. On override detection, emit log event with rule, file, line, reason, session-id. Healthcare layer: required compliance review of override log.

**PHI marker detection (deferred to healthcare layer):** Same PreToolUse hook gets a PHI-detection step. On PHI detection, route to local model + emit audit log entry with marker location (not content).

**The lifecycle hook reusability (from pass 1.4):** PreCompact / PreToolUse / PostToolUse are *Tessera infrastructure*, not Mnemos-specific. Tessera defines a hook composition pattern where multiple concerns (Mnemos, iCPG, override audit, PHI detection, structured logging) all attach to the same lifecycle events without colliding.

### Pass 3 Wrap-up

Hooks are where the abstractions become real behavior. Maggy's hook layer is generally well-engineered — defensive, graceful, async-aware, atomic where needed. Tessera adopts the core architecture (three-layer compaction defense, fatigue pipeline, marker/atomic patterns, hook lookup with fallback) and adds the things specific to Tessera's design:

1. Configurable toolchain via `.tessera/config.yml` *(`test:` built 2026-07-11; lint/typecheck await a consumer)*
2. Structured logging output for the audit log
3. Override annotation parsing
4. Unified iCPG/Mnemos pre-edit hook (no duplication)
5. Versioned schemas with validation
6. Python lifted out of bash heredocs

The hook layer is also where the healthcare-specific extensions land. PHI marker detection, compliance routing, audit trails — all hook-level work, building on the lifecycle infrastructure Maggy already has.

---

## Pass 4 — Security / Credentials / Code-Review Trio (Healthcare Layer)

The most substantive pass for Tessera's original IP. This is where the healthcare layer starts taking concrete shape — not as a separate framework, but as additive extensions to existing skills with a consistent integration pattern.

### Pass 4.1 — `security.md` skill (vs the security rule from pass 2)

Substantial skill: gitignore patterns, env var conventions per framework, pre-commit hooks (detect-secrets, npm audit, safety, bandit), GitHub Actions workflow (TruffleHog, dep audits, CodeQL), OWASP Top 10 patterns, auth/authz (JWT, bcrypt, rate limiting), security headers (helmet), release checklist, anti-patterns. **This is the *how*; the pass 2 rule was the *invariants*.**

**Adopt as-is for the baseline.** Standard web-app security, well-organized. Strong on secrets-don't-leak, OWASP basics, CI integration.

**Completely absent (healthcare layer adds substantially):**
- PHI handling (patient data identification, scope tracking, lifecycle)
- Audit logging (one line in the checklist — nowhere near HIPAA-compliant)
- Encryption at rest patterns
- Access controls / RBAC patterns
- Data retention policies
- BAA scope tracking for third-party services
- Breach notification preparedness

This is *typical web-app security*, not *healthcare data handling*. Healthcare layer is a substantial extension, not a tweak.

### Pass 4.2 — `credentials.md` skill

**Not a "credential security" skill in the abstract sense.** It's a practical tool for parsing API keys from `~/Documents/Access.txt`-style centralized files and converting them into project `.env`. Pattern recognition for ~15 services; validates keys against live APIs before writing.

**Adopt as-is for personal dogfood.** Matches Lorenzo's existing workflow.

**Concerning as default pattern (not just in healthcare).** The "scan your home directory for credential files" pattern is questionable for any project — it can surface credentials the user didn't intend to expose. **For baseline Tessera (`standard` profile):**
- Default to an external secrets manager (1Password CLI is the primary integration — Lorenzo's existing tool). Plain-text-file scanning is opt-in fallback, not default.
- Every credential access — regardless of profile — produces a structured log entry (what was read, when, for what stated purpose) per the Logging & Auditability section.

**For `healthcare` profile, additionally:**
- Auto-scan is disabled entirely. Skill becomes opt-in only when explicitly requested with a named user-confirmed credential source.
- Additional secrets manager backends supported: AWS Secrets Manager, HashiCorp Vault, Delinea Secret Server (used in some enterprise healthcare contexts).
- Credential access requires explicit named-owner approval via `.tessera/security-exceptions.yml` from pass 2.

**The masking pattern (`value[:8] + "..." + value[-4:]`) is correct.** Lift into the structured logging from pass 3 — any log entry referencing a credential gets masked the same way.

### Pass 4.3 — `code-review.md` skill

975 lines, largest skill in the framework. Comprehensive: 7 review categories, 5 severity levels, multi-engine support, ADR gate, CI/CD examples, decision extraction.

**Strengths to adopt:**
- **7-category review framework:** Security, Performance, Architecture, Code Quality, Best Practices, Testing, Documentation
- **5-level severity** (Critical/High/Medium/Low/Info) with "can commit?" semantics matches industry conventions
- **Multi-engine as first-class:** Claude/Codex/Gemini/dual/all. This is Maggy's implementation of the `/arbiter` pattern we'd designed.
- **ADR gate** (the `adr-gate` skill, split out of `code-review` per ADR-0008) — forces architectural traceability by injecting linked ADRs into review context, drafting new ones for undocumented decisions. Genuinely valuable for healthcare audit trails.
- **Decision extraction:** review findings auto-create ADRs or log to `decisions.md`. Connects to iCPG ReasonNodes.

**Concerns matching the pattern from earlier passes:**

- **"NON-NEGOTIABLE" framing.** "Every commit must pass code review. Skip step 3? ❌ NO COMMIT ALLOWED." Same auto-invocation pattern rejected in pass 1.1 / pass 2. **Reframe as suggestion-gate-offered** per principle #12 — trivial changes default to single-engine quick review; consequential changes prompt multi-engine via suggestion-gate.
- **Multi-engine on every commit burns tokens.** The ADR gate's trivial-change exemption is a start; the full multi-engine path is opt-in not default.
- **Codex "88% detection" claim** in the engine comparison is marketing-flavored. Treat with skepticism, not ground truth.
- **No PHI awareness** — pure additive healthcare extension.

### Pass 4.4 — Baseline Improvements (All Profiles)

Several pass-4 takeaways are genuinely good practice regardless of project type. They belong in baseline Tessera, not in the healthcare layer. Sorting honestly:

**External secrets manager integration** (in `credentials` skill):
- 1Password CLI as the primary integration in `standard` profile (matches Lorenzo's existing tool).
- Plain-text credential file scanning becomes opt-in fallback, not default.
- Architecture supports additional secrets manager backends per project profile (healthcare adds AWS Secrets Manager, HashiCorp Vault, Delinea Secret Server, etc.).

**Credential access audit log** (in `credentials` skill):
- Every credential access produces a structured log entry: what was read, when, by which session, for what stated purpose. Useful for any project — debugging, security incidents, "what did I do yesterday."
- Uses the masking pattern (`value[:8] + "..." + value[-4:]`) from the credentials skill — lifted into the structured logging from pass 3.

**Data Handling review category** (in `code-review` skill):
- Add as the 8th review category alongside the existing 7 (Security, Performance, Architecture, Code Quality, Best Practices, Testing, Documentation).
- General framing: how does data flow through this code? Is sensitive data handled appropriately? Are access patterns audited where needed?
- What counts as "sensitive" is project-configured. In the `standard` profile, the category exists but its content is minimal (credentials handling, secret exposure, basic privacy). In the `healthcare` profile, the category specializes substantially with PHI-specific findings.
- The category name is **deliberately non-specific** — it works in any profile without renaming or rephrasing.

**Third-party scope tracking pattern** (in `code-review` skill / `security` skill):
- Track which third-party services your project depends on and what their data-handling characteristics are.
- File pattern: `.tessera/third-party-scope.yml` *(not built)*. Would list services, what data they receive, and what agreements (privacy policy, terms of service, BAA, etc.) are in place. Trigger: build its **consumer** first — the Data Handling review category, which does not exist either. A data file with no reader is ceremony.
- Code review's Data Handling category flags code that introduces a new third-party dependency without updating the scope file.
- `standard` profile uses lightweight version (just track services and what data they receive). `healthcare` profile specializes this as BAA scope tracking.

**ADR gate as recommended baseline** (the standalone `adr-gate` skill, split out of `code-review` per ADR-0008):
- The `adr-gate` skill is genuinely valuable for any project — forces architectural traceability by injecting linked ADRs into review context.
- Recommended baseline behavior (not enforced): trivial changes skip the gate; non-trivial changes get an ADR drafted from git history for user confirmation.
- `healthcare` profile makes the gate stricter (mandatory for PHI boundaries; cannot proceed without ADR).

**Audit log infrastructure** (already in pass 3 Logging & Auditability):
- The structured event log at `.tessera/logs/<session-id>.jsonl` is baseline Tessera, not healthcare-specific.
- Healthcare profile extends what gets logged (PHI marker detections, compliance actions taken) but the infrastructure itself is universal.

### Pass 4.5 — Healthcare Profile (Additive Extensions)

These extensions activate only when `.tessera/project.yml` declares `profile: healthcare`. Everything in this section is genuinely additive and specific to healthcare data handling — wouldn't make sense in a non-healthcare project.

**PHI handling sub-skill** (in `security` skill):
- Defines PHI markers: the 18 HIPAA-identified data types (names, dates, geographic data, contact info, MRNs and other identifiers, biometric data, full-face photos, etc.).
- Routing rule: "if context contains PHI markers, route to local model only."
- Encryption-at-rest patterns and RBAC scaffolding for code that handles PHI.

**Hard-gate behavior on PHI-touching code:**
- The Data Handling review category specializes its findings with PHI-specific checks: appropriate routing, audit logging, encryption in transit/rest, BAA scope verification.
- When PHI handling is wrong, severity is Critical and blocks merge — regardless of test status. *"Tests passing but PHI leaks to logs"* is exactly the failure mode this gate prevents.
- This is the case where Tessera's principle (suggested-not-silent) yields to compliance reality. When PHI is at stake, the gate is real.

**ADR gate strict mode for PHI boundaries:**
- ADRs become mandatory (not suggested) for any code that introduces or modifies a PHI-handling boundary.
- ADRs include compliance fields: HIPAA implications, BAA scope, data classification.
- The `adr-gate` skill runs in its strict mode for PHI-touching changes.

**Multi-engine review auto-suggestion for PHI-touching code:**
- The "consequential code" pattern from the code-review skill's engine comparison table is exactly where multi-engine review earns its weight. Healthcare PHI code is consequential by definition.
- When PHI-touching code is detected, the suggestion-gate offers multi-engine review (Claude + Codex + Gemini) automatically.

**BAA scope tracking** (specialization of baseline third-party scope tracking):
- `.tessera/third-party-scope.yml` *(not built)* would gain a `baa_status` field per service.
- Data Handling category flags PHI-handling code that talks to a service without a BAA on file.

**Bumped encryption defaults:**
- bcrypt 13-14 rounds (vs 12 baseline).
- TLS 1.3 minimum on PHI boundaries.
- AES-256 at rest.

**Healthcare-specific incident response template:**
- Breach notification preparedness runbook generated at install time when healthcare profile activates.
- Templates for HIPAA breach notification timelines, regulator contact, affected-individual outreach.

**Healthcare YAGNI ladder** (Ponytail variant):
- Before writing code that touches data: does it need to leave the secure boundary? Does it need to be persisted? Is there an audit-logged primitive that already does this?
- Pairs the YAGNI discipline with HIPAA-aware defaults.

### Cross-pass connection (still tightening)

The pass 4 architecture works because the connections across earlier passes are real, not nominal:

- **Logging & Auditability (pass 3)** provides the audit trail infrastructure. Healthcare profile extends *what* gets logged; the structure is universal.
- **Override mechanism (pass 2)** handles legitimate exceptions to gates. Healthcare profile makes some overrides stricter (require named-owner approval in `.tessera/security-exceptions.yml`) but the mechanism is universal.
- **Suggestion-gate (pass 1.1)** handles multi-engine invocation for consequential code. Healthcare profile auto-suggests multi-engine for PHI-touching code, but the gate itself is universal.
- **Lifecycle hooks (pass 3)** implement runtime behavior. Healthcare profile adds PHI marker detection in PreToolUse; the hook infrastructure is universal.

This is the architectural win — profiles activate specializations on top of a coherent baseline rather than introducing parallel mechanisms.

### Pass 4 Wrap-up

Pass 4 produced more original Tessera content than any prior pass, then went through a meaningful rework when we caught the WebMD-specific framing creeping in. The cleaner architecture: baseline Tessera has genuine improvements over upstream Maggy (1Password integration, credential audit log, Data Handling review category, third-party scope tracking, ADR gate as baseline good practice). The healthcare profile adds substantive HIPAA-specific specializations on top — but only when projects opt in.

Three takeaways worth carrying forward:

1. **The baseline improvements stand on their own merit.** They make Tessera meaningfully better than Maggy for any project, healthcare or not.
2. **The healthcare profile is genuinely additive, not gravitational.** It exists for projects that need it; other projects don't pay overhead they don't use.
3. **The profile architecture generalizes.** Healthcare is the first substantial profile, but the mechanism supports more (financial, client-work, others) without disrupting existing projects.

**Worth flagging:** the healthcare profile implementation is a substantial work stream (several days of real coding for PHI marker patterns, RBAC scaffolding generation, BAA scope tracking, audit log extensions). Scope as a separate Tessera milestone after baseline dogfood works. The baseline improvements are smaller-scope and can land alongside the initial dogfood setup.

---

## Pass 5 — Language & Framework Skills *(in progress)*

Most of the cluster adopts cleanly per the pass 1 prune decisions. Pass 5 is mostly *applying earlier-established patterns* (targets-not-gates, soften MANDATORY framing, suggestion-gate where appropriate) to the language/framework skills, plus a few skill-specific calls.

### Pass 5.1 — Cross-cutting pattern: targets-not-gates applied globally

Apply the pass 1.1 / pass 2.1 adaptation across all language and framework skills:
- TypeScript skill's ESLint hard limits (`max-lines-per-function: 20`, `max-depth: 2`, `max-params: 3`) reframe as warnings + judgment, not errors that fail builds.
- React-web skill's "TFD MANDATORY / non-negotiable / NEVER" framing softens to the same pattern as TDD elsewhere.
- 80% coverage threshold (appears in both TS jest config and Python pytest config) becomes the project-aware default established in pass 2, not a universal hard gate.

Mechanical application of an already-established Tessera adaptation. Same numbers; softer enforcement language.

### Pass 5.2 — TypeScript skill: Vitest as default, Jest tolerated

Upstream skill recommends Jest throughout. **Tessera default for new TypeScript projects: Vitest.** Jest tolerated for legacy projects and for cases where Jest-specific tooling is in use. Adaptation:
- Replace `jest`, `jest --coverage`, `jest --onlyChanged` etc. with `vitest`, `vitest run --coverage`, `vitest --changed` equivalents.
- Keep React Testing Library as the component-testing layer (works with both Jest and Vitest).
- Pre-commit hook updated to use `vitest --changed` for staged-file tests.
- Coverage threshold mechanism switches from `coverageThreshold` (Jest) to Vitest's coverage config.

### Pass 5.3 — Component development order: Option B (sketch-first)

Upstream's react-web skill specifies Test → Implement → Test → Style. Tessera adopts a sketch-first variant:

**Sketch → Test → Implement → Test → Refine-Style.**

1. **Sketch** — quick visual anchor (whiteboard, Figma, ASCII, even a placeholder mock). Not pixel-perfect; establishes shape and intent. Aligns with design-driven thinking without abandoning TDD discipline.
2. **Test** — write tests against the behavior implied by the sketch. Run them — they fail.
3. **Implement** — write minimum code to pass.
4. **Test** — confirm pass.
5. **Refine-Style** — bring the styling to its final state.

Rationale: pure logic-first iteration is harder to sustain for design-sensitive developers; an early visual anchor helps without contaminating the test-iteration loop. Tests still come first (preserving upstream's actual concern, which was "tests never get written, not anything about CSS specifically").

**Open caveat:** this may evolve during dogfood — sometimes design wants to lead more than the sequence allows; sometimes the sketch step gets skipped if the component is mechanical. Treat the sequence as the default cadence, not a hard ordering. The TFD discipline (tests first, before implementation) is what's non-negotiable; the sketch step is a Tessera affordance for human cognition.

### Pass 5.4 — Mobile cluster *(deferred)*

android-kotlin, android-java, react-native, flutter skills deferred to install. Frameworks recommended in each (Coroutines/Compose/Hilt for Kotlin; Riverpod/Freezed/go_router for Flutter) look current as of pass-5 read. **Trigger for sort-out: before any actual mobile work begins.** Captured in Open Questions.

### Pass 5.5 — AI/agentic cluster

**agentic-development (855 lines) — adopt as-is.**

The reframe that matters: this skill is reference material for projects that *are* AI agents (Pydantic AI for Python, Claude Agent SDK for Node.js, OpenAI guardrail patterns). It operates at a different layer than Tessera's internal architecture, so the conflict checks come back clean:

- Skill's "Plan first, act incrementally, verify always" aligns with suggestion-gate (#12)
- Skill doesn't define a hook system — no collision with Tessera's lifecycle hooks
- Skill's "match model to task complexity" aligns with just-in-time provider principle (#11) and routing-as-rule design
- Skill documents the same skills-pattern Tessera uses (validation, not conflict)

**Industry-alignment note worth carrying:** three patterns in this skill validate Tessera design choices by showing they're industry-standard rather than Tessera-specific:
- Explore-Plan-Execute-Verify workflow ≈ pipeline pattern from pass 1.3
- Human-in-the-loop for high-risk operations ≈ suggestion-gate (#12)
- Match model to task complexity ≈ just-in-time provider addition (#11)

Useful framing for Tessera's future story: these are well-known patterns, not invented ones. Tessera applies them.

**ai-models (683 lines) — adopt as-is with freshness caveat.**

Per-provider reference card (Anthropic, OpenAI, Google, Eleven Labs, Replicate, Stability, Mistral, Voyage). Each section has docs links, current model IDs, usage snippets, cost-per-1M-tokens, and use-case selection. The selection matrix and cost ordering remain durable; specific model identifiers go stale.

Add a top-of-skill caveat: *"Snapshot from December 2025; verify current models via provider docs before relying. The selection matrix and cost ordering remain durable; specific identifiers may have superseded versions. Use `tess models current` to print today's recommended defaults."*

**llm-patterns (328 lines) — adopt as-is with LiteLLM parallel example.**

Real architecture patterns: typed LLM wrapper, structured outputs with Zod, prompt template functions, prompt versioning, three-tier testing (mocks / fixtures / evals), cost & performance tracking, anti-patterns. Industry-aligned and clean.

**Add a parallel LiteLLM example** alongside the existing Anthropic SDK example (~30 lines). The skill shows both patterns side-by-side with a "when to pick each" guide:

- *Use LiteLLM* when you want to swap providers without changing code (most general-purpose projects).
- *Use the direct SDK* when you need provider-specific features (Anthropic's prompt caching, OpenAI's function-calling JSON mode quirks, Gemini's thinking-mode parameters, Claude's extended thinking blocks).

This matches the design doc's principle #11 (just-in-time provider addition) and gives users the actual decision-making framework rather than implying one is right.

**Cross-cutting: hardcoded model identifiers across the skills.**

Both ai-models and llm-patterns reference specific model IDs (`claude-opus-4-5-20251101`, `claude-sonnet-4-20250514`, etc.). The same staleness applies anywhere model IDs appear in skill content — agentic-development examples, template files, hook fallback defaults.

**Pattern A (lower-risk):** replace hardcoded IDs in code examples with placeholders like `process.env.CLAUDE_MODEL ?? 'claude-sonnet-LATEST'`, with a single note across skills: *"In examples, model identifiers reflect a snapshot. Refer to ai-models for current IDs, or use `tess models current` to print today's recommended defaults."*

Rejected: Pattern B (have the refresh script touch skill files in-place). Too many file touches, real risk of corrupting example code with a regex-based update. The dynamic-and-costly nature of model identifiers shouldn't be solved by walking the skill tree.

### Pass 5.7 — Tessera install-time addition: model-refresh script

Solving the staleness problem operationally rather than just cosmetically. Build as part of the Tessera install playbook.

**Scope (Tier 1 + LiteLLM cross-check, ~half day of work):**

- Script fetches current model lists from each provider's API (Anthropic, OpenAI, Google, Mistral, etc.) where available
- Cross-references with LiteLLM's `model_prices_and_context_window.json` catalog to catch mismatches and surface models LiteLLM supports
- Hand-curates pricing for providers that don't expose pricing via API
- Rewrites the ai-models skill snapshot sections in-place

**Commands:**

- `tess models refresh` — regenerate the ai-models snapshot
- `tess models current` — print today's recommended defaults (used by Pattern A placeholders)

**Operations:** Run once at install to bring the snapshot current. Rerun monthly or on demand. Static markdown stays the storage format (Claude Code reads it normally) — refresh is a script you call, not always-on infrastructure.

**Rejected: Tier 3 (live lookup on every session start).** Adds runtime complexity to skill loads and burns network on session start. Overkill for the problem.

### Pass 5.6 — UI cluster *(deferred-read, expected adopt-as-is)*

ui-web, ui-mobile, ui-testing, playwright-testing, user-journeys, pwa-development. Frontmatter checked; no surprises. Expected to adopt-as-is with the same cross-cutting MANDATORY/NEVER softening from 5.1. Detailed read at install time.

---

## Dogfood Plan

### Sequencing

Two-project sequence to disentangle installation friction from framework evaluation:

1. **Warm-up (~2-3 days): Tess dashboard.** Lands installation friction on a small useful project. Output is genuinely valuable (used during real dogfood phase to make Tessera's behavior visible). Stack matches Tessera's web sweet spot, exercises FE/CSS/testing patterns without confounding stack-learning with framework-learning.
2. **Real dogfood (~2-3 weeks): Decibel meter.** Net-new Android Kotlin + Oboe project. Strategic value beyond the dogfood (foundation for future field-recording / IR-capture work). Mobile cluster review fires at start per pass 5.4 trigger.
3. **Decision point (~end of week 4):** Defensible opinion on Tessera. Decision on whether to use it for further projects (hosted models lab, mobile expansion, etc.) or rip-and-replace.

### Project 1 — Tess dashboard (warm-up)

- **Scope:** Local web dashboard surfacing Tessera's runtime data. Single page, three panels for v1.
- **Stack:** Vite + React + TypeScript + Vitest + Tailwind. Local-only; reads `.tessera/logs/<session-id>.jsonl` files via local API routes or direct file reads. No backend, no auth, no deployment.
- **v1 panels:**
  - **Recent sessions** — last 10-20 Claude Code sessions across all Tessera projects, sorted by timestamp. Each row: timestamp, duration, model used, haziness band (color-coded), file count edited. Click → expanded view with per-dimension haziness breakdown.
  - **Suggestion-gate calibration** — aggregate of suggestion-gate events over selectable time window. Counts of suggestions offered / accepted / declined / modified per category (pipeline, multi-engine review, Ralph loop). Bar chart per category.
  - **Mnemos lifecycle** — counts over the same time window: compaction events, recoveries fired (Layer 1/2/3), checkpoints written, fatigue band transitions, iCPG drift events detected.
- **Patterns exercised:** sketch-first component dev order (Option B, pass 5.3), Vitest testing pattern (pass 5.2), CSS/Tailwind, React Query for data fetching, Zustand for global state (time-window selector, project filter).
- **Stack rationale (per principle #15):** Vite chosen over Next.js because the project is local-only with no server-rendering needs. The react-web skill's Next.js default is informative, not prescriptive.
- **v2 deferred:** project-level haziness aggregation, deeper Mnemos drilldowns, custom filters, preference persistence.

### Project 2 — Decibel meter (real dogfood)

- **Scope:** Native Android Kotlin + Oboe app for instantaneous SPL metering. Real strategic value beyond dogfood (foundation for #11 field-recording / IR-capture work; input-metering code carries forward).
- **Stack:** Kotlin + Oboe + Jetpack Compose for UI. Android target.
- **Why this works as dogfood:**
  - Real surface area to exercise Tessera over 2-3 weeks
  - Enough complexity to test Mnemos compaction recovery, suggestion-gate calibration, iCPG drift detection
  - Strategic value means motivation is real (will finish), but not so exciting that excitement hides friction
- **Known cost:** confounded learning (Tessera friction vs Oboe/AAudio friction). Mitigation: keep explicit notes on which is which during work.
- **Mobile cluster review trigger:** fires at start of this phase per pass 5.4. Read android-kotlin skill (and any Oboe-specific addendum needed) before meaningful code starts.

### What's *not* the dogfood project

- **Hosted models lab (#12):** too large (4-6 weeks), too exciting (hides framework friction). Deferred to post-dogfood per the sequencing in Future / Org-Rollout section.
- **Excuse engine (#6):** considered as warm-up, set aside because the dashboard provides equivalent FE/CSS/testing exercise *plus* ongoing utility during the rest of dogfood. Stays on the project list for future.
- **In-progress projects (#1 Battletronic, #8 Pork Chop Express, #9 pr-arbiter):** running in their own workflows; switching mid-stream confounds framework eval with project momentum loss.

### Timeline

- **Day 0:** Tessera install + setup (`maggy/install.sh`, then Tessera renames and customizations).
- **Days 1-3:** Tess dashboard v1 (warm-up).
- **End of week 1:** Dashboard shipped; first impressions of Tessera form; mobile cluster review starts.
- **Weeks 1-3:** Decibel meter as real dogfood.
- **Week 4:** Defensible opinion on Tessera. Decisions on Mnemos / iCPG / pipeline keep-or-cut. Plan for next project (hosted models lab? next iteration of decibel meter into #11?).

### Downstream project scaffold — DECIDED (2026-06-24)

Tessera exists to do downstream projects, so standing one up is a first-class capability, not a chore. The default mechanism is **`bin/tessera-new-project [--frozen] <dir> [name] [profile]`** — it lays down the harness layer (the suggestion-gate recorder, `settings.base.json` + `gitignore.base`, `.tessera/` profile, and a `CLAUDE.md` from `templates/tessera/CLAUDE.md.template`) and `git init`s. It does **not** scaffold the app/stack — generate that with the platform's own tool and layer the harness on top.

- **Hook distribution defaults to `global` (ADR-0004):** the scaffold no longer copies mnemos hook scripts locally — `settings.base.json` resolves them from `~/.claude/templates` via a local→global fallback branch, so all projects share one source and never drift. Pass `--frozen` for ship-critical projects that want pinned, churn-immune local copies. Flip later with `bin/tessera-hooks freeze|thaw|status`. This graduated observatory F-003 to ADR-0004.

- **Why minimal-by-default (principle #15):** the first three downstream harnesses (tess-dashboard #0, Howler #1, and the scaffold output) were each hand-rolled into divergent shapes. The scaffold is the convergence point; it earns complexity through use, one project at a time, rather than an upfront design.
- **Deferred — full packaging/distribution.** Distributing the *skill/command* layer off this machine (second machine, another person, skills diverging from the global install) is a separate, unsolved question with two candidates (the inherited maggy installer vs. extending this scaffold). Not built — no triggering need yet. Tracked in `observatory.md` ("Downstream packaging mechanism"); it graduates to an ADR when real distribution pressure appears.
- **Existing projects:** tess-dashboard and Howler are grandfathered (Howler already matches the scaffold output; tess-dashboard's missing `.tessera/project.yml` was retrofit). No forced migration.

---

## Six review passes (in order)

1. **Most opinionated core skills:** `base`, `iterative-development`, `agent-teams`, `mnemos`, `icpg`. Defines the framework's worldview.
2. **Rules layer.** Small, fast, but shapes behavior most.
3. **Hook scripts.** Actual code, short, reveals implementation quality.
4. **Security / credentials / code-review trio.** The ones needing HIPAA augmentation.
5. **Language/framework skills.** Python, TypeScript, React, Node, mobile cluster.
6. **Questionable cluster + `site-architecture`.** Confirm pruning decisions.

### Timeline

- Half-day: reading (passes 1-6 with conversation).
- Half-day: install, rename, configure.
- 2-3 weeks: real use on the dogfood project.
- ~1 month: defensible opinion on Mnemos vs alternatives, on whether the agent pipeline helps or annoys, on whether to roll out at scale.

---

## Open Questions (Decisions Deferred)

- **Dogfood project — DECIDED.** Tess dashboard (warm-up, ~3 days, Vite + React + TypeScript + Vitest + Tailwind) → Decibel meter (real dogfood, ~2-3 weeks, Kotlin + Oboe). Full plan captured in Dogfood Plan section.
- **`site-architecture` skill** — keep or cut. Decide in pass 5/6.
- **Mnemos trial outcome** — fires on real compaction events? Haziness scoring useful? Decide after 2-3 weeks dogfood. (Skill is more rigorous than first synthesis suggested.)
- **Code-knowledge layer** — code-graph (continuously-loaded, auto-fresh) covers default needs; GitNexus on-demand for deeper analysis. Decide after dogfood whether GitNexus is needed at all, or if code-graph suffices.
- **iCPG behavioral trial** — does the agent actually populate ReasonNodes and contracts well? Does drift detection catch real issues? Decide after dogfood.
- **Codex auto-review hook** — enable or not. Decide after first weeks.
- **Agent pipeline thinning** — which agents stay for solo work. Decide after reading `agent-teams.md`.
- **Pr-arbiter ↔ `/arbiter` integration** — at what point pr-arbiter graduates into a usable tool that backs `/arbiter`.
- **Mobile cluster skill review (android-kotlin, android-java, react-native, flutter)** — deferred to install. **Trigger:** before any actual mobile work starts. Do not skip; sort the mobile skills before beginning Android-first development.
- **GitNexus commercial license** — only blocking if commercial / employer use becomes real; defer.

---

## Logging & Auditability

Structured event logging during dogfood, designed for trial-decision validation and as the foundation for healthcare-layer compliance later.

**Why log:**
- Trial criteria become measurable, not impression-based. ("Did Mnemos fire? Did suggestion-gate calibration help? Is Telos IFS theater or signal?" — all answerable from logs.)
- Compliance posture for healthcare rollout. HIPAA/HITRUST require audit trails; building the infrastructure now means it exists when needed.
- Debugging asymmetry. Mid-pipeline failure with no logs is hours of reconstruction; with logs it's minutes.
- Calibration of the suggestion-gate threshold (#12). Without log data, the threshold is set by feel forever.

**What gets logged (decisions and milestones, not exhaustive tool traces):**
- Session boundaries: start, end, model used, project
- Suggestion-gate firings: what was offered, what was decided (accept/decline/modify)
- Pipeline events: invoked, stage started/completed, aborted, completed; artifact paths
- Hook firings: PreCompact / SessionStart-compact / PreToolUse fallback (Mnemos lifecycle), with what was preserved or recovered (not full content)
- Mnemos recovery events: specifically did it fire on a real compaction and what did it restore
- Mnemos fatigue band transitions (FLOW → COMPRESS → PRE-SLEEP / etc.) and the actions taken
- Mnemos haziness scores per session (composite + dimensional breakdown)
- iCPG pre-task query results: how often the three queries fired, whether they returned useful information
- iCPG drift detection events: dimension, severity, resolved/unresolved
- Routing decisions: which model handled what kind of task
- PHI marker detections: marker location and compliance action taken (routed to local, blocked, etc.), **never PHI content itself**
- Errors classified per the iterative-development pattern: code-fixable (continue) vs human-required (stop)

**What is never logged:**
- Full prompt/response content (too much, too sensitive)
- Every file read or tool call (noise)
- PHI content itself (compliance violation)
- API keys, credentials, secrets
- Anything else captured as 200-char redacted previews via Mnemos's existing ingestion pattern (which already handles this correctly)

**Structure:**
- One log per session: `.tessera/logs/<session-id>.jsonl`
- JSON Lines format: append-only, parseable line-by-line, doesn't need rewriting, survives crashes mid-write
- Each event has timestamp, event type, source (skill/hook/agent), and structured data
- Gitignored by default — these are personal session data, possibly sensitive

**Querying:**
- `tess log query --since 1w --event suggestion-gate` — how often the gate fired last week
- `tess log query --session abc123 --event pipeline` — full pipeline run for that session
- `tess log query --event mnemos-recovery` — every time Mnemos recovered from a compaction event
- Simple jq-style filters over JSON Lines; no separate query engine needed

**Rotation/retention:**
- Keep 30 days by default; configurable
- Compress logs older than 7 days to gzipped JSON Lines
- Hard cap at 1GB total; older logs drop off in age order if cap is hit

**Healthcare layer extension (deferred):**
- Logs capturing PHI markers must also capture the compliance action taken (route to local, block, etc.)
- Logs themselves marked PHI-adjacent if they contain markers (even if content was scrubbed)
- Append-only with cryptographic chaining could be added if regulatory audit requires it
- HITRUST/SOC 2 audit trails build from this base

**Relationship to existing Maggy capabilities:**
- Mnemos already captures `signals.jsonl` (behavioral signals from PreToolUse + PostToolUse hooks). Tessera's log can either consume that file or duplicate the relevant subset — TBD during install.
- Mnemos's transcript ingestion + haziness scoring already handles redaction-before-disk. Tessera log adopts the same redaction patterns.
- Maggy mentions `pipeline logs` in its REST API; if those exist as structured output, consume them. Otherwise Tessera generates its own from pipeline events.

---

## Future / Org-Rollout Considerations (Deferred from Dogfood)

Captured so nothing gets lost. These are *known capabilities* we've decided not to activate yet, with reasons. Re-evaluate when sharing with collaborators, working on commercial projects, or rolling out to a team.

### Multi-agent orchestration (currently deferred — single-Claude dogfood)

- **Anthropic native Agent Teams** as the foundation when this activates (Feb 2026 release, `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`). Don't reimplement multi-agent in markdown — use the native primitive.
- **Maggy's 10-stage feature pipeline as multi-agent orchestration.** Currently runs as a structured single-session sequence (per pass 1.3 decision). When activated, the same stages get split across 6 role-specific agents: team-lead (delegate mode, never edits), feature-X (one per feature, writes code), quality-agent (read-only, TDD verify), security-agent (read-only, OWASP/secrets), review-agent (read-only, multi-engine review), merger-agent (git/PR only, never merges).
- **Structural ordering via task dependencies.** The "deviation made impossible by capability" pattern. When reconstituted, this is the most valuable org-scale property — preserve carefully.
- **Inter-agent communication** via direct messages + shared TaskList. Mailbox pattern from native Agent Teams.
- **Parallel feature execution.** Multiple feature chains running simultaneously; shared reviewer agents process tasks as they unblock.
- **Polyphony** for headless background work (auto-review on commit, scheduled refactor agents, A/B implementation comparisons). Currently kept-but-not-activated; full activation when first headless use case emerges.

### Org-scale operational controls

- **Hook profiles pattern.** Env var control (`TESSERA_HOOK_PROFILE=minimal|standard|strict`, `TESSERA_DISABLED_HOOKS=...`). Different teams want different strictness; central policy controls without editing files. ECC-inspired.
- **Consult/advisor command.** `tess consult "security reviews"` returns matching skills/agents/commands from the Tessera catalog. Discoverability over a sprawling internal toolkit. ECC-inspired.
- **Status snapshot.** `tess status --markdown --write status.md` for portable handoffs. Useful when one engineer hands a setup to a successor. ECC-inspired.
- **Per-team `auto_accept_for` lists.** Patterns where the suggestion-gate is skipped and the loop/pipeline runs directly. Teams codify "we always loop on backend feature work, never on prototypes" without editing global config.

### Review pipeline (currently single-engine; multi-engine deferred)

- **Codex auto-review hook.** Second Stop hook after TDD passes runs Codex review. Deferred decision for dogfood.
- **Gemini review.** Third engine; 1M token context window relevant for large changes.
- **Multi-engine code review via `/arbiter`** for consequential changes. Currently suggestion-gate offered, not default. Path to org rollout: same suggestion mechanism, broader auto_accept_for patterns.

### Telos / IFS measurement (currently opt-in via suggestion-gate)

- **IFS scoring as quality gate.** Currently treated as suspect for continuous use (multiplicative scoring is brittle). For org rollout, may earn its keep as a hard gate at release boundaries — "before this can merge to main, IFS > 0.7." Different invocation pattern, different value calculation.
- **Drift detection as scheduled scan.** `icpg drift check` weekly across the codebase, not just at commit time.

### Memory layer evolution

- **Evaluate Mnemos against external alternatives at org scale.** The persistent-memory-for-Claude-Code space has matured significantly (Engram, Ori-Mnemos, claude-mem, claude-brain, multiple unrelated "Mnemos" projects, native Claude Code memory). Maggy's Mnemos is fine for personal dogfood; an org-scale evaluation deserves a head-to-head trial.
- **Shared memory across engineers.** When multiple Tessera users work on the same codebase, do they share an iCPG/Mnemos state, or each maintain their own? Federation question to answer at rollout time.

### Pr-arbiter integration

- **Graduation from research artifact to usable tool.** Currently a separate research project (Phase 1 in peer review, Phase 2/3 in design). When mature, integrate as the implementation backing `/arbiter` for code-review use cases.
- **Multi-persona review.** Pr-arbiter's adversarial corpus (4 personas) maps to a generalization of multi-engine review — same review query against multiple models *and* multiple personas. Becomes available org-wide when ready.

### Hosted models lab

A separate downstream project: a playground / eval harness where prompts can be run against N models head-to-head and outputs compared. The production-grade version of `/arbiter`. Uses LiteLLM heavily (multi-provider comparison is its whole point), and naturally exercises Tessera's multi-model abstraction at scale.

**Sequencing thinking (deferred decision):**
- *Dogfood first, then lab* — pick a small-but-real project (~2 weeks) to dogfood Tessera against, find framework friction, then build the models lab as Tessera's first "real" project with a debugged framework. Lower risk; cleaner separation of concerns.
- *Parallel-track* — dogfood Tessera and build the lab simultaneously. Appealing but probably means both go slower; harder to tell whether friction is from Tessera or the lab's scope.
- *Lab as dogfood* — rejected. Lab scope (4-6 weeks) is too large for honest dogfood evaluation, and excitement about the project hides framework friction by motivating workarounds.

**Status:** Lab deferred to post-dogfood per dogfood plan (Tess dashboard warm-up → Decibel meter as real dogfood → defensible Tessera opinion → then decide on lab timing).

### Harness / `tess` CLI shape (deferred)

Tessera is already building a lightweight harness organically: `tess profile`, `tess log query`, `tess overrides report`, `tess models refresh / current`, plus the Tess dashboard for trial data. Plus config files (`.tessera/project.yml`, `.tessera/config.yml`, `.tessera/security-exceptions.yml`), structured event log, hook lifecycle conventions, override mechanism.

For solo dogfood, the lightweight harness is enough. The full Maggy harness (inbox/ticket triage UI, plugin system, model routing service) addresses needs we don't have yet.

**Trigger conditions to revisit:**
- **Shared with collaborators.** When Tessera goes from solo to multi-user, the inbox/triage gap becomes real ("what should I work on next across N repos").
- **Hosted models lab activation.** The lab will need some service layer — that's a natural moment to design harness shape deliberately.
- **Orchestration needs hooks can't express.** If background jobs, scheduled tasks, or programmatic plugin extension become real needs, the plugin system pattern earns its weight.

**One thing worth doing eventually (install-time, not design-time):** sit down and consciously design the `tess` CLI's overall shape — subcommand structure, help text, installation, packaging. Commands have been added ad-hoc throughout the design phase; formalizing them as one coherent tool pays off at install. Not blocking; just shouldn't be skipped.

### Compliance and audit (healthcare layer)

- **PHI handling skill** activates with healthcare layer. Currently designed as a Tessera-original principle, not yet implemented.
- **Compliance gate rule** — fires on PHI markers, routes to local model, requires audit trail, can block actions. Implementation deferred.
- **Audit log extensions** — append-only with cryptographic chaining for HITRUST audit. Build on the Logging & Auditability foundation above.
- **AgentShield as required pre-release scan, operationalized in CI.** Currently a manual scan; org rollout makes it a gate.

---

## Sources Consulted

- [alinaqi/maggy](https://github.com/alinaqi/maggy) — base
- [arps18.github.io/posts/claude-code-mastery](https://arps18.github.io/posts/claude-code-mastery/) — Boris/Arpan principles
- [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail) — YAGNI ladder
- [affaan-m/ECC](https://github.com/affaan-m/ECC) — rejected as framework; AgentShield and operational patterns borrowed
- [andrewtrask.substack.com/p/breaking-todays-frontier-ai-companies](https://andrewtrask.substack.com/p/breaking-todays-frontier-ai-companies) — ensembling theory
- [abhigyanpatwari/GitNexus](https://github.com/abhigyanpatwari/GitNexus) — code knowledge graph; alternative to iCPG

---

*Next: pass 1 — read the five most opinionated core skills (`base`, `iterative-development`, `agent-teams`, `mnemos`, `icpg`). Capture decisions back into this doc as we go.*
