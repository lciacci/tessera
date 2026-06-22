# ADR-0001: Open GSD Evaluation

- **Date:** 2026-06-22
- **Status:** Accepted
- **Decision driver:** New tool surfaced during install — Tessera install of Phase 4 (first test session) revealed that the user's existing global ~/.claude/ setup contained GSD's hook infrastructure. Surface evaluation became necessary before continuing install.

---

## Target

- **Name:** Open GSD (gsd-core, gsd-pi)
- **URL:** https://github.com/open-gsd/gsd-core
- **What it is:** A meta-prompting, context-engineering, and spec-driven development framework that drives AI coding agents (Claude Code, OpenCode, Codex, Gemini CLI, Kimi CLI, Cursor, Windsurf, and ~10 others) through a disciplined phase loop using fresh-context subagents.

---

## Side-by-side summary

| Dimension | Tessera | Open GSD |
|---|---|---|
| Maturity | Solo, in design phase (6 commits, ~5 days) | 23 releases, ~2.4k stars, 150 forks, active maintenance (TÂCHES origin, continuing as Open GSD) |
| Cross-runtime | Claude Code only, design-aware (#15) | 16+ runtimes via translation layer |
| Original IP | Healthcare profile, project profiles, override mechanism with named-owner approval, suggestion-gate, principle #15 | Phase loop discipline, fresh-context subagent isolation, file-based .planning/ state, two-stage hierarchical routing, byte-budget enforcement, Package Legitimacy Gate, Plan Drift Guard |
| Maintenance model | Solo | Open-source community + active maintainers |
| License | MIT (planned) | MIT |
| Community size | Single user | Discord community, ~150 forks, multiple downstream ports (gsd-opencode, etc.) |
| Primary problem solved | Personal framework with healthcare-aware profile extensions and a learned workflow shape | Context rot at scale — preventing quality degradation across long agentic sessions |
| Distinct strength | Healthcare-aware compliance layer, profile-per-project architecture, audit asymmetry, override with named-owner approval | Fresh-subagent isolation as the headline mechanism, mature multi-runtime translation, package supply-chain security, file-based durable state |

---

## 1. Identity & maturity

Open GSD is a mature, MIT-licensed framework that originated as "Get Shit Done" (TÂCHES) and evolved through gsd-build/get-shit-done → open-gsd/gsd-core. The current state is substantial: ~3,749 commits on the next branch, 23 releases, 2.4k stars on gsd-core. The org also maintains gsd-pi (CLI), gsd-workbench (desktop, coming soon), gsd-cloud (hosted, coming soon), and gsd-browser (Chrome verification). Recent releases (v1.42.1 introduced the Package Legitimacy Gate; v1.40 introduced two-stage hierarchical routing) demonstrate active feature development rather than maintenance mode. Maintainer model: open-source community with active contributors plus a Discord. Bias risk is moderate — they have downstream products (workbench, cloud) that suggest a future commercial angle, but the core framework is MIT and the architecture documentation is unusually thorough (Diataxis-style docs with tutorials, how-to, reference, explanation). Recent direction: adding security gates, refining context-engineering primitives, expanding runtime support. Not pivoting; not stalling.

---

## 2. Problem-space overlap

| Overlap area | Tessera approach | Their approach | Classification | Notes |
|---|---|---|---|---|
| Context rot / bloat prevention | Mnemos compaction recovery (3-layer defense) + iCPG drift detection + suggestion-gate for heavy machinery | Thin orchestrator + fresh-context subagents (200k clean window per task) | Different bet | Tessera recovers from rot; GSD prevents by structurally isolating contexts. Their approach is more rigorous; ours is lighter-weight. |
| Durable state across sessions | Structured event log (.tessera/logs/*.jsonl), Mnemos checkpoints, Obsidian vault integration | .planning/ directory with structured artifacts (CONTEXT.md, PLAN.md, STATE.md, RESEARCH.md, VERIFICATION.md per phase) | Different bet | Theirs captures decisions and outputs; ours captures events. Ours is finer-grained but less semantically structured. |
| Heavy-machinery activation | Suggestion-gate (#12) — Claude proposes, user disposes | /gsd-quick, /gsd-fast as escape hatches; main loop is heavyweight | Compatible | Same intent (don't force ceremony on small work); different surface (we surface a suggestion, they require explicit invocation of light primitive) |
| Project-specific behavior | .tessera/project.yml declares profile; profile activates extensions | .planning/config.json configures workflow; no profile concept | Different bet | Ours is profile-bundled; theirs is feature-flagged. Profile model is more compositional but more design overhead. |
| Multi-agent orchestration | Single Claude session with hooks lifecycle (current design) | Thin orchestrator spawns specialized agents (researchers, planners, executors, verifiers, etc.) with fresh contexts | Different bet — GSD's approach is more sophisticated, adoptable as a Tessera capability gated by suggestion-gate |
| Supply-chain security | None | Package Legitimacy Gate via slopcheck (registry-API verdicts + hallucination patterns + Levenshtein typosquat detection) | Tessera gap | We don't address slopsquatting at all; this is a real attack vector (USENIX 2025: ~20% of AI-generated package references are hallucinated) |
| Plan correctness pre-execution | Pipeline pattern (pass 1.3) — spec → tests → implement → validate | Plan Drift Guard — verifies symbol references in generated plans against live source before execution | Tessera gap | Our pipeline is testing-driven; theirs catches hallucinated symbols at planning time |
| Cross-runtime support | Claude Code only, design-aware per principle #15 | 16+ runtimes via translation layer (installer adapts file content per runtime) | Different bet | Their cross-runtime is real value; ours is deliberate scope discipline. Not converging on this. |

**Tessera doesn't address (gaps in our design they fill):**
- Supply-chain security at install boundary
- Pre-execution plan drift / hallucinated-symbol detection
- Cross-runtime support (deferred per #15)
- Two-stage skill routing for high-skill-count environments
- Explicit byte-budget enforcement on workflows/skills
- Parallel-executor commit safety (--no-verify + STATE.md file locking with O_EXCL)
- Thinking-model-specific prompt patterns (o3, o4-mini, Gemini 2.5 Pro variants)

**They don't address (gaps in their design we fill):**
- Project profiles as a compositional mechanism (their config.json is flat feature flags)
- Healthcare-aware compliance layer (PHI markers, BAA scope tracking, encryption defaults bump)
- Override mechanism with named-owner approval and audit log
- Audit asymmetry (changes audited per-profile rather than universally)
- Per-project sensitive-data review category (their security-auditor agent is generic)
- Skill-defaults-as-starting-points philosophy (#15) — their opinions are more prescriptive

---

## 3. Integration cost

**Adopt fully (replace Tessera with GSD):**
- Switching cost: High. ~5 days of design work transfers conceptually but not artifact-wise. Would need to learn GSD's mental model, vocabulary, and operational patterns.
- What's lost: Healthcare profile (no equivalent in GSD), project profiles as compositional mechanism, override mechanism with named-owner approval, audit asymmetry, principle #15's explicit skill-as-starting-point philosophy.
- What's gained: Maturity (23 releases worth of bug fixes), cross-runtime support, active community, ongoing maintenance by others.
- Net: Real loss of healthcare-specific IP that matters for some of Lorenzo's work history; gain of maturity and community.

**Adopt patterns (steal ideas, keep Tessera):**
- Patterns worth lifting: Fresh-subagent orchestrator pattern (as a Tessera capability gated by suggestion-gate); file-based decision artifacts pattern (augment audit log); Package Legitimacy Gate (with slopcheck dependency); Plan Drift Guard concept; byte-budget concept for workflows/skills.
- Implementation effort: Moderate. Each pattern is a focused addition rather than a structural rework.

**Hybridize (run alongside):**
- Coexistence cleanliness: Limited. Both want to be the framework, not coexist as peers. Skills systems overlap, hook namespaces would conflict, both want to claim "the main loop" of work. Could install GSD on some projects and Tessera on others, but not both in the same project.
- Conflict points: Skills load globally and would mix; hooks fire on same events; both want to manage .planning/ or .tessera/ style state.

**Continue without (maintain Tessera forever):**
- Implicit maintenance burden: All bug fixes, all new patterns, all runtime adaptations, all skill curation. Solo maintenance load. Hard to sustain past ~4h/week on a long horizon.
- Gaps that remain: Cross-runtime support (acceptable per #15), supply-chain security (addressable by adopting slopcheck), plan drift (addressable by adopting the concept), some operational maturity GSD has earned.

---

## 4. Pattern-level vs implementation-level

| Pattern | Idea-only / Impl-too / Skip | Notes |
|---|---|---|
| Thin-orchestrator with fresh-subagent isolation | Idea + partial impl | Adopt as Tessera capability gated by suggestion-gate. Heavy work goes through orchestrator; light work stays in main session. Implementation in Tessera's idiom — define ~5-6 core agent types when evidence justifies. |
| File-based .planning/ artifacts (CONTEXT.md, PLAN.md, STATE.md per phase) | Idea-only | Augment our existing audit log with structured decision-and-output artifacts. Don't copy their exact schema; adapt to Tessera's .tessera/ convention. |
| Package Legitimacy Gate | Impl-too | Use slopcheck (0xToxSec/slopcheck, MIT, pip-installable). Gate degrades safely if slopcheck unavailable — every package becomes [ASSUMED] requiring human checkpoint. Real attack surface (slopsquatting), low lock-in. |
| Plan Drift Guard (symbol verification against live source) | Idea-only | Concept worth adopting as part of our pipeline pattern. Implementation deferred — exact mechanism (AST parsing? grep-based? semantic search?) is a future design call. |
| Byte-budget enforcement on workflows/skills | Idea-only | The concept of attention budget as motivation for size limits is genuinely useful (better than line-count). Adopt the idea; defer specific tier numbers until we have evidence of which sizes work for our skills. |
| Two-stage hierarchical routing (namespace meta-skills) | Skip | Premature at our skill count (~50). Re-evaluate if we ever cross 60+ skills. To observatory. |
| Cross-runtime translation layer | Skip | Deferred per principle #15. To observatory. |
| Wave execution with --no-verify + STATE.md file locking | Skip for now | Becomes relevant only when we have parallel executors. Deferred to when the orchestrator capability is built. To observatory. |
| Thinking-models-specific prompt patterns | Skip | We don't have differentiated prompt patterns by reasoning-model tier. Worth knowing they exist as a pattern category. To observatory. |
| Capability registry pattern (their plugin/extension system) | Skip | More developed than our skills system. Worth understanding but not adopting now — different design philosophy (we want compositional profiles; they want extensible capabilities). To observatory. |

---

## 5. Lock-in & maintenance

**If we adopt patterns (the chosen verdict):**
- What depends on continued maintenance: slopcheck (0xToxSec) for the Package Legitimacy Gate. If abandoned, gate degrades to "always require human checkpoint" — safe but more friction. Easy to fork if needed (it's HTTP calls to registry APIs).
- Exit story: All other adopted patterns are conceptual — they don't depend on GSD's continued maintenance. If GSD sunsets tomorrow, our adoption of their ideas is unaffected.

**If we don't adopt (rejected):**
- Cost of maintaining the equivalent ourselves: Solo build of every pattern. Real but bounded — each pattern is small. The orchestrator capability is the largest (5-6 agent types, workflow files, init handlers).
- Lock-in risk to our own design: Low. Tessera is text and convention; switching costs in the future are bounded.

---

## 6. Decision

**Verdict:** Adopt patterns (substantial), keep Tessera as the host framework.

**Reasoning:**

GSD is more sophisticated than the initial marketing read suggested. Several concepts it has worked out — fresh-subagent isolation, Package Legitimacy Gate, Plan Drift Guard, byte-budget discipline, file-based decision artifacts — are real engineering that addresses problems Tessera has either ignored or under-specified. Pretending otherwise would be confirmation bias for the path already chosen.

That said, Tessera has original IP that GSD does not match: project profiles as a compositional mechanism, healthcare-aware extensions with PHI markers and BAA tracking, override mechanism with named-owner approval, audit asymmetry, and principle #15 (skill defaults as starting points). For Lorenzo's specific work history (healthcare technology, compliance contexts), that IP is not optional. Switching to GSD entirely would mean rebuilding the healthcare layer from scratch on a different framework — sunk cost is unrecoverable but forward cost still matters.

The honest balance: adopt the patterns where GSD is meaningfully better, keep Tessera's distinct design where its original IP matters. This ADR records what we took and what we left.

Biases noticed in this evaluation: (1) Some confirmation bias toward continuing Tessera surfaced when listing Tessera's strengths — explicitly flagged and counterweighted by surfacing GSD's overlooked strengths in the prior conversation turn. (2) Familiarity bias toward Tessera's design — countered by being specific about which GSD patterns address real problems Tessera doesn't. (3) Excitement bias toward the thin-orchestrator pattern — countered by surfacing the middle-path capability-via-gate option rather than committing to a full architectural pivot.

**Concepts adopted (with implementation notes):**

- **Thin-orchestrator with fresh-subagent isolation, as a Tessera capability gated by suggestion-gate (principle #12).** Heavy work (research, planning, multi-file refactors, work spanning sessions) flows through orchestrator. Light work stays in main session. Implementation is staged: ship dogfood with current Tessera design, observe whether main-session context bloat becomes a real problem during decibel meter work, then layer in 5-6 core agent types (researcher, planner, executor, verifier, plus 1-2 specialized) if evidence justifies. The suggestion-gate decides per-task which mode to invoke.
- **File-based decision-and-output artifacts** augmenting the existing audit log. Where current design captures events (JSONL), additionally capture decisions and outputs as durable structured artifacts (CONTEXT-style files per phase). Schema and storage location: TBD during implementation. Tessera-idiom, not direct port of .planning/.
- **Package Legitimacy Gate using slopcheck (0xToxSec/slopcheck, MIT, pip-installable).** Universal Tessera baseline, not healthcare-only. Reasoning: slopsquatting is a real attack vector for any AI-assisted development project, not specific to compliance contexts. Adopt as a baseline credential/install-time check. Gate degrades safely if slopcheck unavailable (everything marked [ASSUMED], requires human checkpoint).
- **Plan Drift Guard concept** for the pipeline pattern (pass 1.3). Adopt the idea that generated plans should be verified against live source for symbol-reference correctness before execution. Implementation deferred — exact mechanism is a future design decision.
- **Byte-budget concept for workflows and skills** as protection against attention degradation. Adopt the principle (file size is a proxy for attention budget); defer specific tier numbers until we have evidence from real Tessera usage.

**Concepts considered and rejected (with reasoning):**

- **Adopting GSD entirely.** Rejected because the healthcare profile and related compliance IP would have to be rebuilt from scratch on GSD's architecture, with no native support for the profile-bundled extensions we designed. Net loss of meaningful work for unclear gain.
- **Two-stage hierarchical routing (namespace meta-skills).** Premature at our skill count (~50). Listed in observatory; re-evaluate if we ever cross 60+ skills.
- **Cross-runtime translation layer.** Deferred per principle #15 (design-aware, don't build until needed). Listed in observatory; re-evaluate if we genuinely want to try Codex or Gemini CLI for real work.
- **Full pivot to orchestrator pattern (vs capability-via-gate).** Rejected for now because it would delay Phase 4 install significantly and require substantial redesign before any dogfood evidence. Capability-via-gate gets the benefits where they matter without the cost where they don't.
- **Wave execution with parallel-commit safety patterns.** Skipped for now because we have no parallel executors yet. Becomes relevant when the orchestrator capability is built. Listed in observatory.
- **Thinking-models-specific prompt patterns** (separate patterns for o3/o4-mini/Gemini 2.5 Pro). Skipped because we don't differentiate prompts by reasoning-model tier today. Listed in observatory.
- **Capability registry pattern.** GSD's extension system is more developed than ours; their design philosophy (extensible capabilities) differs from Tessera's (compositional profiles). Skipped, listed in observatory.

**Re-evaluate trigger conditions:**

- GSD adds a project-profile-equivalent mechanism (per-project compositional extensions, especially compliance-aware)
- GSD adds a healthcare or finance profile
- Tessera maintenance burden exceeds 4 hours/week for 4 consecutive weeks (signal that solo maintenance is unsustainable)
- Lorenzo wants to use Codex, Gemini CLI, OpenCode, or another non-Claude-Code agent for real work (signal that cross-runtime matters)
- Next quarterly cadence review: 2026-09-22

---

## References

- https://github.com/open-gsd/gsd-core
- https://opengsd.net/
- https://github.com/open-gsd/gsd-core/blob/next/docs/explanation/context-engineering.md
- https://github.com/open-gsd/gsd-core/blob/next/docs/explanation/the-phase-loop.md
- docs/observatory.md (Tessera) — entries for concepts marked Watching from this ADR
- Tessera design doc, principles #12 (suggestion-gate), #15 (skill defaults as starting points), #16 (evaluate the ecosystem on a cadence)
- USENIX Security 2025 research on AI-generated package hallucinations (cited in GSD's Package Legitimacy Gate documentation)
