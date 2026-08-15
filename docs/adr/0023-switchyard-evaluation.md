# ADR-0023: Switchyard — rejected on layer, and the mirror is that ADR-0002's "impossible" was only impossible *in-harness*

- **Date:** 2026-08-15
- **Status:** Watching
- **Decision driver:** New tool surfaced. Lorenzo, in the conclave repo: "evaluate https://github.com/NVIDIA-NeMo/Switchyard".
- **Corrected same day (2026-08-15), pre-acceptance:** a second `/code-review` pass found the §6 chronology inverted — conclave's proxy harness postdates ADR-0002 by three weeks rather than predating it, making this a *missed reconciliation* rather than an overlooked refutation. The verdict, the layer rejection, and the adopted patterns are unchanged; only the dating and the strength of the mirror moved. Recorded here rather than silently, per the not-edited convention — the decision did not change, so this is not a superseding ADR.

> **Watching for:** Switchyard dropping the "not for production use" label (a v1.0 or an
> explicit production-ready declaration), **or** any published evaluation of its routers'
> quality/cost effect. Either one changes whether the ADR-0002 reopening in §6 is worth
> acting on. The known issue *"a cancelled request can still incur provider cost"*
> closing is a secondary signal.
> **Next check:** 2026-10-14 (60 days)

---

## Target

- **Name:** Switchyard (`nemo-switchyard` on PyPI, `switchyard-server` / `switchyard-libsy` as Rust crates)
- **URL:** https://github.com/NVIDIA-NeMo/Switchyard
- **What it is:** An NVIDIA-built **LLM routing proxy** in Rust — it accepts OpenAI-Chat, OpenAI-Responses, or Anthropic-Messages traffic, normalizes it to a provider-neutral type, picks a backend by policy, and translates back, so a client can be re-targeted without touching client code.

---

## Side-by-side summary

| Dimension | Tessera | Switchyard |
|---|---|---|
| Maturity | Solo, ~2.5 months dogfood, 6 downstream projects | Public 2026-06-30, v0.2.0 on 2026-08-10. **Self-labelled "Experimental software. Not for production use."** |
| Cross-runtime | Claude Code only (hooks, `settings.json`, skills) | Runtime-agnostic by construction — it is on the wire, below any runtime |
| Original IP | Project profiles, override mechanism, gate/friction log, spend authorization, escalation packets, haziness scoring, restore receipts | The provider-neutral translation type across three wire formats; the escalation *latch*; the stage router's corroborative signal scoring |
| Maintenance model | Solo | Corp-backed (NVIDIA), 15+ contributors, all NVIDIA-affiliated logins |
| License | MIT | Apache 2.0 |
| Community size | Single user (Lorenzo) | 1,565 stars · 143 forks · 98 open issues+PRs · **5 watchers** |
| Primary problem solved | *The agent's own reliability* — instrumentation that makes agent failure visible (ADR-0006) | *Traffic placement* — getting each request to the cheapest backend that can still do it |
| Distinct strength | Fail-loud instrumentation fired on events, not elected by a model | Re-targets a live client per request, with no cooperation from the client |

---

## 1. Identity & maturity

Created 2026-05-19, first public release 2026-06-30, v0.2.0 on 2026-08-10, last push 2026-08-14 — **under three months old in public**, and v0.2.0 was a ground-up rewrite (Python proxy + YAML routing → native Rust server + `libsy`). 1,565 stars against 143 forks and 98 open issues/PRs, from 15+ contributors whose logins are uniformly NVIDIA-affiliated (`nachiketb-nvidia` 54, `grahamking` 46, `elyasmnvidian` 22, …). This is a corp team shipping fast, not a community. Apache 2.0. **5 watchers against 1,565 stars** is worth naming: attention far ahead of committed use, consistent with a three-month-old repo. None of ADR-0013's or ADR-0020's abandonment risk applies; the risk here is churn, and the README says so — API and algorithm changes are *expected* before v1.0.

**Bias risk is hardware loss-leader, and it is a different shape from ADR-0020's Braintrust or ADR-0021's LangSmith.** NVIDIA does not sell a routing SaaS. It sells GPUs and NIM. A good open proxy that makes multi-backend self-hosting easy pulls inference *onto NVIDIA silicon*, which is the commercial return. The code is genuinely Apache 2.0 and genuinely routes to OpenAI, so the lock-in is weak; the pull is strategic, not contractual. That is a milder version of the pattern, and it should not discount the engineering.

**Bias I noticed in myself, recorded because it nearly shaped the verdict:** the escalation router is an off-the-shelf implementation of a cascade that conclave has deferred for months, and finding it produced an immediate pull toward "NVIDIA shipped it, so the pattern must pay." **It does not follow, and the evidence is absent.** Switchyard publishes **no** quality or cost evaluation for any of its routers. The only number in the routing docs is that the stage router's default `confidence_threshold = 0.5` "was derived from SWE-Bench Pro Python-75 calibration" — a calibration of a knob, not a measurement of an outcome. Its own guidance is to measure in your environment via `/v1/stats`. Convergence on *shape*, from a well-resourced lab, and nothing more.

---

## 2. Problem-space overlap

| Overlap area | Tessera approach | Their approach | Classification | Notes |
|---|---|---|---|---|
| **Choosing a model per unit of work** | ADR-0002: classify the prompt at submit time with a local 3B (`qwen2.5-coder:3b`, 2–8s/prompt), cache the tier, apply it at **dispatch gates** (subagent spawn, workflow `agent({model})`) | Route **every request** at the proxy, by classifier, conversation signals, weights, or session affinity | **Conflicting by layer** | Both answer "which model", at different layers, with incompatible enforcement points. See §6. |
| **Deriving tier without paying for a classifier** | Pays a local model call on every prompt; ADR-0002 booked the 2–8s as a known negative | Stage router reads signals **already in the transcript** — recent errors, spinning, exploring → capable; write/edit intensity → efficient. No extra model call. | **Gap in ours** | The one genuinely transplantable idea. See §4. |
| **Escalating when work is going badly** | No equivalent. ADR-0002 classifies *predicted* difficulty, once, before the work | Escalation router judges the **completed turn**, counts consecutive escalate verdicts, and **latches** the session to the strong tier | **Different bet** | Predicted-difficulty vs observed-failure. Theirs needs a judge call per unlatched turn; ours needs none after the first. |
| **Not letting a model elect its own instrumentation** | ADR-0006: fail-loud, fired on events, not elected by a model | Routing verdicts come from an LLM judge/classifier in two of four algorithms | **Conflicting** | Their control path is model-elected, which is the thing ADR-0006 was written against. |
| **Observability of the decision** | Gate log, friction log, restore receipts — narrative, in-repo, auditable by reading | Prometheus counters + OTel: requests, errors, latency, tokens, routing overhead, `/v1/stats` | **Compatible, and theirs is better instrumented** | Ours records *why*; theirs records *how much*. Different questions. |
| **Wire-format portability** | ADR-0014 made review model-portable at the *code seam* | Portability at the *protocol* seam — three formats, one neutral type | **Different bet** | Theirs is more general and costs a network hop plus a third party in the data path. |

**Tessera does not address (gaps in their design they fill):**
- **Per-request re-targeting of a live client.** Tessera cannot do this at all; see §6.
- **Quantitative routing telemetry.** Tessera has no token/latency/cost counters anywhere.
- **A tier signal that costs nothing.** Ours costs a model call per prompt.

**They do not address (gaps in their design we fill):**
- **Any evidence that routing pays.** No published quality or cost evaluation, for any of the four algorithms.
- **Why a decision was made.** Prometheus counts outcomes; nothing records reasoning, and there is no analogue of the gate log or a restore receipt.
- **Anything about the agent's own reliability.** Switchyard is indifferent to whether the agent is confabulating; it places traffic.

---

## 3. Integration cost

**Adopt fully (replace Tessera with it):** Not coherent. Tessera is instrumentation applied to a runtime it does not own; Switchyard is a data plane. There is no configuration of one that consumes the other. Switching cost is undefined because the products are not substitutes.

**Adopt patterns (steal ideas, keep Tessera):** One candidate — the stage router's transcript-derived signals as a **pre-pass in `tier-classify-hook`**, escalating to the qwen classifier only when signals are inconclusive. Effort is small (the signals are counts over recent messages, and the hook already runs at `UserPromptSubmit`). **The blocker is that the heuristic is unvalidated by its own authors**, so adopting it means adopting an unmeasured rule. See §4.

**Hybridize (run alongside):** Technically clean and already demonstrated — conclave's `harness/run-local-cc.sh` points Claude Code at a LiteLLM proxy today, and Switchyard's `switchyard launch claude` is the same move with a better-built proxy. But it puts a pre-alpha third party **in the data path for every token**, including a known issue where *"buffered upstream work continues after the client disconnects, so a cancelled request can still incur provider cost."* For Tessera, whose subject is reliability, that is a poor trade.

**Continue without (maintain own forever):** Cheapest, and the honest baseline. ADR-0002 already shipped and works. What remains unaddressed is the main-thread limitation — which §6 shows was never as absolute as ADR-0002 recorded.

---

## 4. Pattern-level vs implementation-level

| Pattern | Verdict | Notes |
|---|---|---|
| Transcript-derived tier signals (errors / spinning / exploring vs edit intensity) | **Idea-only** | Directly addresses ADR-0002's booked 2–8s/prompt cost. Take the *signal set*, not the `0.46`/`0.5` arithmetic — that constant is calibrated to SWE-Bench Pro Python-75 and to *their* tier pair, and would be cargo-culted here. Must be measured before it displaces the qwen classifier, not after. |
| Escalation **latch** (once escalated, stay escalated for the session) | **Idea-only** | Cheap and independent of the rest. It bounds judge cost by construction and matches how a hard session actually behaves. Applies to ADR-0002's cache even without a judge. |
| LLM-judge-decides-the-route | **Skip** | ADR-0006. A model electing the control path is the thing that ADR was written against, and a judge call per unlatched turn re-imports ADR-0002's rejected "monitoring cost exceeds the savings it finds". |
| Provider-neutral translation across three wire formats | **Skip** | Real engineering, zero surface in Tessera. Tessera is Claude-Code-only by design; ADR-0014 put portability at the code seam already. |
| Prometheus/OTel routing telemetry | **Skip (for now)** | Wanted, but the dependency is not the way to get it, and Tessera has no counter infrastructure to hang it on. |

---

## 5. Lock-in & maintenance

**If we adopt** (either pattern-only or hybrid):
- Pattern-only depends on **nothing** of theirs — the signals are a paragraph of prose we reimplement. Lowest possible lock-in.
- Hybrid depends on their continued maintenance for **every token of every session**, at v0.2.0, in a repo that says not for production. Exit is real but not free: revert to direct endpoints, or to LiteLLM as conclave does now.

**If we do not adopt:**
- Cost of the equivalent is roughly zero, because the equivalent is not wanted. Tessera does not need a data plane.
- The lock-in risk to our own design is the opposite one and it is the finding of this ADR: **ADR-0002 recorded a limitation as structural when it was contingent on a deployment assumption** — that Claude Code talks to Anthropic directly — and for the four weeks after a sibling repo built a proxy sitting in that exact position, neither repo reconciled the two.

---

## 6. Decision

**Verdict:** **Adopt patterns (idea-only); reject the dependency.** Status **Watching** on the one live question below.

**Reasoning.**

**Rejected on layer, and it is not close.** Switchyard owns a data plane; Tessera owns none, and ADR-0006 settled that Tessera is instrumentation applied from outside a runtime it does not control. Two of the four routing algorithms put an LLM judge on the control path, which is precisely what ADR-0006 rules out. Even setting that aside, the adoption case rests on evidence that does not exist: **not one published quality or cost number for any router.** I want to be exact about what that does and does not mean — it is not a criticism of a three-month-old project, and it is not evidence the routers *don't* work. It means there is nothing here to adopt *on*.

**The mirror, and it is the reason this ADR is worth its number.** ADR-0002 rejected the running-watcher alternative on the grounds that it *"can't apply mid-flight"*, booked as a standing consequence that **"main-thread application stays impossible (harness limitation) — advisory only"**, and wrote its re-evaluate trigger as *"Claude Code exposes a way to set the main-session model mid-turn **from a hook**."* **The trigger names a mechanism where it meant a capability**, and it therefore cannot fire on the application point ADR-0002 did not consider: an **interposed proxy at `ANTHROPIC_BASE_URL`**, which needs no hook and no cooperation from the harness.

**Two claims here, and they must not be merged — merging them is how this correction goes wrong.**

1. **That the application point exists and works is demonstrated, in-house.** Conclave's `harness/run-local-cc.sh` drives Claude Code's main thread through a LiteLLM Anthropic↔Ollama proxy — a working instance of the layer ADR-0002 never examined. **Chronology, corrected after review flagged the first draft as inverted:** it landed 2026-07-17 (`60f2ea6`), *three weeks after* ADR-0002 executed, so it was never a standing refutation Tessera overlooked. The failure is a **missed reconciliation** — conclave built the counter-case, and for the four weeks since, neither repo revisited the claim. "Built and exercised" is also the honest verb: conclave's own notes record the harness has produced almost no data.
2. **That a *policy* can be applied at that point per-request is Switchyard's claim, and nobody here has tested it.** Conclave's proxy binds `ANTHROPIC_MODEL` once at launch against a static two-entry map (`harness/litellm_config.yaml`) — **interposition, not routing.** It contains no policy and makes no runtime decision, so it does not refute *"can't apply mid-flight"* on its own.

The first claim is what corrects ADR-0002. The second is what would have to be measured before anything is built on it, and this ADR asserts only the first.

**What the correction is worth, stated conservatively.** "Impossible" becomes **"impossible from a hook; unexamined from a proxy"** — not "we should do it." Routing the main thread through a proxy means every token of every session traverses a process in the data path, and if the destination is still Anthropic you have inserted a third party into traffic that previously had none. ADR-0002's advisory-only stance may well be *right*; what this ADR establishes is that it was right for a **reason ADR-0002 did not give**, and its trigger will therefore never fire on the thing that actually matters. Per the ADR convention, ADR-0002 is not edited; this record supersedes nothing and corrects the reasoning in place.

**Concepts adopted (with implementation notes):**
- **Transcript-derived tier signals**, as a zero-cost pre-pass in `tier-classify-hook` ahead of the qwen call. Take the signal set (recent errors, repeated attempts without progress, read/plan without output → capable; write/edit density → efficient); **do not** import the `0.46`/`0.5` thresholds. Not yet executed, and **should not ship on their say-so** — it needs its own measurement first.
- **The escalation latch** — once a session has been classified hard, keep it hard rather than re-deciding per prompt. Applies to ADR-0002's per-prompt cache directly and costs nothing.

**Concepts considered and rejected (with reasoning):**
- **The proxy itself**, for Tessera — wrong layer, third party in the data path, pre-alpha, and a known issue that bills you for cancelled requests.
- **LLM-judge routing** — ADR-0006, plus it reinstates the cost objection ADR-0002 already sustained.
- **Protocol translation** — no surface here.
- **Rewriting ADR-0002** — the convention is a new record, not an edit.

**Re-evaluate trigger conditions:**
- Switchyard drops "not for production use" (v1.0 or an explicit production-ready declaration) → reopen the hybrid question for conclave's harness, not for Tessera.
- **Any** published evaluation of router quality or cost effect, by NVIDIA or a third party → reopen §4's pattern adoption on evidence instead of on plausibility.
- The cancelled-request-still-bills issue closes → removes the sharpest cost objection to hybridizing.
- Tessera acquires a data plane for any other reason → the layer rejection lapses and this must be re-argued from the top.
- **Restated ADR-0002 trigger, in capability terms:** *any* mechanism — hook, proxy, env var, or harness feature — that makes the main-session model selectable mid-session. The original wording ("from a hook") cannot fire on the case that already exists.
- Next cadence review: **2026-10-14** (60 days, Watching).

---

## References

- https://github.com/NVIDIA-NeMo/Switchyard — README, `docs/architecture.md`, `docs/core_concepts.md`, `docs/known_issues.md`, `docs/routing_algorithms/{escalation_router,stage_router}_routing.md`, releases, GitHub API metadata. All figures read 2026-08-15.
- **ADR-0002** — model effort-tier routing via dispatch-time hooks; the record this ADR corrects.
- **ADR-0006** — Tessera is instrumentation, not control.
- **ADR-0014** — the review backend seam (portability at the code seam).
- **ADR-0021** — Deep Agents; the prior "rejected on layer" precedent, and the prior instance of a fluent-but-wrong automated repo summary.
- conclave: `harness/run-local-cc.sh:39-42`, `harness/litellm_config.yaml` — the in-house demonstration that the proxy application point works (launch-time binding, static map, **no routing policy**); `docs/INTEGRATION.md` guard 3 (conclave exposes tiers, Tessera decides when to use them), which places this evaluation in Tessera rather than conclave; `docs/TOOL-DIRECTION.md` Option 2.
