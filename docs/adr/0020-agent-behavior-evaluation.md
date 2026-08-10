# ADR-0020: Agent Behavior — the format is a linter, the calibration methodology is the find, and Tessera's conduct instruments all count artifacts

- **Date:** 2026-08-06
- **Status:** Watching
- **Executed:** 2026-08-10 — `scripts/mnemos/fixtures/correction_cases.jsonl`, `scripts/mnemos/fixtures/README.md`, `scripts/mnemos/calibration.py`, `scripts/mnemos/test_correction_fixtures.py`, `scripts/mnemos/eval_correction.py`. The two adopted patterns shipped (fixture matrix incl. the lucky-correct negative; the five-layer disagreement vocabulary), and the third — the observational-vs-conditioned rule — is stated, not code, as §154 specified. **One deliberate deviation from §152, recorded in `scripts/mnemos/fixtures/README.md`: the fixtures are TRACKED rather than added to the silver-label set**, because that set is gitignored (`.gitignore:18` ignores `.mnemos/` entirely), and authored fixtures put there cannot survive a clean clone, back a regression test, or reach a diff. §152 conflated two artifacts — the silver set is 125 *observed* turns judged after the fact; the matrix is *authored* cases with intended verdicts. **Result, against §147's precondition: a judge CAN distinguish a lucky-correct negative** (qwen 7/7 pairs, `regex_match` 0/7) — with the caveat that the matrix is far easier than the real distribution and does not calibrate anything. See `docs/observatory.md` → "Every conduct instrument counts the artifact, not the conduct".
- **Decision driver:** New tool surfaced. Lorenzo: "evaluate https://github.com/braintrustdata/agentbehavior".

> **Watching for:** (a) a **second independent client** implements `.agents/behaviors/` discovery — i.e. the format becomes interop rather than a convention with one author; (b) the judging harness moves out of `examples/` into `packages/` with a provider-neutral interface (today it is Braintrust `Eval` + Braintrust gateway); (c) the standard gets a normative statement about *trajectory* format — today it specifies where the spec file lives and says nothing about what a trace is.
> **Next check:** 2026-10-05 (60 days)

---

## Target

- **Name:** Agent Behavior
- **URL:** https://github.com/braintrustdata/agentbehavior — docs at https://agentbehavior.dev
- **What it is:** An open format for documenting expected AI-agent *conduct* — `BEHAVIOR.md` files with YAML frontmatter under `.agents/behaviors/<name>/` — plus a methodology for judging whole agent trajectories against those documents. Explicitly **not** a runtime activation mechanism.

---

## Side-by-side summary

| Dimension | Tessera | Agent Behavior |
|---|---|---|
| Maturity | Solo, ~2 months dogfood, 6 downstream projects | 16 commits, 3 contributors, created 2026-06-08, last push 2026-07-29. Pre-anything. |
| Cross-runtime | Claude Code only (hooks, skills, settings.json) | Runtime-agnostic by construction — it is a file format, it runs nowhere |
| Original IP | Project profiles, override mechanism, gate/friction log, spend authorization, escalation packets, haziness scoring, restore receipts | The `BEHAVIOR.md` frontmatter contract; the Intent/Evidence/Decision/Execution/Recovery/Failure-modes dimension set; the calibration fixture matrix |
| Maintenance model | Solo | Corp-backed (Braintrust) + partner (Basis). 3 contributors, 2 of them the two orgs. |
| License | MIT | **Apache-2.0** — genuinely open, no strings |
| Community size | Single user (Lorenzo) | 250 stars, 4 forks, 0 open issues, **0 known third-party clients** |
| Primary problem solved | *The agent's own reliability* — instrumentation that makes agent failure visible (ADR-0006) | *Reviewability of long trajectories* — "you cannot reduce hours of work and hundreds of decisions to one outcome metric" |
| Distinct strength | Fail-loud instrumentation fired on events, not elected by a model | A written, reviewable standard for conduct **plus** a calibration method that separates a right outcome from a right process |

---

## 1. Identity & maturity

Repo created 2026-06-08, **16 commits total**, three contributors: `AbhiPrasad` (9, Braintrust), `mitch-basis` / `mitchell troyanovsky` (6, Basis), `ornellaaltunyan` (1, docs). Apache-2.0. 250 stars against 4 forks and 0 open issues — attention without usage. Last push 2026-07-29; the visible arc is spec → CLI → three worked examples → docs site → README polish. That is a **standard being seeded**, not a tool being hardened.

**Bias risk is vendor loss-leader, and it is worth being precise about where it bites.** Braintrust sells eval infrastructure. The *format* is Apache-2.0 and costs nothing to adopt — there is no lock-in in a Markdown file with two required frontmatter fields. The lock-in, such as it is, sits in `examples/`: every worked example routes its LLM judge through `src/braintrustGateway.ts` and runs under Braintrust's `Eval` harness. So the standard is free and the thing that makes the standard *useful* is theirs. That is not malice — it is the shape of every vendor-seeded standard — but it means the adoption decision has two halves and they must be decided separately.

**What the code actually does, having read it rather than the README.** `packages/agentbehavior` is ~20KB of TypeScript whose CLI has one real verb: `validate`. It checks that a directory sits under `.agents/behaviors/`, contains a file named exactly `BEHAVIOR.md`, has YAML frontmatter that parses as a mapping, has a non-empty `name` ≤64 chars matching `[a-z0-9-]` and matching the parent directory, and a non-empty `description` ≤1024 chars. **That is the entire shipped tool: a frontmatter linter.** No judging, no trace handling, no scoring. Everything interesting lives in prose (`docs/specification.mdx`, `.agents/skills/writing-agent-behavior/references/calibrating-with-trajectories.md`) or in the three examples.

---

## 2. Problem-space overlap

The overlap is real but it is **not** where the project's own framing points. Their framing is "a standard for agent conduct," which sounds like it competes with CLAUDE.md. It does not — see §3. The genuine overlap is with Tessera's *instrumentation* layer, and specifically with how Tessera decides whether its own conventions were followed.

| Overlap area | Tessera approach | Their approach | Classification | Notes |
|---|---|---|---|---|
| Stating expected agent conduct | Prose in `CLAUDE.md` "Working conventions", eagerly loaded every session | `BEHAVIOR.md` under `.agents/behaviors/`, explicitly **not** loaded at runtime | **Different bet** | Tessera's is a *channel* (guaranteed delivery). Theirs is a *review artifact* (guaranteed non-delivery). Both are deliberate; see §3. |
| Measuring whether the conduct happened | Count the artifact the conduct emits: `suggestion_gate` events, `restore_receipt`s, `degraded` calls, drift events | Judge the **trajectory** against the written spec, per trigger occurrence | **Different bet, and theirs is better on this axis** | This is the find of the eval. See §6. |
| Distinguishing right-outcome from right-process | Nothing. No Tessera instrument makes this distinction. | The **lucky-correct negative** fixture: "the final outcome is correct, but the required process was not followed" | **Gap in ours** | Tessera has *named* this failure repeatedly (Standing pattern #2 — "it did not break, it produced something plausible") and has never had a test shape for it. |
| Diagnosing a disagreement between expected and observed | Ad hoc | Five named layers — behavior wording / fixture / judge / telemetry / policy — "fix the owning layer, do not contort the behavior text to compensate for a broken judge" | **Gap in ours** | Directly applicable to `eval_correction.py`, which today reports P/R with no attribution of *why* a disagreement happened. |
| Trace store to judge against | Mnemos `claude_turns`: 121 sessions ingested, structural fields + redacted 200-char previews, an LLM judge already running (qwen correction classifier + typing), action-divergence triplets | None. The format says nothing about trace shape; the examples carry their own fixtures. | **Compatible — and we are ahead** | Their methodology needs a trace store. We have one. |
| Scoring/aggregation | Haziness: 5 weighted dimensions → composite → band | Deliberately **unspecified** — "Agent Behavior does not prescribe labels, a judging algorithm, or a folding algorithm" | **Different bet** | Their refusal to specify is defensible for a standard and useless as a tool. One example fold is offered: per-occurrence true/false, section false if any occurrence false, file `not applicable` only if nothing fired. |
| Cost-sensitive action gating | `tessera-authorize` + `scripts/spend/guard.py` on PreToolUse(Bash), deny-by-default, 124 `spend_denied` events logged | `examples/.agents/behaviors/cost-sensitive-actions/BEHAVIOR.md` | **Compatible — independent convergence** | Their example behavior is Tessera's spend gate, written as prose. Convergent arrival is evidence the mechanism is right (same signal ADR-0013 recorded for `locate` ↔ `tessera-decision-surface.sh`). |

**Tessera does not address (gaps in our design they fill):**
- **A written specification of conduct that is separate from the instruction that produces it.** `CLAUDE.md` is simultaneously the instruction *and* the only statement of what good conduct is. There is no artifact a reviewer can hold up next to a transcript and ask "did this happen?" — the instruction and the rubric are the same document, which means the rubric cannot be wrong independently of the instruction.
- **The lucky-correct negative as a test case.** Named above; it is the single most valuable thing in this repo.
- **Layered diagnosis of judge disagreement.** `eval_correction.py` produces precision ~0.4 / recall ~0.5 and no account of which layer owns the error.

**They do not address (gaps in their design we fill):**
- **Delivery.** The spec says clients SHOULD NOT inject behavior specs into runtime prompts. So a `BEHAVIOR.md` cannot change behavior; it can only describe it. Everything Tessera does about conduct is a hook that fires whether the model elects it or not (principle #17).
- **Everything about the agent's own reliability** — fatigue, compaction recovery, restore integrity, escalation, spend envelopes, degraded reporting. This is ADR-0006's line and it holds unchanged.
- **Fail-loud discipline.** Nothing in the standard addresses what tells you the judge died. A trajectory judge that silently returns `not applicable` for every trigger is indistinguishable from a compliant agent — their own fold rule half-acknowledges this ("prevents an all-not-applicable trajectory from silently becoming a pass") and then leaves it to the harness.
- **Trace instrumentation.** They say "if the trace cannot expose a behavior that matters, improve the behavior's observability or the trace instrumentation" — and stop. Tessera's entire hook layer is that sentence, built.

---

## 3. Integration cost

**Adopt fully (move Tessera's conventions into `.agents/behaviors/`):**
- Switching cost: mechanically small — the "Working conventions" section of `CLAUDE.md` is already written in near-behavior-spec shape (each convention states when it applies, what to do, and what failure it prevents).
- What is lost: **the channel.** `CLAUDE.md` is eagerly loaded; `.agents/behaviors/` is by specification *not*. Moving a convention there converts a guaranteed delivery into a review artifact — principle #17 in reverse, deliberately. Tessera has paid for this exact mistake: the #17 gap (gate recording rode pure model recall and missed ~85% of gates) was closed by adding a *hook*, not by writing the rule more clearly.
- What is gained: interop with a client population that is currently **zero**.

**Adopt patterns (steal ideas, keep Tessera):**
- Which patterns: the calibration fixture matrix (positive / negative / **lucky-correct negative** / outside-scope / allowed-boundary); the five-layer disagreement diagnosis; the trigger-occurrence unit ("first decide whether the trigger occurs; when it does, identify each firing and judge the conduct for that occurrence"); the separation of evaluated-agent from judge ("the evaluated agent does not receive the behavior spec solely because it is being evaluated").
- Implementation effort: the fixture matrix is a small, self-contained addition to `scripts/mnemos/eval_correction.py` — new fixtures plus a disagreement-layer field. Hours, not days. The rest is methodology that costs nothing to hold.

**Hybridize (run both):**
- Coexistence cleanliness: perfect. `.agents/behaviors/` collides with nothing Tessera owns, and the CLI is a linter with no runtime.
- Conflict point, and it is the only one: **two statements of the same convention drift apart silently.** A `BEHAVIOR.md` describing the suggestion gate plus a `CLAUDE.md` paragraph describing the suggestion gate is two sources of truth, and this repo has a documented, repeated failure mode of exactly that (the whole reason `scripts/doccheck.py` exists). If a spec file is ever written here, one of the two must be generated from the other or asserted equal by doccheck.

**Continue without (maintain our own forever):**
- Implicit maintenance burden: already being paid. Nothing here reduces it.
- Gaps that remain: no conduct rubric separable from the instruction; no lucky-correct-negative test shape; and the artifact-counting problem in §6 stays unexamined.

---

## 4. Pattern-level vs implementation-level

| Pattern | Verdict | Notes |
|---|---|---|
| **Calibration fixture matrix, incl. the lucky-correct negative** | **Idea-only — ADOPT** | The one thing here Tessera does not have in any form. Lands in `scripts/mnemos/eval_correction.py`. See §6. |
| **Five-layer disagreement diagnosis** (wording / fixture / judge / telemetry / policy) | **Idea-only — ADOPT** | Ships with the fixture matrix; it is the field you record when a fixture disagrees. Cheap and it prevents the specific failure of "tune the detector until the fixture passes." |
| **Judge conduct over a trajectory, not the artifact the conduct emits** | **Idea-only — HELD OPEN** (observatory, dated trigger) | The most consequential idea, and it is a decision about *Tessera's* instrumentation with zero calibration data behind it today. Deciding it here would be deciding on a README. See §6 and the sequencing note. |
| **Trigger-occurrence as the judging unit** | **Idea-only — held open with the above** | Sharper than a per-session score. `tessera-gate-scan` already counts gate-*shaped turns*, which is a crude version of this; the refinement is judging each occurrence rather than diffing counts. |
| **Evaluated agent must not see the spec because it is being evaluated** | **Idea-only — ADOPT as a rule, no code** | Tessera would violate this by default: `CLAUDE.md` is eagerly loaded, so any conduct judge run over Tessera's own transcripts is measuring a *behavior-conditioned* agent. That is a legitimate experiment but it answers a different question, and the ADR should say so before anyone reads a number as if it were observational. |
| **`BEHAVIOR.md` under `.agents/behaviors/`** | **SKIP for now — Watching** | Not delivered at runtime, zero third-party clients, and a second statement of conventions that already exist here. Revisit on the Watching conditions above. |
| **The `agentbehavior validate` CLI** | **Skip** | A frontmatter linter for files we are not writing. `scripts/skill_lint/` already does the equivalent job for the artifacts we do write. |
| **Braintrust `Eval` harness + gateway (from `examples/`)** | **Skip — and it is the dependency to avoid** | Provider-coupled judging. ADR-0014 made the review backend a seam precisely so Tessera would not be single-provider on judgement; taking a Braintrust-shaped judge now would walk back into that. |
| **Intent / Evidence / Decision / Execution / Recovery / Failure-modes dimension set** | **Idea-only — weak, no action** | A reasonable prose skeleton. Tessera's contracts (`docs/contracts/*.md`) already cover the same ground per mechanism. Not worth a rewrite. |
| **Unspecified scoring/fold** | **Skip** | Correct for a standard, useless as a tool. If Tessera builds a conduct judge it needs an opinion, and their example fold (`false` beats `true`, all-`not applicable` is not a pass) is a fine starting default. |

---

## 5. Lock-in & maintenance

**If we adopt (the patterns, per §6):**
- What depends on their continued maintenance: **nothing.** The adopted items are a test-case taxonomy and a diagnostic vocabulary, both read once from an Apache-2.0 Markdown file. If the project sunsets tomorrow, the fixtures already written keep working.
- Exit story: not applicable — there is nothing to exit.
- The path that *would* create dependency is the one being skipped: Braintrust's `Eval` + gateway as the judging harness.

**If we do not adopt:**
- Cost of maintaining the equivalent: near zero for the adopted patterns; they *are* the equivalent, written down.
- Lock-in risk to our own design — the honest one: Tessera's conduct instruments are artifact counters, and every one of them was built that way because counting is what a hook can cheaply do. That is a design commitment made by convenience and never examined. See §6.

---

## 6. Decision

**Verdict: Watching** — adopt two methodology patterns now, hold one instrumentation question open with a dated trigger, take no dependency, do not write `BEHAVIOR.md` files yet.

**Reasoning.**

The shipped artifact is a frontmatter linter and a directory convention. Judged as software, this is nearly nothing: 16 commits, one `validate` verb, zero third-party clients, and a standard whose central instruction to implementers is *do not load these files at runtime*. Judged as software, the answer is a fast no, and the 250 stars are attention, not evidence.

But it should not be judged as software, and the framework-evaluation methodology's §4 exists for exactly this: the question is whether the *idea* is worth taking. Two are.

The first is small and immediately actionable: the **calibration fixture matrix**, and specifically the **lucky-correct negative** — a trajectory where the outcome is right and the required process was not followed. Tessera has named this failure mode more times than any other. It is Standing pattern #2 ("it did not break, it produced something plausible"); it is the spend backstop sitting at 47 fires against a cap of 3 and returning "nothing to report" for weeks; it is `doccheck` reporting *12 checks, 0 false claims* while three wired hooks ran on a bare interpreter. Tessera has never once had a **test shape** for it. `scripts/mnemos/eval_correction.py` scores a detector against silver labels — positives and negatives — and has no case that asks "would this have passed for the wrong reason?" That fixture is hours of work and it lands in a file that already exists.

The second is the find, and it is not about Agent Behavior at all. **Every conduct instrument Tessera owns measures the artifact the conduct emits, not the conduct.** Measured in `.tessera/logs/` on 2026-08-06:

```
suggestion_gate  204 events / 36 sessions   fired 199 · held 5 (2.4%) · retro 34
spend_denied     124                        spend_authorized 1
restore_offered    9                        restore_receipt  6
degraded           2
```

`held` at 2.4% means the friction journal is, in practice, a fired-counter. `tessera-gate-scan` diffs a count of gate-shaped turns against a count of logged events — two counts. The restore receipt records a self-reported verdict. The `degraded` contract had to add an explicit warning that coverage must not be audited by counting `degraded` calls per hook, *because doing exactly that produced three wrong findings on 2026-07-26*. CLAUDE.md already states the general form of this — "counting the artifact instead of the property is principle #3's own failure mode, aimed at the auditor" — and it is written as a warning to a specific auditor rather than as a property of the whole instrumentation layer. It is the property of the whole layer. Agent Behavior was the mirror that made it visible, the same way scryer was the mirror for iCPG's drift backlog in ADR-0013.

**Why that second item is held in the observatory and not decided here — the question was asked directly, so the answer is on the record.** It is a decision about Tessera's own instrumentation with no calibration data behind it. Deciding it in this ADR means deciding on the strength of an external project's README, which is the precise move ADR-0013 refused for iCPG kill/keep and was right to refuse. ADRs are immutable; an observatory entry carries a machine-checkable trigger that `tessera-watch` can fire. And the sequencing is real, not procedural: **the adopted fixture work produces the evidence the held question needs.** A conduct judge is only worth building if a judge can distinguish a lucky-correct negative at all, and the fixture matrix is the cheapest possible test of that. Precedent: ADR-0013 held drift-dimension retirement open in the observatory; it became ADR-0017 and ADR-0018 once numbers existed. Named risk on the other side, because it cuts both ways — the observatory is also where things go to sit; ADR-0008's cut sat unexecuted for 12 days. Hence a dated trigger, not an open one.

**Biases named.** (1) *Excitement bias* — "judge conduct, not outcomes" is articulate and flatters a framework built on exactly that premise; I read the shipped code before the prose specifically so the verdict would not be formed by the framing, and the shipped code is a linter. (2) *Confirmation bias, and it is the one that nearly landed* — I went looking for Tessera's artifact-counting problem *after* reading their trajectory-judging pitch, which is motivated search. Mitigation: the numbers above are live counts from `.tessera/logs/`, and the strongest single piece of evidence (the `degraded` audit producing three wrong findings by counting calls) predates this evaluation by ten days and is recorded in `CLAUDE.md` independently. The finding survives its own provenance. (3) *Vendor scepticism as an over-correction* — Braintrust benefits from this standard, and I notice a pull to discount the methodology because of who wrote it. The calibration document is good on its merits and the format is Apache-2.0; the correct response to vendor incentive is to take the free ideas and refuse the harness, which is what §4 does. (4) *Familiarity* — this evaluation is code-and-docs-deep. I have not authored a `BEHAVIOR.md`, not run a judge, not used Braintrust. That is a real limit and it is a reason the format is Watching rather than Reject.

**Concepts adopted (with implementation notes):**
- **The calibration fixture matrix in `scripts/mnemos/eval_correction.py`.** Add the five case types — positive, negative, **lucky-correct negative**, outside-scope, allowed-boundary — to the silver-label set. The lucky-correct negative is the load-bearing one: a session where the outcome was right and the convention was skipped. Ready-to-ship bar, taken from their document: positive/negative/outside-scope get the intended result, the lucky-correct negative stays negative, and the verdict does not depend on fixture labels or case-specific wording.
- **The five-layer disagreement diagnosis.** When a fixture disagrees with the detector, record which layer owns it — behavior wording / fixture / judge / telemetry / policy — and fix that layer. Prevents the specific failure of tuning a detector until its own fixtures pass, which is the eval-shaped form of Standing pattern #1.
- **The observational-vs-conditioned distinction, as a stated rule with no code.** Any judge run over Tessera's own transcripts is measuring an agent that was *given* the conventions eagerly in `CLAUDE.md`. That is a behavior-conditioned experiment. It answers a different question than an observational one, and no number from it may be reported as if it were observational.

**Concepts held open (observatory entry, dated trigger — not decided here):**
- **Whether Tessera's conduct instruments should judge trajectories instead of counting artifacts.** Trigger: the adopted fixture work above completes and produces a lucky-correct-negative result. Revisit by 2026-10-05 regardless.

**Concepts considered and rejected (with reasoning):**
- **Writing `BEHAVIOR.md` files for Tessera's conventions** — the format specifies non-delivery, so a spec file cannot change conduct, only describe it; and a second prose statement of conventions that already live in `CLAUDE.md` is two sources of truth in a repo that maintains `scripts/doccheck.py` because of that exact failure. Reconsider on the Watching conditions.
- **The `agentbehavior` CLI** — a frontmatter linter for files we are not writing.
- **The Braintrust `Eval` harness and gateway from `examples/`** — provider-coupled judging, directly against ADR-0014's reason for making the review backend a seam.
- **The Intent/Evidence/Decision/Execution/Recovery dimension set as a rewrite target for `docs/contracts/`** — the contracts already cover this ground per mechanism; a reformat buys nothing.
- **Adopting their unspecified fold as-is** — a standard may decline to specify an aggregation; a tool may not. If a judge is ever built, their example fold (`false` beats `true`; all-`not applicable` is not a pass) is the starting default, not the answer.

**Re-evaluate trigger conditions:**
- A **second independent client** implements `.agents/behaviors/` discovery — the format becomes interop rather than one author's convention.
- The judging harness moves from `examples/` into `packages/` behind a **provider-neutral** interface.
- The standard adds a normative statement about **trajectory/trace format** — at which point Mnemos's `claude_turns` either conforms or deliberately does not, and that is a decision.
- Tessera builds a conduct judge for any reason — at that point the format becomes the cheapest available serialization and this ADR reopens on the format question alone.
- Commit activity stops for 6 months (16 commits in ~2 months is already thin; a stall means the standard is seeded and abandoned).
- Next cadence review: 2026-10-05 (60 days, Watching).

---

## References

- https://github.com/braintrustdata/agentbehavior — README, `docs/specification.mdx`, `docs/client-implementation/adding-behaviors-support.mdx`, `.agents/skills/writing-agent-behavior/references/calibrating-with-trajectories.md`, `packages/agentbehavior/src/cli.ts`, the four `examples/.agents/behaviors/*/BEHAVIOR.md`; repo metadata and full 16-commit log read 2026-08-06
- https://www.agentbehavior.dev/ — docs site
- `docs/adr/0006-instrumentation-not-control.md` — the line this ADR applies unchanged: Tessera instruments the session
- `docs/adr/0013-scryer-evaluation.md` — the same shape of finding (external tool as mirror), and its CORRECTION block's method finding: the methodology scrutinizes the target, and the unexamined side is ours
- `docs/adr/0014-review-backend-seam.md` — why a provider-coupled judge is the dependency to refuse
- `docs/adr/0015-restore-trial-rescope.md` — the restore receipt, and why a self-reported verdict needed two parties
- `docs/design-principles.md` principle #16 (evaluate on a cadence), #17 (channel, not convention), #3 (name the pain, not the proxy)
- `.tessera/logs/*.jsonl` tallied 2026-08-06 — 204 `suggestion_gate` (199 fired / 5 held / 34 retro) over 36 sessions, 124 `spend_denied`, 9 `restore_offered` / 6 `restore_receipt`, 2 `degraded`
- `scripts/mnemos/eval_correction.py` — the silver-label eval the fixture matrix lands in (P≈0.4 / R≈0.5)
- Standing patterns #1 (the check that dies silently), #2 (fail-open produces something plausible), #3 (name the pain, not the artifact that correlates with it)
