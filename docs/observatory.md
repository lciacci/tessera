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

### Fail-open everywhere — Tessera cannot tell you when it is broken

- **Status:** Investigating. **This is the most consequential entry in this file.** It is a claim about the framework as a whole, not about any component, and it should be promoted to an ADR once its remedy is designed.
- **Full narrative accounting: `docs/postmortem-2026-07-12.md`.**
- **Source:** The 2026-07-12 F-001/venv session. Not one bug in it was found by the framework announcing a problem. Every one was found by a human getting suspicious, or by an adversarial verifier in a clean context. Three rounds of "it's fixed" were refuted by independent verification, each time correctly.

#### The evidence — eight bugs in one session, and **not one of them announced itself**

| Bug | How it presented |
|---|---|
| **F-001** (original) | Mnemos checkpoints silently no-op'd for **weeks**. Read as *"the graph is unused"* when it meant *"the graph is unreachable."* Confounded the entire Mnemos kill/keep trial. |
| **Hook toolchain fallback** | Fell back to `python3 -m mnemos`, and with `PYTHONPATH=scripts` bare python3 **imports mnemos from source**. So it did not fail — it silently **succeeded on an unmanaged interpreter**. `mnemos status` looked healthy. |
| **Spend guard on py3.9** | PEP-604 annotations raise `TypeError` at definition time → `guard.py` exits 1 → the wrapper passes that through as "not 2" → **Claude Code reads it as ALLOW**. *An unauthorized GPU boot proceeds.* The guard failed **open**. |
| **Spend backstop fire-counter** | `.tessera/.spend-backstop-fires` was committed holding **5**, against a `MAX_FIRES` of **3**. Every clone inherited a backstop **already past its cap — born disabled**, silently. |
| **tess-dashboard hook** | `settings.json` exec'd `.claache/scripts/…` — a typo. The hook had **never once run**, and nothing said so. |
| **`hooks/plugin-trigger`** | `import yaml` under `except Exception: pass` on an interpreter without yaml → **silently discovers zero plugins**, forever. |
| **The test suite** | Wrote **real** `spend_denied` events to the production audit log. 26 of one session's 31 denials were manufactured by pytest — an 84%-polluted friction journal. |
| **`doccheck` itself** | Reported *"12 checks, 0 false claims"* while **three live, wired hooks** ran the toolchain on a bare interpreter. The detector was green over the exact bug it exists to find. |

#### The pattern

Tessera fails open **everywhere** — hooks, wrappers, guards, detectors. Each instance is individually defensible, and most were deliberate:

> *"A backstop that can wedge a session gets ripped out, and then it protects nothing."*
> *"A hook that wedges every Bash call is its own outage."*

Both true. But the **cumulative** property is not a design choice anyone made:

> **Tessera is indistinguishable from healthy when it is broken.**

And the layer meant to catch that — the detectors — **fail open too**, because *a green detector looks exactly like a working one*. There is no signal anywhere in the stack that distinguishes "nothing is wrong" from "the thing that would tell you is also broken."

That is why the session became a rathole. It was never about Python. It was that **nothing in the system reports its own death**, so every fix needed a fresh adversarial read to find the next silent thing.

#### The sharper finding: **mechanized rules held. Prose rules did not.**

This is principle #17 getting its strongest evidence yet, and the evidence is *at the model's expense*. Sorted by whether the rule was a **channel** or a **sentence**:

| Rule | Form | Held? |
|---|---|---|
| doc-drift bug → assertion in `doccheck.py` | **mechanized** | ✅ grew 5 → 13 checks, caught real bugs |
| pre-commit gate blocks a lying commit | **mechanized** | ✅ |
| `tessera-watch` P9 / G-a nags until the venv lands | **mechanized** | ✅ escalated, forced the fix |
| gate-scan Stop hook | **mechanized** | ✅ caught unlogged gates the model forgot |
| *"verify by invoking, not inspecting"* | **prose** (handoff) | ❌ violated repeatedly |
| *"ship both halves or neither"* | **prose** (a comment the model itself wrote) | ❌ violated one layer up — the spend guard shipped downstream **without** doccheck |
| *"existence is local, reachable is shared"* | **prose** | ❌ violated (templates/ updated, `~/.claude/templates/` not) |

**Every rule with a channel held. Every rule that was only a sentence failed.** Including sentences the model had written itself, in the same session, and re-read.

#### Two new rules, earned the hard way

1. **A mechanism that fails OPEN needs a paired detector that fails LOUD.** Fail-open is correct for hooks. It is only *safe* when something else is watching. Today, nothing was. This is the general form of the fix that closed F-001: the venv was the mechanism, `no-bare-python3-with-toolchain-import` was the guardrail, and the venv alone would have been worthless.

2. **A carve-out from a safety invariant must ship with a check that the carve-out holds.** The worst bug of the day was *built by an exception the model wrote*: "the gate/spend hooks may use bare `python3`, because they are stdlib-only and must survive a broken venv." That sentence is the bug — **stdlib-only is not version-independent**; when the interpreter NAME drifts, the VERSION drifts with it. The carve-out was reasonable, undocumented as a risk, and unchecked. It is now checked (`safety-scripts-run-on-system-python`, which *executes* the safety scripts on `/usr/bin/python3` — `ast.parse` passes, because PEP-604 is syntactically valid and only explodes when evaluated. **Compiling is not running.**)

#### The consequence for autonomy — read this before trusting ADR-0005

ADR-0005 named three preconditions for unsupervised operation. On 2026-07-12 all three were declared **met**. Then:

- The **spend guard** — *the* precondition for unsupervised spend — was found to **fail open**.
- The **escalation backstop** shipped with its fire-counter committed **past its cap**, disabled in every clone.

Both were found by adversarial verification, **not** by the framework. **The readiness claim was wrong, and nothing in Tessera could have told us.** Autonomy is further off than ADR-0005 implies, and the blocker is not any single bug — it is that *the framework cannot yet report its own failure*.

#### When to revisit / what would close this

- **The remedy is scoped and ordered in `_project_specs/11-fail-open-detection.md`.** Five components (spend guard, spend backstop, gate-scan, Mnemos hooks, doccheck) — *not* the 54 measured bail-out sites. Mechanism is ~35 lines (`tessera-degraded` + watcher **P10**); the substance is the chaos tests and the per-site classification of *"nothing to do"* vs *"could not do my job."*
- **The ordering is load-bearing: chaos tests FIRST, watched failing, before any mechanism exists.** The session that produced this entry built a detector and then certified the fix *with the detector that had the hole* — three times, reporting green each time, refuted by three independent verifications. A detector you certify a fix with must be tested against that fix's own failure mode, or it is a mirror.
- **Promote to an ADR** once spec 11 ships and the bar is met. This entry is the evidence base.
- **Re-open ADR-0005's readiness assessment** in light of the two broken preconditions.
- **Close when:** a deliberately-broken component (venv removed, guard corrupted, hook typo'd, `python3` pointed at 3.9) is detected by the framework *within one session, without a human asking* — and **confirmed by an independent session, not the one that built it.** That is the bar. Nothing today would have met it.

---

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
- **Update, 2026-07-11 — n≥2 reproduced; backstop BUILT.** The 2026-07-10 session (substrate-vs-engine resolved, surface channel picked, 4 denominators settled, P2 retired, G-a built, phantom script deleted, 9 commits across 3 repos — ≥8 gate-shaped decisions) logged **3**. Second reproduction; the trigger below fired, so the scanner was built rather than deferred a third time.
  - **Shape:** Stop hook `.claude/scripts/tessera-gate-scan.sh` → `scripts/gate/scan.py`. Counts gate-shaped turns in the transcript (structural: an assistant run that asked something, then handed back to a *human* turn — a tool_use is followed by a tool_result, not a human, so the structure alone encodes "proposed, then waited"), diffs against `.tessera/logs/<session>.jsonl`, exits 2 on a gap. **The trigger is now the harness, not model recall — that is the #17 fix.**
  - **Detector is deliberately a recall net; the model is the precision filter.** It over-counts (a clarifying question looks like a gate) and the model adjudicates on the exit-2 turn. What it cannot do is *forget*, which was the entire failure.
  - **Fires when gap ≥ 2, OR nothing was logged at all.** The second clause is the load-bearing one: a session that logs zero gates leaves **no log file**, so it was invisible to `ratio.py` — the 100%-miss sessions may already be in the history, uncounted. The backstop reads transcripts, so it is the first instrument that can see them.
  - **Loop safety:** honors `stop_hook_active`, caps at 3 fires/session, fails open on every error path. A backstop that can wedge a session gets ripped out, and then it protects nothing.
  - **First calibration (n=1 session):** 2 gate-shaped turns detected, **both real gates, zero false positives**; 1 logged. The over-counting I designed around did not materialize — `gap ≥ 2` may prove conservative. Not revising the threshold on one sample; watch it.
  - **It caught its own bug during calibration.** First cut read only an assistant run's *last* text block, so a gate followed by a tool call and a sign-off statement vanished — which is exactly the shape of the turn that scoped this hook. Regression test added. A last-block detector would have shipped a scanner blind to the most common gate shape.
  - **Also fixed:** `ratio.py` globbed `.tessera/logs/*.jsonl` untyped, so the watcher's `watch.jsonl` (added 2026-07-10) counted as a phantom 0-gate session. Same shape as F-003 — a shared directory with no type discrimination. Both consumers now filter on `type == "suggestion_gate"`.
  - **New hole, 2026-07-12 — the CURRENT turn's gate is invisible to the scan that fires on it.** Observed twice in one session: the hook fired, listed 5 gate-shaped turns, and **omitted the gate in the very turn that triggered it** — because the Stop hook scans the transcript *as of the turn it interrupts*, and the turn in flight is not in it yet. So the scan is systematically blind to the **most recent** gate, which is the one still live in the conversation and the one most likely to go unlogged (every already-listed gate had, by then, already been adjudicated). This is the *same shape* as the last-block bug above — a detector that can't see the thing that scoped it — one level up: **last-block → last-turn.** Consequence for calibration: gate counts from the scan skew low by roughly one per session, and the miss is not random — it is always the freshest gate. Fix before any `should_fire` labeling pass, or the corpus is biased toward *stale* gates by construction.
- **Status:** Watching (narrowed) — watch #1 answered (forgetting dominates) and its backstop has shipped; #2 and #3 still open.
- **When to revisit:** Backstop trigger — **DONE (2026-07-11).** Still watching: (2) does reviewing the gate journal in the dashboard surface real friction, or is the convention alone the whole feature? (3) does the mechanical/scored producer (option B) ever get pulled for? **New watch (4): does the backstop actually change the logged-gate rate?** Compare gates/session before and after 2026-07-11 in `ratio.py` — if the rate does not move, the hook is ceremony and should be cut, not tuned. Close when (2)/(3)/(4) resolve.
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
  1. **`tess` umbrella CLI — DECLINED 2026-07-10.** The observatory-watcher's P2
     predicate (verb count ≥2 → build the umbrella) fired, forcing the decision.
     Resolved *not to build*: the umbrella can't consolidate — the `tessera-*`
     binaries are mostly hook-invoked and callers reference them by name, so an
     umbrella adds a human-facing alias layer on top without retiring anything, for
     a surface typed by hand a few times a month. The trigger fired on a proxy (verb
     count) that tracks no real friction. **P2 retired from `bin/tessera-watch`**
     accordingly — the watcher's first real lesson: a predicate can fire correctly
     on its proxy while the proxy tracks no pain; the honest response is to fix the
     predicate, not build what it flagged. Revisit only if a genuinely hand-driven
     multi-command `tess` workflow ever emerges (not verb count).
  2. **Actual gate-bypass semantics** — v1 is **audit-only** (detect + log + review; native skip does the skipping). A mode where an annotation actively suppresses a specific failure was rejected (hard to scope from a whole-suite run; invites silent green). Revisit only if "log it" proves too weak in dogfood.
  3. **Healthcare compliance-review extension** (§54) — required-review-on-override for the healthcare layer. Out of scope until the healthcare layer activates.
- **Status:** Deferred (core built)
- **When to revisit:** #1 resolved (declined, 2026-07-10) — reopen only on a real hand-driven `tess` workflow; #2 if audit-only proves insufficient in dogfood; #3 with the healthcare layer.

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
- **Update, 2026-07-11 — the layer executed for the first time, and it worked.** A hand-run `/compact` (the first compaction of any kind, ever) exercised the whole path end to end:
  - `compaction-log.jsonl` **exists** — one `compaction_fired`, tagged `trigger: "manual"`, followed by `restore_injected`. The marker was **consumed, not orphaned**.
  - **Layer 2 delivered.** `mnemos-session-start.sh` fired on `source=compact` and put the goal, constraints, and a freshly-`--force`d checkpoint into the post-compaction context. No re-derivation was needed. The summarizer also honored the PreCompact preservation block — `## Mnemos Task State` landed verbatim in the summary.
  - **Layer 3 remains unproven.** It logged `restore_injected` and consumed the marker correctly, but its `CONTEXT RESTORED AFTER COMPACTION` text was never *observed* reaching the model. The plumbing ran; the injection is unconfirmed. Operationally moot (Layer 2 had already delivered — exactly the redundancy the design is for), but do not record it as proven.
  - **Prerequisite fix, same day:** PreCompact now reads the hook's stdin and records `trigger` (`manual` vs `auto`), and P3 counts only non-manual events. Without this, three deliberate *tests* of the recovery layer would have delivered the trial's verdict on manufactured evidence — the P2 failure exactly (a predicate firing correctly on a proxy that tracks no real pain). P3 correctly read `0 real (1 manual test excluded)` after the run.
  - **Still untriggered where it counts.** `trigger: auto` — compaction firing unbidden at ≈83% context, mid-turn — has never happened. Same hook, same code path; the only difference is who pulls the trigger. The trial's clock has **not** started.
- **SUPERSEDED 2026-07-26 by ADR-0015 — the trial was scoped to the wrong event.** Everything below
  is kept as the trail (the flapping history is itself the evidence), but the framing is retired.
  `mnemos-session-start.sh` gates on nothing but the checkpoint file existing, so the restore path
  runs identically on `startup`, `resume`, and `compact`: **541 checkpoints, 121 sessions, ~3
  compaction events.** The mechanism did not run 3 times, it ran ~121. This entry spent 37 days
  waiting on the rarest *trigger* — ~2% of invocations — of a mechanism that was running constantly
  and unwatched. Standing pattern #3, and worse than usual: a proxy normally *correlates* with the
  pain; this one tracked a fiftieth of it. The 2026-07-26 goal-blob defect was degrading **all ~121
  restores** and was found via compaction only by accident. See ADR-0015 for the three-way split
  (T1 deliverability / T2 sufficiency / T3 frequency) and the retirement of `COMPACTION_MIN`.
- **Status:** Trial **re-scoped, not concluded** (ADR-0015). `tessera-watch` P3 is now
  `p3_restore_integrity` — a mechanical guard on payload deliverability, explicitly **not** a
  verdict. **T2 (does the agent resume without re-deriving?) is the sole blocker on a real verdict,
  and its instrument is unbuilt.** Until then no verdict is available — not keep, not kill.
- **Historical status (pre-ADR-0015):** Trial **re-armed on an event trigger** (calendar trigger retired). Recovery path **exercised once (manual)**; awaiting a real `auto` event.
- **When to revisit (CURRENT, per ADR-0015):** when **T2's instrument ships** — a model-emitted
  receipt, gate-event shaped, recording whether the agent resumed without re-deriving. That is the
  only thing that can produce a verdict, because `restore_injected` is **a log line the hook writes
  about itself**, not evidence the model received anything. The log shows four; the model got
  nothing on all four. Re-scoping from 3 events to 121 gives 121 self-reports — **volume does not
  fix provenance.** Also revisit if Layer 3 ever delivers to a model even once (it never has), or
  if a restore is observed failing while P3 is green (that would make T1 a proxy too).
- **When to revisit (RETIRED — the criterion ADR-0015 replaced):** **Not on a date.** When `compaction-log.jsonl` records **≥3 non-manual `compaction_fired` events**, judge: did `restore_injected` follow each one, and did the restored checkpoint actually let work resume without re-deriving? Then keep or drop on evidence. A `compaction_fired` with no matching `restore_injected`, or repeated `restore_missed_stale`, is a **failure** signal — distinct from the **untested** signal of an empty log. **`trigger: manual` events never count**: a hand-run `/compact` is a test of the layer, not evidence about it (`tessera-watch` P3 enforces this).
- **Standing caveat:** the trial is about the **compaction-recovery** layer. Mnemos's **session-continuity** layer (checkpoint written on Stop, reloaded on SessionStart) is separately and visibly working — 148 nodes, 134 checkpoints, restores every session. The two got conflated in the original framing. Session-continuity earns its keep on its own; do not let its success vouch for the untested layer, or its trial's failure condemn it.

### Mnemos/iCPG installed on homebrew system python — venv is the durable fix

- **Source:** Same 2026-06-26 session (the interpreter-mismatch root cause above).
- **What it is:** `mnemos`/`icpg`/`polyphony` are `pip install --break-system-packages` into homebrew's python (currently 3.13). When homebrew bumps the default `python3` (it moved to 3.14), bare `python3 -m mnemos` stops resolving the package — the break that silently emptied the Mnemos graph.
- **Mitigation in place:** hooks now resolve the package's interpreter from the `mnemos` console-script shebang, so the pipeline is version-agnostic regardless of which `python3` is default. The symptom is handled.
- **The deferred decision:** the *durable* fix is a dedicated venv (pins the interpreter, immune to homebrew bumps, no `--break-system-packages`). NOT doing it now — reinstalling for each new homebrew python is a treadmill, but a venv is a packaging/install change touching `install.sh` + the bin scaffold, larger than this session warranted. The console-script resolution holds until then.
- **Update, 2026-07-11 — the "just upgrade and deprecate the old one" escape hatch is CLOSED.** Measured, not assumed:
  - `python@3.14` is `installed_on_request: **False**` — Homebrew pulled it in as a **dependency** of `awscli`, `httpie`, `mlx`, `mlx-c`, and **`ollama`** (which the tier-classifier hook runs on). **It cannot be removed.** It owns the `python3` name and has *nothing* installed in it.
  - `python@3.13` is `installed_on_request: **True**` and **nothing in brew depends on it.** It holds the entire toolchain: pytest, pyyaml, mnemos, icpg. It is the *removable* one — the exact inverse of the intuitive read.
  - So migrating the toolchain into 3.14 and dropping 3.13 is *possible*, and **still wrong**: **Homebrew owns the `python3` name and re-points it whenever a dependent formula moves.** 3.14 arrived because ollama/awscli wanted it; 3.15 will arrive the same way and orphan the toolchain again. Migration **resets the clock, it does not stop it** — and it hands the interpreter choice to whatever `awscli` decides next release.
  - **The venv remains the only fix that addresses the class.** This entry said so on 2026-06-26 and was right.
- **The reminder is now mechanical, not prose.** `tessera-watch` **P9 (interpreter-drift)** probes whether bare `python3` can import the toolchain and fires when it cannot — which it does today, and will every session until the venv lands. That is intentional: it is real unresolved debt, and after 3 consecutive runs G-a escalates it. **This is also the F-001 detector we never had** — F-001 was exactly this failure (hooks calling bare `python3` against a package installed elsewhere) and it was *silent* for weeks, confounding the whole Mnemos trial. Nothing watched for a recurrence until now.
- **RESOLVED 2026-07-12 — the venv landed, on a `uv`-managed interpreter.** This entry opened on 2026-06-26 and was right the whole time.
  - **Base is `uv`-managed, NOT Homebrew.** `~/.local/share/uv/python/cpython-3.13.14-…`, pinned by a tracked `.python-version`. `uv` itself is a static binary with **no libpython linkage** — brew cannot break it. A *brew-based* venv was considered and rejected: it would root the fix in the very package manager that caused the problem. **Installed via uv's standalone installer, deliberately not `brew install uv`** — reintroducing the coupling in the first line of the fix would be absurd.
  - **The initial recommendation was brew-based, and it was wrong.** It was reflex ("don't add a dependency") applied without checking whether the cheap option *met the requirement*. It doesn't: the requirement is *never again suffer a silent interpreter break*, and our hooks all **fail open** — so a broken base interpreter degrades into **silence**, which is F-001 exactly. `uv` is a *build-time* tool with no runtime coupling; the anti-dependency rule never applied to it. Corrected on pushback.
  - **The toolchain is now singular.** Removed from Homebrew's python (editable `.pth`, finders, dist-infos, console scripts — all of it). Console scripts are symlinked into `~/.local/bin`, which precedes `/opt/homebrew/bin`. **`tessera/bin` does NOT** — it sits at PATH position ~17, *behind* brew, so a symlink there would have been silently shadowed by the leftover brew copy while everything *looked* fixed.
  - **F-001 happened again, live, during the session that fixed it — and it is the best evidence the fix was needed.** `uv python install` shimmed the name `python3.13` into `~/.local/bin`, ahead of Homebrew. A `pip uninstall` and its verification both silently addressed **uv's** interpreter instead of brew's, and *reported success*. `run-tests.sh`'s `python3.13` pin became a different interpreter with no pytest. **A name is a lookup through a mutable, ordered PATH that four package managers write to. A path is a path.** Every interpreter reference is now a path, and there is no fallback to `python3` — a silent fallback to a toolchain-less interpreter is how F-001 stayed invisible for six weeks.
  - **P9 was rewritten, and had to be.** Its old predicate (*"bare `python3` can import mnemos"*) **could never go green after the fix it was demanding** — post-venv, bare `python3` *should* fail that import. It would have fired forever, G-a would have escalated forever, and the only exit would have been snoozing our own detector. That is the pre-commit lesson inverted: **a detector that cannot go green teaches you to ignore the watcher.** It now asserts the invariant F-001 actually violated: *the interpreter the consumer resolves must be able to import what it imports*, and its base must not be a package manager's.
  - **P9 also had a hole, found by testing the failure and not just the fix:** with the venv absent, `~/.local/bin/mnemos` dangles, `shutil.which` returns `None`, and P9 said *"nothing to drift from"* — **silent on the worst possible state**, the toolchain gone entirely and every hook failing open into quiet. Absence is the loudest drift there is. Fixed and re-tested by parking `.venv` and watching it fire.
  - **The venv is the mechanism; the guardrail is a check.** A venv does not stop anyone typing `python3` in a new script tomorrow. `doccheck`'s **`no-bare-python3-with-toolchain-import`** fails if any hook invokes bare `python3` on code importing a venv-only module. `guard.py`, `backstop.py`, `emit.py`, `scan.py` and `doccheck.py` are stdlib-only *on purpose* so bare `python3` stays safe for them — a split that was the de facto design for months and had **never once been enforced**.
- **Status:** **RESOLVED.** P9 green. `./install.sh` builds and verifies the venv, idempotently; verified from scratch by parking `.venv` and rebuilding.
- **When to revisit:** P9 fires every session now, so this cannot be quietly dropped. Do the venv when there is a clear runway — it touches `install.sh` + the bin scaffold. Hard trigger: **before the first unsupervised downstream run** (ADR-0005). A silent interpreter break in an agent nobody is watching is precisely F-001, with no human present to notice the graph went empty.

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
- **Update, 2026-07-21 — P4 now diffs bytes, and it immediately found real drift.** The watcher's
  P4 predicate was `len(downstream_projects) >= 5` — a *proxy* for drift risk. Adopting settempo
  (`hook_distro: global`, zero local copies) tripped it while adding exactly zero drift surface,
  and the fired message could not name a single stale file. That is the P2 failure shape again:
  a predicate firing correctly on a proxy that tracks no real pain. **This entry had already
  written the fix two bullets up — "a drift check that doesn't compare bytes isn't a drift
  check" — and the check still didn't compare bytes.**
  P4 now diffs each downstream's `.claude/scripts/mnemos-*.sh` against `~/.claude/templates/`,
  reporting `drifted` (differs) and `orphaned` (no global counterpart) by name. On its first run
  it found **3 stale copies of `mnemos-pre-compact.sh`** — in heaviside, howler, and
  tess-dashboard, all three `frozen` projects — silently running an older hook than the global
  source. The count predicate never saw them and never would.
  Two properties the old one lacked: it **names the file**, and it **can go green** (sync the
  copies and it stops firing). A predicate that cannot be resolved teaches you to ignore the
  watcher — the lesson P9's docstring records.
  **Still open:** the 3 stale copies are not synced. These are deliberately-frozen ship-critical
  repos (howler is shipping two platforms), so re-freezing is their owners' call, not a
  drive-by. The added trigger below — teach `tessera-hooks status` to diff all three layers by
  content — is now half-built: P4 covers the downstream↔global layer, doccheck's
  `hook-templates-match-live` covers `templates/`↔`.claude/scripts/`. Nothing yet covers
  `templates/` ↔ `~/.claude/templates/`, the layer `install.sh` writes.
- **Update, 2026-07-22 — the freeze rationale was reviewed, and 2 of 3 had none.** P4's byte-diff
  prompted the question nobody had asked since the freezes were set: *are these projects frozen
  for a reason that is still true?* All three were frozen on the **same day (2026-07-12)** — one
  batch, not three decisions. Reviewing them:
  - **howler** — "churn-immune while shipping to store" (ADR-0004). **Still true**; shipping two
    platforms as of 07-19. Stays frozen and stays stale, deliberately: the drifted hook buys a
    shipping app nothing.
  - **heaviside** — no rationale recorded anywhere, nothing shipping, two active days. **Thawed**
    (`2319e24`). All 7 hook commands verified resolving to executable global targets first.
  - **tess-dashboard** — its own `project.yml` said *"thaw to global when convenient"*. It was
    never meant to persist. **Blocked on the settings gap below.**
  **The real finding is that freeze is a sticky, unreviewed state.** You enter it for a reason,
  the reason expires, and nothing re-asks. The drift was the symptom; the unreviewed freeze was
  the cause. Any future freeze should carry its reason *in `project.yml`* — howler's did, which
  is exactly why howler's was the one that survived review.
- **`tessera-hooks status` now compares BYTES (2026-07-22).** Its usage line advertised a "drift
  check" from day one while only comparing declared-mode against local-copy *count* — the gap
  this entry named two bullets up and then did not close. It now reports `DRIFTED` / `ORPHANED`
  per file against `~/.claude/templates`, skipping `source` repos (where the comparison is
  circular). Guarded by doccheck `hooks-status-compares-content`, which was verified to go red
  when the byte comparison is removed.
- **ADR-0004's deferred settings auto-patch is BUILT, and F-003 is closed (2026-07-22).** The
  trigger — *"first real thaw of a grandfathered repo (build the settings auto-patch then)"* —
  fired on tess-dashboard, whose 7 hook commands were all local-only
  (`if [ -x .claude/scripts/X ]; then exec X; fi`) with `statusLine` a bare local path, the
  pre-`eb21914` shape this entry calls "the literal root cause". `thaw` correctly refused rather
  than silently disabling every hook.
  `scripts/hooks/patch_settings.py` rewrites those to the two-tier form;
  `tessera-hooks thaw --patch-settings` runs it first. It **refuses on any command shape it does
  not recognise** rather than guessing — a settings patcher that guesses is worse than one that
  stops — and leaves non-mnemos hooks (gate-scan, spend) alone, since those are project-local by
  design. 8 tests, including idempotence and that a refusal leaves the file byte-identical.
  **All three frozen repos are now `global`.** howler was thawed too, mid-iOS-ship, on the
  reasoning that mnemos hooks are *dev-time instrumentation that never enters the app binary* —
  the only exposure is a wedged dev session, and it was already running the stale hook that drops
  compaction events. One command (`tessera-hooks freeze`) reverts it.
  **`frozen` now has zero users**, so the propagation-mechanism question that opened this
  discussion evaporates rather than needing an answer: with no local copies anywhere, there is
  nothing to propagate *to*. The capability stays for the next genuinely ship-critical freeze —
  and the lesson stays with it: **record the reason in `project.yml`.** howler's was the only
  freeze rationale ever written down, and it was the only one that survived review.
  **P4 is green.**
- **The sibling gap, found the same day and closed: nothing back-filled the harness either
  (2026-07-22, `bin/tessera-sync-harness`).** ADR-0004's freeze/thaw story was about hook
  *scripts*; the same silence covered every other harness component. `tessera-new-project` ships
  the harness once and nothing ever revisits it, so each component added later existed only in
  projects scaffolded after it. Measured: **tess-dashboard had no gate harness at all** — no
  `emit.py`, no `scan.py`, no `tessera-gate-scan.sh`, no wiring — so every gate there rode pure
  model recall with no backstop, the ~85% miss rate this observatory measured. howler had no
  spend guard. All four pre-settempo repos ran a **retired gate vocabulary** (no `KINDS` enum
  from spec 15, no `turn_id` from F-001). *"Ship both halves or neither" violated by **time**
  rather than by a missing `cp`* — and the scaffold gained two components that same day, so it
  recurs by construction.
  Two design points worth keeping. **The tool diffs against a reference project scaffolded by
  the real `tessera-new-project`**, so it carries no second definition of "what the harness is" —
  a hardcoded list would be F-003's own shape inside the tool built to clean it up. And
  `--update-stale` is gated on a **proof, not a judgement**: a file is refreshed only if its
  bytes match some commit in tessera's history, which demonstrates it was never customized
  downstream. That check turned "a per-file decision across three sessions" into one mechanical
  update — all three stale repos held byte-identical copies of the same two old commits.
  Fleet is current. Only howler's spend guard is outstanding, deliberately (deny-by-default
  hook, mid-iOS-ship; belongs in a howler session).
- **Status:** Adopted → ADR-0004; **re-opened** on the authoring-propagation gap
- **When to revisit:** per ADR-0004's re-evaluate triggers — first real `thaw` of a grandfathered repo (build the settings auto-patch then), a `global` project found silently dead on a machine, or project count crossing ~4–5 with several still `frozen`. **Added trigger (now):** teach `bin/tessera-hooks status` to diff `.claude/scripts/` ↔ `templates/` ↔ `~/.claude/templates/` by content and report drift, or make `templates/` a symlink/generated artifact rather than a hand-maintained third copy. Until one of those lands, every hook edit needs a manual three-way sync — which is precisely the failure mode that produced this entry.

### New-machine bootstrap is tribal knowledge, not a script

- **Source:** Tessera dogfood, 2026-06-27. After a machine move, `install.sh` had never been run — the global layer (`~/.claude/{skills,commands,templates}`) was empty and nobody noticed because every project carried local copies.
- **What it is:** Standing up Tessera on a fresh machine takes four steps that live only in scattered docs / past findings, not one bootstrap: (1) `install.sh` (populate global layer); (2) mnemos pip install **pinned to arm64** (`/opt/homebrew/bin/pip3.13`) with a shebang-resolves check (**F-001** — a dead shebang silently disables every Mnemos hook); (3) ollama + `qwen2.5-coder:3b` pull (else routing fails open to Sonnet — degraded, not broken); (4) Claude transcript slug rename if migrating `.mnemos`/history (**F-002** — slug derives from realpath with on-disk casing).
- **Why it caught our attention:** the empty-global-layer state is a silent-success failure mode — everything works via local copies, so the missing `install.sh` is invisible until you rely on the global fallback. Same shape as the F-001 dead-shebang and the shell-alias/wrong-CWD bug: the framework appears installed while a layer is quietly absent.
- **Update, 2026-06-27 — `verify()` shipped (`51f9f26`).** install.sh now runs a post-install verify: hard-aborts (exit 1) if the global layer is empty, mnemos is off-PATH, the mnemos shebang is dead (F-001), or the scaffold settings.json is invalid; warns-only if ollama/qwen are absent (routing fails open). The silent-success mode is closed — install.sh now loudly fails when the machine isn't known-good. Fail + happy paths both tested.
- **Status:** **RESOLVED 2026-08-09** (the entry was stale for months; see below).
- ~~**What's still open:** install.sh **verifies** mnemos but does not **install** it — that remains the `docs/install.md` Step 2 manual workaround (copy maggy source into a nested layout, arm64-pinned pip) because the upstream `maggy/scripts/mnemos` flat-layout `pyproject.toml` can't be `pip install`ed directly.~~ **`install.sh` HAS INSTALLED THE TOOLCHAIN SINCE THE VENV LANDED** — `uv pip install -e scripts/{mnemos,icpg,polyphony,skill_lint}` — and the maggy workaround it describes was deleted from `docs/install.md`, which now says plainly *"There is no `pip` step any more."* The revisit trigger below is moot for the same reason: Tessera **vendors** `scripts/mnemos/`, so upstream packaging cannot gate this. F-002 slug rename stays out of scope (migration, not fresh-install).
- **And the entry gained a step on 2026-08-09:** `install.sh` now also initialises **`.icpg/reason.db`**, which had no owner at all — no script created it, none checked it — while three live hooks depend on it. `verify()` asserts it. Same shape as the empty-global-layer failure this entry opened with: a layer quietly absent while everything looks installed.
- **How this was caught, because the mechanism is the point:** not by a check. The `tessera-decision-surface.sh` PreToolUse hook surfaced this entry when `docs/install.md` was edited, and reading it revealed the stale claim. A prose "what's still open" has **no mechanical subject** — asserting it would be a judgement wearing a regex (#3's corollary) — so the honest guard is exactly what happened: surface the governing record at edit time and make a human read it.
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

### iCPG cannot see 68% of this repo — the scope-quality question was downstream of a corpus question *(2026-07-27)*

- **Found by authoring one intent and running the loop**, which is the cheapest probe available and
  had never been run: `icpg create` → do the work → `icpg record`. Record returned
  **`Recorded 0 symbols`** for a changed file that is full of `def`s.
- **Cause:** `symbols.py` dispatches on file *extension* via `LANG_MAP`. `bin/tessera-verify` has
  none. Neither `.sh` nor extensionless files are in the map at all.

  | | in repo | iCPG sees |
  |---|---:|---|
  | `.py` | 168 | 84 |
  | `.sh` | 57 | **0** |
  | extensionless executables | 35 | **0** |

  **84 of 260 code files — 32%.** Every tracked symbol is `.py`. Tessera is predominantly shell
  and extensionless executables, so the framework is largely invisible to the layer built to
  track its intent.
- **THE NUMBER THAT DECIDES ITEM 1: 46 of 56 scope entries across all reasons point at files iCPG
  cannot parse. Three point at files it can.** The scopes name `.sh` hooks,
  `hooks/tier-classify-hook`, `.claude/settings.json`, `pyproject.toml`, `design-principles.md` —
  none can hold a symbol, ever.
- **So "46% of symbols are CREATES-linked to a reason whose scope excludes their file" is not
  evidence of incoherent claims.** It follows mechanically from scopes naming files that cannot
  contain symbols. The scope vocabulary (any repo path) and the symbol vocabulary (in practice,
  `.py`) barely intersect. Every prior reading of that figure attributed to *bootstrap scope
  quality* what was actually *extractor coverage*.
- **Second finding, same run: the contract tier the design doc names first has no interface.**
  `--infer-contracts` produced `preconditions: []`, `postconditions: []`, and invariants that are
  the scope restated as `file_exists()` — the heuristic fallback, because inference needs an LLM
  key. `design-principles.md` describes "hand-authored for high-risk intents, LLM-inferred, or
  heuristic"; the CLI exposes the bottom two. There is no flag to author a precondition.
- **THE CHURN THIS ENTRY EXISTS TO STOP.** Item 1 has been re-scoped three times and decided zero:
  thresholds → scope quality → corpus coverage. Each step was evidence-driven and correct, and
  collectively it is a regress that will produce a fourth. **The stopping rule is recorded in
  `active.md` item 1 and is binding: extend the extractor once, re-measure once, then DECIDE —
  and if `usage` still fails to discriminate over a corpus that includes the framework's own
  code, retire it.** No fourth investigation. A dimension that has consumed three cycles without
  producing a signal has been given a fair hearing.

- **CLOSED 2026-07-27 — the stopping rule was followed and the branch it named fired. `usage` is
  RETIRED (ADR-0017).** Step 1 shipped: `symbols.py` gained `.sh`/`.bash`/`.zsh`, shebang
  detection for extensionless executables, and a regex shell extractor — corpus **84 → 261 of
  261 code files**. Step 2 measured over that corpus: 6468 CREATES-linked symbols, 986 fires
  (15.2%), and the top firers were `ok` 311, `run` 262, `err` 247, `ev` 373, `read` 285,
  `check` 271. `git grep --fixed-strings` matches **substrings**, so `ok` hit "hook" and
  "token" in a repo whose subject is hooks: the dimension scored **name commonness**. The
  word-boundary rescue was tested inside step 2, before retiring rather than after — `-lw` cut
  `ev` 373→14 and left `read` 180, `run` 214, `check` 171, all still pinned at 1.00. There was
  **no step 3**, and the two side-findings below are their own entry, not a fourth scope.
- **The corpus fix was necessary and did not change the verdict — worth separating.** Shell
  fired at 68.6% against python's 13.3%, which looks like the new coverage drove the result. It
  did not: the gap is entirely name length (shell function names are 2–6 chars), and **python
  alone fires 829 times** on the same collisions. The extractor work was needed to make the
  hearing fair, not to reach the answer.

### The checkpoint's goal was 40 sessions stale, and `created_at` was the proxy that let it happen *(2026-07-27)*

- **Status:** Fixed. Found by *reading what a live compaction actually delivered*, not by audit.
- **What was observed.** Layer 3's post-compaction restore block stated the goal as
  *"Phase 3: scaffold `.tessera/` profile and config structure"* — the project's opening days.
  Layer 2, nine minutes earlier, had stated this session's real goal. Two checkpoints, and the
  **newer** one carried the **older** goal.
- **Mechanism.** `bridge-icpg` runs backgrounded on every SessionStart. A re-bootstrap earlier
  that session regenerated all 43 iCPG ReasonNode ids; the bridge dedups on `content`, which
  embeds `[iCPG:<id>]`, so **every one missed the cache** and was minted fresh at import time.
  44 goals sharing one `created_at` took all 8 checkpoint slots.
- **The load-bearing detail: constraints came through the same import CORRECTLY** — 3 new against
  53 existing — because their dedup key is the invariant text, which survives a rebuild. One
  bridge, two keys, and only the one coupled to a regenerated id broke. That asymmetry is what
  identifies the bug; a count of "how many nodes did the bridge add" would have shown both halves
  growing and explained nothing.
- **Why the guard already in place did not catch it.** The 2026-07-26 fix replaced weight-sort
  with `created_at`-sort precisely because equal weights made ordering arbitrary — and it was
  right. But `created_at` is *also* a proxy for relevance, and it holds only while nothing writes
  goals in bulk. It survived one day. `test_checkpoint_goal_cap.py` passed throughout: it asserts
  the cap holds and the NEWEST goal survives, and the newest goals were exactly the wrong ones.
  **A test that asserts "newest survives" cannot see that newest stopped meaning relevant.**
- **Fix.** `_select_goals()` excludes `origin='loaded'` outright (bridge imports are historical
  intents, never current work) and ranks the live session's own goals first — the hook already
  parsed `session_id` for `degraded` reporting and simply never passed it, while `--task-id`
  existed on the CLI the whole time. Exclusions are stated in the goal text, not silent.
- **A prediction of mine that the live data refuted, kept because it changed the design.** I
  reasoned the `--task-id` match would never hit, since checkpoint runs *before* ingest in the
  Stop chain, so the current session's goal node would not exist yet. Wrong: **Stop fires per
  turn, not per session**, so ingest has run many times by then and the goal is present. Verified
  against the live database — the goal field now leads with this session's actual opening prompt.
- **Three copies, and only two synced.** The hook exists at `.claude/scripts/` (source, per
  `hook_distro: source`), `templates/` (what ships downstream), and `~/.claude/templates/` (the
  ADR-0004 global fallback). `./install.sh` propagates to the third but **not** the second;
  doccheck's `hooks-match-templates` caught the gap. Standing pattern #5 with a third half.

### A disposition verb that did not move the headline — `icpg status` disagreed with its own list *(2026-07-27)*

- **Status:** Fixed, regression-tested (`test_stats_headline_agrees_with_the_list_it_summarises`,
  watched RED against the old predicate before being accepted).
- **What happened.** ADR-0017's retirement dismissed 165 drift events. `icpg status` then printed
  `Unresolved drift: 224` directly above `icpg drift list  # all 59`. `get_stats()` counted
  `WHERE resolved = 0` alone; `get_unresolved_drift()` filtered `resolved = 0 AND dismissed = 0`.
  Two definitions of "unresolved" in one file.
- **Why it matters more than an off-by-N.** ADR-0016 built `dismissed` *as a disposition* — the
  verb that lets a false positive leave the open set. A headline that ignores it means **disposing
  a finding changes nothing in the number anyone looks at**, which is exactly ADR-0013's
  only-increments counter, alive in a second function after the first was fixed. `icpg status` is
  what SessionStart surfaces and what the checkpoint's `icpg_state` stores, so the wrong number is
  the one with the widest reach.
- **Why it stayed invisible for two days.** Exactly ONE event had ever been dismissed, so the two
  counts differed by 1. The bug needed a *bulk* disposition to open a gap wide enough to see. Had
  the 165 been dismissed a few at a time, the discrepancy would have grown slowly and looked like
  normal backlog.
- **The reusable form.** *A disposition verb needs a test that the headline moves* — not just that
  the row's state changed. The regression asserts the two counts **agree**, rather than asserting
  either number, because the failure was disagreement between a summary and the thing it
  summarises. Both halves were individually "correct"; neither was checked against the other.
- **Adjacent, still open:** the 59 real events now visible are dominated by symbols deleted in the
  two detector shrinks (`_check_spec_drift`, `_check_ownership_drift`, …) — genuine `changed(0.80)`
  findings whose disposition is `resolve` (the removal was intended), not `dismiss`. Not swept
  here; that is a judgement per event, and auto-resolving is how a backlog gets laundered.

### The declared-vocabulary guard keyed on a NAMING CONVENTION — one rename walked past it *(2026-07-27)*

- **Status:** Fixed same hour. Kept because it is standing pattern #1's third instance in this
  one subsystem, and the first two were also found by `bin/tessera-verify`.
- **What happened:** ADR-0017 retired `usage` and added an assertion to
  `test_drift.py` that the dimension stays gone. The Stop hook's verify-scan fired on a false
  positive (it named `scripts/doccheck.py`, which this session only *ran*), but the claims were
  worth falsifying anyway, so they went to the falsifier. Verdicts: CONFIRMED / CONFIRMED /
  **PARTIAL**.
- **The hole.** The guard read
  `re.findall(r"\(\s*'(\w+)',\s*_check_", inspect.getsource(check_symbol_drift))` — keyed on the
  `_check_` prefix. The falsifier re-added `('usage', _usage_score(store, sym))` returning `None`
  and **all 34 tests stayed green**. Renaming one function evaded the only guard that can see a
  silent dimension.
- **Why that shape specifically is the dangerous one, and why nothing else covered it.** A
  dimension that *fires* is caught observationally — the falsifier confirmed a scorer returning
  1.0 trips two other tests under any name. A dimension that returns `None` forever reaches no
  output, so only source inspection can see it. That is the exact failure class this test was
  invented for after `ownership` slipped both guards. doccheck's
  `drift-dimensions-have-producers` is **not** a backstop: it scans EDGE TYPES read by
  `drift.py`, and `usage` never read one — it produced no finding under either landmine.
- **Fix:** match any callable in the scored tuple — `r"\(\s*'(\w+)',\s*[\w.]+\("` — not one
  naming convention. Verified by replanting the landmine and watching the fixed guard fail it,
  then reverting.
- **The reusable lesson, sharper than the existing one.** Standing pattern #1 says *test a new
  check against the failures you did not just fix*. This adds: **a guard that reads source must
  not key on a convention the code is free to break.** The convention was mine, held everywhere
  in the file, and looked like a safe anchor — which is what made it invisible. Both prior
  instances in this subsystem had the same shape (an untyped edge read; a presence-scored
  dimension), and all three were found by the falsifier rather than the suite.

### Is the SYMBOL the right unit for a shell-heavy repo? — corpus coverage bought files, not symbols *(2026-07-27)*

- **Status:** Open. Logged as its own entry because ADR-0017's stopping rule forbade a step 3;
  these are the two findings step 1 surfaced that are **not** part of that decision.
- **Finding 1 — 46 of 78 shell files have ZERO symbols.** The extractor now parses every `.sh`
  and every extensionless `bin/tessera-*`, and coverage went 84 → 261 of 261 code files. But
  Tessera's hooks are **straight-line scripts**, not function libraries: they `set -euo pipefail`
  and run top to bottom. Shell contributes **76 symbols of 1968**. Coverage bought *files*, not
  *symbols*.
- **Why this matters beyond trivia:** iCPG anchors intent to *symbols*, and `changed` — the
  dimension that survived ADR-0017 — is a per-symbol checksum. So for 46 of 78 shell files there
  is nothing to anchor to and nothing to checksum. The layer built to track this framework's
  intent still cannot track the majority of its shell, and the reason is no longer extractor
  coverage — it is that **the unit of tracking does not match the unit of authorship**.
- **The candidate answer is already on the books, which is why this is Open and not a proposal:**
  ADR-0013 §4 rated scryer's file-level predicate (*"this file changed since we last reconciled
  it"*) as "Idea-only — open, do not adopt yet." A **file-level** `changed` would cover the 46.
  That is a design decision needing its own evidence, and adopting it because one measurement
  pointed that way would be the exact re-scoping ADR-0017's stopping rule exists to prevent.
- **Do not read this as "shell coverage was wasted."** The 32 shell files that *do* define
  functions are now tracked, and the extractor is what made ADR-0017's measurement fair. The
  open question is the remaining 46.
- **Finding 2 — `icpg create` has no flag to hand-author contracts.** `design-principles.md`
  names three authoring tiers (hand-authored / LLM-inferred / heuristic); the CLI exposes the
  bottom two, and `--infer-contracts` falls back to heuristic without an LLM key. This is why
  **Q1** (does the agent populate ReasonNodes in practice?) still rests on a single non-bootstrap
  data point. Restated here because the entry above recorded it and that entry is now closed.
- **Revisit when:** a file-level drift predicate is proposed, or Q1's recording half is wired.

### Effort changes invalidate the prompt cache — and the tier advisory's real use is session boundaries *(2026-07-27)*

- **Measured, because the docs do not say.** `output_config.effort` is absent from the
  prompt-caching invalidation hierarchy, which lists model switch (invalidates tools+system+messages)
  and `thinking` enable/disable (preserves tools+system). The plausible reading — and the one I
  argued for before measuring — was that effort behaves like `thinking`: a cheap knob you could
  turn mid-session where `/model` is expensive. **Three requests said otherwise:**

  | request | write | read |
  |---|---:|---:|
  | 1. `effort=high`, cold | 2163 | 0 |
  | 2. `effort=high`, identical prefix (**control**) | 0 | **2163** |
  | 3. `effort=low`, identical prefix | **2163** | **0** |

  Row 3 did not merely miss the messages tier — it re-wrote the entire system prefix. Effort is
  model-switch-grade. `scripts/effort-cache-probe.sh` reproduces it.
- **The control is why this is a result and not a guess.** Without row 2, row 3's zero would be
  indistinguishable from "caching never engaged" — the probe returns `VOID` in that case rather
  than a verdict. That is the same shape as the fire-counter discriminator found earlier the same
  day: a mechanism reporting nothing and a mechanism that is dead present identically, and only a
  second reading separates them.
- **Known limits, n=1:** one model, one prefix size, `high→low` only. Untested: adjacent steps
  (`high→xhigh`), the reverse direction, and whether each level keeps its own entry — row 3's
  *write* suggests it does, which would mean returning to `high` hits rather than re-writes. This
  is external API behaviour: it can change upstream, and no doccheck assertion can guard it.

- **The other half, and it corrects an assumption in ADR-0002.** The ADR frames the main-thread
  tier as *"advisory (suggest `/model`)"* — i.e. mid-session switching, which the cache tax then
  argues against, leaving the flag apparently self-defeating. **That is not how it is used.**
  Lorenzo, asked directly (2026-07-27): the flag is a **gauge**, valuable whether or not it is
  acted on in-session — *"I tend not to invoke it unless it's at the beginning of a session, or it
  might prompt me to start a new session and toggle the model."*
- **Why that resolves the tension rather than dodging it:** a new session pays a cold cache
  anyway, so acting at a session boundary costs nothing the boundary was not already costing. The
  flag's value is *orientation* — am I on the right model for what I am about to do — not
  mid-flight correction. Both knobs now point the same way: model and effort are session-boundary
  decisions, not per-turn ones.
- **This also answers the not-vacuous question** raised against the tier advisory the same day
  ("if nobody acts on it, 'it works' and 'it is decorative' are indistinguishable"). The answer is
  that it is used, in a mode the design did not anticipate and the docs did not describe.
- **An effort-mismatch statusline flag was proposed and DECLINED (same day). Do not build it.**
  `CLAUDE_EFFORT` is a live session env var (`high` here), so a tier/effort mismatch would be
  *readable rather than predicted* — which is why it looked attractive. Three reasons it fails:
  1. **No per-turn signal.** The model-tier flag earns its statusline slot because its input —
     the prompt's shape — changes every turn. Effort is session-scoped: same value every turn,
     so the flag is wallpaper. This repo has retired three predicates for firing correctly while
     meaning nothing.
  2. **The mismatch does not exist yet.** The classifier emits a *model* tier; there is no
     model-tier → correct-effort mapping anywhere. Flagging "OPUS but effort=low" means inventing
     that mapping and then measuring the invention — principle-#3's failure aimed at the proposer.
  3. **Category mismatch with the finding above.** Both knobs are session-*boundary* decisions; a
     statusline is a per-turn channel. The venue that would fit is SessionStart, where no prompt
     has been submitted yet and there is therefore nothing to compare against. It has no good home.
- **The meta-lesson, which is the more transferable half:** this proposal was floated three times
  and shrank every round — second classifier dimension → read the env var → statusline flag → 
  nothing. **A proposal that keeps shrinking under evidence is usually converging on zero.** Each
  smaller version was re-floated instead of asking whether the shrinkage *was* the answer; the
  human's "or is that getting too micro?" is what stopped it. Watch for that shape.

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
- **CLOSED 2026-07-22 → ADR-0012: ADOPTED, warn-only. Supersedes ADR-0011 below.** ADR-0011
  answered "would sqlfluff find defects in settempo's SQL today" (no); the actual ask was
  "implement it across Tessera and downstream projects." A framework's job is to have the rail
  laid before a downstream needs it — the ADR-0004 argument. Shipped in the shape this entry
  prescribed all along: on-demand skill (`paths: **/*.sql`), a pre-commit gate that **no-ops when
  no SQL is staged**, not an eager default. **Warn-only** and `exclude_rules = layout` by
  default, tuned directly from ADR-0011's numbers so the 89% whitespace noise never reaches a
  human. The gate shouts if sqlfluff is unreachable — silent skip is indistinguishable from pass.
  Wired into tessera's `.githooks/pre-commit`, shipped by `tessera-new-project` (script + config
  + downstream hook + `core.hooksPath`), applied to settempo. This entry is now closed; the
  lessons below survive it.
- **The 2026-07-21 evaluation (ADR-0011, superseded — kept because its measurements are load-bearing).**
  settempo arrived as the fifth downstream carrying 2 standalone Postgres files, meeting the
  condition below exactly as written. Run against them, sqlfluff produced **206 violations, 0
  actionable**: 185 (89%) pure layout, and of the 21 survivors, 7 RF05 are idiomatic Supabase
  RLS policy names, 7 PG01 are `CREATE INDEX`-without-`CONCURRENTLY` on a *fresh-install* script
  (nothing to lock; `CONCURRENTLY` cannot run in a transaction), and 7 RF04 are a column named
  `date`. The files contain **zero `SELECT`s** — pure write-once DDL, sqlfluff's weakest case.
  **The trigger was measuring the wrong thing:** file existence is a proxy for "sqlfluff would
  tell us something we don't know," and the proxy was false. Same failure shape as retired-P2
  (verb count) and old-P4 (project count) — *name the pain, not the artifact that correlates
  with it.* Corrected trigger in the ADR: **git-tracked, query-shaped** SQL (a tracked `.sql`
  containing `SELECT`, or dbt), or SQL under frequent edit. Also learned: a naive
  `find -name "*.sql"` would have false-fired on conclave months ago — 130 vendored litellm
  migrations in `harness/venv`, **0 tracked by git**. Use `git ls-files`, never `find`.
- **Adopt-when trigger (SUPERSEDED — see above; kept for the trail):** a downstream project introduces **standalone `.sql` files or dbt models**. Then add it as an **on-demand skill** (`paths: **/*.sql`) plus an optional pre-commit gate that **no-ops when no SQL is present** — not an eager default (principle #15). Worth a `/evaluate-framework sqlfluff` run at that point for a real ADR with verdict + re-evaluate triggers, rather than ad-hoc bolting.
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
  | Downstream script drift (F-003) | "project count crossing ~4–5" | exactly 4 — **and the count was the wrong metric; see below** |
  | Two-stage hierarchical skill routing | "60+ skills"; entry claims "currently at ~50" | 56 |

- **The pattern:** **a trigger written as a sentence can only be checked by someone who reads the sentence.** A trigger written as a predicate checks itself. This is design principle #17 turned on the Observatory itself — the file is a *compendium*, and its value depends on a human seeing a fired condition, which is precisely the model/human-recall channel #17 says drifts. The findings backlog had the identical shape until `bin/tessera-findings` + a SessionStart hook converted it from compendium to channel.
- **The sharp filter is silent vs. self-announcing, not checkable vs. not.** sqlfluff's trigger ("first `.sql` file") is trivially checkable and *worthless* to watch: the day you write SQL and want it linted, the need announces itself. Hook-layer content drift is checkable and **silent** — bare `python3` sat in `templates/` for two weeks with no symptom, because each copy was independently valid bash. Watch only what cannot announce itself. Roughly a third of entries are machine-checkable; about five are *also* silent, and every one of those five corresponds to a failure that already happened.
- **Three things were conflated in the original question** and are worth keeping apart: (a) a **compendium** — this file, durable record, no evaluation; (b) a **watcher over declared triggers** — perfect precision (the condition is stated), recall bounded by expressibility; (c) a **scanner outside the declared set** — discovery of conditions nobody wrote down, unbounded and low-precision. (c) is not worth building: FOCUS-002 swept all 22 entries manually and found nothing dead. Discovery doesn't need automating; it needs **scheduling**.
- **Status:** **Piloting (built 2026-07-10).** The Tier 1 discussion was held and the
  pilot sanctioned (see `_project_specs/todos/active.md`); resolved **substrate-only**
  — flat predicate list + runner + append-only fire-log + surfacing channel, with the
  *stateful engine* (snooze/hysteresis/prose-parsing) deferred until a graduation
  predicate demands it. Built as `bin/tessera-watch` (5 silent+checkable predicates:
  hook-drift, tess-verb count, compaction_fired count, downstream count, skill count)
  + a SessionStart wrapper + `G-a` graduation predicate that reads the fire-log so the
  "graduate to the real engine" decision is itself channelized, not prose. On its first
  run it caught two real drifts (a hook missing from the install payload; a 167-line
  phantom in `templates/`). Still the spec-03 de-risking pilot — ~2% of the risk (shell
  one-liners, not property-based test generation), and deliberately *not* spec 01.
- **Kill / keep criterion (fire-log-fed, judged not automated):** KEEP if the watcher
  fires a *real, not-yet-noticed* trigger at least once before a human catches it;
  KILL if over a run of real sessions it only ever re-reports already-known state, or
  false-positives into noise the user learns to ignore. The fire-log (`.tessera/logs/
  watch.jsonl`) is the evidence; `G-a` firing (a predicate stuck ≥3 runs) is the signal
  to either resolve that trigger or build snooze.
- **When to revisit:** when `G-a` first fires (P2's perpetual fire guarantees it within
  ~3 real sessions) — decide P2: build the `tess` umbrella or add snooze (the first
  stateful piece). The five GSD cluster entries still resolve with the broader Tier 1
  build decision; this pilot informs it rather than settling it.
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

### The profile model has no consumer — `profile:` is a decorative string

- **Source:** 2026-07-11. `doccheck` (new, `scripts/doccheck.py`) flagged three `.tessera/`
  files that `design-principles.md` describes in the **present tense** and that have never
  existed. Chasing why surfaced something larger than three missing files.
- **What it is:** `.tessera/project.yml` declares `profile: standard`. **Nothing reads that
  field.** Verified by grep across every tool, hook, and script:
  - `bin/tessera-new-project` *writes* it (a `sed` substitution) and never reads it back.
  - `bin/tessera-findings`, `bin/tessera-watch`, and `scripts/doccheck.py` use
    `.tessera/project.yml` purely as a **presence marker** — *"is this dir a Tessera
    project?"* They never open the file.
  - **No `profiles/` directory exists anywhere.** There is one profile name and no
    definition of what it means. `healthcare` — named throughout `design-principles.md`,
    load-bearing for the audit-asymmetry, Data Handling, and BAA-tracking sections — exists
    as **zero bytes on disk.**
- **Why the three files were unbuilt, and why that was correct:** all three are *downstream of
  a mechanism that does not branch.* `.tessera/config.yml` would override profile defaults —
  but there is one profile and one set of defaults, so it would override nothing.
  `.tessera/third-party-scope.yml` is an input to the Data Handling review category, which
  does not exist — a data file with no reader is ceremony. `.tessera/project.yml.template`
  solves a leak problem for public projects; all three repos are private. **This is YAGNI
  holding correctly.** The bug was never the missing files — it was the doc's present tense
  implying they exist. Reworded to the conditional, 2026-07-11.
- **`config.yml` was then built the same day — bottom-up, and NOT as the override layer.**
  The doc's framing was speculative; a real need was not. An agent must never have to *guess
  the test command*: bare `python3` on this machine is Homebrew 3.14 with no pytest (F-001's
  interpreter split), and while a human guesses wrong once and recovers, an unsupervised agent
  (ADR-0005) reads "No module named pytest", concludes the suite is broken, and acts on it.
  So: **one key (`test:`), one live consumer (`bin/tessera-test`), zero speculative knobs**,
  and committed rather than gitignored (a command that vanishes on a fresh clone is useless to
  the agent it exists for). The profile-defaults layer remains unbuilt and still has nothing
  to override — the file exists *despite* the profile model, not because of it.
- **The old template is the whole lesson in miniature.** `templates/tessera/config.yml.template`
  already existed, fully written, with six knobs — `claude_code_auto_compact_window`,
  `bcrypt_rounds`, `tls_minimum`, `coverage_threshold`, mnemos fatigue bands, suggestion-gate
  threshold — and **every single one was dead**: commented out, read by nothing, and
  `tessera-new-project` did not even scaffold the file. Designed top-down from the design
  doc's imagination, while the one key that mapped to a real failure was absent. Worse than
  useless: a **silent no-op config knob is a hazard**, because someone sets `tls_minimum:
  "1.3"` or `coverage_threshold: 90` and *believes it is enforced*. All six removed.
- **Why it caught our attention — this has the shape of P2.** P2 (the `tess` umbrella) was
  retired because it fired on a proxy that tracked no real friction. `profile:` is a field
  that currently tracks nothing: a hypothesis about future variation (standard vs. healthcare)
  that has **never been tested, because no second profile exists.** CLAUDE.md calls the
  profile model "original IP." It may be. It is also, today, unexercised and unfalsifiable as
  instrumented — the same posture that made the Mnemos trial meaningless until it was
  re-armed on an event. **Naming the bias:** the profile model is Tessera's most distinctive
  idea, which is exactly why it gets graded generously. Distinctiveness is not evidence.
- **Status:** Watching — kill/keep, on an **event trigger, not a date.**
- **When to revisit:** the trigger is **a second profile becoming real**, i.e. the first time
  a project genuinely needs different gates than `standard`. Then judge: did the profile
  abstraction make that cheaper than a plain per-project config would have? If a second
  profile never arrives, that is the answer — a one-valued enum is a constant, and a constant
  does not need a model. Adjacent, sharper trigger for `.tessera/config.yml` specifically:
  the first *shared hook* that must run a project-specific command (howler is Kotlin/JNI,
  conclave Python/AWS, tessera Python — no hook needs their test commands today).
- **Standing caveat:** this entry is about the profile *model* (does `profile:` earn its
  keep?), **not** about `.tessera/project.yml` as a marker file — which demonstrably works
  and is what lets `tessera-findings` and `tessera-watch` discover downstreams at all. Do not
  let a verdict on the model condemn the marker. (Same conflation the Mnemos entry had to
  untangle between its recovery and continuity layers.)

### "Green" that ran half the suite — a test command must be run, not counted

- **Source:** 2026-07-11, writing the handoff. Noticed only because the backlog entry for the
  `emit` module collision named its own trigger and the trigger had *already fired*, unnoticed.
- **What it was:** `.tessera/config.yml`'s `test:` key **enumerated six test files**. It
  reported **"57 passed"** — quoted all evening as proof the suite was green — and it ran **6 of
  12 real test files.** The gate backstop's own 17 tests never ran. Override's 13 never ran.
  Mnemos's 3 self-checks are run by *nobody* (they are assert-based `-m` scripts with zero
  `def test_`, so pytest collects them and cheerfully reports "no tests ran", which reads
  exactly like success). **This is the precise failure `bin/tessera-test` was written to
  prevent — a green exit that did not run the tests — and it shipped inside the tool built to
  prevent it.**
- **Root cause:** `scripts/gate/` and `scripts/override/` each contain an `emit.py` *and* a
  `scan.py`. With no packages, pytest prepends each test file's directory to `sys.path`, so
  `import emit` binds to whichever suite collected first and the other fails collection. Claude
  dodged it by listing files — silently dropping the colliding suites — rather than fixing it.
- **The trigger had already fired and nobody looked.** The backlog entry said, in writing:
  *"Trigger: next time anything needs a single green-suite command (CI, **a pre-commit gate**,
  or a downstream copying this test layout)."* A pre-commit gate was built that same day. **A
  trigger written in prose is only as good as the person re-reading the prose** — which is the
  identical failure the watcher exists to fix, one level down. This one had no predicate.
- **Fix:** `scripts/run-tests.sh` — each suite in a **separate process** (separate `sys.modules`,
  so the collision cannot occur), plus the mnemos self-checks invoked properly. All **87** tests
  now run. Proper namespacing is deferred with a stated reason: `python3 scripts/gate/emit.py` is
  the invocation documented in four repos' CLAUDE.md and the gate-event contract.
- **Lesson:** **a test command is a claim, and claims get audited.** "57 passed" is not evidence
  that the suite is green — it is evidence that 57 tests passed. Count what *should* run and
  compare. Same family as the `.tessera/*.yml` tracked-vs-exists check.
- **Status:** Mitigated (all suites run); namespacing open.
- **When to revisit:** CI, or the next time the `scripts/gate/emit.py` invocation contract is
  being touched anyway. A candidate `doccheck` assertion if it recurs: **every `test_*.py` on
  disk is reached by the declared `test:` command.**

---

### The agent's shell is not your shell — verify capability the way the agent sees it

- **Source:** 2026-07-11, wiring `.tessera/config.yml` into the downstreams.
- **What it was:** `tessera-escalate`, `tessera-watch`, and `tessera-test` were **"command not
  found" for Claude** while working perfectly for Lorenzo. The PATH export lived in `~/.zshrc`,
  which zsh sources **only for interactive shells**; Claude Code's Bash tool runs a
  *non-interactive* shell and never read it. Every downstream `CLAUDE.md` instructs the agent
  to invoke `tessera-escalate` **by name** — so the escalation channel, built specifically for
  the autonomy inflection (ADR-0005), **did not resolve for the only reader it was written
  for.** `tess-dashboard` had no bridge copy at all; conclave and howler survived only by
  accident, via `scripts/tessera-escalate` fallbacks.
- **Fix:** moved the export to `~/.zshenv` (sourced for *every* zsh invocation, guarded against
  duplicate PATH entries). `install.sh`'s verify already checked this correctly — it runs
  non-interactively, so it tests what the *agent* sees. The check was right; the remedy it
  printed named the wrong file.
- **The general lesson, which is bigger than PATH:** **a capability check must run in the same
  context as the consumer.** We verified with `which` at a human terminal and concluded the
  channel worked. It did — for us. Any instruction in a `CLAUDE.md` is addressed to the agent,
  so "does it work?" means "does it work *in the agent's shell*." This is the same shape as
  F-001 (hooks resolving a different `python3` than the human's) and as the doc-drift class
  (`doccheck`'s `tessera-yml-is-tracked`: **existence is a local fact, tracked is the shared
  one**). Three failures, one root: *we validated against the environment we were standing in,
  not the one the code runs in.*
- **Status:** Fixed. Watching for the class, not the instance.
- **When to revisit:** any time a doc tells the agent to invoke something by name. Ask: has
  anyone run it *as the agent* — `zsh -c 'command -v X'`, not `which X`? A candidate `doccheck`
  assertion if it recurs: every bare command named in a CLAUDE.md must resolve non-interactively.

### Skill registry — which copy is the source of truth (blocks the de-dup, entangled with delivery)

- **Status:** ✅ **RESOLVED — ADR-0010 (2026-07-20).** Repo `skills/` is truth; `~/.claude/skills`
  is a managed mirror written only by `bin/tessera-sync-skills` (wired into `install.sh`, watched
  by P12). The de-dup resolved by *demotion*, not deletion: global stays (union-load needs it) but
  holds no original content. First sync applied 2026-07-20: 10 zombies deleted (listing 57→47
  machine-wide), 6 stale bodies refreshed. Entry kept below for the trail.
- **Source:** ADR-0007 finding #7 + FOCUS-004 execution (2026-07-15).
- **The finding.** `tessera/skills/` and the global `~/.claude/skills/` were byte-identical 56/56 — a duplicate that doubles the session's skill-list cost. ADR-0007 said "kill the duplicate." But FOCUS-004 **diverged them**: this session added `adr-gate` + the `code-review`/`supabase-python`/`council-review`/`code-graph` edits to the *tessera* copy only (now 57 vs 56). So the de-dup is no longer "delete the identical copy" — it *is* the question **which registry is authoritative for downstream delivery**, and that is the delivery design (ADR-0008). Cutting either copy now would either lose this session's work (delete tessera's) or strand it out of the global library (delete global's).
- **When to revisit:** the delivery session. Decide: does Tessera ship skills via `bin/tessera-new-project` (profile-gated), and is the source the tessera-local dir or the global registry? Until then, **do not delete either copy.**

### Skill-body delivery has no copy mechanism — and a skill claimed it did

- **Status:** ✅ **RESOLVED — ADR-0010 (2026-07-20)**, with one correction to this entry's own claim:
  a copier DID exist — `scripts/install-skills.sh` (Maggy baseline, wired into `install.sh`) — but
  **additive-only** (`cp -r`, no delete): it refreshed shared bodies whenever `install.sh` ran while
  keeping every cut skill alive in global forever. Worse than none — fresh enough to look maintained,
  accumulating zombies. Replaced for `~/.claude` by `bin/tessera-sync-skills` (mirror-with-delete +
  delta print); the old script stays for non-Claude targets. Single-body policy adopted: "survives
  globally" is dead as a trim rationale — a cut is a cut for downstream too. The trim blocker in
  `active.md` is lifted; delivery-entangled trims now proceed under ADR-0010's policy. Entry kept
  below for the trail. **Source:** python-TRIM read-first, 2026-07-18.
- **The finding.** Applying the `python` TRIM (ADR-0008) surfaced two entangled facts. (1) The eagerly-loaded
  `base` skill asserted its cut scaffolding was preserved in a full-body GLOBAL `~/.claude/skills/base` copy
  serving downstream apps. **Verified false:** `diff -q` shows the global copy byte-identical to
  the trimmed project copy — the full body is in *neither*; it lives in git history (pre-`3a36bc4`) + live sibling
  overlaps (`iterative-development`, `existing-repo`). (2) **No mechanism copies skill bodies to downstream at
  all:** no `install.sh`/script writes into `~/.claude/skills`, and `bin/tessera-new-project`'s ADR-0009 curation
  toggles skills **on/off** via `skillOverrides` — it never copies a body. So "trim here, the full body serves
  downstream" (the audit's stated rationale for `python`/`base`/`icpg` TRIMs) rests on delivery plumbing that
  does not exist. The global `~/.claude/skills` is Lorenzo's personal-machine copy, coincidentally identical,
  serving *his* other repos — not a Tessera-controlled downstream archive.
- **Why it matters.** The TRIMs are still individually *safe* (a trimmed body only removes framework-session
  harm; downstream never received this copy by any mechanism). But the reassurance that made them feel free —
  "the full body survives globally" — is the same deletion-safety illusion `base`'s own HARVEST-BEFORE-CUT line
  (ADR-0007) exists to prevent, and it was written *into base itself*. Fixed the false claim + guarded it
  (doccheck `no-phantom-global-skill-body-claim`, test in `test_doccheck.py`).
- **The real open question (for the delivery session):** if downstream Tessera apps genuinely need full skill
  bodies (a real Python app *does* use ruff/mypy/FastAPI), what actually delivers them? Curation-on/off does not.
  Either (a) the global registry is the delivery source and downstream gets whatever body it holds (today: the
  trimmed one — so downstream is *under*-served), or (b) `tessera-new-project` must copy profile-selected bodies,
  or (c) framework-vs-downstream skills are genuinely different artifacts. Undecided; **do not TRIM any further
  delivery-entangled skill on the "survives globally" rationale until this is settled.**

### Fail-open skill lint — the check `council-review` earns, and the trap it must avoid

- **Status:** Pending eval. **This is a design task, not a doccheck one-liner** — implementing it naively re-commits the reachability error the whole skill audit was about.
- **Source:** ADR-0007 "standing rule → skills" + FOCUS-004 (2026-07-15). `council-review` ordered the agent to gate on backends (`~/bin/validate-plan`, absent reviewers) and reported failure only inside a JSON field nothing reads — a fail-open living in a skill, of exactly the shape [Fail-open everywhere](#fail-open-everywhere--tessera-cannot-tell-you-when-it-is-broken) names.
- **The trap.** The obvious check — *"every binary a skill names must exist here"* — is **wrong**: it flags every legitimate downstream stack skill (`vercel`, `gh`, `supabase`, `flutter`…) for naming tools absent-in-Tessera, which is the precise reachability error ADR-0007/0008 spent the whole audit un-learning. A binary-existence check on a global skill library judged against one atypical consumer.
- **The correct shape (candidate).** Lint the **fail-open *pattern*, not the binary**: a skill that couples hard-gating imperative language (`do not skip`, `mandatory`, `0 of 3 → revise`, `must not proceed`) to an *external* backend, repo-local, no existence check. That catches council-review's actual defect (ordering a gate whose backend can silently be unreachable) without touching reachability. Needs its pattern set designed + a regression corpus.
- **When to revisit:** when building the skill-instrumentation spec (ADR-0007's open mechanism finding), or the next time a skill orders a gate on an absent backend.

### Mnemos compaction vehicle — does Claude Code auto-`/compact` even happen in *this* harness?

- **Status:** Investigating. **Decision-relevant to the Mnemos kill/keep trial (`tessera-watch` P3).**
- **Source:** FOCUS-004 session (2026-07-14/15), run deliberately long to test Mnemos's compaction-recovery.
- **The test, and the result.** This session was pushed *way* past a normal length on purpose — ~200k tokens of skill-body reads (all 56 `SKILL.md`) plus a long multi-turn execution — specifically to overshoot the auto-compaction threshold and exercise Mnemos's recovery layer. **It did not fire.** `.mnemos/compaction-log.jsonl` has **zero** `compaction_fired` events dated 2026-07-14 or 07-15 — every logged event is from the 07-11 (manual `/compact`) and 07-12 sessions. A deliberate massive overfill produced **no** Mnemos-visible compaction.
- **The hypothesis (to confirm next session).** My own system prompt states: *"when the conversation grows long, some or all of the current context is summarized; the summary … is provided in the next context window."* That is **the harness managing context via its own summarization** — a different mechanism from Claude Code's `/compact`, which is the *only* thing Mnemos's PreCompact hook instruments. **So Mnemos may be watching a door this harness never opens.** If true, "fill the context to trigger compaction" cannot work here *by construction*, no matter how full — which explains ADR-0007's "171 sessions, zero un-manual auto-compactions" and this session's null result as one phenomenon, not two.
- **This is the third+ independent signal at the same conclusion.** ADR-0007 already retired FOCUS-004 as the compaction vehicle ("naturally-occurring auto-compaction is far rarer than assumed"). This adds: *even a deliberate overfill won't trigger it*, and names a probable cause (harness-summarization ≠ `/compact`).
- **Second gap found in the same check: `fatigue.json` is all `None` — fatigue runs *degraded*, not dark.** The statusline hook isn't writing token metrics, so the **token-utilization dimension (0.40 weight, the largest)** is blind. But the behavioral dimensions (scope-scatter, re-read, error-density, from `signals.jsonl`) still compute — a forced checkpoint this session scored **Fatigue 0.29**. So the fatigue model works but can't see context-fullness, which is exactly the signal its **auto-checkpoint-at-0.60 keys on**. Fix is narrow: the statusline → `fatigue.json` token-metric write, not the model.
- **What DID work (so Mnemos isn't all dark):** SessionStart restore fired (`MNEMOS SESSION RESUME` loaded at startup, resumed cleanly); the Stop-hook checkpoint wrote today (`941b43b7`, 16:43Z). Resume-across-*sessions* works; recovery-across-*compaction* is untested because the trigger never occurred (not a failure — an absent event).
- **When to revisit / next-session pickup:**
  1. **Confirm the mechanism.** Does this harness ever invoke Claude Code `/compact` (→ PreCompact hook), or only its own summarization? If the latter, either (a) point Mnemos at whatever signal *does* fire, or (b) accept the compaction-recovery layer is un-exercisable here and evaluate it on a real Claude Code CLI session instead.
  2. **Fix `fatigue.json`.** Find why the statusline isn't writing token metrics; without it the fatigue model and auto-checkpoint are dead.
  3. **Consequence for P3.** If auto-compaction structurally cannot fire in this harness, P3's counter can never move here — the Mnemos keep/kill verdict for the *compaction* half needs a different venue or a different question.
- **UPDATE 2026-07-16 — both gaps re-checked; the picture is clearer and partly better.**
  - **Fatigue is LIVE, not degraded — gap (2) is closed, and needed no code fix.** `.mnemos/fatigue.json`
    today carries real token metrics (`used_percentage: 27`, `source: statusline`), and `mnemos fatigue`
    computes **all four** dimensions: token-utilization **0.27** (weight 0.40, no longer blind), composite
    **0.11 FLOW**. The 07-15 "all `None`" reading was **transient** — the statusline *does* write token metrics;
    that session simply never received the statusline JSON. So the narrow fix contemplated above is unnecessary;
    the fatigue half of the trial is **working and judgeable here**.
  - **Compaction DOES fire in this harness — but on a path that carries no `trigger`.** Re-reading the log:
    the 2026-07-12 event tagged `trigger: unknown` was a **non-manual** PreCompact firing (a `restore_injected`
    followed 23 s later). So the recovery layer *is* exercised here — the 07-15 "did not fire / watching a door
    this harness never opens" was too strong. The refinement: the harness fires PreCompact **without a Claude Code
    `{trigger}` payload** (the 07-11 `manual` `/compact` captured its trigger fine; the harness-summarization path
    sends none → `unknown`). An `auto` (context-full) event has **still never** been observed.
  - **Instrumented (2026-07-16).** `mnemos-pre-compact.sh` now records a **key-only** `payload_probe`
    (`len` + JSON `keys`, no content/secrets) alongside every `unknown` `compaction_fired`, so the *next* such
    event answers the remaining unknown: does the harness send an empty stdin, or a payload with no `trigger` key?
    Diagnostic only — P3 already ignores `unknown` events, so this cannot contaminate the verdict.
  - **ANSWERED 2026-07-26 — it is the first: an EMPTY payload.** The probe fired and recorded
    `"payload_probe": {"len": 2, "keys": []}` — two characters, zero keys, i.e. `{}`. The harness
    sends PreCompact **nothing at all**: no `trigger`, no `session_id`, no `cwd`.
    **This closes the re-instrumentation option, and closes it as PROOF rather than as a guess.**
    `unknown` is not a tagger bug and cannot be fixed by reading the payload harder — there is no
    payload. P3 can never count an event here, so its ≥3 bar is *unreachable*, not merely unmet.
    P3 was snoozed 90d on this evidence, with an EVENT-based revisit trigger rather than a date:
    a `compaction_fired` whose `payload_probe` shows any keys at all, or judging the
    compaction-recovery half on a real Claude Code CLI session (where the docs say `trigger` is
    sent). Session-continuity is unaffected and not on trial — 517 checkpoints and counting.
  - **DECISION (Lorenzo, 2026-07-16): the compaction-recovery verdict moves to a real Claude Code CLI venue;
    the fatigue verdict stays here.** P3 will not reach ≥3 *real* (`auto`) events in this harness — 0 ever, and a
    ~200k overfill produced none — so the compaction half is **structurally un-completable here**. Counting
    `unknown` events as evidence was **rejected**: it measures the harness's self-summarization recovery, not
    `/compact` recovery — the P2 anti-pattern (a predicate on a proxy that tracks no real pain), which P3 already
    guards against. Instrument now; if the probe shows the harness sends nothing usable, the CLI is the only venue.

### Tessera ↔ Conclave ↔ pr-arbiter — the review/model cluster is converging *(seed for ADR-0008's deferred conclave design note)*

> ## ▶ CORRECTED 2026-08-07 — READ THIS BEFORE THE BODY BELOW
>
> **The body of this entry is a 2026-07-16/17 snapshot and four of its load-bearing claims are now
> wrong.** It matters more than an ordinary stale entry because this entry is the declared *seed* for
> ADR-0008's deferred conclave design note — a wrong picture here feeds an unwritten ADR. The stale
> bullets are kept below, marked, per ADR-0007 (harvest before you cut); the heading is kept verbatim
> because `docs/contracts/three-project-cohesion.md` (line-wrapped, in Cross-references) and
> **ADR-0014** cite it as an anchor — an accepted ADR names this entry, so renaming it silently
> breaks a decision record's citation. **`docs/contracts/three-project-cohesion.md` is the source of
> truth for who-owns-what; this entry is the scratchpad.**
>
> *(Corrected within the day: this sentence first claimed `docs/design-principles.md` was a citer. It
> is not — it never references this entry. ADR-0014 does. Noted rather than silently fixed because
> the false claim was introduced by the commit whose entire subject was correcting false claims, and
> because no check catches it: `referenced-paths-exist` verifies paths, not cross-reference targets.)*
>
> **(1) The fleet described below is two generations gone.** "Qwen3-32B / Gemma3-27B / Mistral-24B,
> one per L40S" was conclave's *second* fleet of three — the deliberately-ideal peer-modern one, built
> to give the judge its best shot. A third, genuine-**specialist** fleet followed
> (Qwen3-Coder-Next-80B / DeepSeek-R1-32B / Llama-3.3-70B, 2026-07-17). What conclave carries now is
> not a fleet at all but a **tier ladder** — `local-tiny` 3B/8B → `local-mid` 30B-A3B (the default
> daily driver) → `lab` 80B on-demand → `frontier` — behind one OpenAI-compatible Tailscale-private
> gateway, on RunPod. (`../conclave/docs/design.md` current-state banner; `../conclave/docs/HANDOFF.md`.)
>
> **(2) "Conclave carries both a judge and a router" is stated below as *the converging design*. Both
> halves are dead.**
> - **The judge was DISPROVED on all three fleets.** Headroom (oracle − best single — the ceiling on
>   what *any* selection policy can add) came to **+0.040** on the peer fleet and **+0.0244** on the
>   specialist one. It **shrank** as the fleet got stronger — the convergence effect. A real in-fleet
>   judge scores *below* just always calling the strongest model. Parked with a trigger: revisit only
>   if the model landscape re-diverges.
> - **The router is SHELVED, and it is fleet-dependent rather than wrong-in-principle.** A router pays
>   only when pairwise winners **split**. They split weakly on the peer fleet and **concentrate** on
>   the specialist one — the 80B coder wins 18/30 and 100% of tie-breaks. Since `router ≤ judge ≤
>   oracle`, the headroom figure condemns every selection policy over these fleets, not just the judge.
> - **What conclave actually settled on is `diagnostic → operational → monitor`,** and only the
>   diagnostic is live: `divergence.py` / `divergence_modern.py` / `fleet_pairwise.py` measure a
>   fleet's headroom for $0, offline, before anything is built. It correctly said "don't ensemble" on
>   all three. **That instrument is the reusable deliverable — not a judge and not a router.**
>
> **(3) The pr-arbiter Phase-1 / Phase-2 numbers are cited below as live evidence. Do not repeat them
> as a headline.** The contract's own guard **(d)** says why: Phase 1's critical-recall win is **7/8
> vs 6/8 on one seed** (the "88% vs 75%" below is that, rounded into a percentage it cannot carry),
> and the Phase-2 generation lift **~vanished under 3-seed variance**. pr-arbiter froze as a research
> study on 2026-07-28. **Gate any build on the instrument (S2), not the headline.**
>
> **(4) "pr-arbiter Phase 3" is listed below as an ADR prerequisite. It was ABANDONED 2026-07-28** —
> designed and ratified, never implemented; the project moved from research to tooling instead. It is
> no longer a prerequisite for anything. (`../pr-arbiter/docs/PHASE_3_RESUMPTION.md`.)
>
> ### What is true instead, as of 2026-08-07
>
> - **The pattern shipped, under a different name.** `arbiter` (`../arbiter`,
>   github.com/lciacci/arbiter) is a CLI that reviews a git ref range: reviewer → independent second
>   pass → two-voice KEEP/DROP/UNSURE triage, exit 1 on high/critical. One model, two roles, **no
>   fleet** — it independently built the arrangement conclave measured. It is **not a gate and nothing
>   gates it.** Both conclave and arbiter are Tessera downstreams (contract D4).
> - **Conclave's measurements moved from gate input to DESIGN input.** With nothing gated, the
>   union-recall work is no longer "should Tessera fan review out?" but "should arbiter ever add a
>   fleet?" — and the measured answer is no: MODEL diversity bought **+0.000 recall for +20 false
>   positives**, while ROLE diversity bought **+0.109**. Bounded by a weak second arm; see guard (b).
> - **The escalation trigger is task SHAPE, not model tier.** Conclave's local 30B scores **0.073
>   recall, 0/8 criticals** on structured adversarial review against claude's 0.509 — while *matching*
>   a hosted 80B on edit-and-apply. Review is the shape that breaks the local tier.
>
> ### What in the body below SURVIVES, and is the reason it is kept
>
> - **The union-recall vs select-best distinction** (the "load-bearing insight" bullet) is correct and
>   is now anti-conflation guard **(a)**, binding in all three repos. It has since gained *direct*
>   union-recall evidence rather than resting on the select-best null.
> - **All three harvested `codex-review`/`gemini-review` patterns hold.** Typed JSON findings —
>   confirmed twice over, since `arbiter` ships a typed-finding schema too. Headless/CI mode — that is
>   exactly `arbiter`'s shape. 1M-context whole-repo review — untouched, still a routing case.
> - **"Measure headroom offline before building the aggregator" is the right discipline.** It is what
>   killed the judge, and it is the deliverable conclave kept.

- **Status:** ~~Converging, **not decided**~~ **CORRECTED 2026-08-07, see banner above** — Lorenzo's call to keep updating as the two sibling repos'
  findings refine. This is the ADR-0008 "Tessera ↔ conclave interoperation" thread actually starting,
  and the home the `codex-review`/`gemini-review` removal harvests land in (their findings-schema /
  headless-CI / 1M-context patterns feed here). Not an ADR yet.
- **Source:** 2026-07-16 session — read `~/Claude/conclave` and `~/Claude/pr-arbiter` against the open thread.
- **Harvested from `codex-review` + `gemini-review` before their ADR-0008 cut (2026-07-17)** — three
  patterns the multi-engine review design should carry, now that the vendor-CLI manuals are gone:
  - **Structured JSON findings schema.** `codex exec --json "review …"` emits findings as machine-parseable
    JSON, not prose. This is the SAME shape pr-arbiter independently converged on (its typed-finding schema,
    0 contaminated / 551) — two separate efforts landing on typed findings is the signal that the review
    seam (contract S2/S4) should standardize on a typed schema, not free text.
  - **Headless / CI mode.** `codex exec --full-auto --json --output-last-message out.txt "…"` runs a review
    with no TUI, for automation. The shape Tessera's own review-fan-out gate would invoke a backend through
    — one non-interactive call, structured out. (The vendor `codex`/`gemini` CLIs are absent here; the
    *pattern* is what carries, to be pointed at conclave's gateway per Open decision D1.)
  - **1M-context whole-repo review.** Gemini 2.5 Pro's 1M window reviews an entire repo in one context, no
    chunking — the lever for whole-repo / large-diff review where per-file misses cross-file defects.
    Complements pr-arbiter's union-recall (roles) with a *context-breadth* axis. Tracked as a routing case
    (`docs/observatory.md` → the 1M-context revisit trigger).
- **The three pieces, and how they fit:**
  - **conclave** (`~/Claude/conclave`) — ⚠ **FLEET STALE, see banner (1); the "route, don't judge"
    finding is also superseded — conclave's own doc corrected it to "just call the strongest model."**
    A self-hosted multi-model inference lab: open-weight fleet
    (Qwen3-32B / Gemma3-27B / Mistral-24B, one per L40S) behind an OpenAI-compatible gateway, private
    over Tailscale, on RunPod (AWS fallback). Cost controls built before any GPU boots. **Its research
    finding: "route, don't judge"** — on *answer-quality, select-best* (Q&A), a fan-out judge scores
    *below* the best single model and pays N× for a saturated gap; the instrument `orchestrator/divergence.py`
    measures `headroom = oracle − best_single` offline for $0 before you build anything.
  - **pr-arbiter** (`~/Claude/pr-arbiter`) — ⚠ **FROZEN 2026-07-28, and the numbers in this bullet are
    the ones guard (d) says not to repeat as a headline — see banner (3). Successor: `arbiter`.**
    A POC measuring reviewer + independent arbiter vs single-agent.
    **On code review (Phase 1) fan-out+arbiter PAYS: it catches a critical security bug the best single-agent
    misses across every prompt variant** (critical recall 88% vs 75%, fewer false positives). On code
    *generation* (Phase 2) the effect is real but weak under 3-seed variance (87% vs 82%). Ships a typed-finding
    schema (0 contaminated / 551). Meant to graduate into the tool backing Tessera's `/arbiter`
    (design-principles → "Pr-arbiter ↔ /arbiter integration").
  - **Tessera** — the framework that operationalizes both: its `council-review` / `validate-plan` / `review`
    layer, and eventually the models behind it.
- **The load-bearing insight — why "route, don't judge" does NOT kill Tessera's fan-out:**
  conclave measured **select-best** (pick one best answer; saturates as models converge → route). **Review is
  union-recall** — you want *every distinct true bug* N reviewers find, not one selected answer; that headroom
  **does not saturate** the same way, because models converge on quality yet still find *different* bugs.
  pr-arbiter is the evidence: the fan-out win shows up exactly on the **critical-recall tail** select-best can't see.
  So conclave's disproof is real *and* scope-limited; the two results are consistent, not contradictory.
- **Consequence for `divergence.py` on the review question: the FRAME helps, the current METRIC pollutes.**
  "Measure headroom offline before building the aggregator" is the right discipline — keep it. But its oracle
  (best single *answer*, quality-graded) would falsely condemn review fan-out; review needs a variant whose
  oracle is **union of true findings, scored on bug-recall + false-positive rate** vs a labeled defect set.
  Same instrument shape, different scoring function.
- ⚠ **THIS BULLET IS THE MOST WRONG THING IN THE ENTRY — see banner (2). Both the judge and the
  router are dead: the judge disproved on three fleets, the router shelved because the fleets
  concentrate rather than split. Do not seed an ADR from it.**
  **The converging design (evidence-backed, still refining):** Tessera → conclave as the **default backend**
  (self-hosted fleet for most work; frontier models reserved for occasional/investigation). **Conclave carries
  both a judge and a router**, switched per task by headroom: **fan-out+judge where headroom is real (review /
  recall — pr-arbiter validates), route-to-specialist where it saturates (most Q&A — conclave validates).**
  pr-arbiter graduates to back `/arbiter`, running on conclave's fleet.
- ⚠ **SUPERSEDED — the live version of this list is in the contract's "What would firm this map into
  that ADR". (1) is now partly done (MODEL axis measured and null; ROLE axis +0.109; the missing arm
  is peer-strength). (2)'s pr-arbiter-Phase-3 half is ABANDONED — see banner (4) — leaving "a stable
  conclave fleet", itself narrowed to *a fleet standing at a tier that can review*. (3)'s review half
  was settled by ADR-0014 (option D, review is Claude-only) and its router half evaporated with the
  router.** Original text:
  **What would firm this into an ADR:** (1) a review-flavored divergence measurement (union-recall metric)
  showing the review headroom is real and how big; (2) pr-arbiter Phase 3 + a stable conclave fleet;
  (3) the concrete interop shape (does Tessera call conclave's gateway directly; do `bin/` wrappers collapse
  into conclave calls; where does the router live). Until then: **noted here so it is not lost.**
- **CANONICAL MAP (2026-07-17):** the cohesion contract is now authored — `docs/contracts/three-project-cohesion.md`
  (layering / owns-must-not, seams with owners, sequence, the 4 anti-conflation guards, and Open decisions
  D1–D4). It is a coordination map, **not** the ADR; the ADR above is still what firms it.
  **D1 is DECIDED as of 2026-07-27 — ADR-0014, option D: review is Claude-only, deliberately.**
  Chosen on evidence, not preference: the `review` orchestrator had never run (0 commits since creation) and
  0 of 3 backends were functional — `kimi` execs a phantom path and had been broken 15 days
  unnoticed, `codex` absent, `deepseek` sound but unkeyed. The review stack was cut. **D2–D4 stay
  open**, and the scope limit matters: `bin/validate-plan` + `council-review` were KEPT, because
  plan validation is a different capability that merely shares backends and ADR-0007 forbids
  cutting the multi-model stack without its own design session. **The fact that will decide the
  re-entry:** conclave already carries `litellm/config.yaml` with a model_list and three api_base
  entries, so if that gateway becomes routine the cheap path back is option **B**, not C. This observatory
  entry stays the live scratchpad; the contract is the source of truth for who-owns-what.

### Haziness's correction-detector has near-zero recall — it has been silently blind  ✅ RESOLVED (Phase 1, 2026-07-17 — see UPDATE at end)

- **Status:** RESOLVED by spec 13 Phase 1 (#19). The body below is the original finding, kept for the
  trail; the "Next" items are superseded by the UPDATE at the end of this entry. Detector is no longer
  a keyword regex — a qwen3:8b classifier now un-blinds recall (regex retained as the fail-open fallback).
- **Source:** 2026-07-16 session, while designing capture for gate-disposition (`should_fire`) and,
  more valuably, **action-divergence** friction ("did the agent do the opposite of what was asked").
  Before building anything new, checked what Mnemos *already* captures. It captures almost nothing.
- **What was found — the detector reads ~0 everywhere.** `mnemos haze` scores **0.00–0.06 across every
  session on record** (8 checked); every one bands `clear`. **This is not "every session was clean."**
  The audit's own `tessera-verify` author-error-rate was **38%** — sessions are demonstrably not friction-free.
  A metric that always says "clear" is not measuring; it is blind, and blindness reads as health.
- **The proof is this very session (`b6d7b6f5`).** It contained heavy, repeated *substantive* user
  redirection — corrected a wrong `tessera-watch` root-cause, challenged `should_fire` twice, reframed the
  whole design to action-divergence, questioned the labeling burden. The detector's verdict:
  `correction_density 0.000`, composite `0.00 CLEAR`. **Zero of it registered.**
- **Root cause — detection is a shallow keyword regex.** `scripts/mnemos/claude_log.py`
  (`_CORRECTION_LEAD_RE` / `_CORRECTION_PHRASE_RE`) fires only when a turn *opens* with
  `no | wait | stop | actually | undo | revert | rollback | wrong | don't`. That catches overt "no, undo
  that" corrections and **misses the friction that matters**: probing questions, reframes, "but that would
  require X", "what does that give us" — the redirections that actually change the work. Backtrack detection
  (`git revert` / `reset --hard`) is similarly literal.
- **What is RIGHT, and worth keeping:** the *pipe*. `claude_log.py` passively ingests every transcript and,
  per detected correction, stores the **matched phrase + a redacted text preview + timestamp** — not just a
  count. Zero manual burden, ADR-0006's passive-observation pattern exactly. **The architecture is correct;
  only the detector is too weak to feed it real signal.**
- **Why it bears on the whole friction question:** there are two disposition vectors — *asking* calibration
  (`should_fire`: did I surface the right gates) and *doing* calibration (**action-divergence**: did I do what
  was asked, or diverge / defy / overreach). The second is the more valuable one — it is what the framework's
  own postmortems keep admitting only a human catches ("every correction came from outside me", ADR-0007; the
  deletion-leap; the 38% error rate). **`correction_density` is the one existing instrument that could see it —
  and it has near-zero recall.** So the valuable friction is not merely un-typed; it is essentially uncaptured.
- **Consequence for any labeling design:** the fix for both vectors is the same and it is NOT manual labeling
  (which dies — see the `should_fire` dead backlog: 52 unlabeled gates nobody will ever label). It is **passive
  extraction from the response the user already produces**, on this existing pipe — upgrade the detector, do not
  add a labeling chore.
- **Next:** (1) this entry. (2) **Detector upgrade** — replace the keyword regex with a recall-first classifier
  over the transcript delta (the local-qwen infra from the tier-classify hook already exists), and **type** the
  hit (misunderstood / defied / overreached / wrong) while there. Recall-first because a false "you corrected me"
  is cheap; a missed one is the current failure. **Scoped in `_project_specs/13-friction-detector-upgrade.md`**
  (Phase 1 = recall fix + backtest; typing and action-linking deferred). Not built here.
- **UPDATE 2026-07-17 — Phase 1 BUILT.** Recall un-blinded: `b6d7b6f5` went `0.000 → 0.219` (matches a
  27-turn hand-labeled 0.188); clean sessions stay 0; spread across ~24 dogfood sessions is 0.00–0.35
  (was 0.00–0.06, blind). Three corrections to the original scope, recorded in the spec: (a) the **3B
  tier-classify model is useless** — it parrots the prompt's ending polarity; **qwen3:8b + `think=false`**
  is required (fails open to regex). (b) **Injected user turns** (hook feedback `isMeta`, task-notifications
  `promptSource=system`) were being counted as human corrections — now excluded. (c) **Latency was never
  real** — Stop-hook ingest is backgrounded (`& disown`) and incremental, so a live Stop classifies only
  the new turns; a full backfill of ~26 sessions is 81s. Precision is ~0.5, which is why the **haziness
  band re-tune is deferred behind `tessera-watch` P10** (fires at ≥40 real-signal sessions → spot-check
  precision first, then decide bands + the 0.30 weight). Phases 2 (typing) / 3 (action-link) still deferred.
- **UPDATE 2026-07-18 — Phase 2 (typing) BUILT (#25).** Each detected correction is now typed
  (`misunderstood / defied / overreached / wrong`) by a second qwen prompt run **only on
  already-detected corrections** (small N, not per-turn), sharing Phase 1's wall-clock budget AND its
  consecutive-fail disable. Stored in a new nullable `claude_turns.correction_type` (idempotent
  ADD-COLUMN migration); surfaced in `mnemos haze --session --explain` as a `CORRECTION TYPES` rollup +
  per-turn `CORRECT:<type>` markers; `--reclassify` backfills. **Typing is a diagnostic view — it does
  NOT feed the haziness composite** (weight changes stay gated on P10). Verified end-to-end vs live
  qwen3:8b: `b6d7b6f5` typed 7 corrections (`misunderstood=2, overreached=1, wrong=4`) with
  `correction_density` unchanged at 0.219. **Only Phase 3 (action-link + divergence surface) remains.**
- **UPDATE 2026-07-19 — Phase 3 (action-link + divergence surface) BUILT.** `scripts/mnemos/divergence.py`
  derives, per detected correction, the **ASK → DID → CORRECTED(type)** unit — the nearest preceding human
  prompt, the assistant work since it (files/tools/errored?), and the correction (Phase 1 match + Phase 2
  type). Pure structural derivation over `claude_turns` (no schema, no migration, no ingest cost — the link
  is reconstructable, unlike the stored qwen verdicts). Surfaced via `mnemos divergence --session <id>`,
  `divergence --recent N` (flat by-type rollup), and a DIVERGENCE section in `haze --explain`. **View-only —
  does NOT feed the composite** (verified: `b6d7b6f5` composite unchanged, 0.219 density). The surface makes
  a real distinction legible: action-divergences (`did:` has edits) vs conversational pushback (`did: (no
  tool actions)`). This closes spec 13 — the friction-detector is now the doing-calibration instrument the
  postmortems kept asking for. Remaining follow-ons are the P10 band re-tune (self-firing at 40 sessions) and
  the same passive-extraction pattern applied to retire `should_fire`'s dead labeling path.
- **UPDATE 2026-07-19 — `should_fire` passive extraction BUILT (producer side).** The follow-on above
  landed: `scripts/gate/label.py` fills `should_fire` (the gate-calibration ground truth, else `null`
  forever — the dead P7 backlog) from the user's DISPOSITION, the first human turn after the gate
  (timestamp-joined), via a balanced local-qwen classifier. Writes back in place, idempotent, fail-open,
  `labeled_by: "classifier"`, **never overwrites a human label**. **A ground-truth eval caught a rubric
  bug the anecdotal backtest missed — the real lesson here.** The n=3 self-backtest called precision ~0.5;
  running the classifier over **n=26 human-labeled gates** (`scripts/gate/eval_should_fire.py`) showed the
  shipped rubric was actually **recall 0.08** — near-always-No, because it read terse option-picks
  ("commit", "1a 2a", "go with 2") as dismissals when *selecting a surfaced option IS the decision*. Fixed
  the rubric to count engagement (incl. a terse pick) as `should_fire=true`: **recall 0.08 → 0.76,
  precision 1.00** on the same 26 (tuned+measured on one set; negative class n=1, so precision
  under-measured — P10's fresh sample confirms). This **validates** the `labeled_by` split (#33) AND the
  discipline: *anecdotes lie, ground-truth evals don't* — build the eval, don't trust n=3. Same story as
  correction_density's blind detector. **Backfill-first; Stop-hook auto-wire deferred** until a full
  `--all` backfill + eval on more negatives. Open: (1) Stop-hook wire, (2) `--all` backfill, (3) the last
  6 FN ceiling (2 are unfair summary-bases; 4 non-option-pick engagements — not chased, overfitting risk),
  (4) human-overrides-classifier path (a human disagreeing with an auto-label needs a manual edit today).

### Autonomous test-fix loop — a richer cousin of `iterative-development` *(harvested from `autonomous-testing` before its ADR-0008 cut, 2026-07-17)*

- **The idea worth keeping:** a full closed loop — **Source Scan → Discover coverage Gaps → Generate tests
  → Execute → Evaluate failures → Fix Loop** — not just "run tests on Stop." `iterative-development`
  (Tessera's kept TDD-loop skill) is the *narrow* version: a Stop hook re-runs tests and feeds failures
  back. The harvested shape adds the two ends `iterative-development` lacks: **gap discovery** (scan source,
  find <80%-covered branches / untested endpoints *before* writing) and **AI-authored test generation**
  with **tiered-model routing** (simple fns → cheap/fast model; complex or auth/security logic → the
  thorough tier). The classify-by-stakes routing echoes the tier-classify hook and spec-13's model split.
- **Why only a note, not a build:** the original skill was malformed (no frontmatter) and hard-wired to
  Maggy + `~/bin/deepseek` (absent). The *loop shape* is the durable part; a Tessera build would wire it to
  the real toolchain and the Stop-hook substrate `iterative-development` already documents. Radar until a
  session wants autonomous coverage-gap filling — deferred, not scoped.

### Team-spawning feature seam — unresolved after the agent-teams cut *(2026-07-17)*

- **The seam:** ADR-0008 cut the `agent-teams` skill (Maggy-mandatory framing) but KEPT `polyphony`
  (container isolation) and `/spawn-team` (the command that drives it). `spawn-team` depended on
  `agent-teams`'s 6 role files (`team-lead`/`quality`/`security`/`code-review`/`merger`/`feature`); the cut
  deleted them and broke the command. They were **restored to `templates/agents/`** (they are spawn-team's
  dependency, not part of the retired skill) — but the audit never decided the underlying question.
- **The unresolved question:** does Tessera's downstream template ship a **team-spawning feature** at all?
  `polyphony` is "kept-but-not-activated"; `spawn-team` is documented as a live downstream feature in
  `templates/CLAUDE.md` + `initialize-project`; `install.sh` does **not** currently ship `templates/agents/`.
  Either wire the delivery (install.sh ships the roles, polyphony activates) or retire the whole feature
  (cut spawn-team + roles + the template references). **Evaluate deliberately; do not let it rot half-wired.**
- **Related deferral:** `templates/codex-auto-review.sh` (a guarded, dormant downstream Codex Stop-hook wired
  in `templates/settings.json`) is **deferred to the D1 / `code-review` vendor-review decision** — same
  vendor-CLI-review-deprecation question, resolved there, not piecemeal. (Cohesion contract, Open decision D1.)

### Downstream template + `initialize-project` were stale vs ADR-0008/0009 ✅ RESOLVED 2026-07-17

- **Status:** RESOLVED (the alignment pass). Surfaced when the ADR-0008 skill removals hit dangling
  references the earlier reference-scans missed (doccheck couldn't catch them — `~/…` and `@…` paths).
- **What was actually wrong (my first read overstated it — corrected here):**
  1. **Eager block.** My initial finding said the downstream template should be `base`+`mnemos` only, by
     analogy to ADR-0008's *Tessera* eager set. **That was wrong** — ADR-0008 de-eagered
     `iterative-development` + `security` *because the framework repo has no web/auth/SQL/TDD surface*; a
     downstream **app does**, so they legitimately fit eager there. **`@eager` ≠ "available":** eager =
     loaded into every session's context; universal-available (skill-profiles) = loaded on-demand. The only
     real drift was **`polyphony`** — kept-but-not-activated, not even in the universal set, so eager-loading
     a dormant orchestration skill every session is pure cost. **Fix: dropped only `polyphony` from
     `templates/CLAUDE.md`.** (`cross-agent-delegation` eager line was removed with the cuts.)
  2. **`initialize-project.md` copy model.** It taught `cp -r ~/.claude/skills/X/` delivery; ADR-0009 made
     delivery a **selector** (`skillOverrides` per profile — Claude Code already unions the global registry,
     nothing to copy). **Fix: rewrote Step 2 + Step 4 to the selector model**; Step 2b (cross-tool sync)
     reframed as non-Claude-tools-only (Kimi/Codex don't union). Not retired — `install.sh` + `GETTING_STARTED`
     still advertise `/initialize-project` as the setup path.
  3. **Checker gap — CLOSED.** doccheck `template-skill-refs-exist` (17th check) now catches `@…/skills/X` and
     `cp …skills/X/` references to deleted skills in templates/ + commands/.
- **Open (not this pass):** which is the *canonical setup entry point* — `/initialize-project` (interactive
  onboarding) vs `bin/tessera-new-project` (greenfield scaffold)? They're complementary, but `install.sh`
  advertises only the former. A setup-UX decision, deferred.

### FRICTION (recorded): cut a skill without reading its dependents *(2026-07-17, Lorenzo caught it)*

- **The miss:** the `agent-teams` cut deleted 6 role files that a KEPT command (`spawn-team`, polyphony's)
  depends on. Restoral was needed; it was clean only because git had the files. The break shipped into
  PR #22 at phase 1 and was caught later by a broad scan — had the PR merged after phase 1, the downstream
  template ships broken.
- **Root cause — not ignorance, dismissal.** The phase-1 reference grep DID surface `spawn-team` referencing
  `agent-teams`. It was seen, labeled "orphaned Maggy, follow-on," and the dependency was deleted anyway
  without opening `spawn-team`. This violates the exact rule the whole skill-assessment process was built on
  (base-skill *"never subtract from a knowledge artifact you have not read"*, ADR-0007's lesson). **Bias:
  momentum / execution-mode** — an inconvenient dependency signal filed as out-of-scope to keep the cut clean.
- **Severity of the class:** `referenced-paths-exist` is blind to `~/…` and `@…` skill paths, so the break
  passed doccheck green. No automated check caught it — a human did. This is precisely the action-divergence
  friction spec 13 Phase 1 instruments, and a live example that the miss-shaped ones still get through.
- **Remedy (both landed 2026-07-17):**
  1. **Mechanical:** doccheck `template-skill-refs-exist` — asserts every `@…/skills/X` load and
     `cp …skills/X/` recipe in templates/ + commands/ points to a skill that exists in `skills/`. Would have
     caught this at commit. (17th check.)
  2. **Process:** before cutting a skill, trace its *inbound dependents* and READ them — a grep hit is a
     signal to follow, not a ticket to defer.

### Asking-calibration stop-loss — should_fire classifier shelved, human anchor stands *(2026-07-20)*

- **Status:** Decided (stop-loss adjudicated with Lorenzo, 2026-07-20).
- **What happened:** the first real `label.py --all` backfill (spec 14 Phase A) labeled 71 gates,
  split 23 True / 51 False — vs ~90% True in the 26-label human anchor. Eyeball acceptance failed:
  the False class was largely wrong. Two causes: (1) **retro-logged gates** (scan-adjudication
  emissions, a large share by design) carry adjudication-time `ts`, so the disposition join grabbed
  unrelated wrap-up turns — structural, no rubric fixes it, and pre-flag history is unmarked hence
  permanently unjoinable; (2) soft assents ("i think that's okay for now") read as No — invisible
  to the #35 eval, whose negative class was n=1.
- **The pattern that forced the call:** third tuning cycle on this instrument (manual labeling died
  → P7 snooze; rubric recall 0.08 → #35 fix; now the negative class + join). Meanwhile the human
  anchor already answers the calibration question: **the gate is not over-firing** (25/26 warranted).
  Chasing coverage refines a number whose reading is known. The under-asking side was never
  measurable by this instrument anyway (2/103 held events).
- **Disposition:** all 74 classifier labels rolled back to null (bad Falses would have gutted
  `should_fire_ratio`); `emit.py --retro` flag added + `scan.py` requires it at adjudication +
  `label.py` skips retro events — forward provenance is clean if this is ever revisited. Phases
  B/C (auto-wire, override) shelved; resumption criteria in `docs/contracts/gate-event.md`.
- **The transferable lesson (twice now in one week):** an eval whose negative class is n≈1 measures
  only half the classifier — #35's "precision 1.00" was true and useless about the No-verdicts. And
  a *join* defect masquerades as a *rubric* defect until you read the basis quotes; the eyeball pass
  on real output caught what the committed eval could not. Sample-check the class your eval is
  thinnest on.

### Stop-hook ingest was dead for 3 days — F-001's cousin, caught by an eval probe *(2026-07-20)*

- **Status:** Fixed same day (spec 16, closed). P11 now watches the pipe.
- **What:** every Stop-hook transcript ingest from 07-17 (#19 merge) to 07-20 silently died:
  spec-13's `make_detector()` imported repo-root `scripts.model_routing` from inside the installed
  mnemos package — resolves under `python -m` from the repo root, raises under the console script
  the hook execs. First line of `ingest_session`, before every fail-open guard; hook swallows
  stderr. Hand-runs worked, hook runs no-op'd — **silent divergence between the interactive and
  hook environments, the F-001 signature** ("the agent's shell is not your shell" entry, now with
  a second confirmed instance). P9 was blind by construction: it checks the interpreter can import
  the toolchain, not that the toolchain's own imports survive an arbitrary cwd.
- **How it surfaced:** a progress-eval probe noticed P10's real-signal counter frozen at 24 while
  haze rows grew — and read the signature as F-001-shaped (a zero indistinguishable from a dead
  pipe). The spec-16 hand-run confirmed in one command. **Neither the suite nor doccheck nor any
  watch predicate caught 3 days of it** — the suite mocks the boundary, and nothing diffed
  transcripts-on-disk against sessions-in-store. That diff is now **P11 ingest-pipe** (DEAD =
  recent transcripts with no session row; DEGRADED = 3 consecutive regex-only ingests, via the new
  per-ingest `classifier_status` trace). The fix's regression test runs the real interpreter from
  an outside cwd — the hook's condition, not the developer's.
- **Knock-on:** repair re-ingest lifted real-signal sessions 24 → 50, so **P10 fires legitimately
  now** — the haziness band-recalib (precision spot-check first) is due as next-work.
- **The generalized rule:** *reach the toolchain by path, not name* extends to *a package must not
  depend on its caller's cwd for imports*. And spec-11's thesis got its first live confirmation:
  a fail-open path that leaves no trace converts "broken" into "clean-looking data" — 3 days here,
  weeks for F-001.

### P10 adjudicated: haziness bands re-anchored, weight kept, predicate retired *(2026-07-20)*

- **Status:** Decided (with Lorenzo). Spec 13 fully closed.
- **The protocol held:** P10 fired at 50 real-signal sessions (post-#38 repair) and its own rule —
  *precision spot-check first, then bands* — was followed, then extended at Lorenzo's push to a full
  **silver-label pass**: 125 turns (25 qwen-positives + 100 negatives), Claude-judged under the
  spec-13 rubric, tuning session excluded, replayed against live qwen by the now-committed
  `scripts/mnemos/eval_correction.py`. **Precision ~0.36–0.48, recall ~0.39–0.53, measured density
  within ~±50% of true** — the FP and FN errors partially cancel. Ordinal signal, not absolute rate.
- **Decisions:** bands `0.25/0.50/0.75` → `0.05/0.12/0.20` (distribution ~p50/p90/max; the old bands
  labeled every one of 115 sessions 'clear' — dead letters). Weight stays 0.30 (~0.4 precision argues
  against raising a noisy signal). P10 retired — a one-shot tripwire whose review happened; leaving it
  armed would re-fire forever. **Standing re-eval trigger (recorded, not remembered): any change to
  `correction_detect.py` (model, rubric, prompt) must re-run `eval_correction.py` and re-open
  bands/weight on its numbers.** Bands are display labels; if they ever *drive* anything, that
  promotion re-earns a watcher.
- **The eval-design lessons, now twice-confirmed in one day:** (1) judge BOTH classes — the negative
  sample surfaced ~11% carrier junk in the eligible denominator (`<bash-stdout>`, `[Request
  interrupted]` riding user role — now `user-meta` at ingest) that no positives-only eval could see;
  (2) Claude-as-judge is fine for *eval* (interactive, human in loop) and wrong for *production*
  (the passive pipe stays local-only by design — privacy, cost, fail-open discipline). The named
  upgrade path: Claude silver-labels batches → qwen rubric tuned against them → replay shows the
  before/after.

### Harness-staleness notification inverts: push a record downstream, don't pull from Tessera *(2026-07-24)*

- **Status:** Investigating — design settled in argument, nothing built. Needs a gate before code.
- **The trigger.** howler was 9 files behind on the spend guard. Moving that task off Tessera's
  backlog (correct — no Tessera session can execute it) exposed the fact that **there is no
  framework→downstream channel at all.** `tessera-findings` runs downstream→framework only. A
  downstream has no `bin/`, no `tessera-watch`; `templates/tessera/` ships no `bin/` either. The
  observatory machinery is framework-only, so there was no existing surface to hang a check on.

- **The proposal I made first, and why it was wrong.** A downstream SessionStart hook that shells
  out to `tessera-sync-harness <self>` and prints the gap. Measured cheap — 0.151s for a full
  dry-run, scaffolded reference project and all — so cost was no objection. The objection is
  Lorenzo's question: *Tessera isn't always checked out before a downstream is worked.* That hook
  depends on the framework being present, so it goes **quiet exactly when the framework is
  missing** — and a downstream then reads as current because its checker was unreachable. That is
  the house pattern (*the component ships and the thing that would tell you it's broken is also
  broken*) authored deliberately, one conversation after citing it.

- **The distinction that resolves it.** Two things were conflated, and they have opposite
  dependency requirements:
  1. **Knowing what to fix** — must survive Tessera being absent, offline, or deleted. Zero
     dependency permitted.
  2. **Detecting that *new* drift appeared** — *cannot* work without Tessera. Staleness is defined
     relative to a reference; nothing can know it is behind without the thing it is behind. Not a
     flaw to engineer around, a fact to design with.

- **So the mechanism inverts: push, not pull.** `tessera-sync-harness` **writes** the pending
  record into the downstream's own docs when it finds a gap. The hand-written section now in
  howler's `CLAUDE.md` (`2fab695`) is the *primary* mechanism, not a stopgap that a hook later
  replaces — the hook's real job is generating such a record automatically. A downstream-side
  check becomes optional garnish, and when it cannot reach Tessera it must say so **loudly**
  rather than pass. Same session's cwd bug is the empirical argument for that last clause:
  twelve of thirteen hooks exit 0 silently when their path does not resolve, and the one that
  complained — with a *wrong* diagnosis — is the only reason any of it surfaced.

- **Portability considerations (raised by Lorenzo; the reason this is not just a howler fix):**
  1. **Absolute paths.** `~/Claude/howler` is baked into the record just written, and
     `tessera-findings` roots at "tessera's parent" — a sibling-layout assumption. F-002 already
     burned this repo once via the `lciacci`→`lorenzociacci` path slug.
  2. **PATH-based tool discovery.** `tessera-sync-harness` resolves only because this machine's
     PATH includes `tessera/bin`. F-001's lesson generalizes past interpreters: *a name is not a
     location.* A portable methodology cannot assume the binary exists.
  3. **Sibling coupling.** `discover_projects` globs `root/*/.tessera/project.yml`. Fine for one
     `~/Claude`; breaks across machines, orgs, or nesting.
  4. **Methodology and tooling are entangled.** The methodology ports by copying text
     (design-principles, ADRs, working conventions); the tooling needs `install.sh` + venv +
     PATH. But CLAUDE.md's conventions cite `scripts/gate/emit.py` by relative path — adopt the
     methodology without the tooling and half of it dangles as instructions to run absent things.
  5. **Stdlib-only is already the portability asset,** arrived at for a different reason.
     `doccheck.py`, `gate/*`, `spend/*` port by copy. The venv-dependent parts (mnemos, icpg,
     polyphony) are the least portable *and* the ones still on trial.
  6. **Retraction, recorded because the reasoning was wrong not just the conclusion.** A
     synced-from-commit marker in each downstream's `.tessera/` was dismissed as YAGNI earlier in
     the same session, on cost grounds — 0.15s made live detection cheap, so why store a marker.
     Cost was the wrong axis entirely. Across machines there is no single answer to "is howler
     stale" without a committed marker, because *the reference itself differs per machine*.
     Portability is the real reason to want it.

- **When to revisit:** before building any harness-currency check — the push/pull choice decides
  its shape. Also the moment a second machine or a non-sibling checkout appears, which converts
  consideration 6 from theory into a defect.
- **Related:** open item 3 in `_project_specs/todos/active.md` (cwd-relative retargeting, 15/15
  hook commands) and item 1 (spec 11 fail-open sweep) — both are the same fail-quiet family.

### PreToolUse hooks' bare stdout never reached the model — and it explains a standing Mnemos-trial mystery *(2026-07-24)*

- **Status:** RESOLVED for the two data-injection hooks (fixed + regression-checked); the trial
  reinterpretation is the lasting content.
- **The rule, verified against `code.claude.com/docs/en/hooks`:** a `PreToolUse` hook's plain
  stdout on exit 0 goes to the **debug log only** — it is NOT added to the model's context. The
  only events whose bare stdout reaches context are `SessionStart`, `UserPromptSubmit`, and
  `UserPromptExpansion`. To inject context from `PreToolUse` you must emit JSON
  `{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"…"}}` on exit 0.
- **Found by the multi-agent review** of this session's decision-surface hook (B), which had
  exactly this defect — built to defeat the fail-open class, silent by the fail-open class, the
  ninth instance. Fixing it exposed that the bug was a **class**, not one hook.
- **It explains the Layer-3 compaction mystery the Mnemos skill already recorded.** The skill
  notes (2026-07-11) that Layer 3 (`mnemos-post-compact-inject.sh`, a **PreToolUse** hook)
  "logged `restore_injected` … but its injected text was never *seen* reaching the model," while
  Layer 2 (`mnemos-session-start.sh`, a **SessionStart** hook) "delivered." That asymmetry was
  read as flaky plumbing. It is not flaky — it is **exactly** this rule: SessionStart bare stdout
  reaches context, PreToolUse bare stdout does not. Layer 3 has been firing into the debug log
  the entire trial. The plumbing was confirmed *because* the marker was consumed; the injection
  was never seen *because the channel drops it.*
- **Also silent for the whole trial: `mnemos-pre-edit.sh`** — the documented "PreToolUse checks
  fatigue and intent context" feature (fatigue warning, active constraints, iCPG drift). All of
  it was bare stdout on PreToolUse, so none of it ever reached the model. This is material to any
  Mnemos kill/keep verdict: a feature that "ran" but was structurally unable to affect the model
  is not evidence the *idea* failed — same shape as F-001 (empty ≠ unused), one layer up.
- **Fix:** both hooks now emit the `additionalContext` envelope (advisory, so the error path
  rides the same channel — never exit 2, which would block the edit). The other three PreToolUse
  hooks were checked and are correct: `subagent-route-hook` uses `hookSpecificOutput.updatedInput`,
  `tessera-spend-guard` uses the permission-decision mechanism.
- **Check left behind:** doccheck `pretooluse-hooks-reach-the-model` asserts every PreToolUse-wired
  hook that emits stdout reaches the model via a JSON mechanism (additionalContext / permissionDecision
  / updatedInput), following the referenced `.py`. It would have caught all three at commit.
- **When to revisit:** when the Mnemos compaction-recovery half is judged on a real Claude Code CLI
  session (the open P3 question) — it must be re-judged with Layer 3 *actually reaching the model*,
  because every prior observation of it was through a dropped channel.

### The spend backstop's own cap became a permanent kill switch *(2026-07-27)*

- **Status:** FIXED same day (per-session counter + `tessera-watch` **P15**). Kept because the
  shape recurs and because of how it was found.

- **What it was.** `scripts/spend/backstop.py` returns 0 once `_bump_fires()` exceeds
  `MAX_FIRES` (3), and `.tessera/.spend-backstop-fires` held a **single global integer that
  nothing ever reset**. Found at **47**. So the backstop that catches a spend denial nobody
  dispositioned had been silently dead for a long time, and `rc=0` is indistinguishable from
  "nothing to report" — standing pattern #2 in the mechanism that guards unsupervised spend.

- **The cap was not wrong, its scope was.** The comment says it exists so "a backstop that can
  wedge a session gets ripped out, and then protects nothing" — a statement about ONE session.
  Against a monotonic global counter it outlived every session it was protecting. **A limit
  written for a session, stored for all time, is a kill switch.**

- **The cause was almost certainly the sibling bug fixed the same hour.** Every
  `bin/tessera-test` run under a real session wrote four undispositioned `spend_denied` events
  (a test drove the real guard hook as a subprocess, which inherits `CLAUDE_CODE_SESSION_ID`).
  Each bumped this counter at the next Stop. **The suite burned through the cap of the
  mechanism that guards unsupervised spend** — and neither half announced anything.

- **Fixed three ways, because a fix is not a signal:**
  1. The counter is keyed **per session** and pruned to the last 20. A clean session never
     writes at all; a new session starts at zero because its key is absent. Unreadable or
     legacy state reads as EMPTY, i.e. fails toward the backstop being **alive** — failing the
     other way is how a corrupt file becomes a silent kill switch.
  2. `tessera-watch` **P15** fires on a legacy scalar file, or on the cap being reached in 2+
     recorded sessions (chronically undispositioned denials, or a wedging backstop). It stays
     quiet for ONE capped session, which is the loop-safety working. It reads `MAX_FIRES` out
     of `backstop.py` rather than restating it, so tuning the cap moves the predicate with it.
  3. Five backstop tests + six P15 tests, including that a prior session at the cap cannot
     silence the next one.

- **FOUND BY THE REVIVED BACKSTOP, WITHIN THE HOUR: the "false positive" disposition has no
  recordable form.** The report ends with *"If the denial was a FALSE POSITIVE … say so plainly
  and finish. That is a legitimate disposition"* — and `undispositioned()` clears on exactly two
  things: a `spend_authorized` event **after** the last denial, or any escalation packet. Saying
  it plainly clears nothing, so the hook re-fires at every Stop for the rest of the session (now
  capped per-session, so it stops at 3 rather than forever).
  **This is principle #17 inside the spend gate**: a disposition that rides prose is a
  disposition the mechanism cannot hear. And the two available exits are both wrong here —
  granting an envelope authorizes spend that was never requested, and raising a packet
  manufactures the bogus escalation the contract itself says is worse than none.
  **Needs a design gate before code, because a "dismiss" verb on a spend gate is exactly the
  affordance that could silence a real denial.** Sketch: a `spend_dismissed` event carrying a
  required reason, honoured by `undispositioned()`, emitted only by a human-invoked command —
  never by the agent whose denial it clears. Not built; do not build it without the gate.

- **Two smaller lessons from the fix itself.** The first prune sorted by count and evicted the
  entry it had just written — the freshest session is also the lowest count; caught by the test
  written for it. And a bare `47` is **valid JSON**, so the legacy shape arrived as an `int`
  rather than a parse error, and P15's first version reported the wrong branch.

---

### iCPG's drift detector measures the emptiness of its own graph *(2026-07-25 → 07-26; surfaced by the scryer eval, root cause found on the third pass)*

- **Status:** **SHRINK EXECUTED 2026-07-27** (steps 0–2 and 4–6 of the corrected work order;
  step 3 — dedup on insert, event IDs, evidence on the report — is still OPEN and is now the
  whole remainder). What shipped, and the one thing the fourth pass found:

  - **Six dimensions → three, each with a named producer.** `changed` (checksum, fed by
    `upsert_symbol`), `decision` (contract predicates, fed by `contracts.py`), `usage` (bounded
    to git-tracked files). **Deleted:** `ownership` (needs >3 distinct reason owners; all 10
    reasons are `owner='git-history'`) and `dependency` (needs REQUIRES edges; unwritten).
    **Moved out:** `test` → `scripts/icpg/coverage.py`, reported by `icpg status` as
    `Intents w/o tests: 10/10` — a count, never a severity, with no path into a composite.
  - **A FOURTH root cause, and it is not the "no writer" one.** `_check_decision_drift` gated on
    `reason.postconditions` — **0 of 10 reasons have any** — while `contracts.py:88` writes a
    `file_exists(...)` invariant for every scope path of every reason: **53 invariants across
    10 reasons**, and `evaluate_predicate` has always supported exactly that form. A live
    producer, a live evaluator, and a reader pointed at the wrong field. Not an absent edge
    type; a mis-wiring, invisible to every previous pass because all three parts existed. It
    now reads invariants AND postconditions. *Fourth pass, fourth root cause — see the method
    lesson below, which predicted this shape.*
  - **The 746 stored events were PURGED, not deduplicated.** Deduplicating would have preserved
    154 distinct non-measurements; 725 of the 746 carried the constant `test(0.30)`. Standing
    pattern #7 — a verdict must not rest on what the instrument could not read.
  - **Fresh baseline, honest and interpretable for the first time:** 217 events over 816
    symbols — `usage` 140, `changed` 49, both 28. **`decision` fires ZERO, and that is now a
    different fact than before:** all 53 invariants currently hold, verified by evaluating each
    one. It *could not* fire before; it *did not* fire today. Live-and-silent ≠ dead.
  - **`scripts/icpg/` has tests — its first, ever.** 13 in `test_drift.py`, its own process line
    in `run-tests.sh` (icpg and polyphony both carry `store.py`/`models.py`; the collision is
    latent only because polyphony has no tests yet), registered under doccheck's
    `ignored-test-suites-are-run`. **Three of them were watched going RED** against a re-added
    unfed dimension before being accepted.
  - **The check that would have caught all of this:** doccheck
    **`drift-dimensions-have-producers`** (33 checks now) — every edge type `drift.py` reads
    must be one something in `scripts/icpg/` writes. `drift.py` is excluded from the producer
    scan so it cannot vouch for itself, and **an empty read set is a violation, not a pass**
    (standing pattern #1: what tells you the check itself died). Non-vacuity is tested by
    feeding the shipped module back through the predicate with one edge type swapped.
  - **`bin/tessera-verify` then REFUTED part of the above, and the refutation was correct.**
    Three claims went to the falsifier: CONFIRMED / **PARTIAL** / CONFIRMED, on
    `verdict_channel: "file"` — the second real (non-self-test) run to return a usable verdict
    by file, so that fix now stands at n=2. What it found, by re-adding each removed dimension
    from `git show b619755~1`:
    - The runtime guards catch a re-added **`test`** dimension (3 of 13 fail) but **not
      `dependency`** — all 13 stayed green. Root cause worth keeping: a dimension scoring the
      **absence** of an edge fires on every symbol and is caught by observation; one scoring the
      **presence** of a never-written edge returns `None` forever and never reaches the output
      at all. Testing the emitted dimensions cannot see the second kind. **Fixed** by asserting
      the *declared* vocabulary — `inspect.getsource(check_symbol_drift)` — so a dead dimension
      is visible the day it is added rather than never.
    - **`ownership` was caught by NEITHER guard**, and that was a hole in the new check itself:
      `_check_ownership_drift` called `store.get_edges_to(sym.id)` **untyped**, so it named no
      edge type, so the producer scan saw it consuming nothing and passed. **Fixed** — an
      untyped edge read in `drift.py` is now its own violation, because "every edge type"
      cannot be producer-checked. Both landmines re-run against the fixes: each now trips the
      test suite *and* doccheck.
    **The shape to carry:** I wrote a guard, tested it against the failure I had just removed,
    and it passed — while being blind to two of the three dimensions that motivated the work.
    Standing pattern #1 aimed at a brand-new check, caught within the hour only because the
    claim was stated explicitly enough to be falsified. *A check verified against the bug you
    remember is verified against one example.*

  **RE-INSERTION CLOSED 2026-07-27 (step 3 of the corrected order, the remainder after the
  shrink).** `create_drift_event` now dedups on insert against a natural key, and the report
  became adjudicable for the first time:
  - **The key is `(symbol_id, from_reason_id, sorted(dimensions))` — a judgement, and the
    reason it is not the description.** ADR-0013 proposed keying on the description, but the
    description embeds the scores (`usage(1.00)`), so a severity drifting by 0.1 would mint a
    new row and the backlog would keep creeping — the same defect wearing a smaller hat. A
    symbol drifting the same WAY is one event whose severity and last-seen refresh in place.
  - **Scoped to OPEN events.** A drift that was resolved and then recurs is NEWS and gets a new
    row; folding it into the closed one would silently resurrect an adjudicated finding.
  - **The migration collapses history, not just future inserts.** Dedup-on-insert alone strands
    the existing duplicates — a later scan refreshes ONE copy and the rest sit unreachable
    forever, so the backlog stops growing while staying unreadable. The survivor is the OLDEST
    row per key (so `detected_at` still means first-seen), `seen_count` sums, resolved rows are
    untouched. On the live DB: **218 → 191**.
  - **Every drift line now carries an id, the symbol, and the file.** `icpg drift resolve` has
    existed since the module was written and was unreachable because nothing printed its
    argument; `icpg drift list` and short-prefix resolution close that. And `resolve` **fails
    loud** on an unknown id (rc=2) — it used to `UPDATE ... WHERE id = ?` and print "Resolved"
    whether or not a row matched, the same fail-open that let `mnemos haze --session` score an
    unknown session as `0.00 CLEAR`.
  - **Verified on the property, not the code:** two consecutive full scans over the live graph
    now read 195 → 195. Before, each scan added ~150 rows.
  - 12 tests (`test_drift_dedup.py`), including the migration against a real pre-dedup schema.

  **Original finding, kept — this is what it looked like before the fix:**

  **STILL OPEN, and do not let the purge hide it: the re-insertion defect is live and it
  refills the backlog automatically.** `mnemos-pre-edit.sh` runs `icpg drift file` on every
  Edit/Write and `cmd_drift` persists every event with a fresh UUID and no natural key — the
  746 rows had grown from 712 during this session's own editing. Purging without fixing insert
  buys one clean reading, not a clean counter. That is step 3, unchanged in content and now
  correctly ordered first among what remains.

  **What this does NOT settle: iCPG's kill/keep trial.** `design-principles.md:459` asks two
  questions and this answers one. The other — *does the agent populate ReasonNodes and
  contracts well in practice?* — is still unexercised: **all 10 reasons are `owner='git-history'`,
  `agent=NULL`, `source='inferred'`,** i.e. every one is bootstrap-derived and none was authored
  by an agent doing work. A cause fully explains that (no hook records intent, and the hook that
  *surfaces* it was dropping its output until 2026-07-24), so per FOCUS-004's rule the absence is
  **not evidence** for or against the concept. A verdict needs the recording half wired first.

  **THE CALIBRATION QUESTION, ANSWERED 2026-07-27 — and the answer was not a threshold.**
  Measured before touching anything, because the standing instruction was *state the question
  first, do not tune `>2` and `/10` by eye*:
  - **The distribution is not pathological, and my earlier framing of it was too harsh.**
    Of 879 CREATES-linked symbols: **46% score zero**, 34% sit at 1–2 (below threshold), 9%
    at 3–9, 10% saturated. The threshold *is* discriminating — mass sits on both sides of it,
    which is exactly what a meaningless cut would not produce. "Fires on ~1 in 5" was true and
    the inference "therefore miscalibrated" was not.
  - **The real defect was definitional.** `usage` counted every tracked file mentioning the
    symbol — **including the file the symbol is DEFINED in**. A symbol's own definition is not
    usage outside its scope. **32 of 174 firing verdicts flip** on that alone. Fixed; the
    thresholds are deliberately untouched.
  - **What the measurement actually exposed is SCOPE QUALITY, not threshold choice.** Only
    **42% of tracked files sit inside any reason's scope**, and **46% of symbols are
    CREATES-linked to a reason whose scope does not include the file the symbol lives in.**
    That is incoherent on its face — an intent that "created" a symbol in a file it does not
    claim — and it is a property of git-history bootstrap, which derives scope from one commit
    cluster. **No threshold can repair an input like that**, which is why tuning would have
    been the wrong lever applied confidently.
  - **So the open question is re-stated, not closed:** not *"are `>2` and `/10` right?"* but
    ***"is a bootstrap-derived scope trustworthy input for a scope-comparison dimension?"***
    On this graph, demonstrably not for ~half of it. That is answerable by fixing scopes or by
    scoping the dimension to reasons whose scope covers their own symbols — a design question
    with evidence attached, which is where it should have started.

  **Noticed while re-scanning, recorded not fixed: a drift that STOPS drifting is never closed.**
  Dedup refreshes an existing open row and inserts new ones, but nothing retires a row whose
  condition no longer holds — so the backlog is monotonic between manual dispositions. Auto-closing
  would silently erase findings, so this needs a decision rather than a patch; it is the same
  disposition-authority question ADR-0016 answered for the other two states.

  **A second calibration question, deliberately left open:** `usage` now fires on 168 of 816
  symbols with 64 saturated at 1.00. It is honest — a scope comparison over tracked files — but
  its thresholds (`>2` files, `/10` saturation) were never calibrated against anything, and the
  bootstrap reasons' scope is one commit-cluster wide, so "outside scope" is nearly the whole
  repo by construction. **Do not tune those numbers by eye** — that is how the three retired
  proxy predicates were born. It needs a stated question first.

- **Original status:** OPEN, and this entry had been **corrected twice** — each pass found the
  previous root cause too shallow. Kept in full, because the *sequence* is the lesson: each
  correction came from reading one layer deeper into code I had already formed a confident
  verdict about. *(A third correction, above, landed on the fourth pass. The lesson held.)*
  1. **First claim (wrong):** "iCPG has no verb to close a drift event." False — `icpg drift resolve`
     exists. Corrected in ADR-0013's CORRECTION block.
  2. **Second claim (true but shallow):** "the detector re-inserts duplicates; 700 rows are 154
     distinct drifts." True, and still worth fixing — but it explains the *count*, not the *content*.
  3. **Third, and the actual finding (below):** every dimension the detector scores is measuring
     whether an edge type exists in the graph, not whether the code changed. Fixing dedup would have
     produced 154 correctly-deduplicated meaningless rows.

- **THE FINDING: five of six edge types have no writer, and the drift dimensions score their absence.**

  ```
  edges by type:   CREATES 879   MODIFIES 0   REQUIRES 0
                   DUPLICATES 0  VALIDATED_BY 0   DRIFTS_FROM 0
  ```
  `REQUIRES`, `DUPLICATES`, `VALIDATED_BY`, and `DRIFTS_FROM` appear **only** in `models.py`'s enum
  (`models.py:45`) and on the *read* side (`store.py:303,315,337`). Nothing in the codebase writes
  them. `MODIFIES` has exactly one writer — `icpg record --edge-type MODIFIES` (`__main__.py:60`) —
  which is **wired to no hook** and has therefore never run. One edge type is populated. Six are read.

  What that does to the six dimensions:
  - **test drift** — `_check_test_drift`: `if not test_edges: return 0.3  # "No tests linked — mild
    concern"`. Zero VALIDATED_BY edges exist, so this returns 0.3 for every symbol on every scan,
    permanently. **701 of 701 events (100%) carry `test(0.30)`.** It is a constant, not a measurement.
  - **spec drift** — defined as "checksum changed *without a MODIFIES edge*." With zero MODIFIES
    edges it degenerates to "checksum changed," which is `git diff`.
  - **usage drift** — `_check_usage_drift` shells out to **literal `grep -rl <symbol_name> .`** with no
    path exclusions, so it scans `.venv/`, `.git/`, `build/`, `__pycache__`. `min(1.0, out_of_scope/10)`
    saturates at 1.00 after ten hits, which any common symbol name reaches inside vendored code alone.
  - **decision / ownership / dependency drift** — have **never fired once.** Only three dimension-sets
    have ever occurred: `["test","usage"]` ×543, `["spec","test","usage"]` ×157, `["test"]` ×1.

- **This answers the design doc's own trial criterion, and the answer is no.**
  `docs/design-principles.md:440` sets the iCPG kill/keep test: *"Does drift detection catch things
  grep wouldn't?"* The dimension that fires on 700 of 701 events **is implemented as grep** —
  `subprocess.run(['grep', '-rl', sym.name, '.'])`, `drift.py`. Not grep-like. Grep, in a subprocess,
  over an unfiltered tree. Standing pattern #3 (*name the pain, not the artifact that correlates with
  it*) at full strength: every dimension fires correctly and means nothing.

- **A second confound on the same trial.** `design-principles.md:430` records iCPG's delivery as
  "PreToolUse on Edit/Write shows intent + constraints before every edit; Stop hook auto-records
  symbols after tests pass." Neither is live here: the PreToolUse path is `mnemos-pre-edit.sh`, which
  the entry below ("PreToolUse hooks' bare stdout never reached the model") shows was **silent for the
  entire trial**; and **no Stop hook calls `icpg` at all** — the wired Stop hooks are
  mnemos-stop-checkpoint, mnemos-stop-ingest, tessera-gate-scan, tessera-spend-backstop,
  tessera-verify-scan. That is why nothing writes MODIFIES: the auto-record was described but never
  wired. *(Note: `:430` sits in the Pass 1.5 record of what the upstream skill claims, so it is not
  itself false — it is a description of a design Tessera never implemented. Left unedited as history.)*

- **Bearing on the kill/keep verdict: it is confounded three ways, and none of them are "the idea
  failed."** The graph is fed by one edge type; the detector scores the absence of the other five;
  and the channel that was supposed to deliver its output to the model was dropping it. Same shape as
  F-001 (*empty ≠ unused*) one layer up — a verdict of "drift detection found nothing useful" would be
  measuring the plumbing, not the concept. **Do not judge iCPG until at least the writers exist.**

- **Fail-open class, and a spec-11 candidate.** Nothing anywhere asserts that an edge type the
  detector *reads* has a writer. The natural check — *every edge type consumed by `drift.py` must be
  produced somewhere* — would have caught all of this at commit, and is the check to leave behind
  when the code fix lands (Standing pattern #1: before shipping a check, ask what would tell you the
  check itself died). Worth pointing `tessera-chaos` at too.

- **Corrected work order** (supersedes ADR-0013's, which supersedes the original):
  0. **Decide what the detector is for.** Either wire the writers (`VALIDATED_BY` from the test suite,
     `MODIFIES` from a Stop hook) so the dimensions have real inputs, or delete the dimensions that
     cannot be fed. Do not keep scoring absent edges.
  1. **Bound or delete usage drift.** `git ls-files`-scoped at minimum; it is grep-with-extra-steps
     as written, and it is the dimension the trial criterion explicitly rules out.
  2. **Stop reporting `test(0.30)` as drift.** "No VALIDATED_BY edge" is a graph-completeness signal;
     report it as coverage, separately, or not at all.
  3. **Then** dedup on insert, surface event IDs + `drift list`, evidence on the report, `--note` /
     `dismissed` — the ADR-0013 list, still correct, now correctly ordered *after* the above.
  4. **Tests.** `scripts/icpg/` has zero and is absent from `run-tests.sh`; adding a suite collides
     with `scripts/polyphony/` on `store.py`/`models.py`, so it needs its own process line plus
     doccheck's `ignored-test-suites-are-run` registration or it silently stops running.

- **Method lesson, the reusable part.** Three passes, three verdicts, each stated with confidence and
  each wrong or shallow — and every correction came from reading the next layer of *our own* code,
  never from new external information. The evaluation methodology scrutinises the target by
  construction; nothing in its six dimensions says *read your own implementation before asserting your
  own gap*. First pass read `icpg status` output. Second read the CLI. Third read the detector and the
  edge table. The finding was in reach the entire time. This is the `rule-over-read` memory as a
  repeating failure, not a one-off.

---

**↓ SUPERSEDED ROOT CAUSES (passes 1 and 2), kept verbatim for the trail. Everything from here to
"end superseded" was true-but-shallow or outright wrong; the live finding is above. Do not action
this section — the dedup fix it prescribes is real but is now step 3, not step 1.**

- **What it is, measured** against `.icpg/reason.db`:
  ```
  total=700   unresolved=700   distinct(symbol_id, from_reason_id, description)=154
  distinct_symbols=102         distinct scan-minutes=31
  most duplicated: n=21 for one (symbol, description) pair — one row per scan
  ```
  Standing pattern #2 (*it did not break, it produced something plausible*); a fail-open instance
  for Spec 11's sweep, and a *better* example than first written — the counter is inflated ~4.5× by
  the detector itself.
- **Two real defects, neither of them a missing verb:**
  1. **Unconditional re-insertion.** `cmd_drift` (`scripts/icpg/__main__.py:384`) does
     `for event in events: store.create_drift_event(event)` on every scan — fresh UUID, no
     natural-key check. Same drift, 21 rows.
  2. **The existing verb is unreachable.** `drift check`, `drift file`, and `status` print severity
     and description and **never print `event.id`**; there is no `drift list`. The argument
     `drift resolve` needs cannot be obtained from any command's output — only from raw SQLite.
- **CORRECTED — the original claim was false.** This entry first said iCPG "has **no verb to close
  one**." `icpg drift resolve <event_id>` has existed since the module was written
  (`scripts/icpg/__main__.py:112` → `ICPGStore.resolve_drift()`, `store.py:261`). The claim came from
  reading `icpg status` output and scryer's MCP tool list without reading iCPG's own CLI — the
  `rule-over-read` failure exactly: a documented pattern applied by match, without checking the
  artifact. **The generalisable lesson:** an evaluation scrutinises the *target* by construction;
  the six-dimension methodology has no step that says "read your own code before asserting your own
  gap." The unexamined side was ours, and it produced a confident, wrong, committed root cause.
- **Why nobody noticed the backlog:** the report is unadjudicable. The top five events are
  byte-identical — `[0.65] Drift detected: test(0.30), usage(1.00) (test, usage)` — with no symbol,
  no file, no diff. Nothing in the output a human could act on, so it accumulated in silence.
- **How it surfaced:** reading Scryer's `flag_drift` / `reconcile_drift` / `mark_implemented` verbs
  and then running `icpg status`. The eval's most valuable output was about iCPG, not about scryer.
- **Decided (ADR-0013, as corrected):** (1) **dedup on insert** — natural key over open events, bump
  last-seen/count instead of inserting; (2) **surface the IDs** — print short event IDs in
  `check`/`file`/`status`, add `icpg drift list`, making the existing verb usable; (3) **evidence on
  the report** — symbol, file, and what changed; (4) `--note` and a `dismissed` state (a real gap,
  but the *last* fix, not the first).
**↑ end superseded.**

---

- **Note on test coverage:** `scripts/icpg/` has **zero tests** and is absent from
  `scripts/run-tests.sh`. Any of the above lands untested unless a suite is added — and adding one
  must go through run-tests.sh's separate-process pattern plus doccheck's `ignored-test-suites-are-run`,
  or the new suite silently stops running (Standing pattern #1).
- **Open — do NOT resolve these without their own evidence:**
  1. **6-dimension composite vs. 2 deterministic predicates.** Scryer uses exactly two, no LLM:
     *source-mapped node whose file changed since last reconcile*, and *project file the model does
     not cover*. iCPG's `0.65` over six weighted dimensions is a **proxy** — Standing pattern #3
     (*name the pain, not the artifact that correlates with it*), which has already retired three
     predicates. Retiring iCPG's scoring is a bigger decision than one ADR should make.
  2. **The plan/committed split.** Scryer keeps `planned.scry` (editable draft) and `model.scry`
     (committed) and treats *the diff between them as the plan*. Tessera has no machine-diffable
     "intended state" — `_project_specs/todos/active.md` is prose. Design pass, not a patch.
  3. **Do the 680 mean the detector is miscalibrated, or merely undisposable?** Unanswerable until
     the two decided fixes land and the backlog is actually worked. Do not read the number as
     evidence for either until then.
- **Bearing on the iCPG kill/keep trial:** same shape as F-001 and the PreToolUse channel bug above —
  a signal that was structurally unable to be acted on is not evidence the idea failed. Any iCPG
  verdict formed on "drift detection produced nothing useful" is tainted the same way.
- **When to revisit:** when the two ADR-0013 fixes ship, or when the iCPG kill/keep trial is judged.

### The spend guard matches command TEXT — it over-denies prose and under-denies assembly *(2026-07-26)*

- **THE UNDER-DENIAL HALF STOPPED BEING HYPOTHETICAL (2026-07-27), and it was not assembly — it
  was a plain literal.** This entry said "nothing currently tests the under-denial direction at
  all" and framed the risk as *runtime-assembled* commands. `bin/tessera-verify`, working an
  unrelated claim, found five bypasses that need no assembly at all: `python3
  bin/tessera-authorize grant` returned **ALLOW**, as did `.venv/bin/python …`, `env …`,
  `command …`, and `uv run …`. Static text, typed by hand, against the control ADR-0016 had
  declared refused *unconditionally* one day earlier.
- **Why it survived: the contract's own hedge absorbed it.** "Known ceiling, inherited — a
  runtime-assembled invocation slips past" reads like it covers this. It does not. **A ceiling is
  a class of thing you have decided not to catch; a hole is a member of the class you claimed to
  catch. A hedge phrased broadly enough will launder the second into the first,** and that is the
  transferable lesson — this repo's docs are full of honest, carefully-scoped limitations, and
  each one is a place a real defect can hide in plain sight.
- **And the comparison nobody ran:** `INVOKED_SCRIPT`, twenty lines below in the same file,
  already carried the interpreter group `SELF_AUTHORIZING` lacked. Two patterns, one file, one of
  them right. Standing pattern #1's newest instance — the thing that would have caught it was
  sitting next to it.
- **Fixed narrowly, and the fix does NOT close the entry.** A bounded launcher group closes the
  five literals, regression-tested in both directions; stacking 4+ launchers still passes and is
  recorded as an accepted limit. **The design gate this entry asks for is still open**, and
  ADR-0006's tier ranking sharpens what it should ask: a deny-list is tier 4 (a channel — "works
  until it doesn't, and then it manufactures false confidence", which is precisely what happened
  here). More tier-4 patches buy less each time. **The gate's real question is whether a tier-1
  (bad state unrepresentable) or tier-2 (out-of-band bound) form of this control exists** — not
  which regex to write next.

- **EVIDENCE ADDED 2026-07-27, and it sharpens the shape: the over-denial specifically punishes
  WRITING ABOUT and TESTING the guard.** It blocked me **four times in one session** — twice
  editing docs that described the verbs, twice running a regression matrix over `decide()` — and
  every time for the same structural reason: `python3 - <<'PY'` is **wrapper-led**, so heredoc
  bodies count as code rather than data, and the text contained the commands under discussion.
  The contract's prescribed remedy (use a non-Bash tool) worked all four times, so nothing was
  blocked outright.
- **Why this is not just noise, and belongs in the design gate:** the activities being penalised
  — documenting the guard, and testing it — are exactly the ones that keep it correct. A control
  that taxes its own maintenance is one people route around, and routing around is the failure
  mode the guard exists to prevent. **This is the strongest argument yet that the over-denial is
  a real cost rather than a tolerable one.**
- **It also constrains the fix.** ADR-0016 added `SELF_AUTHORIZING` and its first version matched
  the verb *anywhere* in the command, which blocked the commit documenting the feature within a
  minute of being written. Narrowing to **command position** (optionally behind `bash -c "`)
  fixed that case — so command-position matching is a demonstrated, tested improvement, not a
  hypothesis. **Whether the same narrowing is safe for `COMMITTING` is the open question**, and
  it is not obviously yes: a boot command *is* often wrapper-led legitimately, which is why
  quoted text is treated as code there in the first place.

- **What happened:** while cleaning up after the spec-11 chaos probes, the spend guard blocked a
  **log-cleanup script** — a pure file rewrite that commits nothing — because the script's body
  contained the literal string of a spend command it was filtering for. In the same session it
  also blocked `bin/tessera-verify`'s own meta-command for the same reason: an `echo`/heredoc that
  merely *named* `terraform apply`. `decide()` is handed the Bash tool's whole command text and
  matches substrings in it.
- **The over-denial is the visible half and the safe direction.** An agent that writes *about* the
  spend gate — a commit message, a grep, a heredoc, a test fixture — gets blocked. Annoying, loud,
  self-correcting: you find out immediately.
- **The under-denial is the half nobody has looked at, and it is the serious one.** The same
  imprecision means the guard only ever sees **pre-expansion** text. A command assembled at
  runtime — `CMD=$(...)`, a variable, string concatenation, a `$(cat file)` — reaches the Bash
  tool as text that does not contain the trigger, and passes. The workaround for the false
  positive *is* the bypass for the real control, which is why the two halves cannot be reasoned
  about separately. **Nothing currently tests the under-denial direction at all.**
- **Why this is not a fix-it-now:** the naive tightening (match harder) worsens the over-denial,
  and the naive loosening (only match the resolved command) is not available — a PreToolUse hook
  sees the command *before* the shell expands it, so there is no resolved form to inspect. This
  needs a design gate, not a patch. Candidate directions: treat quoting/heredoc context as
  structure rather than text (the guard already has a `HEREDOC_START` regex, so it half-does this
  for a different reason); or accept text-matching as advisory and put the real control at the
  boundary that *does* see resolved commands (the AWS budget → SNS → hardstop lambda that
  `tessera-spend-guard.sh` already names as its out-of-band bound).
- **Bearing on ADR-0005 / spec 11:** the guard is one of spec 11's five components, and this is a
  DIFFERENT defect class from the one those probes measure. The probes ask *"does it say so when
  it breaks?"*; this asks *"is what it matches the right thing at all?"* Standing pattern #3 — a
  predicate that measures a stand-in (command text) for the thing that matters (committed spend)
  will fire correctly and mean nothing. Deliberately NOT folded into the chaos suite, to keep
  "report your own failure" and "the matching is wrong" from becoming one blurred item.
- **When to revisit:** before any unsupervised-autonomy claim leans on the spend guard, or when
  spec 11 step 2 classifies that component's bail-outs.

### `tessera-verify` did the work and lost the verdict — its own Stop hook ate the final message *(2026-07-26)*

- **What happened:** two runs, seven claims, `NO_VERDICT` on every one. The 2026-07-21 fix
  (`49b4bbc`) correctly ruled out the old cause — a spawn that never ran now raises
  `VerifierDidNotRun`, and it did not fire, so the verifier *did* execute. `raw_excerpt` (added by
  that same fix, and the only reason this was diagnosable at all) shows what actually happened:
  - **Run 1** — the child session's own spend guard blocked its meta-command, because the command
    body contained a spend command as a *string*. The child spent its turn dispositioning spend
    denials instead of answering the claims. See the guard-matching entry above.
  - **Run 2** — the child did the real work: planted landmines in `scripts/gate/ratio.py` and
    `emit.py`, executed against them, reverted cleanly. Then **its own `verify-scan` Stop hook
    fired**, it recorded a skip, and *that acknowledgment became its final message*.
    `parse_verdicts` reads the final message, found no verdict markers, and returned `NO_VERDICT`
    for all three claims. **The verification happened and the answer was overwritten.**
- **Why this is the third instance of one shape, not three bugs:** standing pattern #9 — a
  mechanism that RUNS has not necessarily REACHED its audience. The falsifier is defeated by the
  backstop it is part of, exactly as `decision-surface`, `mnemos-pre-edit`, and Layer-3 compaction
  recovery were defeated by the channel they emitted on.
- **The compounding part:** `raw_excerpt` keeps only `raw_output[-2000:]`, so the tail (the skip
  note) survived and the verdict block did not. The diagnostic captures the wrong end of the
  output for this failure mode.
- **FIX (a) SHIPPED AND PROVEN 2026-07-26.** A live `tessera-verify --self-test` returned
  `verdict_channel: "file"`, verdict `REFUTED`, self-test PASS — the planted landmine caught,
  and **the first usable verdict this tool has produced in four real attempts.** The verifier is
  now told to
  write its verdicts to `tessera-verdicts.json` inside its worktree; `bin/tessera-verify` reads
  that file as authoritative and falls back to scraping the final message only if it is absent,
  recording which channel was used in `verdict_channel`. Rejected for now: (b) stripping Stop
  hooks from the spawned session, which removes the collision but also removes the child's own
  safety net; (c) keeping more of `raw_output`, a diagnostic mitigation that makes the failure
  legible rather than absent.
  - **The fix nearly reintroduced the bug it fixes.** `make_worktree` copies UNTRACKED files
    from the source tree into the worktree, so a stale `tessera-verdicts.json` in the repo root
    would have arrived inside the worktree and been read as this run's verdicts — CONFIRMED for
    a verifier that wrote nothing. Guarded by an unlink before every spawn (authoritative) plus
    a `.gitignore` line (advisory — a `--force` add or a downstream lacking the rule defeats an
    ignore rule; nothing defeats the unlink). Regression test removes the guard and watches
    the false CONFIRMED appear.
  - **What is proven, and what is still only n=1:** one live run wrote the file. That is
    evidence the instruction is followable, not that it is always followed — writing the file
    remains an *instruction to a model*, exactly as the old `VERDICT <n>:` format was. What
    structurally changed is that a file cannot be **overwritten after the fact**; it can still
    be **skipped**. `verdict_channel: "final-message"` on a real run is the signal that this is
    happening, and it is why the field is recorded on successes too.
- **Bearing on spec 11 and ADR-0005:** `bin/tessera-verify` is the framework's adversarial check
  and it had returned no usable verdict on 3 of 3 real attempts, so "Tessera independently
  verifies its own work" was unsupported. **That is now supported at n=1** — the tool caught a
  planted landmine through the file channel. It is not yet a track record: the number worth
  watching is how many real runs come back `file` vs `final-message`, and `tessera-verify stats`
  does not break that out yet.
- **When to revisit:** check `verdict_channel` on the next few real runs. And before spec 11
  step 2 is judged (criterion 5 wants an *independent* session to confirm the bar — this tool is
  what "independent" was supposed to mean, and it is now plausibly able to be that).

### A Tessera skill silently shadowed a built-in command *(2026-07-26, observed live)*

- **Status:** **INSTANCE CLOSED 2026-07-27 (the skill was CUT by ADR-0014, so the collision is
  moot rather than solved); the CLASS is still OPEN and still unguarded.** The check is the open
  part and is harder to ground than it first looks (below) — there is no enumerable source of
  built-in command names inside the repo, so a hardcoded list would be proxy predicate #4.
  *(Status corrected 2026-07-27: the body recorded the closure and this header still read a flat
  OPEN — the index-vs-body drift this repo fixed in two handoff items the same morning.)*
- **What happened.** `/code-review ultra review-base-20260726` was typed to launch the cloud
  ultrareview. It did not launch. Tessera ships a skill named **`code-review`**, which shadowed
  the built-in command of the same name; the arguments `ultra review-base-20260726` were handed
  to that skill as plain text, and it loaded its local multi-engine review guide instead. **No
  error, no warning, no cloud session.** `/ultrareview <base>` — the documented alias, and not a
  skill name — worked first try.
- **Why it belongs here and not in a commit message.** It is the fail-open class again, in a
  place nobody had looked: *you invoked X, got Y, and nothing said so.* A skill loading IS what
  success looks like, so there is no signal to notice. Compare the F-001 family — the failure
  did not announce itself because the substitute behaved plausibly.
- **Blast radius is not one machine.** ADR-0010 makes `skills/` the truth and mirrors it to
  `~/.claude/skills`, which is how this collision exists at BOTH user and project level here,
  and how it reaches every downstream that syncs. Any name Tessera picks is claimed everywhere
  the registry lands.
- **Measured, not assumed:** Tessera owns **51** skills. Against the built-ins visible in this
  session, exactly **one** collides today — `code-review`. `security` vs the built-in
  `security-review` and `python` vs the built-in tooling do NOT collide (different names).
- **Why the obvious check is not obvious.** A doccheck rule "no skill name may equal a built-in
  command" needs a *list of built-in command names*, and there is no stable, enumerable source
  for that inside the repo — the set is defined by the harness, changes with Claude Code
  releases, and is only observable as a rendered listing in a live session. A hardcoded list
  here would be a **proxy predicate** that rots silently (Standing pattern #3, which has already
  retired three of them). **Do not ship the hardcoded version as if it were the real check.**
  Candidate approaches, none yet chosen:
  1. **Rename ours** — `code-review` → `tessera-code-review`. Fixes today's instance outright and
     needs no oracle. Costs: it is referenced in this repo's CLAUDE.md, the `adr-gate` skill, and
     downstream docs, so it is a rename with a blast radius, not a one-liner.
  2. **A namespace convention** — prefix every Tessera skill, making collisions structurally
     impossible and checkable without an oracle (`assert every skill dir starts with the prefix`).
     Cheap to check, expensive to migrate 51 skills, and it makes every skill name uglier.
  3. **A curated known-collisions list** with an explicit staleness marker, accepting the proxy
     but making its rot visible.
- **DECIDED 2026-07-26 (Lorenzo): approach 1 — rename `code-review` → `tessera-code-review`.**
  Cleanest, needs no oracle, and fixes the live instance outright. Approach 2 was considered and
  rejected as disproportionate, on a sharper argument than cost alone: **Tessera's skill names and
  Claude Code's command names occupy different namespaces almost everywhere.** The 51 are mostly
  *domain* names (`android-kotlin`, `supabase-nextjs`, `aws-dynamodb`, `flutter`); built-ins are
  *harness verbs* (`run`, `init`, `review`, `loop`, `schedule`). Prefixing all 51 pays a full
  migration to protect ~45 names that were never at risk, and would churn `base` and `mnemos` —
  the two eagerly loaded by path from CLAUDE.md — for no gain.
- **Residual after the rename, and it is small enough to watch by eye.** Approach 1 fixes today's
  instance only, so the names still generic enough for a *future* built-in to claim are worth
  knowing: **`security`** (built-in `security-review` already exists; `security` is a plausible
  sibling), **`python`** (maximally generic), **`base`** (generic AND eagerly loaded, so a shadow
  would be silent and broad), **`workspace`**, **`credentials`**. Five to watch, not 51 to rename.
  No check is claimed for these — the oracle problem above is unchanged; this is a named watch
  list, which is what the observatory is for.
- **RENAME EXECUTED 2026-07-26** → `tessera-code-review` (the skill was then CUT 2026-07-27, ADR-0014). Global mirror re-synced via
  `bin/tessera-sync-skills` (ADR-0010: repo is truth; the old dir was deleted by the sync, not by
  hand). Also updated: the skill's own `name:` frontmatter, `templates/tessera/skill-profiles.json`,
  and the `Skill(...)` permission entry in `.claude/settings.local.json`. `.claude/skills` is a
  symlink to `skills/`, so the project tier followed automatically. Native `/code-review` is
  unshadowed and `/code-review ultra` reaches the cloud reviewer again.
- **The rename is an INTERIM, not the verdict — and this is the part a future reader must not
  misread.** ADR-0008 (Accepted, 07-14) directed **CUT-the-bulk / KEEP-the-ADR-gate** for this
  skill. The keeper was split out (`skills/adr-gate/`); the cut was never executed. A *later*
  entry in this same file (the conclave/pr-arbiter note, 07-16/17) then deferred the whole
  question: *"same vendor-CLI-review-deprecation question, resolved there, not piecemeal"* —
  **Open decision D1.** So the skill is renamed to stop the live shadowing and otherwise left
  alone, deliberately pre-empting nothing.
- **Why cutting it now would have been wrong, on evidence gathered 2026-07-26.** ADR-0008's two
  stated reasons have both moved: (i) "superseded by native `/code-review`" still holds and is
  stronger; but (ii) "the multi-engine bulk needs Node (**absent**)" is **no longer true** — Node
  and npx are installed (fnm); only the `codex`/`gemini` CLIs are still missing. More importantly,
  the `review` orchestrator existed as an API-based multi-model runner (deepseek/kimi/codex) — **cut 2026-07-27**, having never run and with 0 of 3 backends functional —
  which means the portability the skill *appears* to protect is really a **provider-layer** concern
  that the `review` orchestrator owned — while the skill's content is **harness-adapter** layer, the thing
  design-principles §"Primary harness" strips (*"Codex stays available as a model provider via
  LiteLLM, not as a separate harness"*). Cutting loses no portability; but keeping it also buys
  none, because the provider layer is **not wired to conclave's gateway or LiteLLM**. That gap is
  the real work, and it is D1 — see ADR-0014.
- **CLOSED 2026-07-27 by ADR-0014 (option D): the skill was CUT, so the shadowing question is
  moot rather than solved.** No skill named `code-review` or `tessera-code-review` exists in the
  repo or the global mirror. Note what this does and does NOT settle: the *instance* is gone; the
  **class** — a Tessera skill silently shadowing a built-in — is not, and still has no check, for
  the reason stated above (there is no enumerable source of built-in command names inside the
  repo, and a hardcoded list would be proxy predicate #4). If a future skill name collides, this
  entry is the record that it was foreseen and left unguarded deliberately.
- **What is NOT in question:** the workaround. `/ultrareview` is unshadowed and documented.
- **When to revisit:** next time a built-in command is added that matters here, or when the
  skill corpus is next touched (ADR-0008/0009/0010 lineage) — a rename is cheapest to do while
  the corpus is already open.

### Correction recall: the premise was a bad denominator, and the real defect is budget-exhaustion *(2026-07-26)*

- **Status:** OPEN, re-framed. The "recall crisis" was largely an artifact; a different, sharper
  defect is real and needs no labelling judgement to fix.
- **THE PREMISE WAS WRONG. "5 detections / 2010 user turns" divided by TOOL-RESULT ROWS.**
  Claude Code transcripts carry tool results as `role='user'`, so the raw count is ~19x the human
  turns. `_correction_density` already filters correctly (`event_type='user'` AND
  `tool_use_id IS NULL`) — the handoff figure did not. On eligible turns only:
  ```
  ran               918 eligible  157 det  17.1%
  (null, pre-16)    479 eligible   96 det  20.0%
  budget-exhausted  170 eligible    5 det   2.94%
  recent 8          154 eligible    5 det   3.2%
  ```
  **The detector is not silent. It runs at ~17–20% of human turns.** Any future claim about recall
  must state which denominator it used — this one cost a whole re-framing.
- **THE REAL DEFECT: `CorrectionDetector` has a 180s wall-clock budget, and past it every
  remaining turn returns False.** Those turns are not *measured as* non-corrections; they are
  **unmeasured and recorded as non-corrections.** 24 sessions are `budget-exhausted` and detect at
  2.94% vs 17.1% — ~6x suppression — and haziness then scores them as if the number were real,
  with `correction_density` carrying the largest weight (0.30).
  **This is P3's `unknown` lesson in a different organ: a verdict must never rest on an event whose
  provenance the instrument could not read.** The fix is not the knob (raising 180s only moves the
  cliff). It is that a budget-exhausted session must not report a composite as though measured —
  mark it, or withhold it, exactly as P3 excludes unclassifiable events from BOTH counts.
  **Consequence to check before trusting any band: the 07-20 band re-anchoring used a distribution
  that includes these 24 sessions.**
- **The recall question that remains, and why I did not act on it.** Eval baseline (n=114):
  **precision 0.32, recall 0.53.** Precision is the weaker half. On this session I could
  hand-label ~6 turns as corrections against 1 detection — including *"it's not just compaction
  tho, it's failure too, right or no?"*, which overturned the trial's entire framing, and
  *"I take umbrage with the 16 days"*, an explicit objection. That suggests weak recall on the
  interrogative/polite register.
  **I did NOT change the detector on those labels, deliberately.** I proposed that same hypothesis
  earlier in the session, retracted it for thin evidence, and then produced labels supporting it —
  with a stake in the answer. That is motivated labelling, and the silver set exists precisely so
  the labels are not mine-in-the-moment. **Adding self-labelled turns to the silver set to justify
  a change I already proposed would corrupt the one instrument that could refute me.**
- **When to revisit:** fix budget-exhaustion first (no labels needed). For recall, the turns need
  labelling by a judgement that is not the one that proposed the hypothesis — then re-run
  `eval_correction.py` and re-open bands AND weight per P10.

### Fatigue/intent re-judged, and a proxy I used while auditing for proxies *(2026-07-26)*

- **Status:** item 5 CLOSED. The feature is LIVE and its silence is honest. One real gap found
  and fixed (icpg), and one bad measurement made by me and corrected here.
- **The re-judge (owed since the 07-24 channel fix).** `mnemos-pre-edit.sh` was silenced for the
  ENTIRE Mnemos trial by the bare-stdout bug. Post-fix it works, verified live: the
  `Mnemos + iCPG Context` block landed while editing `scripts/mnemos/checkpoint.py`.
  - **Fatigue half: live.** 0.25 FLOW, real dimensions (token-util 0.39, scope-scatter 0.375).
    Warnings fire only at `pre_sleep` (0.60+), so silence at FLOW is CORRECT — not breakage.
    Auto-checkpoint at 0.60+ and auto-consolidate at 0.40+ are both wired.
  - **Intent half: works when iCPG has intents for the file**, silent otherwise. The
    one-file-in-many firing observed is expected behaviour, not a defect.
- **THE REAL GAP, and it is F-001's confound verbatim: nothing watched `icpg`.** The intent half
  shells out to `icpg`, which resolves through a NAME on a mutable PATH exactly as mnemos did —
  and **no watcher predicate mentioned icpg at all**. If it broke, that half would vanish and the
  hook would read as *"this file has no intents"* rather than *"the tool is gone"*. **Empty would
  have meant unreachable and we would have read it as unused** — the precise error that confounded
  the whole Mnemos trial. Fixed by extending **P9** (whose stated invariant is already *"does the
  interpreter the CONSUMER resolves have what it imports?"* — mnemos was simply the only consumer
  ever checked). Declare-then-check: only a repo with `.icpg/reason.db` can be missing it.
- **THE MEASUREMENT ERROR — mine, made while auditing for exactly this.** I counted
  `grep -c degraded` per hook, found 5 of 16 reporting, and read it as a spec-11 coverage hole.
  **Wrong: that counts an ARTIFACT, not the property.** The property is *"is the failure reported
  within one session by anything?"*, and coverage is DISTRIBUTED across mechanisms:
  - toolchain unreachable → **P9** at SessionStart
  - hook never ran at all → the `settings.json` trailing `tessera-degraded` branch (16/17 commands)
  - `tessera-verify-scan` → covered by something *stronger*, `exit 2` + stderr, which is why
    `report_settings.needs_reporting()` correctly skips it (its `_TRAILING_EXIT` wants `; exit 0`)
  Three separate "missing coverage" findings collapsed on inspection. **Standing pattern #3 aimed
  at the auditor: I named the artifact that correlates with the pain instead of the pain.** The
  honest open question is narrower and still real — *is any bail-out covered by NOTHING?* — and it
  needs per-hook reading to separate "nothing to do" from "could not run", not a grep.
- **When to revisit:** when the per-bail-out audit runs (handoff item 5b). Do not re-open it with
  a count.

### Mnemos: we never broke it — we inherited it half-wired, and the half we ADDED is the half producing data *(2026-07-26)*

- **AMENDED 2026-07-27: "zero in `scripts/mnemos/`" is no longer true.** A fifth Mnemos defect
  landed, and unlike the first four it is **not** an integration failure — it is inside
  `auto_nodes.py`, one of the seven files this entry lists as UNCHANGED since the Maggy import.
  `detect_git_commit` recovered the commit message by regexing the Bash **command text**, which
  cannot work: the shell has already expanded and consumed the quoting before a PostToolUse hook
  sees anything. On this repo's own commit forms it yielded `'$(cat <<'`, `'$MSG'`, and `None`.
  Those became ResultNodes → the checkpoint's "Progress So Far" → what a session resumes from.
  **The headline claim of this entry survives and should not be softened: we still never broke
  it.** This defect is inherited, not introduced. What changes is the sharper claim built on top
  of it — *"all four failures were INTEGRATION, zero in `scripts/mnemos/`"* — which was true when
  written and is now wrong by one. **The core is not defect-free; it was UNEXAMINED**, which is a
  different thing and reads identically from the outside until something looks.
  And note what did the looking: **T2's first `insufficient` receipt**, one session after the
  instrument shipped with zero data. The entry above argues Mnemos "IS producing"; the receipt
  is the first evidence that its *output* was being read closely enough to fault.

- **Status:** OPEN, but the framing is corrected. Prompted by the fair question: *the machinery has
  been broken every time we look, so the trial has never had an honest run — what did Tessera do to
  Maggy's Mnemos that made it useless?*
- **Answer, from diffing our own history against the Maggy import (`ad19913`): nothing.**
  ```
  ad19913..HEAD -- scripts/mnemos/   →  1320 insertions, 41 deletions
  UNCHANGED: checkpoint.py  fatigue.py  signals.py  consolidation.py
             models.py      redact.py   auto_nodes.py
  ```
  The memory core is untouched. Every line we added is the **analysis** layer —
  `correction_detect.py`, `divergence.py`, `eval_correction.py`, haziness bands, and the five
  self-checks. We did not break Mnemos; we bolted analysis onto it and never touched the engine.
- **Maggy shipped it half-wired, and said otherwise.** A file named mnemos-compact-recovery.sh
  exists under templates/ **at commit `ad19913`** (written without backticks: it is a path in
  history, not on disk today, and doccheck rightly reads a backticked path as a current claim), Maggy's own CHANGELOG calls it *"the PRIMARY re-injection point"*, and
  `mnemos-post-compact-inject.sh` defers to it in a comment — **but no hook entry in Maggy's
  `settings.json` references it.** Its primary recovery path was never wired, in Maggy.
  Tessera inherited the file and the claim, then deleted the file (`0255cf0`, "drop phantom
  compact-recovery") — correct — but recorded the reason wrongly.
- **CORRECTION to the mnemos skill and design-principles.** Both say that script *"never existed"* (2026-07-09). **False.** It existed at import, unwired, and was deleted later.
  The *substance* of that 07-09 correction holds — it never ran, Layer 2's job is done by the
  unmatched `mnemos-session-start.sh` — but "never existed" is not what happened, and the true
  version matters more: **the gap is inherited, not introduced.**
- **What every Mnemos failure has actually been: integration, not Mnemos.** F-001's interpreter,
  the dead Stop-hook ingest, the PreToolUse bare-stdout channel, and today's two-tier hook
  silence. Four failures, zero of them in `scripts/mnemos/`. That is why the trial has never had
  an honest run, and it is why "it never fired, so kill it" was never a sound inference.
- **UPDATE 2026-07-26 (later same day) — the "zero in `scripts/mnemos/`" tally is now WRONG, and
  `checkpoint.py` is no longer UNCHANGED.** A real `/compact` was run as the trial's first
  observation through a working channel. It found a fifth failure, and this one IS in the engine:
  `checkpoint.py` joined **every** active GoalNode unbounded. Goals are never-evict AND
  `store.extract_session_goals` mints one per ingested session, so the field grew to **98 nodes /
  11,119 chars — 60% of an 18.2KB checkpoint**, which overflowed the SessionStart output limit.
  The harness spilled the block to a file and delivered a 2KB preview: the model got the goal blob
  and **not** Constraints, Progress, Key Files, or Git State. **The restore blob outgrew its own
  delivery channel** — standing pattern #9, one layer deeper than "did it run": it ran, it
  reached, and the payload still didn't arrive. Capped to the 8 most recent (11,119 → 872 chars,
  −92%), render only, nodes retained per ADR-0007, omitted count stated not silently dropped.
  Guarded by `scripts/mnemos/test_checkpoint_goal_cap.py`.
  - The subtle half: **all 98 goals carry `activation_weight` 1.0**, so the store's
    `ORDER BY activation_weight DESC` is a no-op and a naive head-slice keeps arbitrary rows —
    it dropped the live goal and kept `what is sqlfluffy`. The cap sorts by recency; the test
    asserts that specifically, and was falsified against both the uncapped and naive-cap versions
    before being trusted.
  - **This does not overturn the entry's thesis, it sharpens it.** The defect is still *inherited*
    — the unbounded join is Maggy's line, untouched since `ad19913`. What changed is that it took
    ~2 months of accumulated GoalNodes to cross the limit, so it was invisible at import and
    arrived by TIME, not by an edit. **A latent bug in code nobody touched is still a bug in the
    engine.** "We never touched it" was true and was never the same claim as "it is sound."
- **Same observation, sixth failure, and the one with fleet blast radius: the GLOBAL hook tier was
  badly stale.** `~/.claude/templates/` — which every project on the default `hook_distro: global`
  actually executes (ADR-0004) — held **7 stale hooks and was missing `tessera-decision-surface.sh`
  entirely**. All three PreToolUse hooks had **zero** `additionalContext`: the 07-24 channel fix
  never propagated, so for the whole fleet Layer 3, the fatigue/intent injection, and the decision
  surface were emitting to the debug log or absent. `./install.sh` is the only propagation and it
  is manual, so a fix landing in `.claude/scripts/` reaches nobody until someone remembers.
  Resolved by running it (17/17 now byte-identical). Standing pattern #5, violated by time
  rather than by a missing `cp`.
  - **DETECTOR SHIPPED same day — `tessera-watch` P14 (`p14_global_tier_drift`).** Three tiers
    carry these hooks: `.claude/scripts/` (framework truth) → `templates/` (install payload,
    guarded by P1 + doccheck's commit-blocking `hooks-match-templates`) → `~/.claude/templates/`
    (**what downstream actually runs**). Only the last edge was unguarded, and it is the one
    that matters at runtime. P14 byte-diffs it, reports MISSING and STALE separately, and is
    gated on `~/.claude/.bootstrap-dir` naming this repo — silent when another checkout owns
    the tier, rather than ordering it to overwrite someone else's install.
  - **The finding underneath, which is the durable one: P4 said "all in sync" the entire time,
    and was right by its own definition.** P4 compares downstream local copies *against*
    `~/.claude/templates/` — so it validates against the tier that was stale. **Uniform
    staleness reads as agreement.** Standing pattern #1 aimed at a checker: the thing that
    would tell you the fleet is behind was measuring against the thing that was behind. P4 also
    globs `mnemos-*.sh` only, so a missing `tessera-decision-surface.sh` was invisible to it
    twice over. P4's docstring now says this out loud, and green there still does not mean
    "downstream is current" — only P14 can say that.
    **Generalisation worth carrying: when a checker takes a reference, ask what validates the
    reference.** Three tiers meant two edges, and the unguarded one was the runtime edge.
- **It IS producing, and this is the part the kill/keep framing kept missing:**
  ```
  Active nodes 630 · total 645 · checkpoints 517 · goal 98 / constraint 53 / result 479
  haziness scored across 8+ ingested sessions, with a dominant dimension per session
  ```
  The **session-continuity** half is demonstrably alive. Only the **compaction-recovery** half is
  untested — and P3 now says out loud that its bar may be unreachable on this harness.
- **TWO NEW DEFECTS, both found by pointing the instrument at a session with ground truth:**
  1. **`mnemos haze --session <bad-id>` fails OPEN to the best possible score.** A nonexistent or
     *truncated* id returns `0.00 CLEAR (0 turns)` instead of an error — and the short form is the
     natural thing to type, since every other view prints the 8-char prefix. Live proof: this
     session reads `0.00 CLEAR (0 turns)` by prefix and `0.01 CLEAR (1280 turns)` by full uuid.
     A silent best-score for a typo is the fail-open class inside the measurement tool.
  2. **Haziness scored a demonstrably rough session as `clear`.** This session ran 1280 turns in
     which the agent asserted five confident, wrong things (iCPG's missing verb, the dedup root
     cause, a half-mirrored regex, ADR-0008's cut, the two-tier exclusion) and was corrected on
     every one. Composite **0.01**, band **clear**, `correction_density` 0.029. Whatever roughness
     is, this session had it and the metric did not see it. The likely reason is structural: the
     five dimensions detect *errors and rework* (redo, first-try errors, orphaned calls,
     backtracking) — all near zero here, because the work landed cleanly. What actually went wrong
     was **confidently-wrong-then-corrected**, which leaves no error trace at all. That is a
     calibration finding with a rare gift attached: a session whose ground truth we know exactly.
- **When to revisit:** before any Mnemos kill/keep verdict. Judging it now would measure four
  integration bugs and a metric that cannot see the failure mode this repo actually exhibits.

- **WHY the metric can't see it — measured 2026-07-26, and it is NOT the composite weighting.**
  The suspicion was that `correction_type` already carried the signal and simply wasn't weighted
  in (the skill calls typing "a diagnostic view, NOT a sixth dimension"). It doesn't. The gap is
  one layer earlier, in **detection recall**:
  ```
  this session: 408 user turns · correction_match = 1 · correction_type = 0
  ground truth: at least 5 confident-wrong-then-corrected episodes
  classifier_status = "ran"  (so this is not the dead-pipe failure again)
  ```
  **The detector found 1 of 5+.** Typing produced 0 because there was almost nothing to type.
  Weighting a signal that is 80% missing would not have helped.
- **The reason is register, and it is a real corpus property.** The corrections in this session
  arrived as *questions and challenges*, not as declarations:
  > *"I'm not sure I'm following what doing 3 gets us… or am I missing your point?"*
  > *"so you are prompting me to delete tessera's code-review skill is that right?"*
  > *"those are steps towards portability potentially that we're excising"*

  Every one of those reversed the agent's course. None contains the declarative correction
  language ("no", "that's wrong", "actually") a keyword regex is tuned for, and the recall-first
  qwen pass over regex-missed turns did not catch them either. **This user corrects
  interrogatively.** A detector tuned for the declarative register will keep reading a session
  full of successful course-corrections as `clear`.
- **Consequence for the "can Tessera self-evaluate?" thread.** Haziness is the closest thing here
  to a self-evaluation instrument, and it measures *did the tools error* — redo ratio, first-try
  errors, orphaned calls, backtracking — all near zero this session, because every wrong turn was
  caught and the work then landed cleanly. It does not measure *was the reasoning wrong*. Those
  two came fully apart: tools clean, reasoning wrong five times. **Fixing detection recall for
  interrogative corrections is the single highest-value change available to that thread**, and
  there is now a labelled session to evaluate against (`scripts/mnemos/eval_correction.py` is the
  existing silver-label harness; P10's adjudication requires any detector change to re-run it and
  re-open bands/weights on the new numbers).

### T2 downstream — the instrument shipped 2026-07-29 with ZERO data, and reading it early is the failure it exists to correct

- **Status:** Watching. **No verdict is available and none will be for weeks.** That is the entry.
- **Source:** A read of downstream event logs, prompted by "a couple projects have been run a bit,
  what does that tell us?" — not by anything the framework reported.

**What was found.** `restore_offered` was **0 across 34 downstream sessions in 6 projects**. Of
those, **26 were substantive** (`scan.py`'s own `is_substantive`: ≥1 edit or ≥20 turns) and would
each have owed a receipt. `scripts/restore/` was never added to `bin/tessera-new-project`, so the
SessionStart probe of `$PWD/scripts/restore/offer.py` resolved nowhere and the `for` loop ended
with no `else`. The hook was always correct — verified by dropping the modules into a scaffolded
project, where `restore_offered` appeared immediately. Only the directory was missing.

**Why it mattered more than a missing file.** `active.md`'s own handoff already records that
tessera's receipts are biased: *"orientation came from THIS FILE and the standing-patterns block,
not from the checkpoint… A downstream app has no such file. Do not read tessera receipts as a
general verdict on Mnemos."* T2 is the only question ADR-0015 says can produce a verdict on the
recovery half, and it could only ever be answered in the one venue the repo itself disqualifies.

**Fixed (2026-07-29):** the 4 modules + the Stop hook ship from the scaffold; all six live
downstreams back-filled via `tessera-sync-harness`; the fall-through now emits
`degraded/restore-offer/offer-missing` instead of nothing. Guarded by
`scripts/test_new_project_restore_receipt.py`, every assertion of which was run against the
re-planted defect (standing pattern #10).

#### What we are watching for, and what each finding means

Four signals, deliberately separated — three of them are findings about the *instrument*, and only
the third is evidence about *Mnemos*. Conflating them is how P3 spent 37 days.

1. **Answer rate — offers vs. receipts on substantive sessions.** Offers accruing with no receipts
   means the ask is not landing: the Stop hook is unwired, or the model is skipping it.
   → **An instrument fault. Fix the ask. It says nothing about restore quality.**
2. **The reflex signature — uniformly `sufficient` with thin, generic `--used` text.** The contract
   already reasons that an unconditional demand makes `--sufficient` a reflex, "which rebuilds the
   bug one level up"; that logic was applied to *frequency* and applies equally to *venue*.
   → **Do NOT read those sufficients as evidence.** The finding is that the ask has become
   routine, and the response is to make it rarer or reframe it — not to trust the answers.
3. **Which field `insufficient` names — this is the payload.** tessera's receipts have named
   `progress` (a corrupted extractor, since fixed) and `goal` (the goal blob, still shaped wrong).
   → If downstream names **different** fields, the selection bias is real and measured, which is
   the entire reason this shipped. If it names the **same** fields, that is convergent evidence
   the defect is in `write_checkpoint` and not in the venue — a *stronger* result, not a null one.
4. **The instrument going quiet after a fix.** Already flagged in `active.md` for `progress`; it
   can now be watched across 7 venues instead of 1. → A finding → fix → quiet loop closing would
   be the first this repo has completed end to end.

An immediate n=6 observation, from back-filling alone: **three of six downstream checkpoints carry
no `active_constraints`** (howler, heaviside, arbiter) and tess-dashboard's carries only `goal`.
Not yet a finding — `fields` lists only truthy values, so this may be honest emptiness. It is the
first thing this instrument has ever said about a downstream project.

#### THE STOPPING RULE — binding, and it binds against reading EARLY

This repo's recurring error is a verdict formed on an instrument that has not run: P3 counted 3
compactions and called the mechanism untested for 37 days; `usage` was re-scoped three times and
decided zero. **Shipping an instrument and interrogating it immediately is that same error wearing
new clothes**, and it is the specific risk here because the fix is fresh and the temptation is to
check whether it "worked."

- **Do not read this for a verdict in the next session, or the one after.** Confirming the
  plumbing (an offer appears, a receipt can be filed) is fine and is *not* a reading.
- **The bar: ≥10 downstream receipts across ≥3 distinct projects.** Three because two cannot
  separate a venue effect from one project's bad checkpoint.
- **tessera's own receipts do not count toward it.** That is the whole point.
- **If 30 days pass with <10 receipts, the finding is about the RATE, not about Mnemos** — read
  signal 1, and do not substitute the thin data for the absent data.
- **No re-scope.** If the first honest read is inconclusive, the answer is more sessions or an
  explicit retirement of T2 — not a fourth framing of the question. A dimension that has consumed
  three investigation cycles without producing a signal has had a fair hearing (ADR-0017's rule,
  applied here in advance rather than after the fact).

**Trigger: WIRED as `tessera-watch` P16 (2026-07-29, same day).** Counts `restore_receipt` across
the downstream `.tessera/logs/`; fires at ≥10 across ≥3 projects, or at 30 days with fewer.
Anchored on a dated constant (`T2_SHIPPED`) rather than on the receipts, because the 30-day arm is
load-bearing exactly when there are zero receipts to derive an anchor from. Tessera's own are
excluded for free — `_downstream_projects()` already drops root.

It was briefly left as prose here, which was wrong for the reason this entry itself gives: an
un-evaluated trigger depends on someone re-reading the file. **It counts receipts and never reads
them** — no sufficient/insufficient tally, no score. "Is it time to read" is mechanical; "what do
they say" stays a human's, or P16 becomes proxy predicate #4. Both fire messages are green lights,
and the 30-day one names *the rate* as the finding, in those words, so thin data cannot be
mistaken for a verdict on Mnemos.

### Prompt caching: the fleet reads at 0% because nothing opts in — and the knowledge to prevent that already existed *(2026-07-30)*

- **Status:** Watching → **arbiter half ANSWERED 2026-07-30, measured** (see VERDICT below); the
  fleet audit below is settled in its **verdicts** (one method gap found and closed since — see the
  blind-spot note). Still open: quarry's restructure question, and
  whether a line goes into the downstream CLAUDE.md template.
- **Source:** "the cache is being used very little" — read off the platform console by a human, not
  reported by anything. Standing pattern #1's shape, one rung out: there was no instrument to be
  broken, because nobody built one.

**What was found.** `cache_control` count is **zero across every call site in the fleet** — 7 files
in 5 repos (`arbiter/src/arbiter/client.py` ×3 call sites, conclave's `ensemble.py` /
`selfmoa_judge.py` / `judge_eval.py`, maggy's `ai_client.py`, `quarry/apps/api/src/llm/index.ts`,
`lorenzo-portfolio/api/chat.js`). Caching is **opt-in** — a request-body parameter, per call site.
There is no environment variable, proxy setting, client default, or config file that turns it on.
So the console's near-zero read rate is not a misconfiguration; it is the accurate reading of a
fleet that never asked.

**The uniformity is the finding, not the misses.** Five independent codebases in two languages, all
shipping uncached, while a complete and accurate `shared/prompt-caching.md` sits in the bundled
`claude-api` skill — the source of every number in this entry. Whatever the availability timeline
was in each case, that is not five oversights. **Read-time knowledge did not reach write-time.**
Standing pattern #6 in another organ: knowledge that nothing checks is not load-bearing.

#### The triage — and the point is that it differed every time

| Repo | Verdict | Why |
|---|---|---|
| **arbiter** | **Candidate — marker only** | `reviewer.SYSTEM` (3,304 chars) + its `TOOL` schema (995) + shared `TOOLS`, byte-identical for every file; diff already last via `_user_message()`. `claude-sonnet-4-6` → 1024-token minimum, ~1.5k estimated (chars/4, unverified — `count_tokens` is the measurement). |
| **quarry** | Candidate **after restructure** | `callJSON` has **no `system` block at all** — model, max_tokens, temperature, one user message. The constant preamble is concatenated into that string. Making it cacheable is a design change to working code, justified only by call volume. Not a marker. |
| **conclave** | **Non-candidate by design** | Reaches `api.anthropic.com` — but via the **OpenAI-compatible endpoint** (`ensemble.py:269` asserts `/v1/chat/completions`). `cache_control` is a Messages-API *content-block* field with no slot in the OpenAI request shape, and `ensemble.py:63` names provider-agnosticism as the point: *"That is the seam."* |
| **maggy** | Out of scope | Not a downstream — the ancestor tessera partially forked from. |
| **howler, heaviside, tess-dashboard** | No surface | Zero API call sites. tess-dashboard's single `claude-opus-4-8` hit is fixture data in `src/App.test.tsx`; it renders a model string read from Tessera's logs. |

**One candidate out of five examined.** Which is the result — a uniform "add caching everywhere"
would have produced one no-op, one wrong refactor, and one violated seam.

**The audit's own method had the blind spot this repo already records about arbiter** (found
2026-07-30, same day, re-scanning on the question "anything for tessera?"). The fleet grep filtered
on `*.py`/`*.ts`/`*.js`/`*.sh`, and tessera's `bin/` is **21 extensionless files** — exactly the
class handoff item 2 says arbiter's default `--ext` set cannot see. An unfiltered re-scan found one
missed call site, `bin/deepseek`, and it closes as a non-candidate on shape (no `system` block, no
tools, one user message per one-shot process — no shared prefix exists), so the conclusion stands.
**The conclusion survived; the method did not.** A filter that a repo has already written down as a
known blind spot should not be re-applied by the next person auditing — including when that person
is the one who read the warning that morning.

#### A method correction, recorded because it is the transferable half

conclave was first called a non-candidate because it "uses in-fleet Gemma." **That was wrong.** It
does hit `api.anthropic.com`; it just does so through a schema with nowhere to put the marker. The
first read came from a grep pattern matching the *file*; the correct read came from opening the
call and following the endpoint. Same verdict, different reason — and the wrong reason would have
been recorded as fact if the repo had not been opened before dispatching a session at it.
**A pattern match tells you a file mentions something. It does not tell you the call's shape.**

#### Facts worth not re-deriving

- **The cacheable-prefix minimum is model-specific and NOT monotonic across generations.** 512
  tokens on Opus 5 · 1024 on Opus 4.8, Sonnet 5, Sonnet 4.6 · 2048 on Opus 4.7 · **4096 on Opus 4.6
  and Haiku 4.5**. Below the line: no error, `cache_creation_input_tokens: 0`, silently nothing.
  This is why `lorenzo-portfolio` (Haiku 4.5, one short `SYSTEM_PROMPT`) would accept the marker and
  cache nothing — the most dangerous shape, because it reads as done.
- **`input_tokens` is the UNCACHED REMAINDER, not the prompt size.** Real size is
  `input_tokens + cache_creation_input_tokens + cache_read_input_tokens`. A meter summing only
  input+output silently under-reports after caching lands, and its cost estimate drops for the
  wrong reason. **arbiter's `_record()` (`client.py:46`) does exactly this** — so today it cannot
  report a hit rate in either direction. Standing pattern #1, pre-registered: the fix and the
  instrument that would show it worked must land together, meter first.
- **Invalidation is tiered.** Tool-definition changes (including *reordering*) and model switches
  invalidate all three tiers; system-prompt content spares tools; `tool_choice` and toggling
  thinking spare tools+system. Effort changes are model-switch-grade — measured here 2026-07-27,
  see the entry above.
- **Silent non-caching, distinct from invalidation:** the 20-block lookback (a breakpoint searches
  back at most 20 content blocks — agentic turns exceeding that miss); concurrent identical-prefix
  requests all miss, since an entry is readable only once the first response begins streaming; and
  a breakpoint at the end of the *whole* prompt when the shared part is the *prefix* writes a
  distinct entry per request that is never read.
- **Two escape hatches for the expensive rows.** A mid-conversation system-prompt change can ride a
  `{"role": "system"}` message inside `messages[]` instead of editing top-level `system` — available
  today, no beta header. Mid-conversation tool changes have a beta on Opus 5. Model switch has none.

#### What is deferred, and why

A line in `templates/tessera/CLAUDE.md.template` was proposed and **held, not rejected**. The
scaffold surface is real — `bin/tessera-new-project` copies that template — but the correct action
differed in every repo examined (marker / restructure / not applicable / not ours), and a template
line cannot carry that. It would end up saying some version of *"consider prompt caching,"* which is
the knowledge layer, and the knowledge layer is precisely what is already demonstrated not to work.

The one sentence that **is** uniform, unconditional, and a check rather than a reminder:

> If this project meters its own LLM cost, it must record `cache_creation_input_tokens` and
> `cache_read_input_tokens` alongside `input_tokens` — `input_tokens` is the uncached remainder,
> not the prompt size.

True whether or not caching applies, true on the compat endpoint, true before any restructure. If a
template line goes in, that is the line — **after** arbiter, so it points at something done once
rather than something hoped for. Same rule that keeps `tessera-new-project` free of an `--adopt`
flag: build it on the second instance, not the first.

**No trigger is wired, and that is a known weakness of this entry** — an un-evaluated trigger
depends on someone re-reading the file, which is the failure the T2 entry above names in its own
words. The candidate predicate, if this earns one: *does a downstream with Messages-API call sites
record the cache usage fields* — mechanical, conditional (no false positive on the five repos with
no API surface), and it measures the property rather than counting occurrences of `cache_control`,
which would false-positive on every correctly-uncached one-shot call site. **Do not build it before
arbiter produces a number.** Until then the revisit condition lives in the handoff.

#### VERDICT — arbiter, measured 2026-07-30 (`57a7683`, `46c42e3`, `4efca63` in that repo)

Caching works, and the meter shipped first and alone — deliberately, because `_record()` had been
summing `input_tokens`, the uncached *remainder*. Had the markers landed first, the reported cost
would have fallen while the token total silently under-reported by **exactly the amount caching
saved**: a fix whose own instrument would have confirmed it in the wrong units.

Control first, because a zero read is unattributable without one:

| request | input | cache_write | cache_read |
|---|---:|---:|---:|
| 1 | 332 | 1,822 | 0 |
| 2 | 332 | 0 | **1,822** |

End-to-end at `--jobs 1` (so the thread pool could not muddy it): 6 calls, 75,552 prompt tokens,
**50% served from cache, $0.17 against $0.238** at full input rate — **~29% off**. That figure is
arithmetically consistent rather than merely reported: half the tokens moving 1× → 0.1× saves ~45%
of input, less the ~12.5% write premium on the other half ≈ 32%, diluted to ~29% by output tokens.
**The counterfactual is computed, not re-run, and that is correct** — the pre-caching path differs
only in `cache_control` metadata, so a second paid run would re-derive a number already exact.

**THE PREFIX WAS NOT THE MONEY — THE TRANSCRIPT WAS.** System prompt 2,138 tokens; a five-turn
verified review measured **79,045**, of which **78% is re-sends** (turn one already carries diff +
before + after). Predicted before the run and confirmed by it, which is why the second breakpoint —
a *moving* marker on the newest transcript turn — carries the result and the system-block marker
alone would have bought little.

**The thing the dispatch prompt did not anticipate: the breakpoint cap interacts with loop depth.**
Max 4 breakpoints per request; the system block takes one. Marking *per turn* would sit exactly on
the cap at `MAX_VERIFY_TURNS = 4` and **break silently the first time anyone raised it**. One moving
marker instead. Any future guidance must say this — a per-turn rule is the obvious implementation
and it is a latent fail-open keyed to a constant nobody would think to check.

**The sharpest finding, and it is a near-miss not a success: `triage` is NOT A CANDIDATE by seven
tokens.** Its prefix measures **1,017** tokens for the reviewer voice and **1,024** for the arbiter
voice, against `claude-sonnet-4-6`'s 1,024 minimum — one below the floor, one exactly on it. A
marker there caches nothing half the time and flips on any wording edit, while reporting success.
Same family as this repo's recurring fail-open defect: *not a wrong answer, a confident claim about
work that never happened.* Left unmarked; `cache_prefix` is opt-in on `call_tool` with the numbers
recorded at the call site. (Whether the 1,024 floor is inclusive is undocumented — immaterial, since
a prefix sitting *on* it is one edit from silence either way.)

**Why that near-miss is survivable, and it is the transferable result.** Every cached prefix in
arbiter is now a **load-bearing length** — trimming thirty tokens from `reviewer.SYSTEM` would drop
it under the floor exactly as `triage` already is, and nothing static would catch that. But
`usage()` prints `hit_rate` to stderr on **every run** (`cli.py:284`), so the collapse surfaces
unprompted on the next invocation. **The meter, built first for cost accounting, turns out to be the
regression detector for the mechanism's most likely failure mode.** That ordering — meter before
marker — is worth more than the 29%.

- **Still open:** quarry (candidate only after hoisting its constant preamble into a `system` block;
  justified by call volume, which is a question about quarry, not about caching).
- **Template line — RECOMMENDED, NOT YET EXECUTED (a scaffold change is the human's call; see the
  handoff). Ship the meter half, hold the rest.** *"If this project meters its own LLM cost,
  it must record `cache_creation_input_tokens` and `cache_read_input_tokens` alongside
  `input_tokens`."* One instance now demonstrates that ordering mattered, and the line is
  unconditional — true whether caching applies, on the compat endpoint, and before any restructure —
  so it does not encode arbiter's shape. Guidance on *where to place markers* stays held: one
  observed shape is not enough, and the breakpoint-cap trap above shows how repo-specific that
  guidance gets.
- **Predicate — DO NOT BUILD, and the reason changed.** The proposed check was *does a downstream
  with Messages-API call sites record the cache usage fields*. Arbiter shows the property is
  **runtime, not static**: a prefix that falls under the floor is invisible to any source scan and
  obvious to `hit_rate` on the next run. The meter already is the check. A static predicate would be
  proxy predicate #4.
- **Revisit when:** quarry's call volume is known, or a second repo is done and the two shapes can
  be compared — that is the point at which placement guidance is worth writing down.

### The eager prefix is ~15.6k tokens — and the size of it is NOT the argument *(2026-07-30)*

- **Status:** Watching. Recorded so the measurement is not lost; **explicitly not proposed as a
  trim.** Half of the case that produced this entry does not survive scrutiny, and the note exists
  partly to stop that half being picked up later as if it did.
- **Source:** Asked, while closing out the caching work, whether there was prompt-caching work to do
  *for sessions on Tessera itself*. There is not — Claude Code owns `cache_control` in its own
  sessions, so there is no marker to place. The measurement fell out sideways.

**Measured 2026-07-30, per session, before any work happens:** `CLAUDE.md` ~6,950 tok ·
`.claude/skills/mnemos` ~4,390 · `.claude/skills/base` ~1,470 · the SessionStart surfacer (handoff +
standing patterns) ~2,790 — **~15,600 tokens**, plus the Mnemos checkpoint (~2,600) for ~18k in
practice. (Estimated at chars/4; `count_tokens` if a decision ever rests on it.)

**METERED 2026-08-10: 15,837 tokens tracked** *(was 15,497 on 08-09)* — recomputed by
`scripts/prefix_meter.py`, which doccheck's `eager-prefix-figure-is-current` asserts this figure
against within 5%. **Re-metered because `CLAUDE.md` changed three times that day, not because a
check demanded it** — the 5% band absorbed the drift and stayed green, and CLAUDE.md's own rule is
to re-run the meter on any change to it. A green tolerance does not discharge that; if it did, the
figure would rot inside the band exactly as the frozen prose did. `CLAUDE.md` 7,307 → **7,647**
(+340: the stdlib-only clarification, the sibling-import note, and the doccheck-isolation clause),
every other tracked component unchanged. It is now **48%** of the prefix and still the only
component that grows. **The figure
above was a one-shot number frozen in prose, and that is the class of claim this repo keeps paying
for** — ADR-0021's adopted pattern, taken from Deep Agents, which tracks its base input tokens as a
defined per-release metric rather than a paragraph. Composition today: `CLAUDE.md` 7,307 ·
`.claude/skills/mnemos` 4,354 · standing patterns as *emitted* 2,382 · `.claude/skills/base` 1,454;
plus, measured but **never asserted**, the handoff surfacer 265 (varies with fired triggers) and the
checkpoint 1,822 (machine-local) — 17,584 in practice.

**The comparable total is 15,762 against 15,600, and the flatness is the result.** Ten days, a
standing-patterns split and repeated `CLAUDE.md` growth, and the prefix has moved ~1%: `CLAUDE.md`
+357, the surfacer −143. So the meter's first act is to *confirm* this entry rather than overturn
it. Three cautions on reading it. **The bases differ** — 15,497 is tracked-only and excludes the
handoff surfacer, so it is 15,762 that compares to 15,600; quoting the smaller number against the
older one would manufacture a decline. **A flat total is not a flat composition**: `CLAUDE.md` now
carries 47% of the prefix and is the only component that grows, while the two skills have only
shrunk. And **141 of `CLAUDE.md`'s +357 is the line documenting the meter itself** — the instrument
grew what it measures, which is small here and would not stay small if every future check bought
its own paragraph in the highest-value context position in the repo.

**The meter reports drift and has NO opinion on whether the figure should be smaller** — the
argument below is unchanged by it, and a threshold here would be principle #3's error aimed at the
eager load.

**RESOLVED 2026-08-09, and the resolution corrects this entry's first version — kept, because the
error is the instructive part.** `bin/tessera-verify` and then arbiter both flagged that
`prefix_meter.canonical_path` prefers the literal path, so a **real** `.claude/skills` directory
would be measured stale and a doc naming a deleted skill would go green. This entry first recorded
it as an unresolvable tension between two consumers wanting opposite things — the meter wanting what
*actually loads*, `referenced-paths-exist` wanting the *tracked source* — and attributed the
divergence to `tessera-sync-skills` under ADR-0010.

**Three things about that were wrong.**

1. **The attribution.** `tessera-sync-skills` owns `~/.claude/skills` — the **global** mirror, a real
   copy, which is what ADR-0010 is about. The project-local `.claude/skills` is a different object:
   a hand-made symlink from 2026-06-24, gitignored, that **nothing created, nothing recreated, and
   nothing checked**. `install.sh` never touched it. It had no owner at all.
2. **The tension was not a tension.** When the path is a symlink, literal and canonical resolution
   are **the same file** and no consumer can disagree. They diverge only in a state nothing should
   ever create. So the fix is not to pick a side in the resolver — it is to assert the SHAPE
   (`doccheck` → `mirror-links-are-symlinks`) and make the divergent state *unrepresentable* rather
   than detectable. That is strictly stronger, and it needs no definition of "diverged".
3. **"Found independently twice" was weaker evidence than it was given.** Two reviewers reading the
   same code and noting the same branch is **one finding twice, not corroboration** — correlated,
   not independent. What actually settled it was reading `install.sh` and finding that neither
   reviewer's implied premise held.

**The finding underneath, which neither reviewer reached:** `CLAUDE.md` eagerly `@`-imports
`.claude/skills/{base,mnemos}/SKILL.md`. On a clone without those symlinks — the state of *every*
fresh clone — the imports resolve to nothing and ~5,800 tokens of eagerly-loaded skills do not load.

**MEASURED 2026-08-09, not inferred** — a fixture with four import forms and a unique canary in
each, read back by a nested `claude -p` session. Anchored (`@./present.md`), **inline**
(`see @./present2.md for the reasoning.`) and **through a symlink** all load their content; the
absent one loads nothing. Two consequences worth keeping:
- **The inline form loads**, which is what makes the widened `EAGER_IMPORT` regex in
  `scripts/prefix_meter.py` correct. That was fixed on inference after `bin/tessera-verify` found
  it; it is now measured.
- **The literal `@path` line survives into context in EVERY case, resolved or not.** So its
  presence carries no information — from inside a session you cannot distinguish a live import from
  a dead one by reading `CLAUDE.md`; you would have to already know what content should have
  arrived. *That* is what makes the failure undetectable in-session, and it is a stronger statement
  than "silent": there is a visible artifact, and it looks identical in both states. Now owned: `install.sh` creates the three links idempotently and
its `verify()` asserts them (machine state), while doccheck asserts the shape and treats absence as
green (repo state, and it runs in pre-commit). Same split the doc-claims contract already draws —
existence is a local fact, the shared one is what gets asserted. **Framework-only, deliberately:
downstream projects receive skills through the global union (ADR-0009) and have no `skills/` to
point at; none of the six has these symlinks and none should.**

**Caching makes that CHEAP, not FREE, and the distinction is the point.** A large, stable, turn-to-turn-
identical prefix is the *ideal* caching case — written once at 1.25×, read at 0.1× thereafter. So
cost is not an argument against it. **Attention still is**, and someone reasoning "caching is on,
therefore prefix size is free" would be drawing the wrong conclusion from the right fact.

**Why this is NOT yet an action, stated so the next reader does not skip the step.** Token count is
an *artifact*; the pain would be a miss attributable to dilution, which is unmeasured. Proposing a
cut on size alone is principle #3's failure aimed at the eager load — and this repo has retired
three predicates for measuring a stand-in. **ADR-0008's cut was structural, not dimensional:** it
removed content with *no surface in this repo* (OWASP web patterns, no web server). "It is large" is
a different claim and a weaker one. Note also the proposer's bias — the agent is the consumer of
this context, so an agent arguing there is too much of it is arguing about its own working
conditions without evidence of cost. The session that produced this entry is mild counter-evidence:
the standing-patterns block and the decision-surface hook both fired usefully, and the Mnemos trial
background is what made that session's restore receipt specific rather than generic.

**The one part that IS structural, and the only part worth acting on.** `.claude/skills/mnemos/SKILL.md`
carries the **P3 compaction-trial narrative that ADR-0015 superseded**, including an explicitly
retained *"original 07-15 reading, kept for the trail."* That is archival history occupying the
highest-value context position in every session — ADR-0008's criterion exactly, not a size
complaint.

**Corrected within the hour, and the correction is the instructive part.** This entry first said the
narrative should be *relocated here, its natural destination*. It already **is** here: the
compaction question is `docs/observatory.md` → "Mnemos compaction vehicle" (and the trial mystery it
explains is the PreToolUse-stdout entry), and the re-scope is ADR-0015. So the `SKILL.md` copy is a
**third** copy, not a homeless one, and "relocate" was the wrong verb chosen without checking the
destination. The actual next step is a **read-and-compare**: establish what in the SKILL.md text is
*not* already carried by ADR-0015 and the two entries, harvest only that, then cut. ADR-0007's rule
applied rather than cited — and a reminder that "harvest before you cut" also means *check whether
it was already harvested*.

- **A design constraint worth preserving, surfaced by the same measurement:** the PreToolUse hooks
  append via `hookSpecificOutput.additionalContext`, which lands *after* the cached prefix. Had they
  instead rewritten system-position content per tool call, every Edit would invalidate all ~15.6k.
  The 2026-07-24 fix that moved them off bare stdout was made for delivery reasons and is
  cache-correct by accident. **Nothing should ever inject varying content into a stable prefix
  position** — no timestamps, no session ids, no per-turn assembly ahead of the messages.
- **Revisit when:** a real miss is plausibly attributable to context dilution, or the next
  ADR-0008-style audit runs — at which point the Mnemos narrative relocation is the concrete item
  and the token total is context, not justification.

### Every conduct instrument counts the artifact, not the conduct *(2026-08-06, surfaced by the Agent Behavior eval)*

- **Status:** Watching. **Dated trigger, deliberately — not an open "Investigating".** Re-open when the ADR-0020 fixture work lands and produces a lucky-correct-negative result, or by **2026-10-05** regardless.
- **Source:** ADR-0020 (`docs/adr/0020-agent-behavior-evaluation.md`), §6. Agent Behavior was the mirror; this entry is the reflection, and it is about Tessera.

**The claim.** Tessera has a rule about proxies — principle #3, *name the pain, not the artifact that
correlates with it* — and its own conduct instruments are, without exception, artifact counters.
Measured in `.tessera/logs/` on 2026-08-06:

```
suggestion_gate  204 events / 36 sessions   fired 199 · held 5 (2.4%) · retro 34
spend_denied     124                        spend_authorized 1
restore_offered    9                        restore_receipt  6
degraded           2
```

- The **friction journal** is in practice a fired-counter: `held` is 2.4% of events. It records that
  a gate happened, never whether it was the right gate or a good one.
- **`tessera-gate-scan`** diffs a count of gate-shaped turns against a count of logged events. Two
  counts. It is a recall net by design and CLAUDE.md says so — but nothing sits behind it that
  measures the property.
- The **restore receipt** is a self-reported verdict. ADR-0015 split the offer from the receipt so
  neither party marks its own homework, which fixed *who reports*; the report is still a label, not
  a measurement of whether re-derivation actually occurred.
- The **`degraded` contract** carries an explicit warning not to audit coverage by counting
  `degraded` calls per hook — added because doing exactly that produced three wrong findings on
  2026-07-26. That warning is written as advice to one auditor. It is a property of the whole layer.

**The alternative, and where it came from.** Agent Behavior's calibration document judges the
*trajectory* against a written statement of the conduct, per **trigger occurrence**, with a fixture
matrix whose load-bearing case is the **lucky-correct negative** — outcome right, required process
skipped. Tessera has named that failure more than any other (Standing pattern #2) and has never had
a test shape for it.

**Why this is not already a decision.** No calibration data exists. Deciding to retire artifact
counting on the strength of an external README is ADR-0013's refused move, one organ over. The
sequencing is real: ADR-0020's adopted fixture work in `scripts/mnemos/eval_correction.py` is the
cheapest possible test of whether a judge can distinguish a lucky-correct negative at all, and a
conduct judge is worth nothing if it cannot.

**Two things to carry into that decision, both already known here:**
- **A conduct judge over Tessera's own transcripts is behavior-conditioned, not observational.**
  `CLAUDE.md` is eagerly loaded, so the agent was *given* the conventions. That answers a different
  question, and no number from it may be reported as if it were observational.
- **Fail-loud applies to the judge.** A trajectory judge returning `not applicable` for every
  trigger is indistinguishable from a compliant agent. Standing pattern #1, aimed at the instrument
  this entry proposes.

**Counter-argument, recorded so it is not lost:** counting is what a hook can do cheaply and
deterministically, and determinism is principle #17's whole point. An LLM judge is elective,
costly, and itself unverified. The honest framing is not *counters are wrong* — it is that the
counter was never chosen over the alternative, it was the only thing convenient, and no one has
looked since.

### 11 of the 12 standing patterns never reach the model — and the check guarding them is green *(2026-08-06)*

- **Status:** Investigating. **Reproducible in two commands; validate before acting.**
- **Source:** Found by accident, checking whether this session's own handoff edit had made the SessionStart spill worse. It had not — but the measurement exposed this.
- **Related:** the sibling entry below (same root cause: the harness's output cap). Different mechanism, different fix, so it is filed separately.

**The measurement:**

```bash
git show <pre-fix-sha>:.claude/scripts/tessera-watch-surface.sh > /tmp/old.sh; chmod +x /tmp/old.sh
/tmp/old.sh > /tmp/sf.txt
wc -c < /tmp/sf.txt                                    # 10,878  — over the 10,000 cap
grep -c '^[0-9]*\. \*\*' /tmp/sf.txt                   # 12  standing patterns emitted
head -c 2048 /tmp/sf.txt | grep -c '^[0-9]*\. \*\*'    # 1   survives the preview
```

Composition of that 10,878: **927** handoff pointer + **8,950** standing patterns + **~1,001**
observatory triggers.

> **A correction, recorded because the wrong number was load-bearing for an hour.** The first
> measurement of the patterns block read **9,951** and concluded it cleared the cap "by 49
> characters." That was wrong: the `awk '/^=== STANDING PATTERNS/{f=1} f'` used to isolate it runs
> to end-of-file, so it swept in the observatory block that follows. The block is **8,950**. The
> finding is unchanged — the *total* is what spills, and the 1-of-12 survival was measured
> directly, not derived — but any argument resting on "49 characters of headroom" was resting on a
> measurement artifact. The real margin against a 9,000-char budget is 50 characters, which
> happens to justify the same remedy for a different reason.

The harness caps hook output at 10,000 characters and hands the model a ~2KB preview past it. The
surfacer emitted 10,878. **One pattern arrives. Eleven do not.** This session's own SessionStart is
the proof: the injected block cut off mid-pattern-1, at *"a guard written for a bug and tested
against that same bug is"*.

> **THE SPILL WAS INTERMITTENT, NOT CONSTANT — refuted by `bin/tessera-verify`, 2026-08-06, and the
> correction makes the bug worse rather than smaller.** The claim above originally read "the
> surfacer emits 10,878 characters" as a flat fact. It is not flat. Checked out at HEAD with no
> observatory trigger firing, the same script emits **9,947 bytes / 9,880 characters — under the
> cap.** Decomposition: handoff 927 + patterns 8,950 + observatory **70**. In the run that was
> measured, the observatory section was ~1,001, because P3 and the G-a graduation were both red.
>
> So the standing patterns stopped arriving **exactly when the observatory had something to say** —
> the delivery of the cross-cutting lessons was silently coupled to how much else was wrong. A
> quiet repo delivered all 12; a repo with fired triggers delivered one. That is a worse failure
> than a constant one and it is undetectable by any single measurement, which is why a flat figure
> concealed it. **Do not restate the 10,878 without its condition.**

**Why this is the sharpest instance of Standing pattern #1 yet recorded** — and pattern #1 is the
one that got truncated:

`scripts/doccheck.py` → `check_standing_patterns_are_surfaced` asserted two things: that
`active.md`'s newest handoff contains a `### Standing patterns` block, and that
`tessera-watch-surface.sh` extracts it. **Both were true.** The check was green. Its docstring
stated the intent exactly:

> *"So the through-lines rode model recall — and a session re-derived a lesson the repo had already
> paid for eight times. A pointer would ride recall too; the block is printed verbatim."*

It is **not** printed verbatim. 92% of it is dropped one layer past where the check can see. The
mechanism built specifically to stop lessons riding model recall has, in practice, been delivering
one lesson and leaving eleven to model recall — and the check certifying it cannot observe the
channel it is certifying. *A check that verifies the sender and never the receiver.*

**Note what this does NOT imply.** The block has been growing since 2026-07-24; it is not knowably
"broken since then" — the truncation depends on total surfacer size, which varies with the handoff.
**When each pattern stopped arriving is unmeasured.** Do not write a date on this without checking.

**Possible remedies, none decided — this needs a decision, not a patch:**

1. **Emit the patterns as their own hook output**, separate from the handoff pointer, so each fits
   under the cap. Cheapest, and it keeps verbatim delivery.
2. **Rotate** — print N patterns per session, cycling. Verbatim but incomplete by design; a lesson
   would be absent on most sessions, which is what this entry is complaining about.
3. **Compress the block** to one line per pattern with the detail behind a pointer. Contradicts the
   docstring's own reasoning, and the detail is where the instances live.
4. **Measure the cap and assert against it in doccheck** — whatever else is chosen, the check must
   verify the *delivered* size, not merely that the surfacer emitted something. Otherwise the next
   growth spurt silently re-breaks it.

Option 1 plus option 4 looks right and is untested. **Option 4 is the load-bearing half**: without
it, any fix to 1–3 is a fix verified by the same blind check.

**ANSWERED, then RESOLVED — same day.** The cap did not need measuring; it is **documented**:
code.claude.com/docs/en/hooks — *"Hook output strings, including `additionalContext`,
`systemMessage`, and plain stdout, are capped at 10,000 characters. Output that exceeds this limit
is saved to a file and replaced with a preview and file path."* **Characters, not bytes**, and per
output string, so each registered hook entry carries its own budget — which is what makes the
part-split work. An hour was spent inferring a bound from two observed spills before anyone read
the docs; *the empirical estimate (≤10,944) was correct and useless, because the exact figure was a
fetch away.*

**Shipped 2026-08-06** — option 1 + option 4, as decided: `.claude/scripts/tessera-patterns-surface.sh`
takes `--part N --of M`, is registered twice on SessionStart, and doccheck's
`standing-patterns-fit-the-cap` **runs the parts** and asserts (a) the registered indices are
exactly 1..N, (b) each part is under a 9,000 budget, (c) the union carries every pattern exactly
once. All four branches were falsified against planted defects before the check was trusted.
`standing-patterns-are-surfaced` was retargeted in the same commit — **and the stated reason for
retargeting it was wrong, refuted by `bin/tessera-verify` before commit.** The claim was that the
old check would have kept passing on the *comment* left behind in the surfacer. It would not have:
the comment reads "The standing patterns USED TO BE PRINTED HERE" in lowercase, the old check
grepped for `"Standing patterns"` capitalised, and run against the new tree the old check **fires
correctly.**

The hazard is nonetheless real, and the falsifier demonstrated it rather than taking either side on
argument: capitalising one letter in that comment — a wholly ordinary way to write the same
sentence — produced a surfacer emitting **zero** patterns while the old check returned **PASS**.
So substring-matching prose is genuinely unreliable, and this repo escaped it **by a capital
letter, not by design**. The retarget stands; the near-miss was a near-miss, not a hit, and the
original write-up overstated it.

**Still not verified:** whether the harness counts the 10,000 against the raw string or some
post-processed form, and whether many small hook outputs have an aggregate ceiling of their own.
Neither is load-bearing for the fix.

---

### P3's budget sits ABOVE the harness's real spill limit, and the field it names is 5% of the overflow *(2026-08-06)*

- **Status:** Investigating — **but every number below is reproducible in one command, so validate before acting.** This entry is written to be falsified, not believed.
- **Source:** Measured while answering "what does fixing P3 actually give us?" during the ADR-0020 session. Nothing here was found by reading the predicate; all of it came from measuring the artifacts it governs.
- **Related:** ADR-0015 (P3 re-scoped to restore integrity), `docs/contracts/restore-receipt.md`, `_project_specs/todos/active.md` → "T2's first real receipt" (2026-07-27) — this entry compounds with that one.

**Three findings. They are independent — one being wrong does not touch the others.**

**1. The budget is above the real threshold, so P3 can certify a checkpoint that does not arrive.**

`bin/tessera-watch:38`:

```python
RESTORE_BUDGET_BYTES = 12_000   # see p3_restore_integrity; 18,755 was observed to SPILL
```

18,755 is an **upper** bound — it is the only spill anyone had seen, so the budget was set below it
with margin. Nobody established a lower bound. This session does: **both** SessionStart hooks
spilled, and the harness persisted them at

```
12,611b  mnemos-session-start    → harness: "Output too large (12.3KB)" → 2KB preview
10,944b  tessera-watch-surface   → harness: "Output too large (10.6KB)" → 2KB preview
```

The cap is **documented at 10,000 characters** (code.claude.com/docs/en/hooks — see the sibling
entry above), not 18,755. A checkpoint at 11,500 bytes passes P3 and still
spills. The predicate is not merely lenient — it is capable of reporting green on a checkpoint the
model never receives, which is the exact failure ADR-0015 rebuilt it to catch.

**2. The field P3 tells you to check is not the field overflowing.**

P3's own remediation text says *"Check the goal field first — goals are never-evict and one is
minted per ingested session."* Measured against `.mnemos/checkpoint-latest.json` (12,364b total):

```
  8316b  67%  active_constraints   ← the overflow
  1454b  11%  active_results       (progress)
   671b   5%  goal                 ← what the hint names
   444b   3%  recent_files
   224b   2%  task_narrative
     2b   0%  current_subgoal      (empty)
     2b   0%  working_memory       (empty)
```

Deleting `goal` **entirely** does not get under budget. `active_constraints` is 77 entries, **61 of
them `file_exists("path")`** invariants bridged from iCPG intents — e.g.
`INV: file_exists("scripts/override/")`. Those are static repo facts, not session constraints, and
`scripts/doccheck.py` already asserts every one of those paths with a pre-commit hook behind it.
Two-thirds of a restore budget is spent re-asserting paths that a commit cannot violate.

The hint is not merely unhelpful; it is *directionally wrong*, and it was presumably written when
the goal blob was the overflow (the 2026-07-27 receipt saw `+90 older goal(s) omitted`). The blob
shrank; the hint did not follow.

**3. Fixing the bytes turns P3 green and does not answer T2 — this is ADR-0020's finding landing on
the predicate itself.**

This session's receipt was `insufficient`, missing `goal` and `decisions`. There is **no decisions
field in the checkpoint schema at all**, and `current_subgoal` and `working_memory` are 2 bytes
each — empty at source, not truncated. Freeing 6.5KB of budget cannot fill a field that does not
exist or is empty before delivery. **Budget was never the binding constraint on the things that
actually had to be re-derived.**

So: fix the constraint bloat, and P3 goes green while the next receipt still reads `insufficient`.
P3 measures **bytes delivered** — an artifact. T2 asks **did the agent resume without
re-deriving** — the property. See the sibling entry, "Every conduct instrument counts the artifact,
not the conduct"; this is that entry's first concrete instance, found the same day and not planted.

**Where it compounds with the 2026-07-27 receipt** (`active.md` → "T2's first real receipt"):

- That receipt found `progress` **corrupted** — `write_checkpoint`'s extractor capturing `$(cat <<`
  and `$MSG` fragments out of shell command text. This session could not see progress **at all**:
  `active_results` sits below the spill boundary. **The field that is corrupted is also the field
  that does not get delivered.** Across two receipts, nobody has yet observed the progress field
  arrive intact — so its corruption has never been seen under real delivery conditions.
- That receipt's defect #2 — goal stale and misleading, `+90 older goal(s) omitted` — **recurred
  verbatim ten days later** as `+87 older goal(s) omitted`. It was recorded and not fixed.

**Proposed remedy — three parts, in this order. Parts 1 and 2 are ~30 minutes; part 3 is not a patch.**

1. **Drop `file_exists` invariants from the checkpoint's constraint set.** They are owned by
   doccheck + pre-commit, and they still live in iCPG. Takes the checkpoint to roughly 5,900b.
2. **Re-anchor `RESTORE_BUDGET_BYTES` on the measured bound.** Something at or below 8,000, which
   carries real margin under 10,944. Without this, part 1 fixes one checkpoint and leaves the
   predicate still able to certify a spilling one.
3. **The T2 gap is a `write_checkpoint` defect, not a budget defect.** No decisions field, empty
   `current_subgoal`, empty `working_memory`, corrupted `progress`. That is the finding worth
   promoting; it needs its own decision, not a patch.

**What was NOT verified — read this before acting:**

- **One checkpoint was measured.** The 61/77 `file_exists` ratio may not be typical. Check two or
  three before treating it as the general shape.
- **The spill threshold is bounded, not measured.** 10,944 spilled; the largest payload that
  *successfully* delivered this session was not measured, so the true limit is somewhere at or
  below 10,944 and the floor is unknown. **8,000 is a margin, not a measurement** — if the real
  limit turns out to be ~4KB, part 1 alone does not clear it either.
- **Removing the constraints was not attempted.** The safety argument is "doccheck asserts the
  paths"; that was read, not exercised.
- **Whether `active_results` arriving would have changed the `insufficient` verdict is unknown** —
  it never arrived, and per the point above it may be corrupt when it does.
- **This is a tessera receipt, and the 07-27 caveat still binds:** orientation here came from the
  handoff file and the standing-patterns block, not from the checkpoint. A downstream app has no
  such file. **Do not read tessera receipts as a general verdict on Mnemos.**

**Revisit when:** parts 1 and 2 land and a subsequent session's receipt is compared against this
one — specifically whether it still reads `insufficient`, which is the prediction this entry makes
and the cheapest way to falsify it.

> ### ✅ PARTS 1 AND 2 LANDED 2026-08-07 — and measuring first moved two of this entry's own numbers
>
> **The result:** checkpoint **12,835 → 7,077 bytes**; SessionStart output **7,609 characters**
> against the documented 10,000-character cap, with ~2,400 of headroom. P3 is green. G-a clears on
> the next hook-driven run — the fire log is written only by `bin/tessera-watch --log`, which the
> SessionStart hook passes and manual runs deliberately do not, so ad-hoc runs cannot pollute its
> consecutive-run window.
>
> **Two of this entry's "NOT verified" items were checked, and both moved:**
>
> 1. **The 61/77 `file_exists` ratio is not just typical — it is CONSERVATIVE.** Measured across 7
>    real checkpoints: **53/53, 53/53, 56/56, 53/53, 61/77, 62/80**. Four of the seven are **100%**.
>    So dropping the static predicates does not shrink the constraint set in the common case, it
>    **empties** it — which is a finding about Mnemos rather than about bytes; see the sibling entry
>    below.
> 2. **"8,000 is a margin, not a measurement" — now it is a measurement, and 8,000 was the wrong
>    number.** The wrapper is **105 characters** (`mnemos-session-start.sh` headers), so the
>    checkpoint→delivered ratio is **1.011, essentially 1:1**, and the cap is *documented* at 10,000
>    characters rather than inferred. The derived ceiling is **≈9,895 checkpoint bytes**.
>    `RESTORE_BUDGET_BYTES` is re-anchored at **9,500**, which is that with margin for wrapper drift
>    — not the 8,000 guess this entry proposed. **The old 12,000 rested on 18,755, an UPPER bound and
>    the only spill anyone had seen; three tighter spills (12,611b, 12,472b, 10,944b) refuted it.**
>
> **What was NOT done, deliberately:** part 3. It is a `write_checkpoint` defect, not a budget one,
> and it needs its own decision.
>
> **The prediction stands and is now testable.** This entry predicts that P3 goes green *and the next
> receipt still reads `insufficient`*. It is unfalsified so far — the 2026-08-07 receipt read
> `insufficient` on `goal` and `decisions`, and **there is no decisions field in the schema at all**,
> which no byte fix reaches. The cheap test is the next session's receipt. **If it reads `sufficient`,
> this entry is wrong, and that is worth more than being right.**

### P3 has never measured what it claims to measure — three anchors, three proxies *(2026-08-07)*

- **Status:** Investigating. **Named, scoped, and deliberately NOT built in the session that found
  it** — the fix lands in the only restore layer ever proven to deliver, and it is a design
  decision, not a patch.
- **The pattern, which is the entry.** P3 exists under ADR-0015 to answer **deliverability**. Every
  anchor it has ever had measured something *adjacent* to delivery:

  | anchor | what it measured | how it was wrong |
  |---|---|---|
  | `12_000` | an observed spill at 18,755b | an **upper** bound — the only spill anyone had seen. Sat above the real limit; three tighter spills (12,611 / 12,472 / 10,944) refuted it |
  | `9_500` | `hook_stdout_bytes − checkpoint_bytes` = 105, called "wrapper overhead" | a **NET of two errors cancelling**: the render is ~718 chars *smaller* than the JSON, and the hook emits a second block (`=== iCPG STATUS ===`, ~1,037 chars) that was never counted. Real overhead is **1,250** |
  | `8_000` *(current)* | checkpoint JSON bytes × an assumed ratio | the render/JSON ratio is **content-dependent, 0.598–0.944 observed**. No constant is exact; this one is merely safe today |

  **The magnitude of the error keeps shrinking. The class does not.** Each anchor was set by someone
  who had just been burned by the previous one.
- **How the 9,500 error was caught, which is the reusable part.** Not by review and not by a test —
  the tests passed. `bin/tessera-verify` built a checkpoint of **exactly 9,500 bytes**, confirmed it
  **PASSED P3**, and measured its hook stdout at **10,230 characters** — over the documented
  10,000-character cap. A landmine at the threshold, which is the one input a guard's own tests
  never try because the author picked the threshold.
- **Why the current anchor is documented rather than fixed.** `bin/` is stdlib-only (doccheck
  `bin-scripts-are-stdlib-only`), so P3 **cannot import the renderer** and cannot compute delivered
  characters itself. The derivation and both prior failures are written into `bin/tessera-watch` at
  the constant, so the next person to touch it does not repeat the sequence.
- **The fix, with the constraint that makes it non-trivial — this is what the session found.** The
  integration point is **`scripts/restore/offer.py`**, which already writes `restore_offered` with
  `bytes` and `fields`; `delivered_chars` is the natural third field, and P3 would read the most
  recent event instead of stat-ing a file. **The blocker:** `mnemos-session-start.sh` calls
  `offer.py` **mid-hook**, right after the resume block prints — and the iCPG block, the 1,037 chars
  the 9,500 anchor missed, is emitted *later*. A true total means moving the offer call to the end
  of the hook. Every variant trades one fail-open for another: **buffer the output** and a trap
  failure suppresses the restore entirely, or **move the call** and an early exit records no offer
  at all, which reads to `restore/scan.py` as "nothing was owed".
- **Two things the fix would NOT solve, so it is not oversold:** it records *last run's* delivered
  size, not a prediction about the next; and it is silent on **T2 sufficiency** (part 3), which is a
  `write_checkpoint` defect and a different question entirely.
- **A rejected alternative, recorded so it is not re-proposed:** having P3 detect real spills from
  the harness's own `tool-results/` artifacts. Genuine ground truth with no modelling — rejected
  because it depends on undocumented harness internals, and this same session produced a wrong
  number by inferring structure from an artifact without verifying it.
- **Revisit when:** the hook is next touched for another reason (do it then, not standalone), or a
  checkpoint between 8,000b and the true ceiling is observed spilling — which would mean the current
  anchor has stopped being merely imprecise and started being wrong.

### Mnemos's never-evict guarantee is spending its budget on facts a pre-commit hook already enforces *(2026-08-07)*

- **Status:** Investigating. Surfaced by measuring the P3 remedy, not by looking for it.
- **The observation.** ConstraintNodes are **never evicted** — that is Mnemos's headline typed-graph
  guarantee, the thing the type system exists to provide. Measured across 7 real checkpoints, the
  constraint set was **53/53, 53/53, 56/56, 53/53, 61/77 and 62/80** `file_exists("path")`
  invariants, bridged in bulk from iCPG. **Four of seven were 100%.** So in the common case the
  never-evict policy was protecting *nothing but static assertions that a repo path exists* — and
  spending 5.3–8.7KB of a 10,000-character delivery channel to do it, which is why Constraints,
  Progress and Files were the fields that never arrived.
- **Why this is not merely redundant but inverted.** Those same paths are asserted by doccheck's
  `referenced-paths-exist` with a **pre-commit hook that blocks the commit**. That is a strictly
  stronger guarantee than a line in a payload which was, measurably, not being delivered. The
  weaker mechanism was consuming the budget that the load-bearing fields needed.
- **The shape, and it is the one ADR-0020 named.** *Every conduct instrument counts the artifact the
  conduct emits.* A ConstraintNode is the artifact; "the agent is operating under a real invariant"
  is the conduct. Counting nodes made a graph full of `file_exists` look like a graph full of
  constraints. This is the second concrete instance in two days, and like the first it was found by
  measuring rather than by reading the design.
- **What this does NOT say.** It does not say never-evict is wrong, or that ConstraintNodes are
  worthless — 19 real constraints survived the filter in the live checkpoint. It says the *population*
  was dominated by a bridge writing static predicates in bulk, and nothing was watching the mix.
- **The open question, which is the entry:** should `bridge-icpg` be writing `file_exists` invariants
  as ConstraintNodes at all? Filtering at render time (what shipped) treats the symptom. The
  alternative is not importing them, which is a change to the iCPG↔Mnemos bridge contract and wants
  its own decision. **Not made here.**
- **Revisit when:** the bridge is next touched, or a downstream project's checkpoint is measured —
  every measurement so far is from this repo, whose iCPG graph is unusually path-heavy.
- **UPDATE 2026-08-10 — the second cut landed, and it refilled inside one session.** Postconditions
  for `fulfilled` intents are now excluded too (`2eccb2a`): 39 of them, 5,238b, **39.6%** of a
  12,909b payload, every one belonging to a closed intent, all listed under *"DO NOT VIOLATE"*.
  12,909b → **7,780b**. Then bridging **this session's own intent** put it back to **8,556b**.
  **The entry's open question is now answered in one direction and sharpened in the other.** The
  static-predicate half is a *population* problem the render filter can hold. The remaining half is
  a *growth* problem it cannot: non-static invariants are ~139b each, at least one per intent, and
  they are exactly the constraints that should NOT be filtered — 23 distinct bodies out of 24, no
  redundancy to reclaim, all genuinely standing ("no predicate crashes on a fresh clone"). So a cap
  here is lossy by construction and picks winners by recency, on the payload's most valuable field.
  **The two halves want different remedies, and only the first one has shipped.**
- **RESOLVED 2026-08-10 — the growth half is closed, and NOT with a cap.** The entry's remaining
  problem was that invariants accumulate ~139b each, ≥1 per intent, uncapped, while being exactly
  the constraints a recency cap must not touch (23 distinct bodies out of 24, all standing). The
  discriminator turned out to be **scope, not age**: an invariant whose iCPG scope touches no file
  the session has read or edited is omitted, with a stated count. **This is only defensible because
  a better-targeted channel delivers the omitted ones** — `mnemos-pre-edit.sh` runs
  `icpg query constraints <file>` on every Edit/Write, so a scoped invariant arrives exactly when
  its files come into play. ~~**Verified, not assumed.**~~
  **RETRACTED SAME DAY — THE SAFETY ARGUMENT WAS FALSE, AND ESTABLISHING ITS SCOPE IS WHAT KILLED
  IT.** Asked to pin down "what monitors this channel", the answer turned out to be that the
  channel does not carry the thing at all. `mnemos-pre-edit.sh` → `icpg query constraints <file>`
  → `get_reasons_for_file`, which resolves by recorded **`CREATES`/`MODIFIES` symbol edges**, NOT
  by `reason.scope`. The checkpoint drops by scope. The two sets barely overlap here, because
  symbol recording requires exactly one executing intent at Stop time, so most intents never got
  symbols in most of their scoped files. **Measured: 2 of 18 dropped invariants are reachable via
  the per-file channel. Sixteen are simply gone from the session's view.**
  **How the wrong verification passed:** one CLI call, `icpg query constraints bin/tessera-watch`,
  returned *an* intent's invariants. True, and it did not establish what it was used for — it
  showed the command works, not that it returns *the dropped ones*. Standing pattern #12 aimed at
  the verification step: a check can be accurate and still not test the claim it is cited for.
  Three intents scope `bin/tessera-watch`; the channel returns the one with recorded symbols.
  **State of the cut:** left ON, with the payload note rewritten to warn instead of promise (it now
  says DO NOT ASSUME the hook will surface them, and names the symbol-edge mechanism). What it buys
  is SIZE and nothing else. **The principled repair is to make the channel match the criterion** —
  union scope-matching into `get_reasons_for_file`, whose only callers are
  `icpg query context|constraints`, both read-only pre-edit surfaces. Sized: that would take a
  typical file from 0–2 predicates to 11–23. **Not done — it changes what the pre-edit hook shows
  on every Edit/Write and is a decision, not a cleanup.**
  *And the monitoring gap that prompted this is real but secondary: even once the channel carries
  the right thing, nothing asserts the pairing — for every invariant the checkpoint omits, the
  fallback should return it, and that is mechanically checkable from the two data sources with no
  hook execution. That is the check to build.*
  Unscoped invariants are always kept (the
  per-file channel is keyed on scope and cannot reach them), and a session with no file signals
  keeps everything — "I don't know what you're touching" is not evidence nothing matters.
  **Measured: 8,675b → 6,334b live, and 50 further intents / 100 invariants move the payload 4
  bytes.** The leak was monotonic in intent count; it is now bounded by session scope, which is the
  structural difference between this and a bigger cap.
- **A smaller finding inside the measurement: `STATIC_PREDICATE` names one family and the class has
  two.** `test_exists("path")` constraints (2 today) leak through a filter written for
  `file_exists("path")` — standing pattern #11, in the filter itself.
  **~~The claim that deferred it was FALSE, and measuring it inverted the instruction.~~**
  This entry said widening had to wait because *"asserted by something stronger"* is *"not true
  today — deleting `scripts/icpg/test_intent_lifecycle.py` fails neither doccheck nor the suite."*
  **Measured 2026-08-10 by actually deleting it: doccheck goes RED with TWO blocking findings** —
  `referenced-paths-exist` (the observatory names the path) and `adr-execution-recorded` (ADR-0019's
  `Executed:` line names it), both enforced by the pre-commit hook. The suite half was right
  (`scripts/icpg` runs 36 instead of 46 and passes); the doccheck half was asserted without being
  run. **So the blocker is gone: widening is justified today.**
  **What survives is weaker and worth keeping:** that coverage is INCIDENTAL, not structural — it
  holds because this particular path happens to be named in two documents, and a future
  `test_exists("some/undocumented/test.py")` would have none. So the assertion still worth adding is
  one that makes the coverage a property of `test_exists` rather than a coincidence of citation.
  *Found by arbiter's second prose pass doubting a claim it could not verify — right for a reason it
  did not know, and the deferral rested on the one half of the sentence nobody had measured.*
- **And P3's structural limit is now partly addressed — but NOT by the instrument it asked for.**
  `write_checkpoint` measures itself at write time and warns on stderr (`cf25330`), so the news
  arrives when the payload is made rather than at the next SessionStart alongside the harm. **This
  is an earlier-firing PROXY, not the "honest instrument" `bin/tessera-watch:56-59` names.** That
  comment asks for *the hook recording its own DELIVERED size* — rendered characters plus sibling
  hook output; what shipped measures *checkpoint JSON bytes*, the same proxy P3 uses, just sooner.
  The delivered-size instrument is `delivered_chars` in `scripts/restore/offer.py`, still unbuilt
  (part 4). **An earlier draft of this bullet claimed `cf25330` WAS that instrument** — caught by
  arbiter 2026-08-10, and it is the day's own lesson pointed at the record of the day: a fix that
  partially answers a request is not the request answered. Budget now defined twice (bin/ is
  stdlib-only and cannot import mnemos), guarded by doccheck `checkpoint-budget-matches-p3` — **verified firing against both broken states** (a diverged value, and a renamed constant, which fails loud rather than passing blind). Recorded because a guard whose regression test is unstated is indistinguishable from one that was never run, which is the pattern every prior anchor in this entry got wrong.

### `doccheck.run()` has no per-check isolation — one raising check takes all 45 down *(2026-08-10)*

- **Status:** RESOLVED same day. Found by `bin/tessera-verify` refuting a claim I had just written,
  twice in a row; fixed once the gate-policy fork was decided. Kept rather than deleted because the
  three-row-fixes trail is the reusable part.
- **The observation.** `bin/tessera-watch`'s `evaluate()` was given per-predicate isolation on
  2026-08-09 precisely because one crashing predicate silenced the rest. **`scripts/doccheck.py` never
  got the same treatment**, and it is the stronger gate of the two — it runs in `.githooks/pre-commit`
  and blocks commits. Any check that raises takes the whole process down and **0 of 45 checks report**.
- **How it surfaced, and the shape is the finding.** Adding `checkpoint-budget-matches-p3` I wrote an
  unguarded `read_text()` → crashed under a synthetic ROOT. Guarded `exists()` → the falsifier
  returned a directory and `chmod 000`, both of which exist and raise. Caught `OSError` → the
  falsifier wrote **binary content**, and `UnicodeDecodeError` subclasses `ValueError`, not `OSError`,
  so it escaped again. **Three consecutive row-fixes, each under a comment claiming the class was
  fixed** (#11, aimed at the person quoting #11). The rows are closed and regression-tested; the
  pattern is that a check's author can always find one more exception type, which is the argument for
  isolating at `run()` instead of at each call site.
- **What shipped.** `run_detailed()` isolates each check and returns `{name: (findings, exc|None)}`;
  `run()` stays as a flattening wrapper; `render()` prints crashes in their own section; a crashed
  check exits 1. **DECIDED: a crashed check BLOCKS the commit** — that reverses the pre-commit's
  written "a crashing checker must not wedge every commit", which was authored when a crash killed
  the *whole* run. An isolated, named crash beside 44 working checks is a defect to fix, and
  `--no-verify` is still the documented escape. **Catastrophic failure still fails open** (doccheck
  unparseable, `render()` raising, a traceback with no recognisable verdict) — that is the case the
  original rule was really for. **Say the consequence plainly, since "fails open" understates
  it: in that state the pre-commit hook prints a warning and LETS EVERY COMMIT THROUGH.** That is
  the deliberate trade — a totally broken checker must not wedge the repo — but it means the
  commit gate is bypassed exactly when doccheck is most broken, and the warning on stderr is the
  only thing standing there.
- **THE TWO THINGS THAT WOULD HAVE MADE THIS A SILENT REGRESSION, both caught before shipping.**
  (1) **P8's loud channel was BUILT ON `run()` raising.** It flattens `run().values()` and cannot
  tell a crash from a false claim, so naive isolation would have downgraded every crash to an
  ordinary fire — the 2026-08-09 `render()`-never-read-the-`crashed`-field defect, one layer up. P8
  now reads the new channel and names the crashed checks. (2) **The pre-commit grep keyed on
  `"claim(s) that are no longer true"`**, and crashes print their own section — so isolation would
  have *inverted* the decision, letting every crash sail through the gate it was meant to close.
  **Both are consequences of adding a channel: the existing readers keyed on the old one.**
- **A third, found by the repo's own check mid-fix:** the first implementation annotated
  `BaseException | None`, and `safety-scripts-run-on-system-python` failed — PEP 604 is 3.10+ and
  this file must run on `/usr/bin/python3` (3.9.6), because a hook invokes it via bare `python3` and
  a crash there makes the spend guard exit non-2, which Claude Code reads as ALLOW. Fixed with
  `from __future__ import annotations` so the next union does not re-learn it. *A check in this repo
  caught a defect in the code being written to improve that same checker.*
- **The pre-existing 3.9 red is FIXED, and it was worse than "doccheck is red on 3.9".**
  `scripts/decision_surface.py:61` had a backslash inside an f-string EXPRESSION (3.12+), so it did
  not parse on 3.9. `.claude/scripts/tessera-decision-surface.sh:55` invokes it via **bare
  `python3`** — the documented stdlib-only split — and ends the line with `2>/dev/null`. On a
  `/usr/bin`-first PATH that is a `SyntaxError` into a black hole: **the `DECISION SURFACE` block
  silently stops reaching the model, and the hook built to defeat silent failure fails silently**
  (#1). The em dash is hoisted to a named constant; behaviour verified byte-identical to the
  original across six inputs; doccheck is now green on 3.9 **and** on the venv.
- **AND THE MEMBERSHIP RULE THAT LET IT HAPPEN IS NOW MECHANICAL.** `SAFETY_SCRIPTS` states its own
  rule in prose — *"a hook invokes it via bare `python3`"* — and nothing enforced it, so
  `decision_surface.py` was simply never added. New check
  **`bare-python3-hook-scripts-are-probed`** greps `.claude/scripts/*.sh` for bare-`python3`
  invocations of `scripts/*.py` and asserts each target is listed. Explicit interpreter paths
  (`.venv/bin/python`) are out of scope — that is the split working. **Note the detection asymmetry
  this closes: the bug was found only because a doccheck run happened to be on 3.9 and tripped a
  DIFFERENT check (`decision-surface-is-wired`). Membership in `SAFETY_SCRIPTS` makes the 3.9 probe
  unconditional — proven by re-planting the f-string and watching it fire from the VENV run, the
  case that was previously blind.** Scanned all of `scripts/`: 0 other files fail to parse on 3.9,
  so no blanket "everything must be 3.9" check — that would forbid modern syntax in venv-only code
  with no evidence behind it.
- **A smaller mislabel fixed in passing:** the safety check's remedy string always said *"Add
  `from __future__ import annotations`"* — correct for the PEP-604 bug it was written for, wrong for
  an f-string backslash. It now picks the remedy from the actual error (#12, aimed at the remedy).
- **Revisit when:** any check is added — an added check is a new chance to take the gate down, and
  the isolation makes that a named finding rather than a blackout.

### Findings have a channel to the framework but none to a PEER *(conclave F-002, transferred 2026-08-07)*

- **Status:** Watching. **Deliberately not built**, on the raiser's own recommendation. Trigger below.
- **Source:** conclave `docs/FINDINGS.md` **F-002**, raised 2026-08-07 during the conclave ↔ arbiter
  reconciliation, addressed at Tessera because the fix would land here. Closed there as
  `transferred:` this entry — the finding *did* land in the framework; what it did not do is become
  code, and that distinction is the whole content of this entry.

**The gap, in its sharp form.** `FINDINGS.md` + `tessera-findings` is **hub-directed by
construction**: there is no addressee field, and only Tessera's SessionStart reads the backlog. A
fact one downstream measures that binds *another downstream's* work has nowhere to go. It ends up in
`docs/contracts/three-project-cohesion.md`, which is read at **coordination** time, not at **work**
time.

**But the evidence narrows it, and the narrowing is the valuable part.** Checking the conclave ↔
arbiter pair (both carry `.tessera/project.yml`, so both are downstreams):

- **Technical findings DID cross.** arbiter reviewed conclave twice; both defects are recorded in
  conclave at the site, credited by name and date, with the not-fixing rationale
  (`../conclave/harness/run-t1t3.sh:139`, `:189`). That path works, **because a finding about code
  has an obvious home — the code.**
- **What did NOT cross is everything without a line number.** The usage rules that came with those
  reviews — *"the finder is better at locating than at concluding: take the location, re-derive the
  consequence"* and *"`--ext ""` or the review is silently narrower than it claims"* — were absent
  from conclave until 2026-08-07, and they are needed **before** the next run, not after.
  Symmetrically, conclave's measurement that its local tier scores **0.073 recall** on review, which
  bounds arbiter's cost work and the D3 seam, was absent from arbiter for ten days.

> **A finding that names a file finds its own way home. A usage rule, a negative result, or a bound
> on someone else's design does not.** Those are exactly the facts a coordination map is too slow to
> carry — and note the shape: this is principle #17 one level out. The peer channel exists as a
> *convention* (write it in the contract, hope the other project reads it at the right moment) where
> the framework channel is a *hook*.

**The proposed fix, recorded unbuilt** — one optional field and one hook line, not a new store. The
scanner already globs every `.tessera/` project, already parses `F-NNN` blocks and statuses, already
emits `--json`:

1. Optional `**To:** <project>` line in the finding shape. **Absent = framework**, so every existing
   finding stays valid and the contract change is backward-compatible.
2. `tessera-findings --to <project>` — a filter over parsing the scanner already does.
3. A SessionStart line in each downstream running `tessera-findings --to <self>`. **This is the
   load-bearing piece**; without it the change builds a mailbox nobody opens.
4. `acknowledged:<ref>` added to the status vocabulary. A peer-directed finding's terminal state is
   not "transferred to the framework", so without it peer findings can never close.

**Impact to weigh if it is ever built:** `docs/contracts/findings.md` is where shape changes land,
and **tess-dashboard consumes `--json`** — an addressee field has a downstream consumer.

**Explicitly NOT proposed: a coordination database.** It would move facts away from the code they
describe, need a service running at SessionStart, and could not be branched or reverted with the
change that motivated it. The evidence against it is already in these repos: arbiter's own docs
record a test count going stale twice and a commit trail running fifteen behind in a day — both
hand-maintained mirrors of facts a command could answer. Their rule was **"prefer a command in the
doc over a number in the doc."** A coordination DB is that failure class with a three-project blast
radius.

**Why it is not being built now.** n is **2 projects**, and the manual writes are already done. The
raiser recommended against building it, and that recommendation is the finding's most useful part:
a mailbox built for one observed pair is a mechanism justified by the case that no longer needs it.

**Revisit when EITHER of these fires:**

- **A third peer pair appears** — i.e. two downstreams other than conclave/arbiter needing to bind
  each other's work. (Six projects carry `.tessera/project.yml` today; the count is not the trigger,
  the *pairing* is.)
- **The same fact is found missing a second time** — a bound, negative result, or usage rule that a
  peer had measured and the consuming project did not have when it needed it.

**Not yet fired, and the near-miss is worth recording precisely.** This very reconciliation looks
like an instance and is not one: conclave knew this file's cluster entry was stale, wrote it in its
own `HANDOFF.md` and flagged the contract in place — and it reached Tessera because a **human
relayed it**. That is a third *manual write*, not a missed fact. It counts toward the cost of the
status quo, not toward the trigger. Recording it as a trigger hit would be manufacturing the
evidence for a thing I want to build, which is the failure mode this entry exists to resist.

### A lane going stale in a peer contract has NO mechanical subject — recorded as a finding about the checker *(2026-08-07)*

- **Status:** Watching. **No check was built for the bug that was actually found**, deliberately, and
  the standing rule (`CLAUDE.md`: *"every doc-drift bug a human finds becomes an assertion in
  `scripts/doccheck.py`"*) says that fact must be stated rather than quietly skipped.

**The drift.** `docs/contracts/three-project-cohesion.md` named frozen **pr-arbiter** as the Pattern
lane's owner while S4, S5 and D4 in the same file already named its successor **`arbiter`**. Found by
conclave reading the file, not by any check.

**Three candidate checks, measured against it:**

1. **"Every sibling-relative path the docs cite exists."** Mechanical subject, closed extraction,
   measured 39 citations → 37 resolve, 2 placeholders, 1 peer not checked out — **zero false
   positives. BUILT** as `sibling-paths-exist`, with brace sets expanded rather than skipped, and
   peers that are not checked out skipped rather than failed. **It would NOT have caught this bug** —
   every path involved was on disk. It is here for the class one step out (a peer renaming a file the
   contract cites), and was falsified against the real repo by deleting
   `../arbiter/src/arbiter/second_pass.py` and watching it go red.
2. **"Every project named as a lane Owner is a live Tessera downstream."** **REJECTED on
   measurement.** pr-arbiter has no `.tessera/project.yml` and never had one — so this check would
   have fired continuously from the day the contract was written, throughout the entire period when
   pr-arbiter was the legitimate Pattern owner. **D4 existed precisely because a lane owner need not
   be a downstream.** *Being a downstream is not the same property as owning a lane*, and a check
   that conflates them is a proxy predicate (principle #3) wearing a file-existence test.
3. **"A project named as a lane Owner must not also be described as frozen."** **REJECTED as
   judgement wearing a regex** — the Owns column is authored prose in an unenforced format, which is
   exactly the A6 case (2026-07-27) where two of three candidate handoff checks were rejected, one
   scoring 12 false positives in 13 and one failing open.

**The conclusion, which is the entry:** *"is this lane's owner still the right project?"* is a
question about the world, not about the file. Its subject is a judgement someone has to make. **The
honest answer is a human re-read, and the mechanism that actually worked here is the one that already
exists** — a peer noticed, flagged it **in place with an interim precedence rule** rather than fixing
it unilaterally, and the owner disposed of it. That is not a checker gap to be closed; it is what the
peer-contract convention is *for*.

**Revisit when:** a lane goes stale a second time **and** the flag-in-place convention fails to catch
it. One instance caught by the convention is evidence the convention works, not evidence it needs a
check behind it.

---

### Three environments are not a machine — a measured rejection that was correctly measured and wrongly scoped *(2026-08-09)*

- **Status:** Closed as a defect (fixed in `136cef7` + `33cc3b3`), **kept as a correction to the
  record**, because commit `136cef7`'s own message states the opposite and history is not rewritten
  here. If you read that commit, read this entry.

**What `136cef7` claims:** *"Honest scope: this cannot fire here. Measured on darwin, that call
returns UTF-8 under the default locale, under `LC_ALL=C`, and under `LC_ALL=C LANG=C`. […] a latent
landmine on the first non-UTF-8 host, not a bug on this one."*

**Both halves are false, on this host, two ways** — found by `bin/tessera-verify`, not by the author
who wrote that sentence three commits earlier:

| condition | `getpreferredencoding(False)` | pre-fix behaviour |
|---|---|---|
| default / `LC_ALL=C` / `LC_ALL=C LANG=C` | `UTF-8` | fine — the three I sampled |
| `PYTHONUTF8=0 LC_ALL=C` | `US-ASCII` | **UnicodeDecodeError**, `stats` dies |
| `LC_ALL=en_US.ISO8859-1` | `ISO8859-1` | **silently decodes as mojibake, exit 0** |

The three sampled environments all returned UTF-8 for the *same* reason — PEP 540 auto-enables UTF-8
mode under C/POSIX — so they were one observation wearing three coats. **93 ISO8859 locales are
installed on this machine**, and latin-1 never raises, so that row is the fail-open half: no
exception, no signal, wrong bytes. (Narrower than it first reads: `stats` prints only counts, never
claim text, so the corruption is real at the decode layer and invisible in that command's output.)

**The lesson, which is why this is an entry and not just a fixed bug.** The rejection was *measured*
— that is what made it persuasive, including to me. Principle #3 says name the pain, not the artifact
that correlates with it; this is the same error in the sampling frame. **Three passing samples were
generalised to "this machine", and the generalisation was never stated as the claim it was, so it was
never tested.** The 2026-08-09 handoff already carries the parent lesson in bold — *a mitigation
claim is a claim: it needs the same evidence as the defect it downgrades* — and this rejection was
written two turns after quoting it.

**Also recorded:** the fix itself then shipped the same shape one layer down. `136cef7` pinned the
three JSONL I/O sites and left the console on the locale, so `cmd_stats` crashed printing the ⚠
banner — **the only non-ASCII output, emitted only when a run lands on the fragile verdict
channel.** The crash appeared precisely and only in the case the banner exists to report.
Fixed in `33cc3b3`.

**Revisit when:** never as a question — it is closed. Cite it when a rejection rests on an
enumeration of environments, inputs, or cases rather than on the boundary of the class.

---

### `CLAUDE_CODE_SESSION_ID` reaches a filename unsanitised in 7 modules — accepted risk, recorded so it is a decision *(2026-08-09)*

- **Status:** Watching. **Not a vulnerability; a real robustness defect.** Proven, not argued:
  `CLAUDE_CODE_SESSION_ID=/tmp/PWNED-absolute bin/tessera-verify skip --reason …` wrote a 228-byte
  file outside the repo, and the `../../../` form escapes `.tessera/logs` too.

**Why it is not a security finding, verified rather than asserted.** arbiter rated it high/security.
`bin/tessera-verify` was given the rejection as a claim and attacked both premises: a repo-wide grep
found **only reads** of the variable (`tessera-verify`, `tessera-escalate`, `override/emit`,
`gate/emit`, `spend/event`, `spend/authorize`, `restore/{emit,offer}`, `override/scan`) plus exactly
one write — a hardcoded `CLAUDE_CODE_SESSION_ID=""` self-probe in `bin/tessera-degraded`. Every other
input surface was probed and closed: no CLI flag accepts a session id, stdin is not read, and
`.claude/settings.json` carries no `env` block. Setting the variable requires control of the process
environment, which every invocation path already grants as arbitrary code execution. **Verdict:
CONFIRMED — correctly rejected.**

**What is left, and why it is written down instead of fixed.** The missing sanitisation is real, and
**the identical env-var-as-filename pattern exists in at least 6 other modules** — so it is a class,
not a row, and standing pattern #11 says fixing the instance where it was noticed is the failure mode
rather than the fix. A same-session sweep of 7 modules on the back of a *rejected* finding is the
wrong trade; recording the accepted risk explicitly is the honest alternative to a silent one.

**Revisit when:** any of these tools starts taking a session id from an argument, a config file, or
a hook payload — i.e. the moment the "only ever set by the harness" premise stops holding. At that
point it is one shared helper, applied to all 7, not a patch at the call site that changed.

---

### The clean-clone path has no exercise — three defects found by tripping over it in one day *(2026-08-09)*

- **Status:** Watching. A runner is the right instrument and is **deliberately not built yet**; the
  design constraint that blocks a naive version is measured below so the next session does not
  rediscover it.

**Three instances, same day, none found by a check.** Every one surfaced because something else
tripped over it:

| instance | kind | what was asserted | found by |
|---|---|---|---|
| `referenced-paths-exist` red on a clean clone | a **check** | docs name paths under `.claude/skills`, a gitignored symlink | the pre-commit gate blocking a fresh clone |
| P5 crashed on absent `.claude/skills` | a **predicate** | `iterdir()` on the same gitignored symlink | a whole-file arbiter review |
| two P9 tests red before `./install.sh` | **tests** | `.icpg/reason.db`, gitignored runtime state | `bin/tessera-verify` reporting its own baseline |

**NAME THE PAIN, NOT THE ARTIFACT (#3). It is not "we have no clean-clone test."** It is that
**this repo's own green-makers assert MACHINE state they do not own.** That reading is what made each
fix obvious and made the third one large: the remedy was never "relocate the assertion", it was
*give the artifact an owner, or stop asserting it*. `.claude`'s dogfood symlinks got an owner in
`install.sh` that morning; `.icpg/reason.db` got one that evening — and **that ownership gap was
invisible until an assertion was moved toward `verify()` and would have failed there.** A check
looking only for red tests would have found none of the three causes.

**What would actually measure the property:** clone → `./install.sh` → `tessera-test` →
`tessera-watch` → `doccheck`, all green. That is the property ("does this repo work from clean"),
not a proxy for it.

**THE CONSTRAINT THAT MAKES THE NAIVE VERSION USELESS, measured 2026-08-09 rather than predicted.**
`install.sh` writes to `$HOME` — `CLAUDE="$HOME/.claude"`, console links into `$HOME/.local/bin`,
and `.bootstrap-dir` → `$REPO`, which would hand ownership of the global tier to a temp directory
and take P14 with it. Redirecting `HOME` isolates all of that **and it works** (verified: a full
sandboxed install produced `✓ iCPG database present` and a 73,728-byte db). But the **ambient PATH
still resolves the OUTER repo's `mnemos`**, so `verify()` emits two ✗ that are artifacts of the
sandbox, not defects of the clone:

```
✗ mnemos resolves /Users/…/tessera/.venv/bin/python, NOT the venv
✗ mnemos does NOT resolve in a pristine non-interactive shell
```

A runner that inherits those is **red forever**, and P9's own docstring already names that failure:
*a detector that cannot go green teaches you to ignore the watcher.* So the runner must neutralise
`PATH` as well as `HOME`, or scope its assertions to what is genuinely clean-clone-relevant. That is
the actual work, and it is why this is an entry rather than a commit.

**Two shapes ruled out, with reasons:**
- **Not a `tessera-watch` predicate.** Predicates *read* state in milliseconds at SessionStart; this
  one has to *build* something over minutes, with network.
- **Not folded into `tessera-test`.** Clone + `uv venv` + four editable installs + network turns the
  main suite slow and flaky, and `bin/tessera-chaos`'s own header records where that ends: *"a
  permanently-red main suite is one people learn to ignore."* The precedent that fits is
  `tessera-chaos` itself — expensive, opt-in, deliberate, and kept from rotting by a doccheck
  reachability assertion rather than by being run constantly.

**Rejected, and this one is a near-miss worth recording:** a cheap doccheck source-scan for *"no test
or check asserts a path matching `.gitignore`"*. It is a **proxy** (#3) — the paths are built
dynamically, so it would key on source shape, which #10's corollary warns against — and it could not
have found the real defect in any of the three instances, because in two of them the assertion was
*correct* and the missing owner was the bug.

**Revisit when:** a fourth instance appears, **or** before the next `bin/` whole-file review round —
~4,500 lines across 19 files are still unreviewed, and on today's base rate that is where instance
four lives.

---

## Closing notes

This file is meant to be light-touch. Drop entries in when you notice something; promote to ADR when evidence justifies; close out when decided. Do not let it become a place that requires its own maintenance schedule — that defeats the purpose.

If an entry sits in "Investigating" for >6 months without being touched, that itself is evidence it doesn't matter. Either close it (move to a "Closed without action" section), or commit to a real decision.
