# ADR-0021: Deep Agents — rejected on layer, and the mirror is that our prefix measurement is frozen prose

- **Date:** 2026-08-08
- **Status:** Accepted
- **Executed:** not yet
- **Decision driver:** New tool surfaced. Lorenzo: "eval https://www.langchain.com/blog/deep-agents-v0-7".

---

## Target

- **Name:** Deep Agents (`deepagents`), and its sibling CLI Deep Agents Code (`dcode`)
- **URL:** https://github.com/langchain-ai/deepagents — docs at https://docs.langchain.com/deepagents
- **What it is:** An opinionated Python/TypeScript **agent harness** layered on LangChain's `create_agent` and the LangGraph runtime — planning, a virtual filesystem, sub-agents, context management, skills, and human-in-the-loop, bundled as overridable middleware. v0.7 (2026-07-29) cut base input tokens ~65%.

---

## Side-by-side summary

| Dimension | Tessera | Deep Agents |
|---|---|---|
| Maturity | Solo, ~2 months dogfood, 6 downstream projects | Created 2025-07-27, pushed daily, ~100 contributors, near-daily releases. Mature and fast-moving. |
| Cross-runtime | Claude Code only (hooks, `settings.json`, skills) | Model-agnostic by construction; `dcode` is its own runtime |
| Original IP | Project profiles, override mechanism, gate/friction log, spend authorization, escalation packets, haziness scoring, restore receipts | The middleware stack and its override-in-place protocol; the virtual filesystem as context layer; a 135-eval harness benchmark suite |
| Maintenance model | Solo | Corp-backed (LangChain Inc, VC-funded). LangSmith is the commercial product. |
| License | MIT | MIT |
| Community size | Single user (Lorenzo) | 27,521 stars · 3,841 forks · 205 open issues |
| Primary problem solved | *The agent's own reliability* — instrumentation that makes agent failure visible (ADR-0006) | *Building* a long-horizon agent — supplying the loop, the tools, and the context policy |
| Distinct strength | Fail-loud instrumentation fired on events, not elected by a model | An owned agent loop, and an eval suite that licenses changes to it |

---

## 1. Identity & maturity

MIT, 27.5k stars against 3.8k forks and 205 open issues — usage, not just attention. Created 2025-07-27, pushed 2026-08-07, ~100 contributors with a clear core (`mdrxy` 1,632 commits, `eyurtsev` 244, `ccurme` 65, `hwchase17` 44). Releases are near-daily across `deepagents`, `deepagents-code`, and a fleet of sandbox partner packages. This is a healthy, well-resourced project; none of the abandonment or seeding risks that shaped ADR-0013 and ADR-0020 apply.

**Bias risk is vendor loss-leader, and it is the LangSmith shape.** LangChain Inc sells LangSmith — tracing, evaluation, deployment. The harness is genuinely MIT and genuinely portable, and the README's model-agnosticism is real. The pull is that the things which make the harness *legible* — trace inspection, the eval scorecards, deployment — are the paid platform. That is not a reason to discount the engineering; it is a reason to be precise that the free thing and the useful thing are not the same thing, exactly as ADR-0020 found with Braintrust.

**One correction worth recording, because it nearly entered this ADR as fact.** The first automated fetch of the repo reported the maintainer as "LangChain AI (Anthropic's open-source division)." That is false — LangChain Inc is an independent, VC-backed company with no Anthropic ownership. The summary was fluent and wrong, and it was caught only by already knowing the answer. Standing pattern #2's shape aimed at a research step: it did not fail, it produced something plausible.

---

## 2. Problem-space overlap

**The headline is the layer mismatch, and it is not close.** Deep Agents **owns the agent loop**: it assembles the prompt, defines the tools, decides when to summarize, and spawns the sub-agents. Tessera **rents one**. Everything Tessera does is instrumentation applied from outside a runtime it does not control — which is ADR-0006 stated as a structural fact rather than a preference. There is no configuration of Tessera that consumes `deepagents`, and no configuration of `deepagents` that would want Tessera's hooks.

| Overlap area | Tessera approach | Their approach | Classification | Notes |
|---|---|---|---|---|
| Harness prompt budget | ~15.6k eagerly loaded per session, measured once (2026-07-30) and never since | *Base input tokens* as a named, tracked, per-release metric: ~6k → ~2k | **Different bet — and theirs is a discipline, not a number** | The find. See §6. |
| Licensing a harness change | Structural argument (ADR-0008: content with no surface in this repo) | 135 evals / 8 categories / 4 models, reward + tokens + cost | **Gap in ours, and one we structurally cannot close** | We do not own the loop, so there is nothing to A/B. |
| Context management at the limit | Mnemos: fatigue bands, PreCompact checkpoint, restore on any discontinuity | `SummarizationMiddleware`, default trigger at 85% of the window, threshold configurable | **Conflicting by ownership, not by design** | Claude Code decides when it compacts. We can only observe and recover; they can pre-empt. |
| Replacing a default in the stack | ADR-0009 curation: skills toggle **on/off**; hook arrays **concatenate** (ADR-0001) | Pass a middleware whose `.name` matches a default — it replaces in place | **Gap in ours** | Their #1 user ask for six months. Users were writing "hacky stuff" to strip defaults. Same wall, and we have no answer either. |
| Skill format | `SKILL.md` + `name`/`description` frontmatter, on-demand load | The same — explicitly the Agent Skills specification (agentskills.io), three-level progressive disclosure | **Compatible — already interoperable** | Bears on ADR-0010: the corpus is portable today, unintentionally. |
| Where boundaries are enforced | Deny-by-default `PreToolUse` guards; principle #17 (channel, not convention) | "Trust the LLM" — *"Enforce boundaries at the tool/sandbox level, not by expecting the model to self-police"* | **Compatible — third independent convergence** | See §6. |

**Tessera does not address (gaps in their design they fill):**
- **A repeatable measurement of its own prompt budget.** Ours is a prose figure; theirs is a metric with a definition and a release history.
- **Override-in-place of a default.** Curation is a switch; theirs is a substitution.

**They do not address (gaps in their design we fill):**
- **Everything about the agent's own reliability** — fatigue, restore integrity, escalation, spend envelopes, degraded reporting, the friction log. ADR-0006's line holds unchanged.
- **Fail-loud discipline.** `dcode`'s hook doc records that non-JSON stdout is context only on `SessionStart`/`UserPromptSubmit` and a *diagnostic* everywhere else — the exact rule that silenced three Tessera hooks for weeks. They documented the trap; they did not build anything that tells you when you have fallen into it.

---

## 3. Integration cost

**Adopt fully / hybridize: both columns are empty, and that is the finding.** There is no artifact to install. Tessera does not run an LLM agent loop in-process — polyphony orchestrates containerized coding-agent sessions, it does not host graphs. Adoption would require Tessera to first become a thing it is not.

**Adopt patterns (steal ideas, keep Tessera):** one pattern, cheap — the prefix metric as a *reproducible measurement* rather than a frozen figure. Hours.

**Continue without:** the maintenance burden is already being paid and nothing here reduces it. The gap that remains is the honest one: no venue for measuring whether a harness change helped or hurt.

**A fourth path this eval surfaced and which the methodology has no column for — port the harness to a second runtime.** `dcode`'s hook contract is a near-clone of Claude Code's: `SessionStart` (`startup`/`resume`/`clear`/`compact`), `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `PreCompact`, `Stop`, exit code `2` as block, `hookSpecificOutput.additionalContext`, and `CLAUDE_PROJECT_DIR` — that variable name, unchanged. It adds events we lack: `PostToolUseFailure`, `SubagentStart`/`SubagentStop`, `SessionEnd`, `PermissionRequest`. It also carries a consent model we do not have — project-scoped hooks require an explicit workspace-trust prompt before they load.

**The cost is therefore not uniform, and the split matters more than the total.** The gate, spend-guard, degraded, and decision-surface layer is a *config translation* — `settings.json` to `.deepagents/hooks.json`. The Mnemos measurement layer does not port at all: `fatigue.json` is fed by Claude Code's statusline, haze ingests `~/.claude/projects/*.jsonl`, and the eager load rides CLAUDE.md's `@` imports where `dcode` uses `AGENTS.md`. **So the side-by-side's "Claude Code only" line is a claim about the measurement half, not the control half.** It has been unfalsifiable since ADR-0001 and is now priced. It is recorded here and nothing more — see §6.

---

## 4. Pattern-level vs implementation-level

| Pattern | Verdict | Notes |
|---|---|---|
| **Base input tokens as a tracked metric** | **Idea-only — ADOPT** | The one thing here that lands. See §6. |
| **An eval suite as the licence for harness changes** | **Idea-only — NOTED, not adoptable** | We do not own the loop. The nearest venue is Mnemos's 121-session corpus, which is observational, confounded, and scored by a detector at P≈0.4 / R≈0.5 whose correction density is a floor. It cannot resolve an A/B and should not be asked to. |
| **Boundaries at the tool layer, not model self-policing** | **Idea-only — already ours** | Convergence, not adoption. §6. |
| **Override-in-place by `.name`** | **Skip — real gap, premature** | Six downstreams, one author, and no instance yet of a project needing to replace a Tessera default rather than disable it. Revisit if one does. |
| **Agent Skills spec conformance** | **No action — already conformant** | Worth knowing that ADR-0010's corpus is portable; nothing to do. |
| **`PostToolUseFailure` / `SubagentStart|Stop`** | **Skip — wishlist against the wrong vendor** | `PostToolUseFailure` is the native channel `tessera-degraded` hand-wires into bail-out branches. We cannot ask Claude Code for it here. |
| **Removing the planning tool on eval evidence** | **Skip — not our call to make** | Claude Code owns `TodoWrite`. Their result does not transfer to a harness they did not measure. |
| **`deepagents` as a dependency** | **Skip — wrong layer** | §3. |
| **LangSmith for tracing / eval / scorecards** | **Skip — and it is the dependency to avoid** | Provider-coupled judgement, directly against ADR-0014's reason for the review-backend seam. |
| **Virtual filesystem, `SummarizationMiddleware`, sub-agent middleware** | **Skip — owned by the runtime** | Claude Code decides these. Nothing to adopt. |

---

## 5. Lock-in & maintenance

**If we adopt (the one pattern, per §6):** nothing depends on their continued maintenance. A metric definition read once from a blog post keeps working if the project sunsets tomorrow.

**If we do not adopt:** no cost, because there is nothing to maintain. The real lock-in this eval exposes is **ours to Claude Code**, and it is narrower than assumed — the control surface would port for the price of a config translation; the measurement surface would not port at all. That is worth knowing and is not worth acting on today.

---

## 6. Decision

**Verdict: Reject.** No dependency, no adoption path, no Watching status — and the last of those is a deliberate departure from the two evals before it.

**Reasoning.**

**Why Reject and not Watching.** *Watching* means there is a condition under which we would adopt. For a Python library that supplies an agent loop, there is none — Tessera does not build agents, and a Watching status with no reachable adoption path is a fiction that buys a `Next check` date and generates work on a question that will never turn. **Named bias, because it is the reason the first draft of this ADR said Watching: anchoring on ADR-0020.** The previous eval landed Watching-with-dated-triggers and was right to, because Agent Behavior is a file format Tessera could plausibly have written files in. I reached for the same shape without checking that the premise transferred. Lorenzo pushed back on it, and the pushback was correct.

**The one adopted pattern, and why it is not the release's headline.** v0.7's claim is that a 65% base-prompt cut held performance steady. **Their own evidence does not establish that, and they say so:** reward confidence intervals span zero for *every* model. What is statistically clear is the token and cost reduction — the trivially measurable half. So this is **not** external licence to trim Tessera's ~15.6k eager prefix, and `docs/observatory.md` → "The eager prefix is ~15.6k tokens — and the size of it is NOT the argument" survives contact intact. **The counter-datum, stated because I am weighting it less than it may deserve:** the same blog cites Anthropic cutting over 80% of Claude Code's system prompt for Opus 5 and Fable 5 with no measurable drop in coding evals. That is a stronger signal toward trimming than anything in v0.7's own numbers, from a party with far better instrumentation, and it is the thing most likely to make this paragraph look wrong later.

What *does* transfer is upstream of the trim question. They treat **base input tokens** as a named metric with a definition — *"tokens associated with the builtin prompt, tools, and middleware"* — measured per default turn and tracked release to release. Tessera measured its equivalent **once**, on 2026-07-30, as a chars/4 estimate frozen in a paragraph of prose, and has since split the standing-patterns block into two hook outputs and grown `CLAUDE.md` in most sessions. **A one-shot number in prose that nothing recomputes is precisely the doc-claim class this repo has paid for six times**, and the fix is the one this repo already knows: make it a script, and let doccheck assert that the quoted figure matches what the script measures. **Report drift; do not gate on a ceiling** — the observatory entry established that size is an artifact and not the pain, and a threshold would be principle #3 aimed at the eager load. The meter does not reopen the trim question. It makes the number honest enough that reopening it would mean something.

**The portability fact, recorded once and given no trigger.** §3 prices it: control surface ports as a config translation, measurement surface does not port at all. **Named bias: this is the shiniest finding in the eval and I went looking for it after reading `HOOKS.md` — motivated search.** Its correct weight is one paragraph. A Watching trigger on "does Lorenzo switch runtimes" is decoration, because that is a thing you would know without an ADR telling you. What the paragraph buys is that a line in the side-by-side table which has been unfalsifiable since ADR-0001 now has a price attached.

**Convergence, third instance.** Their security posture is *"enforce boundaries at the tool/sandbox level, not by expecting the model to self-police"* — principle #17 and the `PreToolUse` spend guard, arrived at independently by a project with 27.5k stars and no knowledge of this one. ADR-0013 recorded `locate` ↔ `tessera-decision-surface.sh`; ADR-0020 recorded cost-sensitive-actions ↔ the spend gate; this is the third. At three, the convergence itself is the signal: it is the cheapest external validation a solo framework gets, and it is evidence about the *mechanism class*, not about any particular implementation.

**Remaining biases named.** (1) *Deference and its inverse* — 27.5k stars against a single user invites both over-crediting and defensive dismissal; the methodology's six dimensions exist so neither is the answer, and the layer mismatch in §2 is a structural finding that would hold at any star count. (2) *Convenience* — discovering that their statistics support a position this repo already holds is comfortable, which is why the Anthropic counter-datum is stated above rather than buried. (3) *Familiarity/substrate loyalty* — this evaluation was written inside Claude Code, by an agent whose entire operating context is the harness under comparison. (4) *Depth limit, stated plainly* — this is a docs-and-metadata evaluation. I have not installed `deepagents`, not run `dcode`, and not read the middleware source. For a Reject-on-layer that is sufficient, because the layer mismatch is visible from the README; it would not be sufficient for an adopt.

**Concepts adopted (with implementation notes):**
- **A reproducible eager-prefix meter.** A script that recomputes the four components measured on 2026-07-30 (`CLAUDE.md`, the two eagerly-loaded skills, the SessionStart surfacer output) plus the checkpoint, and a `scripts/doccheck.py` assertion tying the figure quoted in `docs/observatory.md` to what the script measures. **No threshold and no gate** — drift is reported, not failed. Follows the caching work's meter-before-marker rule; the meter is the deliverable here, and there is no marker.

**Concepts considered and rejected (with reasoning):**
- **`deepagents` as a dependency** — wrong layer. Tessera instruments a loop it does not own; adopting would require becoming something else first.
- **LangSmith for tracing, evals, or scorecards** — provider-coupled judgement, against ADR-0014's seam.
- **An eval suite licensing harness changes** — the right discipline, structurally unavailable. Named as a standing gap, not a task.
- **Their conclusion that a planning tool does not earn its keep** — measured on their harness, not ours, and Claude Code owns `TodoWrite` regardless.
- **Middleware override-in-place** — a genuine gap against ADR-0009's on/off curation, premature at six downstreams with no project yet blocked by it.
- **Porting the control surface to `dcode`** — priced in §3, no demand, recorded without a trigger.

**Re-evaluate trigger conditions:**
- Tessera, polyphony, or a downstream needs to run an **LLM agent loop in-process** rather than spawning a coding-agent CLI — at which point the layer mismatch that decided this ADR disappears and the whole evaluation reopens.
- Lorenzo adopts `dcode` as a primary or secondary coding runtime.
- A downstream project is **blocked** by curation's on/off limit and needs to replace a Tessera default rather than disable it.
- The Agent Skills specification gains implementers such that skill portability becomes a live interop question for ADR-0010.
- Next cadence review: 2026-11-06 (90 days, Accepted).

---

## References

- https://www.langchain.com/blog/deep-agents-v0-7 — Sydney Runkle, 2026-07-29; full text read 2026-08-08, including the confidence-interval footnote
- https://github.com/langchain-ai/deepagents — `README.md`, `libs/code/HOOKS.md`, `libs/evals/README.md`, `libs/evals/EVAL_CATALOG.md` (135 evals / 8 categories), `libs/code/ARCHITECTURE.md`; repo metadata, releases, and contributor list read 2026-08-08
- https://docs.langchain.com/oss/python/deepagents/skills and https://agentskills.io/specification — the skill format Tessera already conforms to
- `docs/observatory.md` → "The eager prefix is ~15.6k tokens — and the size of it is NOT the argument" (2026-07-30) — the position this eval tested and did not overturn
- `docs/observatory.md` → "Prompt caching: the fleet reads at 0% because nothing opts in" (2026-07-30) — the meter-before-marker rule the adopted pattern follows
- `docs/adr/0001-gsd-evaluation.md` — hook arrays concatenate; the origin of the override gap
- `docs/adr/0006-instrumentation-not-control.md` — the line this ADR restates as a structural fact: we do not own the loop
- `docs/adr/0009-skill-delivery-is-curation-not-copying.md` — curation is on/off, which is the gap §2 names
- `docs/adr/0014-review-backend-seam.md` — why a provider-coupled judge is the dependency to refuse
- `docs/adr/0013-scryer-evaluation.md`, `docs/adr/0020-agent-behavior-evaluation.md` — the two prior mirror-shaped evals, and the two prior convergence instances
- `docs/design-principles.md` principle #16 (evaluate on a cadence), #17 (channel, not convention), #3 (name the pain, not the proxy)
- Standing patterns #2 (fail-open produces something plausible), #3 (measure the property, not the artifact), #9 (running is not reaching), #12 (a true report can still be a false green)
