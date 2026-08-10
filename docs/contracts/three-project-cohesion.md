# Contract: three-project cohesion (Conclave · Tessera · arbiter)

> **Pattern lane RENAMED `pr-arbiter` → `arbiter`, 2026-08-07.** Conclave flagged the inconsistency
> in place rather than fixing it, correctly: renaming a lane is that lane's sign-off to give.
> **Lorenzo signed for `arbiter`**; Tessera made the edit; `../arbiter` was notified in the same pass
> (`../arbiter/docs/INTEGRATION.md` — its stub, written here for the first time — and its
> `NEXT_SESSION.md`). `pr-arbiter` still appears below **only** where it is cited as the frozen
> research study it now is, chiefly in guard (d). The engine paths moved
> `../pr-arbiter/agents/{reviewer,arbiter,triage}.py` → `../arbiter/src/arbiter/{reviewer,second_pass,triage}.py`.

**Status:** Canonical. **Tessera-hosted peer contract — hosting ≠ ownership.** Tessera holds this
file as the coordinator of record; the three projects are runtime **peers**, and no one of them owns
the others. Any of the three may propose an edit. A change that touches a project's **lane** (its
`Owns` row below, or a seam it owns) needs **that project's sign-off**.

This is a **coordination MAP, not an ADR.** It records how three sibling projects fit, what each
owns, and where the seams are. It **surfaces** the open integration decisions; it does **not** decide
them — those are deferred to a later ADR (see *Open decisions* below).

> **One clarification, added 2026-08-07 when two open decisions closed here.** Recording that a
> decision was *made elsewhere* (D1 — by ADR-0014) or that it *ceased to exist* (D2 — its subject,
> a review gate, does not exist and has no candidate) is **not** the map deciding it. The rule above
> still binds: **no open decision is RESOLVED in this file on its merits.** The distinction matters
> because the opposite failure is real — a dead open-decision left open reads as unfinished work and
> costs as much as an unanswered one, so a map that cannot close them rots in the other direction. The peer repos hold **thin
stubs** that point here (`../conclave/docs/INTEGRATION.md`, `../arbiter/docs/INTEGRATION.md`); if a
stub and this file disagree, **this file wins**. `../pr-arbiter/docs/INTEGRATION.md` still exists and
still points here; it is the **frozen study's** stub and is not maintained.

Evidence is referenced by **sibling-relative path** (`../conclave/…`, `../arbiter/…`) so the map
survives a machine move — never an absolute `/Users/…` path.

---

## The one system, in three layers

The three projects are a substrate / pattern / policy stack. Each layer consumes the one below and is
task-agnostic to the one above.

| Layer | Project | **Owns** | **Must NOT** |
|-------|---------|----------|--------------|
| **Substrate** | **Conclave** (`../conclave`) | Model **serving** — the tier ladder (`local-tiny` 3B/8B → `local-mid` 30B-A3B default daily driver → `lab` 80B on-demand → `frontier`) behind one OpenAI-compatible, Tailscale-private gateway. The **measurement instrument** (`../conclave/orchestrator/divergence.py`, `../conclave/orchestrator/fleet_pairwise.py`). | Build routing **policy** (Tessera's *when*) or the review **pattern** (`arbiter`'s). Serving exposes tiers; it does not decide their use. |
| **Pattern** | **arbiter** (`../arbiter`) | The multi-**ROLE**, **union-recall** review workflow: reviewer → independent second pass → two-voice KEEP/DROP/UNSURE triage, **one strong model, role-differentiated prompts** (`../arbiter/src/arbiter/reviewer.py`, `../arbiter/src/arbiter/second_pass.py`, `../arbiter/src/arbiter/triage.py`). The typed-finding schema. Ships as a CLI over a git ref range, exit 1 on high/critical. | Decide **when** review runs or on **which tier** (Tessera's), or **serve** the models (Conclave's). It is a pattern, not a policy and not a substrate. **It is not a gate, and nothing gates it.** |
| **Policy** | **Tessera** (this repo) | **Governance** (gate / verify / watch / escalation) and the routing / dispatch / **escalation DECISIONS** — *when* to escalate a tier, *when* a change is consequential enough to fan out review. Hosting this contract. | **Serve** inference (Conclave's) or own the review **internals** (`arbiter`'s). Policy says *when/whether*, never *how the substrate runs* or *how the pattern reviews*. |

> ✅ **RESOLVED 2026-08-07 — the lane is renamed; see the banner at the top of this file.** Conclave
> raised this on 2026-08-07 (*"the Pattern row still names `pr-arbiter`, which is frozen"*) and
> deliberately flagged rather than rewrote, because renaming a lane needs that lane's owner. It has
> now been signed and made. The table and S4 no longer disagree, so the interim precedence rule
> (*"where this table and S4 disagree, S4 is current"*) is retired.
>
> **Kept as the trail, because the flag-don't-fix judgement was the right one** and is the reusable
> part: a peer that finds a lane stale should say so **in place, with a precedence rule**, so the map
> is safe to read in the interim — rather than either fixing it unilaterally or leaving it silently
> wrong.

**Directionality.** Conclave is **downstream of Tessera on governance** (it carries a `.tessera/`
profile, its gate-scan and findings feed Tessera) and **upstream of Tessera as an inference
substrate** (Tessera's routing consumes conclave's gateway). Not a contradiction: governance flows
down, inference flows up. All three are **runtime peers**.

---

## Seams (each with an owner)

| # | Seam | Owner (produces) | Consumer(s) | Status |
|---|------|------------------|-------------|--------|
| S1 | **Inference gateway** — OpenAI-compatible, Tailscale-private, multi-backend (LiteLLM). | Conclave | Tessera routing/dispatch (`scripts/model_routing.py`, ADR-0002 hooks); **`arbiter`** (`ANTHROPIC_BASE_URL` — a bare Anthropic-SDK client, so no code change; but see D3's bound on *which tier*). | Build stance decided; fleet not yet standing (Phase-0 local tier proven — see S-evidence). |
| S2 | **Union-recall divergence metric** — a scoring **variant** of `divergence.py` whose oracle is the **union of true findings** (bug-recall + false-positive-rate vs a labeled defect set), NOT best-single-*answer*. | Conclave (instrument shape) — the **"true finding" scoring function is co-owned with `arbiter`** (it defines a finding; inherited from the frozen pr-arbiter study, whose matcher the scorer still reproduces to 4dp). | ~~Tessera's *"is review-fan-out worth it?"* gate~~ — **that consumer no longer exists; see D2.** Now **design input**: whether `arbiter` should ever add a fleet. | **Partly built (conclave, 2026-07-28).** `../conclave/orchestrator/s2_model_axis.py` implements the union-recall scoring function and reproduces pr-arbiter's committed numbers to 4dp — but only along the **MODEL** axis, and against a weaker second model (see guard (b)). The generic port stays **parked**: a labeled corpus and recall harness already existed, so the lever was more seeds, not the port. |
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
- ~~The routing **home** (D1), the union-recall variant as the review gate (D2),~~ **`arbiter` on a
  conclave tier that can review (D3)** — the only one still open. **D1 closed 2026-08-07** (its
  review half by ADR-0014; its router half evaporated). **D2 closed 2026-08-07 as moot** — the gate
  it proposed has no gate to be. See *Open decisions*.

---

## Anti-conflation rules (verbatim, binding)

These four exist because the two sibling research results are easy to cross-wire into a false
blocker. They are mirrored in each peer's stub because they bind work **in** that repo.

**(a) Conclave's "judge/ensemble doesn't pay" null is SELECT-BEST only** — do **NOT** cite it to
block `arbiter`'s **UNION-RECALL** review *(originally written of pr-arbiter's; the subject moved to
its successor 2026-08-07, the guard is unchanged)*. Different objective: select-best picks one best answer and
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
>
> **2026-08-10 — Round 3 was checked against this and does not move it.** Its three arms (arbiter,
> a 17-agent `/code-review`, cloud `ultra`) are **one model in three arrangements**, so it varies
> architecture, not model: the Round 2 shape above with the *scale* half controlled, not the model
> half introduced. Peer-strength MODEL diversity stays **unmeasured**; conclave's paid experiment
> stays unspent. One correction it does force on the table above: those recall figures are
> **single-draw point estimates** — arbiter re-ran one arm 4× on byte-identical input and got a 1–4
> spread — so `0.618` binds as a *direction*, not a value, and any future model-diversity run needs
> **same-model-k-draws** as its control arm rather than best-single. Deliberately not re-measured;
> the instrument (`../conclave/orchestrator/s2_model_axis.py`) answers it on demand.

**(c) Serving tiers ≠ routing policy** — Conclave **exposes** tiers (`local`/`lab`/`frontier`);
**Tessera decides WHEN** to use them. A tier existing is not a decision to route to it.

**(d) pr-arbiter's numbers are thin** — the Phase-1 critical-recall win is **7/8 vs 6/8, one seed**,
and the Phase-2 generation lift **~vanished under 3-seed variance** (2 tasks across 39 runs). **Gate
any build on the instrument (S2), not the headline.** The load-bearing move is measuring the review
headroom with a labeled defect set, not repeating the press number.

---

## Open decisions (surfaced here, deferred to a later ADR)

Do **not** resolve these in this map. They are the ADR's job. **Two of the four are now closed, and
both were closed by the ground moving rather than by anyone deciding them** — recorded here because
a dead open-decision left open is as costly as an unanswered one.

- **D1 — Routing home. CLOSED 2026-08-07, in two halves, because only one of them was ever
  answered.** The original question had three parts: (i) does Tessera call conclave's gateway
  directly, (ii) do the `bin/` council wrappers collapse into conclave calls, (iii) where does the
  router live — Tessera policy, conclave substrate, or a thin seam?
  - **The review-portability half: DECIDED by ADR-0014 (Accepted 2026-07-27, option D — review is
    Claude-only, deliberately).** That ADR names *"Observatory Open decision D1"* as its decision
    driver. It settles (ii) outright — the `review`, `kimi` and `research` wrappers under `bin/` were
    **removed**, and are named here without backticks on purpose: they are gone, and writing a
    deleted thing as a live path is the drift this contract keeps paying for. It settles
    (i) **for review**: no. Decided on evidence, not preference: 0 of 3 backends were
    functional and the review orchestrator had never run. `bin/validate-plan` + `council-review` were
    deliberately **kept** (plan validation is a different capability that merely shares backends).
  - **The router half: EVAPORATED, not answered.** ADR-0014 is scoped to the review backend seam and
    never addressed (iii). Meanwhile conclave **shelved its router** — it pays only when pairwise
    winners split, and the fleets concentrate — so on current evidence *there is no router to home*.
    A future ADR that wants to reopen (iii) must first establish that a router should exist at all.
  - **The re-entry fact, carried forward from ADR-0014 because it will matter:** conclave already
    carries `litellm/config.yaml` with a `model_list` and three `api_base` entries. If that gateway
    becomes routine, the cheap path back is option **B**, not C.
- **D2 — The review gate. CLOSED 2026-08-07 as MOOT.** The decision was *"adopt the S2 union-recall
  divergence variant as Tessera's 'is review-fan-out worth it?' gate"*. **There is no such gate and
  no candidate for one:** `arbiter` ships as a CLI that a human or CI invokes, it is not a gate, and
  nothing gates it. A decision about which metric should govern a gate cannot be made when the gate
  does not exist.
  - **What survives the close, and it is the more useful half: S2 is retained as DESIGN input.**
    Conclave's measurements moved from *gate* input to *design* input. The question the instrument
    now answers is not "should Tessera fan review out?" but **"should `arbiter` ever add a fleet?"**
    — and the measured answer is no (MODEL diversity: +0.000 recall, +20 false positives; ROLE
    diversity: +0.109). See guard (b), including its weak-second-arm bound.
  - **What would REOPEN D2:** something in Tessera actually gating on review — a Stop hook, a
    pre-commit hook, or a CI required-check wired to `arbiter`'s exit code. At that point "is
    fan-out worth it, and scored on what corpus?" becomes a live question again with a real consumer.
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
3. ~~The concrete interop shape (D1).~~ **Struck 2026-08-07 — D1 is closed** (review half decided by
   ADR-0014; router half evaporated). It is no longer a prerequisite. **So the list is down to two,
   and only item 2 is genuinely outstanding** — which is worth stating plainly, because a
   prerequisite list that keeps its dead entries reads as further from an ADR than it is.

---

## Cross-references

- **This repo:** `docs/observatory.md` → "Tessera ↔ Conclave ↔ pr-arbiter — the review/model cluster
  is converging"; ADR-0002 (routing via dispatch-time hooks — the routing-decision home);
  ADR-0006 (instrumentation-not-control — why the guards gate builds on instruments, not headlines);
  `.claude/skills/council-review/SKILL.md` (its pending roster/config decision points here — see below);
  `bin/validate-plan` (the `review` orchestrator was cut 2026-07-27, ADR-0014 — review is Claude-only).
- **Conclave:** `../conclave/docs/INTEGRATION.md` (stub), `../conclave/docs/design.md`
  — read its **current-state banner first**: the judge is disproved on three fleets, the router is
  shelved, and "route, don't judge" was itself corrected there to *"just call the strongest model."*
  Also `../conclave/docs/LOCAL-CODER-FAILURES.md` (the local tier's review failure, D3's bound) and
  `../conclave/orchestrator/s2_model_axis.py` (S2).
- **arbiter:** `../arbiter/docs/INTEGRATION.md` (stub), `../arbiter/docs/STATE.md`,
  `../arbiter/src/arbiter/{reviewer,second_pass,triage}.py` (the engine).
- **pr-arbiter:** `../pr-arbiter/README.md`, `../pr-arbiter/PHASE_2_FINAL.md` (the variance result +
  typed-finding schema), `../pr-arbiter/docs/PHASE_3_RESUMPTION.md` (Phase 3 status),
  `../pr-arbiter/docs/INTEGRATION.md` (stub).
