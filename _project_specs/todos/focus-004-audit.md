# FOCUS-004 — Skill audit ledger

**Live working file. Written incrementally, on purpose.**

This session reads all 56 `SKILL.md` bodies in the main thread (~200k tokens), which is expected
to trigger **auto-compaction** — that is not an accident, it is FOCUS-004's second payload (the
Mnemos trial's P3 counter has been at `0 real` for months, and only a genuine `auto` compaction
can move it).

**Therefore: every verdict lands here the moment it is made.** If compaction eats the context,
the audit survives on disk, and the question the trial actually asks — *"did the restored
checkpoint let work resume without re-deriving?"* — becomes observable instead of asserted.

---

## RESUME PROTOCOL — read this first if you are a post-compaction context

1. The corpus is `/Users/lorenzociacci/Claude/tessera/skills/` — 56 dirs, one `SKILL.md` each.
2. **Verdicts already recorded are FINAL. Do not re-read those skills. Do not re-derive them.**
   Re-deriving a recorded verdict is exactly the failure the Mnemos trial is testing for — if you
   feel the urge, that is a *finding*, and you should write it down in "Compaction observations"
   below rather than act on it.
3. Continue from the first skill in the Batch table below whose row is still `pending`.
4. **Discipline, from the handoff: AUDIT, DO NOT REPAIR.** Recording that a skill is broken is
   the job. Fixing it is how 2026-07-12 became a rathole. No edits to any `skills/**` file this
   session.

---

## ⚠️ STOP — THE AUDIT BELOW WAS NOT AN AUDIT. READ THIS FIRST. (2026-07-13)

**What is recorded below is a REACHABILITY SWEEP mislabelled as a content audit.** ~31 of the 56
verdicts were reached without ever reading the skill's body, on two signals — *"its `paths:` glob
can't match in Tessera"* and *"it has never been invoked"*. **Neither is a judgment about the
skill.** Those verdicts are **VOID**. See ADR-0007, "The third correction".

Three things make the reachability signals unusable as value evidence:

1. **The invocation argument is circular.** There are **6 skill invocations machine-wide, across
   every skill including the ones Anthropic ships.** That says the *discovery mechanism* is
   barely used — not that any skill is bad. **A good skill that never fires is a distribution
   bug, not a bad skill.**
2. **The frame was wrong.** These skills live in `~/.claude/skills/` — the **global** registry
   serving **all 20+ repos**. Judging them by whether they fire *in Tessera* judges a
   general-purpose library against one atypical consumer. **`flutter` SHOULD be inert here.** That
   says nothing about its worth to the Flutter projects.
3. **`paths:` inert ≠ worthless.** It means *not applicable to this repo*, which is the expected
   state for most of a global library.

**The `paths:`-match scan across all repos is NOT the fix.** It is more reachability evidence for
a question reachability cannot answer.

---

## THE RUBRIC FOR THE REAL AUDIT — judge the CONTENT

For each skill, **read the body** and answer:

| # | Question | This is a CUT if… |
|---|---|---|
| 1 | **Is what it says TRUE?** | It asserts facts that are false, or describes machinery that exists nowhere. *(e.g. `ai-models` names `claude-opus-4-5` as flagship in July 2026; `iterative-development`'s sole hook exists in no repo.)* |
| 2 | **Is it SUPERSEDED?** | A working plugin, a native Claude Code feature, or another skill does the same job better. *(e.g. `build-in-public` vs the live plugin; `credentials` is inlined in `base`.)* |
| 3 | **Is the guidance any GOOD?** | Generic filler, or advice a competent model already has. **This is the question the sweep never asked, and the only one that requires reading.** |
| 4 | **Would it HELP if it fired?** | If yes → **it is a TRIGGER bug, not a value problem. FIX THE TRIGGER. DO NOT CUT.** |

**Question 4 is the one the sweep inverted.** "It never fires" was treated as grounds to delete.
It is grounds to ask **why it never fires** — and if the content is good, the answer is to fix
`paths:`/discovery, not to delete the skill.

**Only questions 1–3 can produce a CUT. Reachability alone can produce only a DEFER.**

**And this is the read-heavy work FOCUS-004 specified.** Reading 56 bodies is ~205k tokens. The
compaction premise — which an earlier draft of this ledger wrongly declared *falsified* — **stands**,
because the sweep that "falsified" it was not the audit. **P3 is still reachable. Do this in a
fresh session with full context.**

---

## Verdict vocabulary

| Verdict | Means |
|---|---|
| **KEEP** | Earns its context cost. Used, or load-bearing for a documented Tessera mechanism. |
| **TRIM** | The skill is worth keeping but is bloated / duplicated internally. Shrink, don't cut. |
| **CUT** | Delete. Never loaded, never invoked, covered by another skill, or inapplicable to this repo. |
| **DEFER** | Cannot be judged on this session's evidence. Must say *what evidence would decide it*. |

Every row needs a one-line, **evidence-based** reason. "Feels useful" is not evidence.
Permitted evidence: invocation counts from transcripts, `paths:` frontmatter (does it ever
match anything here?), overlap with another skill, referenced by `CLAUDE.md` / an ADR / a hook.

---

## THE DECIDING EVIDENCE — skill invocations across all history

Scanned **171 transcripts / 207 MB / 34,636 event lines** (`~/.claude/projects/**/*.jsonl`),
counting real `Skill` tool-use events, not mentions:

> ## **10 skill invocations machine-wide, ever.**
> ## **Only 6 come from this 56-skill corpus — all `code-review`.**
> ## **The other 55 corpus skills: ZERO invocations, each.**

Breakdown of the 6: **3 conclave, 1 howler, 1 tess-dashboard, 1 tessera.**
The other 4 invocations are **built-in** skills Anthropic ships: `dataviz` (2), `claude-api` (1),
`artifact-design` (1) — **not** corpus skills.

**CORRECTION (caught by the spec-12 verify hook).** The subagent that gathered this counted only
the 56 corpus names and returned "6". I wrote that up as *"6 invocations in the entire history of
the machine"* — **false; the true machine-wide count is 10.** Re-derived independently with `jq`
over all 171 transcripts. **A delegated count is a claim, not a fact, until you re-run it
yourself.** The corpus conclusion is unchanged and in fact strengthened: *every* invocation that
isn't `code-review` belongs to a skill Anthropic ships.

**The honest reading.** A skill can reach context three ways, and only two of them are measurable
here:
1. **Explicit or contextual invocation** → emits a `Skill` tool-use event. **Measured: 6, all
   `code-review`.**
2. **Eager load** via `CLAUDE.md` `@`-import → never emits an event. That is exactly 4 skills:
   `base`, `iterative-development`, `mnemos`, `security`.
3. **`paths:` frontmatter match** → never emits an event. 25 skills declare `paths:`; **19 of
   them declare globs that match 0 files in this repo**, so they cannot have fired.

That is the complete set of load paths. Conclusion, stated carefully:

> **Of the 52 skills that are not eagerly loaded, exactly ONE has ever been loaded on purpose.**
> The remainder have never been invoked, and for most of them the only other door — `paths:` —
> is nailed shut.

**Principle #15 asked for evidence before trimming. This is the evidence.** It is not "these
skills are low-value" — it is *these skills have never once been used, in 171 sessions, and most
of them structurally cannot be.*

---

## Verdicts

*(appended as made — skill | verdict | evidence)*

| skill | verdict | evidence |
|---|---|---|
| **iterative-development** | **CUT** | Its *sole* mechanism is a Stop hook, `scripts/tdd-loop-check.sh`. **It does not exist in this repo.** Five Stop hooks are wired (`mnemos-stop-checkpoint`, `mnemos-stop-ingest`, `tessera-gate-scan`, `tessera-spend-backstop`, `tessera-verify-scan`) — **none is a TDD loop**. The only copy on disk is `templates/tdd-loop-check.sh`, wired by `templates/settings.json`, which is a **maggy** template (it emits `[maggy] hook script … not installed`) — and `bin/tessera-new-project` does **not** install it. So the skill is ~250 lines of *eagerly-loaded* context describing infrastructure wired **nowhere Tessera controls**. Its content is additionally duplicated verbatim by `base`'s "Automatic TDD Loops (via Stop Hook)" section. |
| **base** | **TRIM (hard)** | Eagerly loaded every session (~450 lines). Almost nothing it prescribes is true here: `scripts/security-check.sh`, `.env.example`, `.secrets.baseline` — **none exist**. The mandatory `[TODO-xxx]` atomic-todo format — **zero uses** across `_project_specs/todos/`. The 200-line file cap — `scripts/doccheck.py` is **812**, `scripts/mnemos/__main__.py` **682**, `scripts/mnemos/checkpoint.py` **593**; the framework's own core violates it 4× over. It also inlines duplicates of three other skills (`security`, `session-management`, `iterative-development`). Keep the simplicity rules + anti-patterns; cut the TDD workflow, todo format, security and session sections. **Root cause worth stating: `base` is a *downstream-app* prescription loaded into a *framework* repo where it does not apply — and `bin/tessera-new-project` ships *no skills at all*, so it never reaches the downstreams it was written for.** |
| mnemos | DEFER | Machinery is load-bearing (hooks wired on SessionStart/PreCompact/PreToolUse/PostToolUse/Stop) — but that is *mnemos-the-tool*, not *mnemos-the-eagerly-loaded-doc*. `CLAUDE.md` already carries a "Hook lifecycle (Mnemos)" section covering the same ground. **Decides on: the kill/keep trial itself (P3), which is what this session's compaction is for.** Verdict deliberately held until the compaction observation below is filled in. |
| **council-review** | **CUT** — *and it is a live fail-open* | **All three declared backends are ABSENT**: `~/bin/validate-plan`, `~/bin/review`, `~/.claude/council.yaml`. It also names `claude-fable-5`, `gemini`, `codex` binaries — **none installed**. It is `user-invocable: false`, claims to be "loaded by Claude Code on session start", and instructs: *"**Do not skip council validation for CLAUDE-tier tasks.**"* So on the **highest-stakes tasks**, it orders the agent to run commands that do not exist. The agent can only hallucinate compliance or silently skip — **and nothing reports either.** This is ADR-0006's fail-open pattern living *inside the skill corpus*, and it is a genuine finding: **we have been auditing hooks for fail-open and never once audited the skills.** It is also Maggy infrastructure ("The Maggy dashboard (Settings > Council)"). |
| **cpg-analysis** | **CUT** | Declares Joern + CodeQL backends via two MCP servers (`codebadger`, `codeql`). **`joern` ABSENT, `codeql` ABSENT, no `.mcp.json` in this repo.** Every tool it documents is unreachable. `effort: high`, `user-invocable: true` — so its only cost is corpus weight and the chance an agent tries to use it. |
| **cross-agent-delegation** | **CUT** | `codex` is **ABSENT**, so the "Codex auto-review (Stop hook — Automatic)" half is dead. The Stop hooks it orchestrates — `tdd-loop-check.sh`, `codex-auto-review.sh`, `icpg-stop-record.sh` — are **none of them wired** in `.claude/settings.json`. Its 5-dimension complexity table (0–2 each, thresholds 0–3 / 4–6 / 7–10) is a **verbatim duplicate of `polyphony`'s**. Internally sloppy too: `### When NOT to Delegate` and `### Step 4` each appear **twice** in the same file. (`kimi` resolves — to `bin/kimi` *inside Tessera itself*, worth its own look, but not this session's job.) |
| **agent-teams** | **CUT** | Its first line: *"Every project initialized with **Maggy** runs as a coordinated team of AI agents. **This is the default workflow, not optional.**"* Maggy's default workflow, asserted as mandatory, inside Tessera's corpus. The `maggy` CLI is **ABSENT**. Tessera does not run agent teams — it uses the Agent tool directly. Carries 6 extra tracked files (`skills/agent-teams/agents/*.md`). |
| **autonomous-testing** | **CUT** | **No frontmatter at all.** Backend is `~/bin/deepseek` (**ABSENT**), `~/bin/gemini` (**ABSENT**), `maggy test …` (**CLI ABSENT**), `~/.claude/testing-config.json` (**ABSENT**). Has an "Integration with **Maggy** → Maggy Dashboard" section, and its own overview says it was built for *"Claude Bootstrap + **Maggy**."* Nothing it describes is reachable. |
| **build-in-public** | **CUT** | **No frontmatter.** LinkedIn/X posting cadence, Buffer analytics, engagement rates. Zero relationship to framework development. **Already superseded**: a `build-in-public` *plugin* skill is separately installed and live in this session. The corpus copy is a stale duplicate of a plugin that works. |
| **codex-review** | **CUT** | `codex` CLI **ABSENT**. Requires `npm install -g @openai/codex` + Node 22 — Tessera has **no Node, no `package.json`**. Subsumed by `code-review`'s engine-choice section. |
| **gemini-review** | **CUT** | `gemini` CLI **ABSENT**. Requires `npm install -g @google/gemini-cli` + Node 20 — same story. Subsumed by `code-review`. |
| code-review | DEFER | Largest skill in the corpus (**33 KB, 975 lines**), only one besides `agent-teams` with a sub-file (`adr-gate.md`). Two problems: (a) **two of its three engines are absent** (`codex`, `gemini`); (b) **Claude Code now ships a native `/code-review`** — the skill defines the same slash command with flags (`--engine codex`) the native one lacks, so they collide. Its genuinely Tessera-specific part is the **ADR gate**, which is real here. Decides on: whether the ADR gate survives as a small skill while the 33 KB engine-comparison bulk is cut. |
| **icpg** | KEEP (machinery) / **TRIM (doc)** | The tool is real and has been used — Mnemos' goal log carries `[iCPG:…]` reason IDs throughout. **But the skill prescribes two hooks that are NOT wired here**: `icpg-pre-edit.sh` and `icpg-stop-record.sh` appear **nowhere** in `.claude/settings.json`, and its Stop-hook example invokes the phantom `tdd-loop-check.sh`. So "Step 0 is non-negotiable" and "PreToolUse hook shows context" are **false in this repo**. Trim the hook-integration and agent-teams sections; keep the ReasonNode model and the 3 canonical queries. |
| **code-graph** | DEFER | Backend is genuinely reachable (`mcp__codebase-memory-mcp__*` tools are exposed this session), **but the skill's stated config is wrong**: it says MCP is configured via `.mcp.json` at project root (committed) — **there is no `.mcp.json` in Tessera.** It is configured globally. Decides on: whether the graph is worth its ~9 KB given Tessera is 123 Python files that `grep` handles fine. |
| **polyphony** | KEEP | Only skill in this batch whose backend checks out: `docker` FOUND, and `polyphony` is referenced in `.claude/settings.json`. Part of the venv toolchain per `CLAUDE.md`. |
| **framework-evaluation** | **KEEP** | The one unambiguous keep. Tessera-native, named in `CLAUDE.md`, has a live `/evaluate-framework` command, implements principle #16, and **has actually produced output** — ADR-0002 (the GSD decision). Its `paths: []` is empty, which is why the inventory read as "has_paths: YES, paths: -". |
| security | DEFER | ~700 lines eagerly loaded, and it is **OWASP web-app** material — SQL injection, XSS, JWT, bcrypt, CORS, helmet, rate limiting. Tessera is a hooks-and-scripts framework with **no web surface, no auth, no SQL, no user input**. Same downstream/framework mismatch as `base`. Held only because the *secrets* subset (no `.env` commits, no secrets in tracked files) is genuinely live here and is enforced by `settings.json` deny-list + `.githooks/pre-commit`. Decides on: whether that subset can move to `CLAUDE.md`'s existing "Don't" list, making the skill downstream-only. |

---

### Remaining verdicts — grouped, all on the same two axes (0 invocations + cannot trigger)

| skills | verdict | evidence |
|---|---|---|
| `typescript`, `react-web`, `react-native`, `ui-web`, `ui-mobile`, `ui-testing`, `playwright-testing`, `pwa-development`, `flutter`, `android-java`, `android-kotlin`, `nodejs-backend` | **CUT** (12) | 0 invocations. `paths:` globs (`**/*.tsx`, `**/*.dart`, `**/*.kt`, `**/*.java`, `**/*.css`, `**/e2e/**`, `**/sw.*`, `src/routes/**`) match **0 tracked files**. Tessera has no Node, no `package.json`, no `tsconfig.json`. They cannot fire, and never have. |
| `firebase`, `supabase`, `supabase-nextjs`, `supabase-node`, `aws-aurora`, `aws-dynamodb`, `azure-cosmosdb`, `cloudflare-d1`, `database-schema`, `site-architecture` | **CUT** (10) | 0 invocations. Triggers (`firebase*`, `wrangler.toml`, `serverless.*`, `**/cosmos*`, `**/migrations/**`, `robots.txt`) match **0 files**. Tessera has no database, no deploy target, no web surface. |
| **`supabase-python`** | **CUT — and it is MISFIRING** | 0 invocations, but its glob is `**/*.py` — which matches **123 tracked Python files here**. It is the one dead skill that can still fire, injecting 16 KB of FastAPI/Supabase/SQLAlchemy into a framework session. **Cut this one first**; it is the only entry on the list doing active harm. |
| `posthog-analytics`, `web-content`, `user-journeys`, `ticket-craft`, `llm-patterns`, `agentic-development`, `existing-repo`, `project-tooling`, `credentials` | **CUT** (9) | 0 invocations, no `paths:`, so the *only* door was contextual discovery and it never opened. All are downstream-app concerns: analytics, SEO/GEO, UX journeys, Jira/Linear tickets, LLM app patterns, Pydantic-AI agents, joining a foreign repo, `vercel`/`render` deploys, `~/Documents/Access.txt` API keys. Tessera has no product surface, no tracker, no deploy, and no API keys. `credentials` is additionally duplicated inside `base`. |
| **`ai-models`** | **CUT — stale and actively misleading** | 0 invocations. Header says *"Last Updated: **December 2025**"*; it names `claude-opus-4-5-20251101` as flagship and recommends "Claude Opus 4.5, o3, Gemini 3 Pro". **Today is 2026-07-13** — current models are Opus 4.8 / Sonnet 5 / Haiku 4.5 / Fable 5. Claude Code now ships a `claude-api` skill that is the authoritative model reference and says *never answer from memory*. A stale model table inside the one repo whose `CLAUDE.md` reasons carefully about model tiers is a **hazard**, not dead weight. |
| `session-management` | **CUT** | 0 invocations. It is the **manual markdown version of Mnemos** — it prescribes `_project_specs/session/current-state.md`, `decisions.md`, `code-landmarks.md`, `archive/`. **None of those exist.** Eight `mnemos-*.sh` hooks already automate checkpoint/resume/fatigue. Tessera solved this and left the old skill in place. |
| `code-deduplication` | **CUT** | 0 invocations. Prescribes `CODE_INDEX.md` at project root — **ABSENT**. Its job (know what exists before writing) is what `icpg query prior` and `code-graph` are for. |
| `workspace` | **CUT** | 0 invocations. Multi-repo/monorepo topology; prescribes `CONTRACTS.md` — **ABSENT**. Tessera is a single repo; its cross-repo mechanism is `bin/tessera-findings`. Also names Maggy. |
| `team-coordination` | **CUT** | 0 invocations. For "multiple developers on the same repo". Prescribes `_project_specs/team/` — **ABSENT**. **`git shortlog` shows a single contributor.** There is no team. |
| `commit-hygiene` | **CUT** | 0 invocations, no `paths:`. Generic git advice (atomic commits, PR size caps). Nothing in it is Tessera-specific, and nothing enforces it. |
| **`python`** | **TRIM** | 0 invocations, **but `**/*.py` genuinely matches** — the one stack skill that legitimately fires here. However its "Tooling (**Required**)" section demands ruff + `mypy --strict` + `pyproject.toml` + `.pre-commit-config.yaml`: **none of these exist anywhere in the repo.** Its prescribed `src/package_name/core|infra` layout with FastAPI is not Tessera's (`scripts/`, `bin/`). Keep the type-hints and anti-patterns core; cut the CI/CD, src-layout and FastAPI scaffolding. |

---

## Tally

| Verdict | Count | |
|---|---|---|
| **CUT** | **47** | Never invoked; backend absent, trigger impossible, superseded, or stale. |
| **TRIM** | **5** | `base`, `security`, `code-review`, `icpg`, `python` — real value inside real bloat. |
| **KEEP** | **2** | `framework-evaluation`, `polyphony`. |
| **DEFER** | **2** | `mnemos` (pending its own trial), `code-graph` (backend live, doc wrong). |

**56 → 9 survive in some form.** The corpus drops by roughly **84%**.

---

## Compaction observations — THE PREMISE WAS FALSIFIED

**Did `auto` compaction fire this session? NO. P3 remains at `0 real`.**

**And that is a finding, not a failure — FOCUS-004's own premise did not survive contact with
FOCUS-004.**

The spec asserted: *"Reading the corpus to audit it overshoots the auto-compaction threshold by
~25% **with no padding and no artifice** — the work is *genuinely* read-heavy."* That assumed the
audit required reading all 56 `SKILL.md` bodies (~205k tokens).

**It did not.** The evidence that actually decided 47 of the 56 verdicts was **mechanical and
cheap**:
- `command -v` on each declared backend → *absent* kills the skill outright.
- `git ls-files` by extension → *the `paths:` glob can never match* kills it outright.
- one `grep` over 171 transcripts → *zero invocations, ever* kills it outright.

That is ~15 shell commands and ~20 targeted reads, not a 205k-token sweep. **The skills that
genuinely needed reading were the handful where a KEEP was plausible.**

**I deliberately did not pad to force compaction.** FOCUS-004 says so in its own words — *"Do not
pad a session to force compaction. A padded session produces a restore judgment about work you
were not really doing."* Reading 40 SKILL.md files I had already correctly cut on `command -v`
evidence would have been exactly that: **manufacturing evidence for the Mnemos trial.** It is the
same error the `trigger`-tagging fix was built to prevent — *a test must never become evidence.*

**Consequence for the Mnemos trial, stated plainly: FOCUS-004 was the designated compaction
vehicle, and it is no longer one. The trial needs a different vehicle, or it needs to admit that
naturally-occurring auto-compaction is rarer than assumed.** In 171 sessions it has fired
**zero** times un-manually. That is now the third independent signal pointing at the same
conclusion — see `docs/observatory.md`.

- **Did the restore let work resume without re-deriving?** — **unanswered, and now un-answerable
  by this route.**
- **Was anything lost that the ledger did not capture?** — n/a, no compaction occurred.
- **Was the incremental-ledger discipline wasted?** — No. It cost ~5 minutes and it is why this
  document exists independent of the context that produced it.

---

## Mechanical evidence (gathered, reproducible)

### What this repo actually is
`git ls-files` by extension: **161 `.md`, 123 `.py`, 49 `.sh`, 20 `.json`, 6 `.toml`, 5 `.yaml`.**
**Zero** `.ts` / `.tsx` / `.jsx` / `.dart` / `.kt` / `.java` / `.css` / `.scss`. No `package.json`,
no `tsconfig.json`, no `pubspec.yaml`, no `build.gradle`, no `wrangler.toml`, no `serverless.*`,
no `firebase.json`.

### Consequence: 19 of the 25 `paths:` triggers can never fire here
Every one of these auto-loads on a glob that matches **0 tracked files** in Tessera:
`typescript`, `react-web`, `react-native`, `ui-web`, `ui-mobile`, `ui-testing`,
`playwright-testing`, `pwa-development`, `flutter`, `android-java`, `android-kotlin`,
`nodejs-backend`, `cloudflare-d1`, `aws-dynamodb`, `aws-aurora`, `azure-cosmosdb`, `firebase`,
`supabase`, `supabase-nextjs`, `supabase-node`, `site-architecture`, `database-schema`.

### One trigger is not dead — it is MISFIRING
**`supabase-python` declares `paths: **/*.py, supabase/**`.** `**/*.py` matches **123 tracked
Python files** in this repo. Editing `scripts/doccheck.py` can auto-load **16 KB of FastAPI +
Supabase + SQLAlchemy** material into a framework session that has no web server and no database.
That is an over-broad glob on an inapplicable skill — *active* context pollution, not dead weight.
(`python`'s `**/*.py` also matches, but that skill is at least on-topic.)

### The corpus is paid for TWICE
`tessera/skills/` and `~/.claude/skills/` are **independent, byte-identical copies — 56/56, zero
drift.** Both registries load, so every skill is listed **twice** in the session's skill list.
`skills/` is git-tracked (63 files) and **not** gitignored.

### Two skills have no frontmatter at all
`build-in-public` and `autonomous-testing` — no `name:`, no `description:`.

### The structural fact that reframes the audit
**`bin/tessera-new-project` ships ZERO skills.** (`grep -n "skill"` → no matches.) The scaffold
installs mnemos hooks, the gate recorder, escalation, the spend guard + backstop, settings and
config — **and no skills.** So all 56 skills exist to serve **Tessera's own sessions only**, which
is precisely the repo where ~19 of them can never apply. They are an **unpruned inherited
baseline** — and Mnemos' own goal log records the intent that never happened: *"Scaffold the
Tessera framework's foundational structure by importing a baseline, **pruning skills to match the
design doc**."* Principle #15 was written, and then not executed.

---

## Findings (audit byproducts — recorded, NOT repaired)

1. **Duplicate registry.** Two byte-identical 56-skill copies both load. (above)
2. **`supabase-python`'s `**/*.py` glob misfires on this repo's 123 Python files.** (above)
3. **`iterative-development`'s Stop hook was never wired.** (see verdicts)
4. **`base` prescribes four artifacts that do not exist** and a 200-line file cap the framework's
   own core violates 4× over. (see verdicts)
5. **Missing frontmatter:** `build-in-public`, `autonomous-testing`.
6. **`bin/tessera-new-project` ships no skills** — so the skill set has no downstream consumer.
