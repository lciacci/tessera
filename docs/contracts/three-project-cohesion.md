# Contract: three-project cohesion (Conclave · Tessera · pr-arbiter)

**Status:** Canonical. **Tessera-hosted peer contract — hosting ≠ ownership.** Tessera holds this
file as the coordinator of record; the three projects are runtime **peers**, and no one of them owns
the others. Any of the three may propose an edit. A change that touches a project's **lane** (its
`Owns` row below, or a seam it owns) needs **that project's sign-off**.

This is a **coordination MAP, not an ADR.** It records how three sibling projects fit, what each
owns, and where the seams are. It **surfaces** the open integration decisions; it does **not** decide
them — those are deferred to a later ADR (see *Open decisions* below). The peer repos hold **thin
stubs** that point here (`../conclave/docs/INTEGRATION.md`, `../pr-arbiter/docs/INTEGRATION.md`); if a
stub and this file disagree, **this file wins**.

Evidence is referenced by **sibling-relative path** (`../conclave/…`, `../pr-arbiter/…`) so the map
survives a machine move — never an absolute `/Users/…` path.

---

## The one system, in three layers

The three projects are a substrate / pattern / policy stack. Each layer consumes the one below and is
task-agnostic to the one above.

| Layer | Project | **Owns** | **Must NOT** |
|-------|---------|----------|--------------|
| **Substrate** | **Conclave** (`../conclave`) | Model **serving** — the tier ladder (`local-tiny` 3B/8B → `local-mid` 30B-A3B default daily driver → `lab` 80B on-demand → `frontier`) behind one OpenAI-compatible, Tailscale-private gateway. The **measurement instrument** (`../conclave/orchestrator/divergence.py`, `../conclave/orchestrator/fleet_pairwise.py`). | Build routing **policy** (Tessera's *when*) or the review **pattern** (pr-arbiter's). Serving exposes tiers; it does not decide their use. |
| **Pattern** | **pr-arbiter** (`../pr-arbiter`) | The multi-**ROLE**, **union-recall** review workflow: reviewer → independent additive arbiter → KEEP/DROP mutual triage, **one strong model, role-differentiated prompts** (`../pr-arbiter/agents/reviewer.py`, `../pr-arbiter/agents/arbiter.py`, `../pr-arbiter/agents/triage.py`). The typed-finding schema. | Decide **when** review runs or on **which tier** (Tessera's), or **serve** the models (Conclave's). It is a pattern, not a policy and not a substrate. |
| **Policy** | **Tessera** (this repo) | **Governance** (gate / verify / watch / escalation) and the routing / dispatch / **escalation DECISIONS** — *when* to escalate a tier, *when* a change is consequential enough to fan out review. Hosting this contract. | **Serve** inference (Conclave's) or own the review **internals** (pr-arbiter's). Policy says *when/whether*, never *how the substrate runs* or *how the pattern reviews*. |

> ⚠️ **The Pattern row still names `pr-arbiter`, which is frozen — flagged, not rewritten (conclave,
> 2026-08-07).** S4, S5 and D4 below already record that the engine lives in **`arbiter`**
> (`../arbiter`), so this table disagrees with the rest of the file; the title, the stub list above,
> and the `../pr-arbiter/agents/*` evidence paths carry the same staleness. Renaming the Pattern
> **lane** is that lane's sign-off to give, not conclave's, so it is left for Tessera + `arbiter`.
> Until then: **where this table and S4 disagree, S4 is current.**

**Directionality.** Conclave is **downstream of Tessera on governance** (it carries a `.tessera/`
profile, its gate-scan and findings feed Tessera) and **upstream of Tessera as an inference
substrate** (Tessera's routing consumes conclave's gateway). Not a contradiction: governance flows
down, inference flows up. All three are **runtime peers**.

---

## Seams (each with an owner)

| # | Seam | Owner (produces) | Consumer(s) | Status |
|---|------|------------------|-------------|--------|
| S1 | **Inference gateway** — OpenAI-compatible, Tailscale-private, multi-backend (LiteLLM). | Conclave | Tessera routing/dispatch (`scripts/model_routing.py`, ADR-0002 hooks); pr-arbiter (`base_url`). | Build stance decided; fleet not yet standing (Phase-0 local tier proven — see S-evidence). |
| S2 | **Union-recall divergence metric** — a scoring **variant** of `divergence.py` whose oracle is the **union of true findings** (bug-recall + false-positive-rate vs a labeled defect set), NOT best-single-*answer*. | Conclave (instrument shape) — the **"true finding" scoring function is co-owned with pr-arbiter** (it defines a finding). | Tessera's *"is review-fan-out worth it?"* gate. | **Partly built (conclave, 2026-07-28).** `../conclave/orchestrator/s2_model_axis.py` implements the union-recall scoring function and reproduces pr-arbiter's committed numbers to 4dp — but only along the **MODEL** axis, and against a weaker second model (see guard (b)). The generic port stays **parked**: a labeled corpus and recall harness already existed, so the lever was more seeds, not the port. |
| S3 | **Escalation tiers** — the `local → lab → frontier` ladder as addressable roles behind the gateway. | Conclave (exposes tiers) | Tessera (owns the **WHEN** — the confidence-gated cascade / escalation trigger). | Tiers specified; the *trigger policy* is Tessera's, unbuilt. |
| S4 | **Review pattern → `/arbiter`** — the reviewer+arbiter+triage pattern graduates into the tool backing Tessera's `/arbiter`, running on conclave's fleet. | **`arbiter`** (github.com/lciacci/arbiter) owns the engine; Tessera owns the `/arbiter` surface + when-to-invoke | Tessera users / CI | **Prerequisite met, still ADR-gated on D3.** The pattern graduated 2026-07-28: pr-arbiter froze as a research artifact and the engine now lives in `arbiter`, a standalone CLI that reviews a git ref range. Phase 3 was never run and is no longer the gate. |
| S5 | **Findings feedback** — a peer's `FINDINGS.md` feeds Tessera's backlog via `tessera-findings` (globs `*/.tessera/project.yml`). | Conclave (already a downstream); **`arbiter`** (adopted `.tessera/` at scaffold). | Tessera | Live for conclave; **arbiter is now a downstream too** — D4 resolved, see below. |

---

## Sequence — what is live, parked, ADR-gated

**LIVE (binding / proven now):**
- The **four anti-conflation guards** below — they bind work in all three repos today.
- **Conclave Phase-0 result (2026-07-17; ~~≈~~ RETRACTED, corrected 2026-08-07):** the local $0
  30B-A3B is daily-driven **on COST, not on measured quality parity**. The study is underpowered
  (n=30, MDE ≈0.077, margin CI [-0.005, +0.103] crosses 0) — "failed to distinguish", not "equal".
  The point estimate favours the 80B (+0.049) and among the 12 queries the grader could separate the
  **80B won 10–2** (sign-test p≈0.04); the 80B leads or ties every category and loses none. The
  earlier "≈" was an over-claim in conclave's write-up, corrected there on adversarial review and
  now here. **The decision is unchanged; its grounds are not.**
  (`../conclave/docs/design.md` § Phase-0 RESULT.)
- **Gate-scan** live in Tessera and conclave (`scripts/gate/scan.py`); shared governance substrate.

**PARKED (decided-in-principle, not standing):**
- **Conclave standing fleet** — build stance is set (local-first tier ladder); the fleet is not
  deployed and the escalation signal is unmeasured (needs a real workload trace).
- **pr-arbiter Phase 3** — **abandoned 2026-07-28, not parked.** Design complete and ratified but
  never implemented; the project moved from research to tooling instead. No longer a prerequisite
  for anything. See `../pr-arbiter/docs/PHASE_3_RESUMPTION.md` for the record.
- **S2 union-recall divergence variant** — specified here; not built.

**ADR-GATED (a later ADR decides; NOT decided in this map):**
- The routing **home** (D1), the union-recall variant as the review gate (D2), pr-arbiter → `/arbiter`
  on conclave's fleet (D3). See *Open decisions*.

---

## Anti-conflation rules (verbatim, binding)

These four exist because the two sibling research results are easy to cross-wire into a false
blocker. They are mirrored in each peer's stub because they bind work **in** that repo.

**(a) Conclave's "judge/ensemble doesn't pay" null is SELECT-BEST only** — do **NOT** cite it to
block pr-arbiter's **UNION-RECALL** review. Different objective: select-best picks one best answer and
saturates as models converge (→ route); union-recall wants *every distinct true bug* N reviewers find,
and that headroom does not saturate the same way. The results are **consistent, not contradictory**.

**(b) The diversity that pays is ROLE, NOT MODEL** — one strong model plus role-differentiated
prompts for the review pattern. **No fleet** for review. Conclave's null is about a *model* fleet;
the review win is about *roles* on one model.

> **Measured on the adversarial path, 2026-07-28 — with a bound (conclave, added 2026-08-07).**
> Guard (b) previously rested on conclave's *select-best* null, which guard (a) says cannot be cited
> against union-recall. It now has direct union-recall evidence. `../conclave/orchestrator/s2_model_axis.py`,
> arms matched at two passes: best single (claude reviewer) **0.509 recall / 30 FP**; **ROLE**-diverse
> union (claude reviewer ∪ claude arbiter) **0.618 / 35 FP**; **MODEL**-diverse union (claude reviewer
> ∪ qwen reviewer) **0.509 / 50 FP**. MODEL diversity: **+0.000 recall, +20 false positives, zero
> decorrelated catches.** The scorer reproduces pr-arbiter's committed numbers to 4dp on their matcher
> and their expected findings.
>
> **BOUND — do not over-read this.** The second arm was a ~7× **weaker** model (qwen 30B alone scored
> 0.073 recall, 0/8 criticals). A weak model's findings are a near-subset, so it *cannot* add
> union-recall; the result is close to true by construction. This is **directionally supportive, not
> settling**. The open measurable is **peer-strength**: does a second *frontier* model decorrelate?
> Unmeasured. Guard (b) stands as written until an ADR moves it.
>
> Note the countervailing anecdote, so the guard is not read as stronger than it is: `arbiter` and a
> workflow-backed `/code-review` looked independently at the same security boundary and produced six
> exploits between them, **one apiece missed by the other** (`../arbiter/docs/STATE.md`, "Round 2").
> That is a peer-strength union-recall gain — but confounded, since the two differ in *architecture*
> (31 agents / 1.3M tokens vs ~4 calls per file), not only in model.

**(c) Serving tiers ≠ routing policy** — Conclave **exposes** tiers (`local`/`lab`/`frontier`);
**Tessera decides WHEN** to use them. A tier existing is not a decision to route to it.

**(d) pr-arbiter's numbers are thin** — the Phase-1 critical-recall win is **7/8 vs 6/8, one seed**,
and the Phase-2 generation lift **~vanished under 3-seed variance** (2 tasks across 39 runs). **Gate
any build on the instrument (S2), not the headline.** The load-bearing move is measuring the review
headroom with a labeled defect set, not repeating the press number.

---

## Open decisions (surfaced here, deferred to a later ADR)

Do **not** resolve these in this map. They are the ADR's job.

- **D1 — Routing home.** Does Tessera call conclave's gateway directly? Do the `bin/` council
  wrappers (`bin/validate-plan`, and the `review` orchestrator **cut 2026-07-27 per ADR-0014**) collapse into conclave calls? Where does the router
  live — Tessera policy, conclave substrate, or a thin seam between?
- **D2 — The review gate.** Adopt the S2 union-recall divergence variant as Tessera's
  "is review-fan-out worth it?" gate, and on what labeled corpus is "true finding" scored?
- **D3 — `/arbiter` graduation.** The engine exists (`arbiter`), so the pr-arbiter-Phase-3 half of
  this gate is discharged. What remains is a stable conclave fleet and the ADR itself. Note the
  engine is deliberately **not** Claude-Code-bound: it is plain Python against the Anthropic SDK
  with a bare client, so `ANTHROPIC_BASE_URL` points it at conclave's gateway with no code change.
  Layering holds — `arbiter` is the pattern, Tessera decides when review runs.

  > **Bound on that "no code change" (conclave, 2026-08-07): mechanically true, and it does not
  > follow that conclave's LOCAL tier can serve this workload.** Measured — the local 30B scores
  > **0.073 recall, 0/8 criticals** on structured adversarial review against claude's 0.509 on the
  > identical task, while *matching* the hosted 80B on edit-and-apply (T1–T3). **Task SHAPE, not
  > model tier, is the escalation trigger, and review is the shape that breaks the local tier.**
  > So "a stable conclave fleet" is not sufficient for D3 unless the tier it stands up is one that
  > can actually review; on current evidence that is `lab`/`frontier`, not `local-mid`.
  > (`../conclave/docs/LOCAL-CODER-FAILURES.md`.)
- **D4 — RESOLVED 2026-07-28.** Moot for pr-arbiter, which is frozen and will never adopt. Its
  successor `arbiter` adopted `.tessera/` at scaffold, so it is a downstream now and S5 applies to
  it. The `tessera-watch` P4 trip this decision warned about (downstream count → 5) is therefore
  live; treat that as expected rather than as a regression.

## What would firm this map into that ADR

Three things, from the observatory thread (`docs/observatory.md` → "Tessera ↔ Conclave ↔ pr-arbiter"),
**restated 2026-08-07** — (2) named pr-arbiter Phase 3, which this same file records as abandoned:

1. A **review-flavored divergence measurement** (S2) showing the review headroom is real and how big.
   **Partly done** — the MODEL axis is measured and null; the ROLE axis is +0.109. What is missing is
   the **peer-strength** arm (guard (b)).
2. A **stable conclave fleet** — and per D3's bound, one standing at a tier that can review.
   *(pr-arbiter Phase 3 is struck: abandoned 2026-07-28, no longer a prerequisite for anything.)*
3. The concrete interop shape (D1).

---

## Cross-references

- **This repo:** `docs/observatory.md` → "Tessera ↔ Conclave ↔ pr-arbiter — the review/model cluster
  is converging"; ADR-0002 (routing via dispatch-time hooks — the routing-decision home);
  ADR-0006 (instrumentation-not-control — why the guards gate builds on instruments, not headlines);
  `.claude/skills/council-review/SKILL.md` (its pending roster/config decision points here — see below);
  `bin/validate-plan` (the `review` orchestrator was cut 2026-07-27, ADR-0014 — review is Claude-only).
- **Conclave:** `../conclave/docs/INTEGRATION.md` (stub), `../conclave/docs/design.md`
  § "External validation + scope" (the route-don't-judge null + Phase-0 local-30B≈80B result).
- **pr-arbiter:** `../pr-arbiter/README.md`, `../pr-arbiter/PHASE_2_FINAL.md` (the variance result +
  typed-finding schema), `../pr-arbiter/docs/PHASE_3_RESUMPTION.md` (Phase 3 status),
  `../pr-arbiter/docs/INTEGRATION.md` (stub).
