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
| **CUT** | 47 |
| **TRIM** | 5 — `base`, `security`, `code-review`, `icpg`, `python` |
| **KEEP** | 2 — `framework-evaluation`, `polyphony` |
| **DEFER** | 2 — `mnemos` (pending its own trial), `code-graph` (backend live, doc wrong) |

Full per-skill ledger with evidence: `_project_specs/todos/focus-004-audit.md`.

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

## Decision

### Decided — cut, on evidence that holds machine-wide

These are dead in *every* project, because their backends do not exist anywhere:

- **`council-review`** — cut the skill: it misdescribes its own machinery (points at `~/bin/`,
  documents a `council.yaml` that is never read) and instructs the agent into an unbounded
  revise-revalidate loop against a council that cannot approve. **But cutting the skill does not
  fix the defect — see below.**
- **`agent-teams`**, **`autonomous-testing`** — Maggy infrastructure; `maggy`, `~/bin/deepseek`,
  `~/bin/gemini` all absent.
- **`cpg-analysis`** — `joern`, `codeql`, both MCP servers absent.
- **`cross-agent-delegation`** — `codex` absent; orchestrates three hooks that are wired nowhere;
  its complexity table duplicates `polyphony`'s verbatim.
- **`codex-review`**, **`gemini-review`** — CLIs absent, Node absent.
- **`ai-models`** — stale to the point of misleading; superseded by the native `claude-api` skill.
- **`iterative-development`** — its sole mechanism (`scripts/tdd-loop-check.sh`) does not exist;
  duplicated inside `base`. *(Eagerly loaded, so this cut is pure win.)*
- **`build-in-public`** — no frontmatter; superseded by a live plugin of the same name.

### Decided — `bin/validate-plan` and `bin/review` are broken Tessera tooling, not skill debt

**These are git-tracked binaries in Tessera's own `bin/`. They run on every invocation and can
never return an approval.** Deleting the `council-review` skill removes the *instruction* to call
them; it does not remove the *binaries*, which remain on PATH for any agent or human who runs
them and will keep emitting authoritative-looking `CHANGES_NEEDED 0/3` verdicts forever.

**Either delete them, or make them fail LOUD** (ADR-0006: *a mechanism that fails open needs a
paired detector that fails loud*). A reviewer whose backend is missing must not be counted as a
reviewer who declined — that is the exact confusion `0/3` currently encodes. **This is now the
highest-priority item in this ADR, and it is a code change, not a doc change.**

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
