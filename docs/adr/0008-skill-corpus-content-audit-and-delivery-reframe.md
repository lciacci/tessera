# ADR-0008: The skill corpus, read at last — the content audit inverts the prune, and the fix is delivery, not deletion

- **Date:** 2026-07-14
- **Status:** Accepted
- **Supersedes:** ADR-0007 (its *conclusions* — the cut-heavy tally, the specific cut list, and the "compaction premise falsified" claim). ADR-0007 stays as the immutable record of the reachability error; **its corrections and lessons are carried forward here unchanged.**
- **Decision driver:** ADR-0007 ended by saying, in its own words, that **the audit had never been run** — that what ran was a *reachability sweep* mislabelled as a content audit, and that the real, read-heavy audit was still owed. FOCUS-004 (2026-07-14) ran it: all 56 `SKILL.md` bodies read in the main thread, judged on content only. The result contradicts ADR-0007's tally strongly enough to require a new ADR rather than an amendment.

---

## What actually changed between ADR-0007 and this one

**ADR-0007 did the corrections but not the work.** It correctly established *how the audit had gone wrong* — reachability substituted for value, a subtractive vocabulary authored before reading a single skill, usage spent as evidence when two causes already fully explained it — and then, crucially, it left the real judgment undone: **~31 of its verdicts were reached without reading the skill's body**, and it said so and marked them void.

This session read the bodies. That is the entire difference, and it is the difference the whole saga was about.

| | ADR-0007 (reachability) | ADR-0008 (content, bodies read) |
|---|---|---|
| Was the audit actually run? | **No** — "what ran was a reachability sweep" | **Yes** — 56 bodies read, ~200k tokens, in-thread |
| CUT / remove | **44** | **10** (1 CUT + 9 HARVEST→CUT) |
| KEEP-in-some-form | 12 (2 KEEP + 7 TRIM + 3 DEFER) | **46** (38 KEEP + 3 FIX + 3 TRIM + 1 ADAPT + 1 MERGE) |
| Basis for every removal | invocation count + `paths:`-can't-match | stale-false / superseded / foreign-product / vendor-manual — **zero on reachability** |
| Compaction premise | "**falsified** — the audit didn't need the read" | **vindicated** — the real content audit *is* read-heavy, exactly as specified |

**It is a near-exact inversion.** ADR-0007 kept 12 and cut 44; this audit keeps 46 and removes 10. Every one of the void-cuts that reversed was cut on reachability — and reading the bodies showed the overwhelming majority are **current, accurate, additive stack/agent skills, inert in Tessera by design** (they live in the global registry serving 20+ repos; `flutter` *should* be inert here).

Full per-skill ledger: `_project_specs/todos/focus-004-audit.md` → "═══ REAL AUDIT (2026-07-14) ═══".

---

## The three verdicts that flipped *because* the body was read against current state

These are the audit's proof that reading changes the answer — each reverses an ADR-0007 disposition:

1. **`council-review`: CUT→TRIM (0007) → FIX (now).** ADR-0007's own §4 documented that `bin/validate-plan` manufactured `CHANGES_NEEDED 0/3` out of its own brokenness — and then §"DONE" recorded the fix (`7a725f7`, `ec041d3`) in the *same prior session*. So by the time the body is read against current state, **the backends exist and fail honestly**: `bin/validate-plan` and `bin/review` are real and run. The skill's only remaining defect is that it points at `~/bin/` (should be `bin/`) and documents a `~/.claude/council.yaml` the binaries never read. **Good content, broken trigger = FIX**, not TRIM, not CUT.

2. **`iterative-development`: decided-cut (0007) → KEEP (now).** ADR-0007 cut it as "its sole mechanism (`scripts/tdd-loop-check.sh`) does not exist." That is reachability. On content: the mechanism it *teaches* — a Stop hook exiting 2 feeds stderr back and continues the turn, a plugin-free TDD loop — is a **real, non-obvious Claude Code capability that Tessera's own wired Stop hooks use** (`tessera-gate-scan` exits 2). The skill is a setup guide, not a false claim of an existing script. True, not superseded, good, on-path. Nothing admissible cuts it.

3. **`cpg-analysis`: decided-cut (0007) → KEEP (now), and I caught myself re-cutting it.** I first wrote "CUT — joern/codeql/MCP servers/install script all absent." Then stopped: that is verbatim ADR-0007's reachability cut of this exact skill, the one the "third correction" singled out. On the five content questions it's a correct, honestly-labeled-opt-in guide to **real tools** (Joern, CodeQL) with specialized query cookbooks a model doesn't just have. The stress test that caught me: *"if Joern+CodeQL were installed, would I keep it?"* — yes — which proved the cut was resting on the absent backend. **The exact ADR-0007 error, reproduced mid-write and corrected.** Its scope fit (does Tessera intend Tier-2/3 taint analysis?) is an open human question, but that is KEEP-or-relocate, not a cut.

---

## The 10 removals, and why each is admissible (none on reachability)

Every removal is HARVEST-first (extract the ideas, *then* cut — the base-skill licence, corrected in ADR-0007, requires it). Three honest causes:

**Stale / false (Q1):**
- **`ai-models`** — CUT. "Last Updated December 2025", names `claude-opus-4-5` as flagship; it is 2026-07-14 (Opus 4.8 / Sonnet 5 / Haiku 4.5 / Fable 5). Superseded for the Claude portion by the native `claude-api` skill. *Harvest: the provider doc-URL pointers (live links, not hardcoded IDs).*

**Fossils superseded by Tessera's own machinery (Q2) — HARVEST→CUT:**
- **`session-management`** → Mnemos automates its tiered summarization. *Harvest → design-doc as Mnemos's lineage.*
- **`code-deduplication`** → `icpg query prior` is its capability index. *Harvest the "duplicate PURPOSE not duplicate code" framing → icpg.*
- **`agent-teams`** → its structural step-enforcement (task N+1 invisible until N verifies) is the shape of Tessera's Stop-hook gates. *Also foreign-product-mandatory (Maggy). Harvest the pattern → design-doc; cut the roster + 6 `agents/*.md` files.*
- **`cross-agent-delegation`** → scoring lives in polyphony, iCPG triad in icpg; nothing unique. *Confirm-then-cut.*

**Foreign-product / vendor-manual / superseded-by-native (Q2/Q3) — HARVEST→CUT:**
- **`autonomous-testing`** — no frontmatter (malformed skill) + entirely Maggy/`~/bin/deepseek`-bound.
- **`build-in-public`** — no frontmatter + superseded by the live plugin of the same name. *Harvest the writing guidance → the plugin's docs.*
- **`code-review`** — HARVEST→CUT-the-bulk / **KEEP-the-ADR-gate**. The core `/code-review` command is now superseded by Claude Code's **native** `/code-review`; the Codex/Gemini multi-engine bulk needs Node (absent). **The ADR gate + `adr-gate.md` is the Tessera-native keeper — split it into its own small `adr-gate` skill *before* cutting the rest.**
- **`codex-review`, `gemini-review`** — vendor CLI manuals, Node-absent, subsumed by `code-review`'s engine section and native `/code-review`. *Harvest the findings JSON-schema + headless-CI + 1M-context patterns → the conclave/council design note.*

---

## What carries forward from ADR-0007, unchanged

The reframe corrects 0007's *conclusions*, not its *lessons*. These stand:

- **Every correction in ADR-0007 is right and is the reason it exists.** Usage is not evidence; reachability is inadmissible for value; the subtractive vocabulary was authored before reading; harvest-before-cut; the base-skill "git remembers" licence is code-only (fixed in `base`). This ADR is those lessons *applied*, not revised.
- **The through-line stands, and this session added a fourth line to it.** ADR-0007: three times the fault was externalised (dead subsystem → our path; cruft skills → our missing distribution; bad session → our own `base` skill). This session's near-miss on `cpg-analysis` is the fourth: *skill unusable here → the absent backend*, caught before it shipped. **Externalising is the reflex; the call is coming from inside the framework.**
- **The mechanism finding is untouched and is still the sharpest thing in either document:** a loaded skill (`ponytail`) steered judgment invisibly, and the agent was not a reliable witness to it — not while steered, not when asked. **Skills act on the agent's *reasoning*, and they are the one mechanism with no instrumentation.** That is ADR-0006's thesis reaching the skill layer, and it deserves its own spec. This audit does not close it.
- **Tessera ↔ conclave interoperation** remains a **design session with ADR weight, explicitly not decided here.** The multi-model stack is a kept directional bet. Do not let a future prune quietly decide it by deleting things.

---

## The reframe — prune → profile-gated delivery

**This is the decision, and it is what Lorenzo accepted.**

ADR-0007's own headline finding was that **6 invocations machine-wide indicts the framework's distribution and discovery, not the skills** — and its finding #8, that **`bin/tessera-new-project` ships zero skills**, is the structural cause. This content audit confirms it from the other side: the corpus is mostly *good, current, downstream-applicable* skills that **cannot reach the repos they are for.**

So the task was mis-framed. FOCUS-004 was handed over as "prune the corpus." The corpus barely needs pruning — 10 of 56 for cause. **What the framework actually lacks is a way for the good skills to reach downstream projects, selected by that project's profile** (`.tessera/project.yml` — Tessera's original IP). A Supabase app wants a different skill set than a Flutter app; the profile is the selector. Leading with cuts shrinks the corpus ~18% and changes nothing about the real failure — it is motion, not progress, and it re-enacts the deletion momentum this whole saga exists to warn against.

**FOCUS-004 pivots from *prune the corpus* to *build profile-gated skill delivery.*** The 10 cuts still happen (harvest-first), but they are cleanup on the way to the real work, not the work.

---

## Decision

**Accepted (Lorenzo, 2026-07-14):**

1. **The content audit is the corpus verdict**, superseding ADR-0007's reachability tally. Record: the REAL AUDIT section of `_project_specs/todos/focus-004-audit.md`.
2. **FOCUS-004 is re-scoped: prune → profile-gated skill delivery.** The corpus is mostly a keep; the framework's gap is distribution.
3. **ADR-0007 is superseded, not edited** — it is the record of the reachability error and the corrections that followed.

**Authorised as follow-on execution (order matters):**

- **First, HARVEST.** Work the harvest manifest in the ledger. **The load-bearing one: split `code-review`'s ADR gate + `adr-gate.md` into a standalone `adr-gate` skill before touching anything else** — `docs/adr/` is real here and doccheck asserts the index. Fossil harvests (`session-management`, `code-deduplication`, `agent-teams`) land in the design-doc.
- **Then, the 10 removals** (1 CUT + 9 HARVEST→CUT), once their harvests exist.
- **The 3 FIXes and 3 TRIMs / 1 ADAPT / 1 MERGE** are independent and safe: `council-review` (repoint `~/bin/`→`bin/`, drop phantom config), `code-graph` (correct `.mcp.json`/install claims), `supabase-python` (narrow the `**/*.py` glob — the one active misfire); `base`/`python`/`icpg` trims; `security` → downstream-only + on-demand; `ui-testing` → merge into `ui-web`/`ui-mobile`.
- **De-duplicate the registry** — Tessera must not carry a second byte-identical `tessera/skills/`; the global registry is the one that serves downstream (ADR-0007 finding #7).
- **The standing rule reaches skills** — a skill that instructs the agent to invoke a binary must have that binary; add `skill-declared-backends-exist` to doccheck + a regression test (ADR-0007's earned check; `council-review` is the bug behind it).

**NOT decided — genuinely open, needs its own session:**

- **The delivery mechanism itself.** *Which* skills a downstream gets is selected by its profile — but the mapping (profile → skill set), whether it copies or symlinks, and how it interacts with the global registry, is a design decision that intersects the profile IP. This ADR decides *that* delivery is the goal, not *how* it works.
- **Skill instrumentation** (ADR-0007's open mechanism finding) — its own spec.
- **Tessera ↔ conclave** — carried from ADR-0007, unchanged.

---

## Re-evaluate triggers

- **`bin/tessera-new-project` gains a skill-shipping step** → this ADR's reframe is realised; re-judge the KEEP set against *downstream* profiles, not Tessera.
- **A future session proposes cutting stack skills on reachability** (never-invoked / `paths:`-can't-match-here) → that is the exact drift ADR-0007 and this ADR were written to stop. Point at this section.
- **Any removed skill's superseding cause reverses** — e.g. the native `/code-review` gains the multi-engine flags, or a fossil's Tessera-machinery replacement is themselves removed → re-open that cut.
- **`ai-models`'s content is replaced with live pointers rather than hardcoded tables** → the staleness cut no longer applies.
- **Skill invocations rise materially above 6** → the mechanism-level finding (ADR-0007) weakens; revisit.

---

## References

- **ADR-0007** — the reachability error and the corrections this ADR applies. Read it first; this document is 0007's lessons executed.
- **ADR-0006** — instrumentation, not control; the thesis the skill-instrumentation finding extends.
- `_project_specs/todos/focus-004-audit.md` — the full per-skill content ledger (REAL AUDIT section) and the harvest manifest.
- **Principle #15** — "skill defaults are a starting point; trim or expand on evidence." Satisfied at last — the evidence, read, says *keep most, cut ten for cause, and build the pipe.*
