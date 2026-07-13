# ADR-0007: The skill corpus — an unpruned inherited baseline, and what the evidence can and cannot authorize

- **Date:** 2026-07-13
- **Status:** Proposed
- **Decision driver:** FOCUS-004 executed. Principle #15 ("skill defaults are a starting point — trim or expand based on evidence in subsequent sessions") was written at Tessera's founding and **never executed**. 56 skills, zero ever evaluated. ADR-0006 §5 sanctioned the prune as tier-1 work (*deleted machinery cannot fail silently*).

---

## Target

- **Name:** Tessera's skill corpus — 56 `SKILL.md` files, ~802 KB, ~205k tokens
- **What it is:** A general-purpose Claude Code skill library, imported wholesale as a baseline when Tessera was scaffolded, and never pruned since.

---

## The evidence

### 1. Skills are almost never invoked

Scanned **171 transcripts / 207 MB / 34,636 event lines** across `~/.claude/projects/**/*.jsonl`,
counting real `Skill` tool-use events:

> **10 skill invocations, machine-wide, ever.**
> **Only 6 of them are from Tessera's 56-skill corpus — and all 6 are `code-review`**
> (3 conclave, 1 howler, 1 tess-dashboard, 1 tessera). **The other 55 corpus skills: zero, each.**

The remaining 4 invocations are **skills Anthropic ships**, not corpus skills: `dataviz` (2),
`claude-api` (1), `artifact-design` (1).

**That sharpens the finding rather than softening it.** Every skill invocation on this machine that
is not `code-review` belongs to a *built-in* skill. **The inherited 56-skill corpus has contributed
exactly one skill, ever.**

> **Provenance note, recorded because it nearly shipped as a false claim.** The "6" was gathered by
> a subagent that counted only the 56 corpus names. An earlier draft of this ADR reported it as
> *"6 skill invocations in the entire history of the machine"* — **which is false; the true
> machine-wide figure is 10.** The error was caught by the spec-12 verify hook forcing an
> independent re-derivation. **A delegated count is a claim, not a fact, until you re-run it
> yourself.**

### 2. In *Tessera*, most skills cannot fire even in principle

`git ls-files` by extension: **161 `.md`, 123 `.py`, 49 `.sh`, 20 `.json`.** Zero `.ts`/`.tsx`/
`.dart`/`.kt`/`.java`/`.css`. No `package.json`, `tsconfig.json`, `pubspec.yaml`, `build.gradle`,
`wrangler.toml`, `serverless.*`, `firebase.json`.

**22 of the 25 `paths:` triggers match 0 tracked files in this repo.** They have never fired here
and cannot.

Only **3** match anything: `python` (**123** files), `supabase-python` (**123** — the same files),
and `database-schema` (**1**, and only because the repo vendors a whole `cortex-mcp/` subtree).

> *Corrected 2026-07-13 by the spec-12 adversary, which **REFUTED** the original text.* The first
> draft said "19 of 25" and called `supabase-python` "the exception." Both wrong: the zero-count is
> **22**, and `python` matches **the identical 123 files** — so `supabase-python` is not *the*
> skill that can misfire, it is the *inappropriate* one that can.

### 3. Several skills are corpses of another framework

`agent-teams` opens: *"Every project initialized with **Maggy** runs as a coordinated team of AI
agents. This is the default workflow, not optional."* Four skills name Maggy (`agent-teams`,
`autonomous-testing`, `council-review`, `workspace`). The `maggy` CLI is **absent**, as are
`~/bin/deepseek`, `~/bin/gemini`, `~/bin/validate-plan`, `~/bin/review`, `codex`, `joern`,
`codeql`.

### 4. Tessera ships a council that CANNOT APPROVE ANYTHING — and nothing reports it

> **This section was REWRITTEN after the spec-12 adversary returned PARTIAL on the original
> claim. The original was wrong, and the truth is worse.**

The original claim was: *"`council-review` orders the agent to run commands that do not exist."*
**False.** The skill names `~/bin/validate-plan` and `~/bin/review`, which are indeed absent — but
the bare names **resolve on PATH to Tessera's own `bin/`**, where `validate-plan` and `review` are
**git-tracked, executable, and real** (imported in `ad19913 Import Maggy baseline (pre-prune)`).

**They run. And they can never succeed.** Live output:

```
$ bin/validate-plan --threshold 2 <plan>
[validate-plan] 3 reviewers, threshold=2
[validate-plan] DeepSeek Pro: CHANGES_NEEDED
[validate-plan] Codex:       CHANGES_NEEDED
[validate-plan] Gemini Pro:  CHANGES_NEEDED
{ "verdict": "CHANGES_NEEDED", "approvals": "0/3", "threshold": 2,
  "reviews": { "deepseek": { "approved": false,
      "reason": "[Errno 2] No such file or directory: '/Users/lorenzociacci/bin/deepseek'" },
               "codex":    { "approved": false,
      "reason": "[Errno 2] No such file or directory: 'codex'" }, ... } }
```

Every reviewer backend is missing, so **approvals are structurally pinned at 0/3 against a
threshold of 2.** The failure is reported only inside a JSON `reason` field that nothing reads.

**The skill tells the agent to gate on this.** `council-review` says: *"Do not skip council
validation for CLAUDE-tier tasks"*, and *"**0 of 3 → revise plan, re-validate**."* An agent
obeying it enters an **unbounded revise-revalidate loop**, because approval is unreachable by
construction. Separately, neither binary ever reads `~/.claude/council.yaml` (`grep -c council`
→ **0**), which the skill documents as its configuration.

**This is not a dead skill. It is a live mechanism that fails in the shape ADR-0006 named — it
runs, it returns a verdict, the verdict is an artifact of its own brokenness, and nothing says
so.** It is exactly the class of bug the 2026-07-12 postmortem was written about, and it has been
sitting in `bin/` since the Maggy import.

**We audit hooks for fail-open. We had never once audited skills, and we had never once run the
binaries the skills point at.** That is a finding about the *checker*, not just the skill — and by
the standing rule (CLAUDE.md), it must leave a check behind.

### 5. One dead skill is actively misfiring

**`supabase-python`** declares `paths: ["**/*.py", "supabase/**"]`. The first glob matches **123
tracked Python files in Tessera.** Editing `scripts/doccheck.py` can auto-load 16 KB of FastAPI +
Supabase + SQLAlchemy into a framework session with no web server and no database. It is the only
skill on the **cut list** doing *active* harm rather than merely occupying space.

*(`python` declares the same `**/*.py` glob and matches the same 123 files — but it is on-topic
and is a TRIM, not a CUT. `database-schema` matches exactly 1 file, and only because the repo
vendors a `cortex-mcp/` subtree.)*

### 6. `ai-models` is stale enough to mislead

Header: *"Last Updated: December 2025."* Names `claude-opus-4-5-20251101` as flagship; recommends
"Claude Opus 4.5, o3, Gemini 3 Pro". It is **2026-07-13**; the current models are Opus 4.8 /
Sonnet 5 / Haiku 4.5 / Fable 5. Claude Code now ships an authoritative `claude-api` skill whose
own instruction is *never answer from memory*. A stale model table inside the one repo whose
`CLAUDE.md` reasons carefully about model tiers is a hazard.

### 7. The corpus is duplicated, and Tessera is the only project that duplicates it

`tessera/skills/` and `~/.claude/skills/` are **independent, byte-identical copies — 56/56, zero
drift.** Both registries load in Tessera, so every skill appears **twice** in the session's skill
list. **Tessera is the only project on the machine with a local skills dir**; all 20+ others
(conclave, howler, and every Supabase / mobile / other-language project) load the global registry
only.

### 8. The skill corpus has no downstream consumer

**`bin/tessera-new-project` ships ZERO skills.** (`grep -n "skill"` → no matches.) The scaffold
installs Mnemos hooks, the gate recorder, escalation, the spend guard + backstop, settings and
config — and no skills.

---

## The audit result

56 skills judged on: invocation count, whether the declared backend exists, whether the `paths:`
trigger can match, and overlap with Tessera's own machinery.

| Verdict | Count |
|---|---|
| **CUT** | 44 |
| **TRIM** | 7 — `base`, `security`, `code-review`, `icpg`, `python`, `council-review`, `cross-agent-delegation` |
| **KEEP** | 2 — `framework-evaluation`, `polyphony` |
| **DEFER** | 3 — `mnemos` (pending its own trial), `code-graph` (backend live, doc wrong), `gemini-review` (names the wrong wrapper) |

*(Revised from 47/5/2/2 by the second correction below. `council-review`, `cross-agent-delegation`
and `gemini-review` were wrongly cut — their backends are real and merely misnamed.)*

Full per-skill ledger with evidence: `_project_specs/todos/focus-004-audit.md`.

**Of the 44 cuts, 22 are the stack/infra skills, and those are DEFERRED, not decided — see
"NOT decided" below. The count of skills this ADR actually authorizes cutting today is 22.**

---

## The correction — and it is the reason this ADR exists

**The first draft of this prune was overreach, and it is recorded here rather than quietly fixed.**

The recommendation was "cut 47, ship none." Two facts kill it:

1. **The invocation count is blind to the use that matters.** A `paths:` auto-load **emits no
   `Skill` event.** "Zero invocations" therefore says *nothing* about whether `supabase`,
   `flutter`, or `react-web` have been loading and doing real work in the projects that *do* have
   `supabase/`, `*.dart`, and `*.tsx` files. Tessera's evidence proves those skills are dead **in
   Tessera**. It proves nothing about the other 20 repos. Cutting them on it would be cutting on
   a measurement that is blind to exactly the use in question.

2. **Cutting `tessera/skills/` would not even reduce Tessera's context.** The byte-identical
   global copy still loads. The only prune that achieves the stated goal targets
   **`~/.claude/skills/` — the registry shared with every project on the machine.**

> **So the honest scope of this ADR's authority: the evidence gathered is sufficient to condemn
> skills that are dead *everywhere* (absent backends, Maggy corpses, stale references, active
> misfires). It is NOT sufficient to condemn the stack/infra skills, which are dead in Tessera
> and unmeasured elsewhere.**

---

## ⚠️ THE SECOND CORRECTION — the multi-model stack was BROKEN, not DEAD, and I nearly deleted it

**This ADR originally condemned Tessera's multi-model stack as a Maggy corpse. That was wrong,
it was the most consequential error in the audit, and it was caught by Lorenzo asking *"what are
we short-shrifting in your sprint to carve things out?"* — not by any check.**

The stack is real. `deepseek`, `kimi`, `grok`, `qwen3`, `gemini-api`, `gemini-cli`, `research`,
`validate-plan`, `review` all live in `tessera/bin/`, which **is on PATH**. Every caller,
however, hardcoded **`~/bin/X`** — a directory that **does not exist**. So the council raised
`FileNotFoundError` on every reviewer.

**And I made the audit's own error twice more, in the same hour:**

1. I read `file not found` as *"dead subsystem."* It meant *"wrong path."* **This is F-001's exact
   confusion — `unreachable` misread as `unused`** — and `CLAUDE.md` warns about it in those very
   words. I had quoted that warning earlier in the same session.
2. Then I announced "the stack works" on the strength of `command -v` finding the files. **It did
   not work.** `deepseek`, `grok` and `gemini-api` `import httpx`, and **httpx is installed
   nowhere** — not in the venv, not in any Homebrew python. They had never executed, ever.
   `build-in-public-status` would not even *compile*. **Existence is not function** — the precise
   distinction I was, at that moment, writing into `validate-plan`.

> **The lesson, and it is the whole session's lesson: I kept auditing whether files were at the
> paths the docs claimed, and never once RAN the thing I was condemning. The one time I executed
> something, it told me the truth immediately.**

**Direction (Lorenzo, 2026-07-13): the stack is KEPT.** It is a directional bet — more local
models are coming (beyond qwen/ollama), possibly Tailscale-fronted and AWS-hosted, and **council
/ ensemble review across them is the path forward.** conclave is itself a multi-model stack.
**How Tessera and conclave interoperate — shared council, isolated, or something else — is a
DESIGN SESSION, not a prune decision, and it is deliberately not made here.**

---

## Decision

### DONE — the council no longer manufactures verdicts (`7a725f7`)

`bin/validate-plan` returned a confident `CHANGES_NEEDED 0/3` on every invocation, every part of
it an artifact of its own brokenness. Two bugs; the second is the ADR-0006 one:

1. **Path.** Reviewers resolved as `~/bin/deepseek`. Now resolved by NAME on PATH.
2. **Fail-wrong.** The resulting `FileNotFoundError` was caught and scored `approved: False` —
   **a missing backend became DISSENT**, and the council gated on it.

*Fixing only (1) would have HIDDEN (2)*: the council would have started returning 2/3, looked
healthy, and kept miscounting absent reviewers as "no".

There are **three** states, not two — and the third was found only by **driving the real council**,
after the tests were green:

| state | before | now |
|---|---|---|
| ran, answered | a vote | **a vote** |
| not installed | counted as **NO** | `unavailable` — excluded, named in JSON + stderr |
| **installed, ran, crashed** | counted as **NO** | `broken` — excluded, named in JSON + stderr |

Thresholds clamp to reviewers that actually **voted**. **Zero usable reviewers → exit 2, no
verdict.** A council that could not ask anyone must never answer `CHANGES_NEEDED`.
Pinned by `scripts/test_council.py` (7 tests).

### DONE — `bin/` is stdlib-only again, and the F-001 detector was a blacklist (`ec041d3`)

Five `bin/` scripts imported `httpx`, which exists nowhere. **Ported to `urllib.request`** — *not*
by adding httpx to the venv: `bin/` is reached by a bare interpreter **name**, so it must import
only what a bare interpreter already has. They now run, and fail *honestly*
(`DEEPSEEK_API_KEY not set`) — which the fixed council correctly reads as `broken`, not as a NO.

**Why the existing F-001 detector missed it, and this is the real finding:**
`no-bare-python3-with-toolchain-import` matched a **hardcoded set of module names** —
`{mnemos, icpg, polyphony, skill_lint, pytest, yaml, requests}`. `httpx` was not on the list.
**A blacklist of names someone must remember to extend is not a detector; it is a to-do list that
fails open.** Adding `"httpx"` would have closed this escape and guaranteed the next one.

New check **`bin-scripts-are-stdlib-only`** names nothing. It states the invariant and tests it by
**execution**: *every module `bin/` imports must be findable by the interpreter it actually runs
on.* It was wrong twice before it was right, and both are pinned as regression tests: it flagged
local `sys.path` siblings (false positive), and it **skipped venv-re-exec scripts — trusting the
hatch instead of probing it**, which is the same "reaching ≠ having" error one level up.

### Decided — the skill cuts that SURVIVE the correction

Backend genuinely absent **everywhere**, so dead in every project:

- **`agent-teams`**, **`autonomous-testing`** — the `maggy` CLI is absent; both are Maggy's.
- **`cpg-analysis`** — `joern`, `codeql`, both MCP servers absent.
- **`codex-review`** — `codex` absent; needs Node, which Tessera does not have.
- **`ai-models`** — stale to the point of misleading; superseded by the native `claude-api` skill.
- **`iterative-development`** — its sole mechanism (`scripts/tdd-loop-check.sh`) does not exist;
  duplicated inside `base`. *(Eagerly loaded, so this cut is pure win.)*
- **`build-in-public`** — no frontmatter; superseded by a live plugin of the same name.

### REVERSED by the correction — these were wrongly cut

- **`council-review`** — **CUT → TRIM.** The council is *real* and now *honest*. The skill is
  wrong about it: it points at `~/bin/`, and documents a `~/.claude/council.yaml` that the
  binaries **never read** (`grep -c council` → 0). Fix the skill's paths and drop the phantom
  config; keep the mechanism.
- **`cross-agent-delegation`** — **CUT → TRIM.** `codex` is genuinely absent, but the Kimi path is
  directional. (`bin/kimi` is itself broken — it `exec`s `~/.local/bin/kimi`, which does not
  exist. Recorded, not fixed.)
- **`gemini-review`** — **CUT → DEFER.** It names `gemini`; the working wrapper is `gemini-api`.
  A naming bug, not a dead skill.

### Decided — fix the active misfire

- **`supabase-python`**'s `**/*.py` glob is over-broad and pollutes every Python session in every
  repo that isn't a Supabase+FastAPI app. Narrow it to `supabase/**` or cut it.

### Decided — de-duplicate

- **Tessera must not carry a second byte-identical copy of the global registry.** `tessera/skills/`
  is a duplicate that doubles the listing cost and buys nothing.

### Decided — the standing rule applies to skills now

- **A skill that instructs the agent to invoke a binary must have that binary.** Add a doccheck
  assertion (`skill-declared-backends-exist`) + regression test. `council-review` is the bug that
  earns it. **This is the check the fail-open leaves behind**, per CLAUDE.md's standing rule.

### NOT decided — deferred pending a measurement that has not been taken

- **The 22 stack/infra skills** (`typescript`, `react-*`, `ui-*`, `flutter`, `android-*`,
  `supabase*`, `firebase`, `aws-*`, `azure-*`, `cloudflare-d1`, `database-schema`,
  `playwright-testing`, `pwa-development`, `nodejs-backend`, `site-architecture`). Dead in
  Tessera; **unmeasured elsewhere.**
  **The missing measurement: a `paths:`-match scan across all 20 projects** — for each skill's
  globs, how many tracked files does it match in each repo? That, not the invocation count, is
  what can authorize or spare them.
- **What the skill set is FOR.** `tessera-new-project` ships none. Either skills are Tessera-local
  (and the stack skills belong only in the global registry), or Tessera should ship a curated
  subset downstream. **Unresolved. It is the structural question under the whole prune.**

- **HOW TESSERA AND CONCLAVE INTEROPERATE — its own design session, explicitly not decided here.**
  The multi-model stack is kept as a **directional bet**: more local models are coming beyond
  qwen/ollama, likely Tailscale-fronted with an AWS environment hosting them, and **council /
  ensemble review across them is the intended path.** conclave *is* a multi-model stack. Whether
  Tessera and conclave share a council, run isolated, or one fronts the other is a **design
  question with ADR weight**, and answering it inside a prune ADR would be exactly the accretion
  this document was written to catch. **Do not let a future prune session quietly decide it by
  deleting things.**
  *Prerequisite now satisfied:* the stack RUNS and FAILS HONESTLY, so the design session can be
  had against a working mechanism rather than a phantom one. That was not true this morning.

---

## The larger finding — skills as a *mechanism*

**6 invocations in 171 sessions is not a verdict on these 56 skills. It is a verdict on skills as
a mechanism.** The corpus is ~205k tokens — larger than the context window — and it bought six
tool calls.

ADR-0006 ranked five mechanism tiers by their record under adversarial pressure. **Skills were
never on that list, and on this evidence they would rank at or near the bottom**: passively
loaded, never verified, unmeasured, and — as `council-review` proves — capable of failing open
while *instructing the agent that it must not*.

That does not mean skills are worthless; `code-review` earned its six calls, and the eagerly-loaded
four shape every session. It means **the eager-load path and the `paths:` path are the only ones
that demonstrably work, and the contextual-discovery path — the one the corpus was built for — has
fired essentially never.** Design accordingly: a small number of loud, load-bearing skills beats a
large library nobody opens.

---

## Consequence for the Mnemos trial — FOCUS-004's compaction premise was falsified

FOCUS-004 was designated the compaction test vehicle on the claim that auditing the corpus is
*"genuinely read-heavy"* — ~205k tokens against a ~166k threshold, *"with no padding and no
artifice."*

**Auto-compaction did not fire. P3 remains at `0 real`.**

The audit **did not need the 205k-token read.** 47 of 56 verdicts fell to `command -v` on declared
backends, `git ls-files` by extension, and one grep over the transcripts — roughly 15 shell
commands. Reading the 40 files already condemned on mechanical evidence would have been **padding
a session to manufacture evidence for the Mnemos trial** — which FOCUS-004 explicitly forbids, and
which is the same error `trigger`-tagging was built to prevent: *a test must never become
evidence.*

> **Tessera no longer has a designated compaction vehicle.** In 171 sessions, auto-compaction has
> fired **zero** times. The trial must either find a genuinely token-heavy task, or accept that
> naturally-occurring auto-compaction is far rarer than the trial assumed — which is itself the
> answer to "is Mnemos' compaction-recovery layer worth keeping?"

---

## Re-evaluate triggers

- **Any skill's declared backend becomes installed** (`codex`, `gemini`, `joern`, `codeql`, a real
  council) → re-open that skill's cut.
- **The `paths:`-match scan across all 20 projects is run** → the 22 deferred stack skills get
  their verdict. **This ADR should be superseded, not edited, when it is.**
- **`tessera-new-project` gains a skill-shipping step** → the "what is the skill set for" question
  is answered and the deferred list must be re-judged against downstream, not Tessera.
- **Skill invocations rise materially above 6** → the mechanism-level finding weakens; revisit.
- **A future session proposes cutting the stack skills without the paths-scan** → that is drift.
  Point at this section.
