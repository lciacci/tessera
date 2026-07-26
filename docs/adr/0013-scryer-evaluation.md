# ADR-0013: Scryer — near-total overlap with iCPG, and the mirror that showed iCPG has 680 undisposed drift events

- **Date:** 2026-07-25
- **Status:** Watching
- **Decision driver:** New tool surfaced. Standing handoff item #6 ("Evaluate scryer — https://github.com/aklos/scryer. Run `/evaluate-framework`. Unread as of 2026-07-24").

> **Watching for:** (a) FSL-1.1-MIT converts to MIT (2028, two years from each release), or the project relicenses earlier; (b) a headless mode — the model core, extraction, and MCP server usable without the Tauri desktop app; (c) a second maintainer, or corp/foundation backing.
> **Next check:** 2026-09-23 (60 days)

---

## Target

- **Name:** Scryer
- **URL:** https://github.com/aklos/scryer
- **What it is:** A Tauri desktop app that maintains a living architecture model (`.scryer/model.scry`) mapped to source line ranges and tests, exposes it to coding agents over MCP, and detects drift between the model and the code.

---

## Side-by-side summary

| Dimension | Tessera | Scryer |
|---|---|---|
| Maturity | Solo, ~1 month dogfood, no external users | Solo (`aklos`), v0.3.5, multiple commits/day, ~2 weeks of visible history at eval time |
| Cross-runtime | Claude Code only (hooks, skills, settings.json) | Claude Code + Codex via MCP — genuinely cross-runtime |
| Original IP | Project profiles, override mechanism, gate/friction log, spend authorization, escalation packets, haziness scoring | The plan/committed model split; C4-shaped node taxonomy anchored to line ranges |
| Maintenance model | Solo | Solo |
| License | MIT | **FSL-1.1-MIT** — Fair Source, converts to MIT two years after each release. Not OSI-open today. |
| Community size | Single user (Lorenzo) | 95 stars, 12 forks |
| Primary problem solved | *The agent's own reliability* — instrumentation that makes agent failure visible (ADR-0006) | *Review bandwidth* — "agents write faster than you can review; what you meant drifts from what got built" |
| Distinct strength | Fail-loud instrumentation across the whole session lifecycle; nothing about it requires a GUI | A model that **leads** the code, with a human-editable draft as the unit of planning |

---

## 1. Identity & maturity

Solo project by `aklos`, Rust core + React/TypeScript frontend in a Tauri desktop shell, at v0.3.5. Commit cadence is high (several per day through 2026-07-12 → 07-24), including commits co-authored with Claude and one — "Track scryer's own architecture model" — that is a genuine dogfood signal: the tool is being pointed at itself, which is the same evidence standard Tessera applies to its own subsystems. 95 stars, 12 forks. Licensed **FSL-1.1-MIT**: Fair Source, source-available with a non-compete restriction, converting to MIT two years after each release. Bias risk is the **indie-tool** shape — the maintainer wants users, the risk is abandonment — but with an added wrinkle: FSL is the license of choice for projects that intend to monetize later, so a paid tier or hosted product is a plausible future, and the desktop-app form factor is consistent with that. Direction over the visible window is feature-adding, not stabilizing: this is a growing project, pre-1.0, with a shape that could still change substantially.

---

## 2. Problem-space overlap

The overlap is not partial. Scryer and **iCPG** are two implementations of the same idea: a graph of *what code is for*, anchored to symbols, checked for divergence from the code, and queried by an agent before it works.

| Overlap area | Tessera approach (iCPG) | Scryer approach | Classification | Notes |
|---|---|---|---|---|
| Intent graph anchored to code | ReasonNodes over 816 symbols, 879 edges, bootstrapped from git history | C4-shaped nodes (person/system/container/component/symbol) anchored to file + line ranges and to backing tests | **Different bet** | Same object. iCPG derives intent *from* existing code; scryer authors intent *before* it. |
| Drift detection | 6 weighted dimensions (spec/decision/ownership/test/usage/dependency) → composite score | 2 deterministic mechanisms, no LLM: source-mapped node whose file changed since last reconcile; project file the model does not cover | **Different bet** | Scryer's is a direct predicate; iCPG's is a proxy composite. See §4. |
| Drift disposition | *None.* No verb to adjudicate a drift event. | `flag_drift` / `reconcile_drift` / `mark_implemented` — explicit state transitions | **Conflicting** — and iCPG loses | This is the finding of the eval. See §6. |
| Code → intent reverse lookup | `tessera-decision-surface.sh` (PreToolUse) prints governing ADRs/observatory entries for the file about to be edited | `locate` MCP tool: file/symbol → anchored claims + owning node chain | **Compatible** — convergent design | Independent arrival at the same mechanism is evidence the mechanism is right. |
| Pre-task orientation | 3 canonical iCPG queries (`prior`, `constraints`, `risk`) | `orient` — one call returning governing nodes, claims, directives, pending work, drift | **Different bet** | One composite call vs. three named ones. Scryer's is likelier to actually get called. |
| Agent surface | Hooks + skills + CLAUDE.md, Claude Code only | MCP server, runtime-agnostic | **Different bet** | Tessera's channel discipline (principle #17) needs *deterministic* delivery; MCP tool calls are model-elective, hooks are not. |

**Tessera does not address (gaps in our design they fill):**
- **The model leading the code.** `planned.scry` vs `model.scry`, where the *diff between them is the plan*. Tessera has no artifact that says "what the code should be but isn't yet" — `_project_specs/todos/active.md` is prose, not a checkable object.
- **A human-editable view of the intent graph.** iCPG's graph is agent-written and CLI-read. Nobody edits it by hand, which is a large part of why nobody adjudicates it.
- **Cross-runtime reach.** Everything Tessera does dies outside Claude Code.

**They do not address (gaps in their design we fill):**
- Everything about *the agent's own reliability* — fatigue, compaction recovery, haziness, gate/friction logging, escalation packets, spend authorization. Scryer models the *system*; Tessera instruments the *session*. This is ADR-0006's line, and it holds.
- Fail-loud discipline. Scryer's drift detection is the kind of mechanism that can go quiet without announcing it; nothing in what is published addresses the check-on-the-check problem (Standing pattern #1).
- Downstream fleet distribution, doc-claim checking, override auditing.

---

## 3. Integration cost

**Adopt fully (replace iCPG with scryer):**
- Switching cost: high and mostly *shape*, not effort. Scryer is a **desktop GUI application**. Tessera's entire value delivery is headless — hooks, CLI, statusline, SessionStart injection. Adding a required GUI to the loop contradicts principle #17's channel discipline in the other direction: a signal that requires a human to open an app is weaker than one that fires on an event, not stronger.
- What is lost: iCPG's git-history bootstrap (816 symbols populated with no human authoring), the `bridge-icpg` → Mnemos goal feed, and the Rust/Tauri stack lands entirely outside this repo's Python+bash toolchain.
- What is gained: a working plan/committed split, deterministic drift, and cross-runtime reach — none of which require *adopting* scryer to obtain.

**Adopt patterns (steal ideas, keep iCPG):**
- Which patterns: drift disposition verbs; inline code evidence on a drift report; deterministic drift predicates; the plan/committed split.
- Implementation effort: the first two are small and land in `scripts/icpg/`. The third is a re-litigation of iCPG's 6-dimension scoring — medium, and it needs its own decision. The fourth is a design question, not a patch.

**Hybridize (run alongside):**
- Coexistence cleanliness: technically fine — separate `.scryer/` and `.icpg/` directories, separate processes, no hook collision.
- Conflict points: two intent graphs over one codebase is not a hybrid, it is a fork of the source of truth. Both would go stale, and the failure would be silent in both. Reject this path on principle, not on plumbing.

**Continue without (maintain iCPG forever):**
- Implicit maintenance burden: already being paid, and — per §6 — **partly unpaid**. 680 unresolved drift events is the interest accruing.
- Gaps that remain: no human-editable model, no plan-ahead-of-code artifact, Claude Code only.

---

## 4. Pattern-level vs implementation-level

| Pattern | Verdict | Notes |
|---|---|---|
| Drift disposition verbs (`flag` / `reconcile` / `mark_implemented`) | **Idea-only — adopt** | iCPG detects drift and has no way to close one. A detector with no dispose verb produces a monotonically growing number, which is indistinguishable from a broken detector. |
| Inline code evidence attached to a drift report | **Idea-only — adopt** | Scryer embeds the changed code in the drift report so the agent judges without re-reading the model tree. `icpg status` prints `[0.65] Drift detected: test(0.30), usage(1.00)` — a score with no referent. Unadjudicable by construction. |
| Deterministic drift, two predicates, no LLM | **Idea-only — open, do not adopt yet** | Directly implicates Standing pattern #3: *name the pain, not the artifact that correlates with it*. A 0.65 composite over six weighted dimensions is a proxy. "This file changed since we last reconciled it" is the pain. But retiring iCPG's dimensions is a bigger decision than this ADR should make — logged to the observatory. |
| Plan/committed split (`planned.scry` vs `model.scry`; the diff is the plan) | **Idea-only — open** | The strongest genuinely-new idea here. Tessera's specs are prose; a machine-diffable "intended state" would be checkable. Needs its own design pass; not a patch. |
| `locate` — code → owning claims | **Skip (already have it)** | `tessera-decision-surface.sh` is this, on a hook rather than a tool call. Convergence noted as validation. |
| `orient` — one composite pre-task call | **Idea-only — weak** | Merging iCPG's three queries into one is plausible, but the queries' problem is that they are not *fired*, not that there are three. A hook fires; a tool call is elective. |
| C4 node taxonomy (person/system/container/component/symbol) | **Skip** | Ceremony for a solo repo. iCPG's flat symbol+reason model is sufficient here. |
| Tauri desktop GUI, live component previews | **Skip** | Wrong form factor; no visual components in this repo. |
| MCP as the primary agent surface | **Skip for now** | Real cross-runtime value, but model-elective delivery is exactly what principle #17 warns about. Revisit if Tessera ever targets a second runtime. |
| FSL license | **Skip — a reason not to depend** | Not a pattern; a constraint. Source-available with a non-compete is a dependency Tessera should not take on a core subsystem. |

---

## 5. Lock-in & maintenance

**If we adopt:**
- Depends on their continued maintenance: the Rust extraction engine, the `.scry` format, the MCP server contract, and the desktop app binary. All four, at v0.3.x, from one person, under a license that does not permit a competing offering until 2028.
- Exit story: fork is legally constrained until conversion; a re-implementation in Python is feasible but is just "build iCPG again." Exit cost is real but not catastrophic because the *ideas* port freely — which is the whole argument for taking the ideas and not the code.

**If we do not adopt:**
- Cost of maintaining the equivalent: already sunk, and iCPG is on the books either way. The marginal cost of this ADR's adopted patterns is small.
- Lock-in risk to our own design: the honest one. iCPG has 10 ReasonNodes over 816 symbols and 680 undisposed drift events. Keeping it because it exists is sunk-cost protection; this ADR does not settle iCPG's kill/keep trial, and should not be read as evidence for it.

---

## 6. Decision

**Verdict:** **Watching** — adopt two patterns now, hold three questions open, take no dependency.

**Reasoning:**

Scryer is a good project solving a real problem with a defensible design, and Tessera should not adopt it. Three independent reasons, any one sufficient: it is a **desktop GUI application** where every Tessera mechanism is headless and event-fired; it is **FSL-licensed**, i.e. not open source until 2028, which is a bad dependency for a core subsystem; and it **overlaps iCPG almost completely**, so adopting it means running two intent graphs or killing one — and killing iCPG on the strength of a v0.3.5 solo project's README is not a decision this evidence supports. Its strongest genuinely-distinct idea, the model leading the code via a `planned` / `committed` split, is an idea Tessera can hold without the app.

**The most valuable output of this evaluation is not about scryer.** Reading scryer's drift-disposition verbs and then running `icpg status` produced this: **680 unresolved drift events.** iCPG detects drift, scores it, prints it — and has no verb to close one. That number cannot go down. It is therefore not a measurement of anything; it is a counter that only increments, and a counter that only increments is indistinguishable from a broken detector. This is **Standing pattern #2** exactly — *it did not break, it produced something plausible* — and it is a fail-open instance for Spec 11's sweep. The top five drift events are byte-identical (`[0.65] test(0.30), usage(1.00)`) with no symbol, no file, no diff: unadjudicable by construction, which is why 680 accumulated without anyone noticing. Scryer was the mirror. That finding is worth more than the verdict.

**Biases named.** (1) *Excitement bias* — scryer's framing ("the model leads; the code follows") is articulate and made me want it to be right; I checked the license and form factor before the ideas, deliberately, to avoid reasoning backwards from wanting to adopt. (2) *Sunk-cost protection for iCPG* — 816 symbols and a git-history bootstrap are real work, and I noticed a pull toward defending iCPG's 6-dimension scoring against scryer's 2-predicate design. On the evidence, scryer's is better, and I have marked it open rather than resolving it in iCPG's favor. (3) *Familiarity bias* — I understand iCPG's model because it is documented in this repo, and scryer's only through its README; I have not run it, and the eval is README-and-commits-deep, not usage-deep. That is a real limit on this ADR's confidence, and it is a reason the verdict is Watching rather than Reject.

**Concepts adopted (with implementation notes):**
- **Drift disposition verbs for iCPG.** `icpg drift resolve <id> --note "<why>"` and a `dismissed` state, so an adjudicated drift event leaves the open set. Without this, `unresolved drift: N` is decoration. Lands in `scripts/icpg/`.
- **Evidence on the drift report.** Every drift event must print the symbol, the file, and what changed. A report a human cannot act on is a report nobody acts on — which is the 680.

**Concepts held open (logged to the observatory, not decided here):**
- **Deterministic two-predicate drift vs. iCPG's 6-dimension composite.** Standing pattern #3 says the composite is a proxy. Retiring it is a separate decision needing its own evidence.
- **The plan/committed split.** A machine-diffable "intended state" artifact. Design pass, not a patch.
- **Whether the 680 events mean iCPG's detector is miscalibrated, or merely undisposable.** Answerable only after the two adopted patterns land and the backlog is actually worked.

**Concepts considered and rejected (with reasoning):**
- **Adopting scryer itself** — GUI form factor, FSL license, duplicate of iCPG. Any one is disqualifying.
- **Hybridizing** — two intent graphs over one codebase forks the source of truth, and both would go stale silently.
- **C4 node taxonomy** — ceremony without payoff at this repo's scale.
- **MCP as the agent surface** — model-elective delivery, which principle #17 specifically warns against. Reconsider only if Tessera targets a second runtime.

**Re-evaluate trigger conditions:**
- Scryer ships a **headless mode** — model core, extraction, and MCP server usable without the desktop app.
- The license converts to MIT, or is changed to an OSI-approved license earlier.
- A second maintainer joins, or the project takes corp/foundation backing.
- **Tessera itself targets a second agent runtime** (Codex, or any non–Claude Code harness) — at that point cross-runtime reach stops being a nice-to-have and scryer's MCP-first design becomes directly relevant.
- The iCPG kill/keep trial concludes **kill** — if Tessera is going to have no intent graph, the question of whether to have someone else's reopens.
- Next cadence review: 2026-09-23 (60 days, Watching).

---

## References

- https://github.com/aklos/scryer — README, commit log through 2026-07-24, v0.3.5
- `docs/adr/0006-instrumentation-not-control.md` — the line this ADR applies: Tessera instruments the session, scryer models the system
- `docs/design-principles.md` §"iCPG (Maggy)" and the 6 drift dimensions — the overlapping design
- `docs/design-principles.md` principle #16 (evaluate on a cadence), principle #17 (channel, not convention)
- `icpg status` run 2026-07-25 — 10 ReasonNodes, 816 symbols, 879 edges, **680 unresolved drift**
- Standing patterns #1 (the check that dies silently), #2 (fail-open produces something plausible), #3 (name the pain, not the proxy)
