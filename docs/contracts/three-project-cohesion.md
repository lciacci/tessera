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

**Directionality.** Conclave is **downstream of Tessera on governance** (it carries a `.tessera/`
profile, its gate-scan and findings feed Tessera) and **upstream of Tessera as an inference
substrate** (Tessera's routing consumes conclave's gateway). Not a contradiction: governance flows
down, inference flows up. All three are **runtime peers**.

---

## Seams (each with an owner)

| # | Seam | Owner (produces) | Consumer(s) | Status |
|---|------|------------------|-------------|--------|
| S1 | **Inference gateway** — OpenAI-compatible, Tailscale-private, multi-backend (LiteLLM). | Conclave | Tessera routing/dispatch (`scripts/model_routing.py`, ADR-0002 hooks); pr-arbiter (`base_url`). | Build stance decided; fleet not yet standing (Phase-0 local tier proven — see S-evidence). |
| S2 | **Union-recall divergence metric** — a scoring **variant** of `divergence.py` whose oracle is the **union of true findings** (bug-recall + false-positive-rate vs a labeled defect set), NOT best-single-*answer*. | Conclave (instrument shape) — the **"true finding" scoring function is co-owned with pr-arbiter** (it defines a finding). | Tessera's *"is review-fan-out worth it?"* gate. | **Not built.** Same instrument, different scoring function. Cheapest next lever; validates pr-arbiter's headline before any integration is built. |
| S3 | **Escalation tiers** — the `local → lab → frontier` ladder as addressable roles behind the gateway. | Conclave (exposes tiers) | Tessera (owns the **WHEN** — the confidence-gated cascade / escalation trigger). | Tiers specified; the *trigger policy* is Tessera's, unbuilt. |
| S4 | **Review pattern → `/arbiter`** — pr-arbiter's reviewer+arbiter+triage graduates into the tool backing Tessera's `/arbiter`, running on conclave's fleet. | pr-arbiter (the pattern) + Tessera (the `/arbiter` surface + when-to-invoke) | Tessera users / CI | **ADR-gated** (Open decision D3). pr-arbiter Phase 3 is the prerequisite. |
| S5 | **Findings feedback** — a peer's `FINDINGS.md` feeds Tessera's backlog via `tessera-findings` (globs `*/.tessera/project.yml`). | Conclave (already a downstream); pr-arbiter (only if it adopts `.tessera/`). | Tessera | Live for conclave; **pr-arbiter adoption is an open question** (Open decision D4). |

---

## Sequence — what is live, parked, ADR-gated

**LIVE (binding / proven now):**
- The **four anti-conflation guards** below — they bind work in all three repos today.
- **Conclave Phase-0 result (2026-07-17):** local $0 30B-A3B ≈ rented 80B on the hard-QA proxy →
  daily-drive local. (`../conclave/docs/design.md` § "External validation + scope".)
- **Gate-scan** live in Tessera and conclave (`scripts/gate/scan.py`); shared governance substrate.

**PARKED (decided-in-principle, not standing):**
- **Conclave standing fleet** — build stance is set (local-first tier ladder); the fleet is not
  deployed and the escalation signal is unmeasured (needs a real workload trace).
- **pr-arbiter Phase 3** — design complete and ratified, **blocked on an 8–15h senior-annotator
  pilot** (`../pr-arbiter/docs/PHASE_3_RESUMPTION.md`). Prerequisite for S4.
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

**(b) The diversity that pays is ROLE (pr-arbiter), NOT MODEL (conclave's null)** — one strong model
plus role-differentiated prompts for the review pattern. **No fleet** for review. Conclave's null is
about a *model* fleet; pr-arbiter's win is about *roles* on one model.

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
  wrappers (`bin/validate-plan`, `bin/review`) collapse into conclave calls? Where does the router
  live — Tessera policy, conclave substrate, or a thin seam between?
- **D2 — The review gate.** Adopt the S2 union-recall divergence variant as Tessera's
  "is review-fan-out worth it?" gate, and on what labeled corpus is "true finding" scored?
- **D3 — `/arbiter` graduation.** pr-arbiter → the implementation backing `/arbiter`, on conclave's
  fleet — gated on pr-arbiter Phase 3 + a stable conclave fleet.
- **D4 — Should pr-arbiter adopt `.tessera/`?** It pre-dates Tessera and is mid-research; adoption is
  cheap/reversible (`hook_distro: global`, no app restructure) but was parked to avoid confounding
  its own eval with harness churn. Natural **output** of the conclave/interop design session, not a
  prerequisite. (Adopting pushes downstream count to 5 → trips `tessera-watch` P4.)

## What would firm this map into that ADR

Three things, from the observatory thread (`docs/observatory.md` → "Tessera ↔ Conclave ↔ pr-arbiter"):
(1) a **review-flavored divergence measurement** (S2) showing the review headroom is real and how big;
(2) **pr-arbiter Phase 3** + a **stable conclave fleet**; (3) the concrete interop shape (D1).

---

## Cross-references

- **This repo:** `docs/observatory.md` → "Tessera ↔ Conclave ↔ pr-arbiter — the review/model cluster
  is converging"; ADR-0002 (routing via dispatch-time hooks — the routing-decision home);
  ADR-0006 (instrumentation-not-control — why the guards gate builds on instruments, not headlines);
  `.claude/skills/council-review/SKILL.md` (its pending roster/config decision points here — see below);
  `bin/validate-plan`, `bin/review`.
- **Conclave:** `../conclave/docs/INTEGRATION.md` (stub), `../conclave/docs/design.md`
  § "External validation + scope" (the route-don't-judge null + Phase-0 local-30B≈80B result).
- **pr-arbiter:** `../pr-arbiter/README.md`, `../pr-arbiter/PHASE_2_FINAL.md` (the variance result +
  typed-finding schema), `../pr-arbiter/docs/PHASE_3_RESUMPTION.md` (Phase 3 status),
  `../pr-arbiter/docs/INTEGRATION.md` (stub).
