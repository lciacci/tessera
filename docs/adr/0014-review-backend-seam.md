# ADR-0014: The review backend seam — make review model-portable, or admit it is Claude-only

- **Date:** 2026-07-26
- **Status:** Accepted (Lorenzo, 2026-07-27) — **Option D: review is Claude-only, deliberately**
- **Decision driver:** Observatory **Open decision D1**, reached from two directions on 2026-07-26.
  (1) Tessera's `code-review` skill was found **shadowing Claude Code's native `/code-review`**,
  which forced the question of the skill's fate — and the observatory explicitly defers that to D1,
  *"resolved there, not piecemeal."* (2) The portability question was then put directly: what
  happens when Tessera runs in concert with **conclave**, or against **open-weight models**, or for
  a user who wants **Codex instead of Claude**?

- **Executed:** 2026-07-27 — `skills/council-review/SKILL.md`, `templates/tessera/skill-profiles.json`, `docs/design-principles.md` updated; removed: `bin/review`, `bin/kimi`, `bin/research`, `skills/tessera-code-review/`.

> **DECIDED 2026-07-27 — Option D, on evidence gathered by running the ADR's own re-evaluate
> trigger #4.** The skeleton below is preserved as written; §5's table stays *unscored* because
> the scoring is here, not there.
>
> **What the evidence showed.** Trigger #4 said "exercise `bin/review`'s existing backends."
> They do not run:
> - **`kimi`** execs `$HOME/.local/bin/kimi`, which does not exist. Recorded broken on
>   2026-07-12 and **still broken fifteen days later** — inside the review stack whose
>   portability is this ADR's subject.
> - **`codex`** is not on PATH and `OPENAI_API_KEY` is unset.
> - **`deepseek`** is sound code (urllib → `api.deepseek.com`) with `DEEPSEEK_API_KEY` unset —
>   **dormant, not dead**, which is the one correction to a flatter reading.
> - **`bin/review` had never run.** Zero commits touching it since creation.
>
> **Nobody noticed because a dead backend is indistinguishable from an unused one** — this
> repo's signature failure, applied to an architecture exactly as §"The question" predicted.
>
> So the ADR's own words were righter than it knew: the repo *"has drifted into [Claude-only]
> while keeping portable-looking artifacts that do not run."* Not "do not run" — **never ran**.
> Choosing D makes the real state explicit, and ADR-0006 ranks pruning tier 1 precisely because
> **deleted machinery cannot fail silently**, which is the failure already in progress.
>
> **The one fact arguing against D, recorded because it will matter at the re-evaluate:**
> LiteLLM is *not* hypothetical. conclave already carries `litellm/config.yaml` with a
> `model_list` and three `api_base` entries, so option B's cost is largely paid next door. If
> the conclave gateway becomes routine, B is the cheap re-entry — not C.
>
> **§4 question 4 resolved: the 978 lines are CUT**, not thinned. ADR-0008's verdict, finally
> executed after thirteen days. Harvested first per ADR-0007: the ADR gate was already split
> out as `skills/adr-gate/` in July, the review frameworks were already recorded in
> design-principles §Pass 4.3, and the one idea *not* recorded anywhere — review's position in
> the TDD loop (RED → GREEN → REFACTOR → **REVIEW** → FIX → VALIDATE → COMMIT) — was harvested
> to design-principles before the delete. The remaining ~900 lines were vendor-CLI setup and
> five GitHub Actions variants: **harness-layer** content, which §2 shows buys no provider
> portability either way.
>
> **SCOPE LIMIT, deliberate and load-bearing.** The prune stops at *review*. `bin/deepseek`,
> `bin/validate-plan`, `council-review` and `scripts/test_council.py` are **kept**: plan
> validation is a different capability that happens to share backends, it degrades honestly
> (`exit 2`, no verdict — built 2026-07-13), and **ADR-0007 says explicitly "do not cut the
> multi-model stack… do not re-litigate it without the design session."** This ADR was scoped to
> review, so it does not overrule that. `validate-plan`'s roster never included `kimi`, so the
> cut does not touch it — verified by running `scripts/test_council.py`, which stays green.

---

## The question

**Is Tessera's review layer backend-portable, or is it Claude-only with portable-looking parts?**

Today the honest answer is: *neither, quite.* The pieces for portability exist, were designed
deliberately, and are **not connected to each other**. The gap is invisible because each piece
looks healthy in isolation — the fail-open shape this repo keeps finding, applied to an
architecture rather than a hook.

---

## 1. What already exists (verified 2026-07-26, by reading)

| Piece | State | Where |
|---|---|---|
| **`bin/review`** | **Live.** Multi-model review orchestrator, runs backends in parallel. Defaults deepseek-pro + kimi; codex optional on `OPENAI_API_KEY`. API-based, not vendor-CLI. | `bin/review` |
| **`council-review` skill** | Live, 96 lines — multi-model validation council. | `skills/council-review/` |
| **`tessera-code-review` skill** | Live, 978 lines, mostly vendor-CLI setup + CI YAML. Renamed 2026-07-26 to stop shadowing. Fate = this ADR. | `skills/tessera-code-review/` |
| **conclave** | Live sibling repo. Open-weight fleet (Qwen3-32B / Gemma3-27B / Mistral-24B) behind an **OpenAI-compatible gateway**, private over Tailscale. | `~/Claude/conclave` |
| **pr-arbiter** | Live sibling. Typed-finding schema (0 contaminated / 551). Fan-out + arbiter **beats single-agent on critical recall** (88% vs 75%) for code review. | `~/Claude/pr-arbiter` |
| **LiteLLM** | **Declared, not wired.** design-principles names it the unified multi-provider abstraction. | design-principles §"Model abstraction layer" |
| **Tier routing** | Live for *task effort*, not for *review backends*. | ADR-0002, `tier-classify-hook` |

**The gap, stated plainly:** `bin/review`'s backends are effectively hardcoded. conclave exposes an
OpenAI-compatible gateway. LiteLLM is the declared abstraction. **No edge connects them.** If
Claude's review were unavailable tomorrow, there is no working alternative path — only a design
note describing one.

---

## 2. The distinction this ADR must not blur

design-principles §"Primary harness" already draws the line, and it resolves most of the apparent
conflict:

> Codex stays available as a **model provider** via LiteLLM, **not as a separate harness**.
> *(and principle #10: "Single-harness focus. Adapter sprawl is a cost, not a feature.")*

- **Provider-layer portability** — swap the model behind a review. **In scope, and the point of this ADR.**
- **Harness-layer portability** — run Tessera itself under Codex CLI / Cursor / OpenCode. **Explicitly
  rejected** and not reopened here.

The `tessera-code-review` skill's Codex/Gemini bulk (`npm install -g`, `codex exec`, GitHub Actions
YAML) is **harness-layer** content. That is why cutting it costs no provider portability — and also
why keeping it buys none.

---

## 3. Evidence already gathered (do not re-derive)

- **"Route, don't judge" is real but scope-limited.** conclave measured *select-best* (Q&A): fan-out
  judging scores *below* the best single model and pays N×. **Review is different** — it is
  *union-recall*, where you want every distinct true bug N reviewers find. That headroom does not
  saturate the same way. pr-arbiter is the evidence: the win appears exactly on the critical-recall
  tail select-best cannot see. **Both results hold; they are not in conflict.**
- **Typed findings are a convergent result, not a preference.** codex's `--json` review output and
  pr-arbiter's schema arrived at the same shape independently. Two separate efforts converging is
  the signal to standardize the seam on typed findings rather than prose.
- **Headless contract already characterized:** one non-interactive call, structured out
  (`codex exec --full-auto --json --output-last-message`). The *pattern* carries even though the
  vendor CLIs are absent.
- **`divergence.py`'s frame is right, its metric is wrong for review.** "Measure headroom offline
  before building the aggregator" — keep. But its oracle (best single *answer*, quality-graded)
  would **falsely condemn** review fan-out. Review needs an oracle of **union of true findings**,
  scored on bug-recall + false-positive rate against a labeled defect set.

---

## 4. What must be decided (OPEN)

1. **Does the seam exist as a contract, or as `bin/review`?** Is the portable unit a documented
   *contract* (any backend that accepts a diff and returns typed findings), or is `bin/review` itself
   the seam with pluggable backends behind it?
2. **What is the backend selection mechanism?** Config file, env var, `.tessera/config.yml` key, or
   the existing tier-routing hook extended from effort-tiers to review-backends?
3. **Does conclave's gateway become a first-class backend, or a LiteLLM provider behind one?** One
   fewer moving part vs. one more indirection that buys every other provider free.
4. **What happens to `tessera-code-review`'s 978 lines?** Three live options: (a) execute ADR-0008's
   cut once the seam exists and makes it redundant; (b) reduce it to a thin pointer at the seam;
   (c) keep it as vendor-CLI documentation for users who *do* have those CLIs. **This ADR is where
   that resolves — not piecemeal.**
5. **Is the fan-out actually paid for here?** pr-arbiter's win was measured on its own harness. Does
   it replicate through this seam, on this repo's defect history?

---

## 5. Options (unscored — fill in on evidence, do not pick from the armchair)

| # | Option | Buys | Costs | Open question |
|---|---|---|---|---|
| A | **Config-driven base_url in `bin/review`** — point at any OpenAI-compatible endpoint | Smallest diff; conclave works immediately | Only covers OpenAI-compatible backends | Is that enough for the real cases? |
| B | **LiteLLM behind `bin/review`** | Every provider LiteLLM supports, free | A dependency + an abstraction to maintain | Does it earn its slot (principle #11)? |
| C | **Typed-findings contract + backends as plugins** | Backend-agnostic by construction; matches the convergent schema result | Most design work; a contract to version | Who else consumes the schema — tess-dashboard? |
| D | **Do nothing; declare review Claude-only** | Zero work; honest | Kills the conclave/open-weight/Codex story | Is portability actually wanted, or hypothetical? |

**D is a real option and must stay on the table.** "We are Claude-only for review, deliberately" is
a defensible decision that this repo has never actually made — it has drifted into it while keeping
portable-looking artifacts that do not run. Choosing D explicitly would be more honest than the
status quo.

---

## 6. Success criteria for whatever is chosen

1. **A backend swap is demonstrated, not asserted** — a review runs end-to-end against conclave's
   gateway (or whichever backend is chosen) and returns findings, watched, not inferred.
2. **The Claude-unavailable path is exercised at least once.** Untested fallbacks are the fail-open
   class; a fallback nobody has run is a fallback that does not exist.
3. **Findings are typed** at the seam, not prose.
4. **The decision about `tessera-code-review`'s 978 lines is executed**, not merely recorded —
   ADR-0008's cut sat unexecuted for twelve days and produced a live shadowing bug.
5. **A check is left behind** that fails if the seam decays: at minimum, that every declared backend
   is reachable, so a silently-dead backend cannot read as "nobody used it."

---

## Re-evaluate / close triggers

- conclave's gateway becomes routinely available (it is on RunPod with cost controls, not always-on).
- Claude Code's native review becomes unavailable or rate-limited in practice — the scenario that
  motivates this.
- A downstream project asks to run Tessera against non-Claude models.
- `bin/review`'s existing backends (deepseek/kimi) are exercised and found sufficient — which would
  argue for A or D over C.

---

## References

- `docs/observatory.md` → "Tessera ↔ Conclave ↔ pr-arbiter — the review/model cluster is converging"
  (Open decisions D1–D4; the harvest home for the removed vendor-review skills)
- `docs/observatory.md` → "A Tessera skill silently shadowed a built-in command" (2026-07-26) — how D1 surfaced
- `docs/adr/0008-skill-corpus-content-audit-and-delivery-reframe.md` — the CUT-the-bulk verdict this defers
- `docs/design-principles.md` §"Primary harness", §"Model abstraction layer", principles #10 and #11
- `docs/adr/0002-model-effort-tier-routing.md` — routing precedent (effort tiers, not review backends)
- `bin/review`, `skills/council-review/`, `skills/tessera-code-review/`
