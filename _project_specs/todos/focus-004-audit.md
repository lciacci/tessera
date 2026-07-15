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

### First: USAGE IS NOT EVIDENCE. Not a CUT, not even a DEFER. Strike it.

*(Corrected again 2026-07-13, Lorenzo: "we're building a framework, we may not have gotten there
yet, isn't that true?" — **it is true, and it is the floor of this whole error.**)*

An earlier rubric said *"never fires → DEFER."* **That was still smuggling the signal in.** DEFER
is suspicion, and suspicion is a verdict. The honest position is that zero usage carries **zero
information**, because **the audit already found what fully explains it:**

1. **`bin/tessera-new-project` ships ZERO skills.** The downstream repos — the ones that *have*
   `.tsx`, `.dart`, `supabase/` — have **no delivery path** for these skills. They could not have
   fired there.
2. **6 invocations machine-wide, across *every* skill, including the ones Anthropic ships.**
   Discovery is barely functioning at all.

**Once a cause fully explains an observation, the observation stops being evidence for anything
else.** The audit wrote down both causes and then kept spending the zero-usage number as a verdict
on 55 skills. That is the error, stated exactly.

**And it is the same argument that saved the multi-model stack**, one hour earlier in the same
session: *it has never run, it is directional, the framework has not got there yet — KEEP it.*
That reasoning was accepted for `bin/` and refused for `skills/`. **That is not a principle, it is
a mood.**

### The discriminator is not "did it fire." It is:

> **Has the framework built the thing that would make this fire?**
>
> - **NO** → never-firing is **exactly what you would expect. Zero information. Not a mark against
>   the skill.** The gap is in the **framework** (ship skills downstream), not the skill.
> - **YES**, it is reachable, and it *still* never fires → *now* there is a question. And even
>   then it is ambiguous between "the model does not find it useful" and "discovery is broken" —
>   and at **6 invocations machine-wide, discovery is the odds-on explanation.**

**Therefore: usage is uninformative FULL STOP, until discovery is shown to work.** It does not
appear below. If a future session reaches for an invocation count to justify a cut, **that is
drift — point at this section.**

### The questions that CAN decide a skill — all require reading the body

| # | Question | CUT if… |
|---|---|---|
| 1 | **Is what it says TRUE?** | It asserts false facts, or describes machinery that exists nowhere. *(`ai-models` names `claude-opus-4-5` as flagship in July 2026; `iterative-development`'s sole hook exists in no repo.)* |
| 2 | **Is it SUPERSEDED?** | A working plugin, a native Claude Code feature, or a better skill already does the job. *(`build-in-public` vs the live plugin; `credentials` is inlined in `base`.)* |
| 3 | **Is the guidance any GOOD?** | Generic filler, or advice a competent model already has without being told. **The question the sweep never asked, and the only one that cannot be answered without reading.** |
| 4 | **Is it ON THE PATH we are building?** | **This is a KEEP question, not a cut question.** If the framework intends to reach where this skill applies — it stays, however cold. *(This is the multi-model-stack call, applied consistently.)* |

**Only 1–3 can produce a CUT. 4 can only produce a KEEP. Nothing else is admissible.**

**And this is the read-heavy work FOCUS-004 specified.** Reading 56 bodies is ~205k tokens. The
compaction premise — which an earlier draft of this ledger wrongly declared *falsified* — **stands**,
because the sweep that "falsified" it was not the audit. **P3 is still reachable. Do this in a
fresh session with full context.**

---

## Verdict vocabulary — REPLACED (2026-07-13)

### The vocabulary WAS the bug

The original was **KEEP / TRIM / CUT / DEFER**. Three destructive outcomes and a holding pen.
**There was no verdict meaning "this idea is good — take it somewhere better."**

**It was written in the first ten minutes, before a single skill had been read.** An instrument
with no setting for *adapt* cannot produce an *adapt*. Everything downstream was decided by a
rubric authored in ignorance.

**Why it came out that way — named, because CLAUDE.md says to name biases and this one went
unnamed all session:**

1. **The task was handed over as a prune.** `active.md`: *"PRUNE — and FOCUS-004 **is** the
   prune."* ADR-0006 §5 sanctions pruning and ranks *"deleted machinery cannot fail silently"*
   tier 1. **I took the framing as given rather than as a claim to test.**
2. **The `ponytail` skill was live in the session and is an explicit deletion bias** — *"Deletion
   over addition", "Does this need to exist at all?", "Speculative need = skip it"*, and a
   `ponytail-audit` command whose stated output is *"a ranked list of what to delete."* **I named
   excitement bias and sunk-cost while this sat unremarked in my context, steering every verdict.**
3. **Then I chose instruments that could only confirm it.** `command -v`, `git ls-files`,
   invocation counts — **every one of them can detect absence and none of them can detect value.**
   Absence was then reported as if it were value.

### The corpus is a FOSSIL RECORD, and the audit's job is partly to MINE it

Tessera's own machinery already descends from these skills: `session-management`'s tiered
summarization is what **Mnemos** automates; `code-deduplication`'s capability index is what
**`icpg query prior`** does; `agent-teams`' RED/GREEN-verify pipeline is the shape of the
**Stop-hook loop**. **A keep/cut sweep destroys that evidence without reading it.** *This is why
FOCUS-004 was held back so long, and running it as a chainsaw was the one thing it must not be.*

### The verdicts

| Verdict | Means |
|---|---|
| **KEEP** | Good as it stands. Leave it. |
| **FIX** | Content is sound; the **trigger or backend** is broken. *(`paths:` never matches, names the wrong binary, points at `~/bin/`.)* **A skill that never fires because nothing could reach it is a DISTRIBUTION bug. Fix the trigger. Do not cut.** |
| **ADAPT** | The idea is worth having; this expression of it is wrong for us. Rework it. |
| **MERGE** | Overlaps another skill. Combine into the better one; keep the union of the good parts. |
| **HARVEST → CUT** | The skill as a unit does not earn its place, **but it contains ideas worth extracting** — into `docs/design-principles.md`, an ADR, or another skill. **Extract FIRST, then cut. A cut that loses an idea is a loss, not a saving.** |
| **CUT** | Genuinely nothing worth keeping. **Must state what was considered for harvest and rejected** — naming what you did not take is the trail. |

**There is no DEFER, and there is no usage-based verdict.** See the section above: usage is not
evidence.

### Admissible evidence

Only these, and each requires **reading the body**:

1. **Is what it says TRUE?** — false facts, or machinery that exists nowhere.
2. **Is it SUPERSEDED?** — a working plugin, a native feature, or a better skill does the job.
3. **Is the guidance any GOOD?** — or is it filler a competent model already has?
4. **Is it ON THE PATH we are building?** — **KEEP-only. Never a cut.**
5. **What IDEAS are in here worth taking?** — **the question the sweep never asked at all.**

**"It was never invoked" and "its `paths:` can't match in Tessera" are NOT admissible.**
If a future session reaches for either to justify a cut, that is drift. Challenge it.

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

---

# ═══ REAL AUDIT (2026-07-14) — content verdicts, main-thread body read ═══

**This is the audit the handoff item 0 ordered. Every row below was reached by READING the
`SKILL.md` body and applying only the 5 admissible questions (TRUE / SUPERSEDED / GOOD / ON-PATH /
HARVESTABLE). Reachability (never-invoked, `paths:` can't match) is NOT used. The VOID table above
is superseded by this one wherever they disagree — and they disagree materially in several places,
which is the point.**

Verdicts: KEEP / FIX / ADAPT / MERGE / HARVEST→CUT / CUT.

## Batch A — framework-native / plausible-keep cluster (5)

| skill | verdict | content-grounded reason |
|---|---|---|
| **framework-evaluation** | **KEEP** | Unambiguous. A real 6-dimension methodology (identity, overlap, integration cost, pattern-vs-impl, lock-in, decision) that has produced output (ADR-0002). Guidance is *good and live*: its anti-patterns section (confirmation / sunk-cost / excitement / familiarity / single-dimension bias) is the exact failure catalogue the ADR-0007 saga fell into — this skill names the biases that broke the void audit. On-path (principle #16). Nothing stale. |
| **polyphony** | **KEEP** | Machinery is real and reachable (`polyphony` on PATH + `.venv/bin/polyphony` + allow-listed in settings.json + docker). Body is accurate: 6-layer architecture, task lifecycle, container isolation, CLI. Directional/on-path (multi-agent orchestration). **One overlap:** its 5-dimension complexity-scoring table is duplicated verbatim in `cross-agent-delegation`; polyphony is the canonical home (it's the working tool), so the duplicate counts against the *other* skill, not this one. |
| **mnemos** | **KEEP** | Eagerly loaded (~166 ln), and every line is TRUE: documents hooks that ARE wired (SessionStart/PreCompact/PreToolUse/PostToolUse/Stop), CLI that runs (`.venv/bin/mnemos`), and is visibly self-corrected against reality ("two known wrinkles", "corrected 2026-07-09"). Not superseded — CLAUDE.md's "Hook lifecycle" is a pointer; the fatigue weights / haziness dimensions / node-eviction detail live only here. It IS the P3 path. *(Void table's DEFER dissolves: the doc is sound regardless of the tool's kill/keep trial — auditing the doc ≠ deciding the trial.)* Minor: the manual-CLI + haziness detail could load on-demand rather than eager, but that's a CLAUDE.md `@import` question, not a content defect. |
| **council-review** | **FIX** *(void table said CUT — that verdict is now false)* | The void audit CUT this as "all three backends ABSENT + live fail-open." **Both premises were repaired by the very session that wrote them:** `7a725f7` fixed `bin/validate-plan` (broken-reviewer now = silence, not dissent; zero usable reviewers → exit 2, no manufactured verdict), `ec041d3` ported the stack off phantom `httpx` to stdlib. **Verified now: `bin/validate-plan` and `bin/review` both EXIST and run.** So machinery exists — the skill just points at the wrong path (`~/bin/validate-plan` → should be `bin/`), references a Maggy dashboard that isn't here, and overclaims a 13-tier roster whose `gemini`/`codex`/`deepseek`/`grok` binaries are absent. That is a **distribution/trigger bug = FIX**, not a value failure. The dangerous fail-open ("Do not skip council validation for CLAUDE-tier tasks" ordering runs that didn't exist) is already closed by the exit-2 fix. Guidance (when to validate plans/PRs/architecture, threshold semantics) is sound and directional — this is the conclave-design-session skill (handoff item 1). **FIX: repoint paths `~/bin/`→`bin/`, drop Maggy ref, prune roster to installed models.** |
| **cross-agent-delegation** | **HARVEST→CUT** | Content-grounded, not reachability. (a) **Self-duplicated:** `### When NOT to Delegate` and `### Step 4` each appear **twice** in the file (confirmed 2×/2×) — the body is internally broken. (b) **Superseded on every good part:** the 5-dim complexity table is verbatim `polyphony`'s; the iCPG pre-task triad (`query prior/constraints/risk`) is verbatim the `icpg` skill's; the mnemos checkpoint-as-bridge is the `mnemos` skill's. (c) Orchestrates Stop hooks (`codex-auto-review.sh`, `tdd-loop-check.sh`, `icpg-stop-record.sh`) that are wired nowhere and a `codex` that's absent. **Harvest considered:** every idea worth taking (scoring rubric, iCPG triad, checkpoint bridge) *already has a canonical home* — the union is held elsewhere, so there is nothing to MERGE *in*. What's unique to this file is the broken orchestration flow. **CUT; nothing unique lost.** |

*(Batch A done.)*

## Batch B — eagerly-loaded core / TRIM cluster (4)

| skill | verdict | content-grounded reason |
|---|---|---|
| **base** | **TRIM (hard)** | Eagerly loaded (~532 ln). The verdict matches the void table but for the *right reason now* — read, not reachability. **Keep (real, some Tessera-specific):** Core Principle, Simplicity Rules, Architectural Patterns, Anti-Patterns — and especially the "git remembers = CODE-ONLY / HARVEST-BEFORE-YOU-CUT" clause (added 2026-07-13, ADR-0007), which is the single most load-bearing line in the corpus for this very audit. **Cut (duplicated elsewhere or downstream-app-shaped):** the `[TODO-xxx]` atomic-todo format (**zero uses** in `_project_specs/todos/`), the RED/GREEN/VALIDATE TDD workflow (points to `iterative-development`, and npm/Node examples in a repo with no Node), the Credentials section (verbatim `credentials` skill), the Security section (verbatim `security` skill; prescribes `.env.example` / `scripts/security-check.sh` / `.secrets.baseline` — none exist), the Session-Management section (verbatim `session-management`; prescribes `_project_specs/session/*` — Mnemos replaced it). ~60% is inlined copies of three other skills + a downstream-app doc tree. **Root cause: a downstream-app prescription eager-loaded into a framework repo.** |
| **security** | **ADAPT** *(void table said DEFER)* | The content is *correct* — real OWASP practice (secrets hygiene, SQLi/XSS, JWT, bcrypt, rate-limit, helmet, CodeQL). It is not false and not filler. But ~95% of it (SQL, XSS, JWT, CORS, Vite/Next bundles) has **no surface in Tessera** — no web server, no auth, no SQL, no user input, no Node. So this is not a value defect, it's a **placement** defect: the whole skill is eager-loaded (~580 ln) in the wrong repo. **ADAPT: the OWASP bulk is on-path *downstream* — move it to the downstream template and let it load on-demand via `paths:` when auth/`.tsx` code is actually present; keep only the live subset (no `.env` commits, no secrets in tracked files) where it already lives — CLAUDE.md's Don't list + settings.json deny + `.githooks/pre-commit`.** Not a CUT: the material is sound and genuinely needed by the apps Tessera is meant to build. |
| **iterative-development** | **KEEP (relocate)** — *void table said CUT; that verdict is DRIFT and this reversal is the whole lesson* | Void CUT it because "its sole Stop hook `tdd-loop-check.sh` is wired nowhere." **That is reachability, and it is inadmissible.** On the five content questions: (1) TRUE — the mechanism it teaches (a Stop hook exiting 2 feeds stderr back and continues the turn → a plugin-free TDD loop) is a *real, non-obvious Claude Code capability*, and Tessera's own wired Stop hooks (`tessera-gate-scan` exit 2) **use exactly this mechanism**; the skill is a setup guide ("Create `scripts/tdd-loop-check.sh`"), not a false claim that it exists. (2) NOT superseded — `base` points *to* it for detail. (3) GOOD — the Error-Classification table (code-error→loop, access/env-error→stop) is a genuinely useful distinction. (4) ON-PATH — TDD loops are core to the downstream apps Tessera builds. **Nothing here earns a cut.** The only real defects are placement: it's eager-loaded in the framework repo where no TDD loop is wired, and it's downstream-shaped. **KEEP the content; relocate from eager framework-load into the downstream template (on-demand). Relocation is a distribution fix, not a value cut.** |
| **python** | **TRIM** | Legitimately auto-fires here (`paths: **/*.py`, 123 files) — so its defects do real harm on every `.py` edit. **Keep:** type-hints guidance, the anti-patterns (`import *`, mutable defaults, bare `except`, unexplained `type: ignore`), DI and Result-pattern. **Cut/fix:** the "Tooling (**Required**)" block asserts ruff + `mypy --strict` + `pyproject.toml` + `.pre-commit-config.yaml` — **none exist in Tessera** (it's uv-venv + stdlib-heavy `scripts/` + `run-tests.sh`), so an auto-loaded skill is prescribing a toolchain the repo pointedly does not use; also the `src/package_name/core|infra` + FastAPI layout is not Tessera's (`scripts/`, `bin/`), and the GitHub-Actions/pre-commit scaffolding is downstream. TRIM to the language core, drop the CI/src-layout/FastAPI prescriptions. |

*(Batch B done.)*

## Batch C — tool-backed cluster (4 of 5; code-review next)

| skill | verdict | content-grounded reason |
|---|---|---|
| **icpg** | **TRIM** | The Reason-Graph model is real, Tessera-native, and *actively used* — Mnemos' goal log carries `[iCPG:…]` reason IDs throughout, so this isn't cold. **Keep:** ReasonNode primitive, 6 edge types, 6-dimension drift model, the 3 canonical pre-task queries, contract predicates, CLI, anti-patterns — good and load-bearing. **Cut (Q1 — asserts things false in *this* repo):** the "Hook Integration" section claims a PreToolUse `icpg-pre-edit.sh` "shows context before every edit" and a Stop `icpg-stop-record.sh` — **verified NOT wired (0 matches in settings.json)**, and its Stop example invokes the phantom `tdd-loop-check.sh`; and the "Agent Teams Integration" 10-step pipeline is Maggy infra. So "Step 0 is non-negotiable / the PreToolUse hook shows context" is a false claim here. TRIM to the model + queries; drop the hook-wiring and agent-teams sections. |
| **code-graph** | **FIX** *(void table said DEFER)* | **Backend is LIVE — the `mcp__codebase-memory-mcp__*` tools are exposed in this very session** (MCP configured globally). So this is not cold and not a cut. But the doc's config section is **wrong**: it says "MCP config: `.mcp.json` at project root (committed, shared with team)" — **there is no `.mcp.json` in Tessera** (it's global); it cites `~/.claude/install-graph-tools.sh` — **absent**; and the "post-commit hook + file-watcher freshness" claims are unverified here. Guidance ("graph first, file second", the grep-vs-graph decision table) is sound. **FIX: correct the config/install/freshness claims to match the global setup.** (Whether graph-nav earns its weight in a 123-file repo where grep suffices is a real scope question, but it is not a content defect and not a cut.) |
| **cpg-analysis** | **KEEP (cold / opt-in)** — *and this row is where I applied the lesson against myself* | **I first wrote "CUT — joern absent, codeql absent, codebadger/codeql MCP not exposed, `install-graph-tools.sh` absent." Then I stopped: that is verbatim the void table's reachability cut of this exact skill, the one the ADR-0007 correction singled out.** The backend being unprovisioned *here* is inadmissible. On the five content questions: (1) TRUE — it describes **real tools** (Joern, CodeQL), accurately, and honestly self-labels "opt-in … require Docker/JVM or CodeQL CLI"; it does not claim they're installed. (2) NOT superseded. (3) GOOD — CPGQL / CodeQL taint-query syntax is specialized enough that the curated query cookbooks are real value, not "advice a competent model already has." (4) The tiered escalation principle (cheap Tier-1 nav → deep Tier-2/3 only on flagged areas) is a genuinely good idea. **Nothing admissible cuts it.** Honest tension recorded: there is no evidence in CLAUDE.md / design-principles that Tessera intends Tier-2/3 deep taint analysis, so its *scope fit* is open — but that is a KEEP-or-relocate scope question for a human, **not** a cut, and above all not a cut on the absent backend. **Stress test that caught me:** "if Joern+CodeQL were installed, would I keep it?" — yes — which proved my cut was resting on the backend, i.e. reachability. KEEP. |
| **autonomous-testing** | **HARVEST→CUT** | Grounded admissibly, not on the absent `~/bin/deepseek` / `maggy`: (1) **structurally not a well-formed skill — it has NO frontmatter at all** (`# Autonomous Testing Agent`, no `---`), so it cannot carry `name`/`paths`/`when-to-use`; (2) **superseded** — Tessera already has its own testing path (`run-tests.sh` + the Stop-hook TDD loop) and its own error taxonomy; (3) it is explicitly "generalized for Claude Bootstrap + **Maggy**", with an "Integration with Maggy → Maggy Dashboard Testing tab" section — it is **another product's infrastructure**, model-routing hard-wired to `deepseek-pro`/`gemini-flash`. **Harvest considered:** the discover→generate→execute→evaluate→fix pipeline shape, and the TEST_BUG / CODE_BUG / ENV_BUG failure classification — but the latter already lives in `iterative-development`'s Error-Classification table, so marginal harvest value is low; note the pipeline shape as a possible future autonomous-test design and cut. |

| **code-review** | **HARVEST→CUT** (keep the ADR gate as its own skill) | The corpus's biggest skill (974 ln) and the *only one ever invoked* (6×) — but usage is inadmissible for keeping too, so it earns nothing from that. On content: **(Q2) the core `/code-review` command is now superseded by Claude Code's NATIVE `/code-review`** (the session's own system-reminder confirms `/code-review ultra` is a live native command and a native `review` skill exists) — this skill *defines the same slash command*, so they collide. **(Q1) the Codex/Gemini/dual/triple engine machinery needs `npm install -g @openai/codex` / `@google/gemini-cli` + Node 22/20 — Tessera has no Node**, and those halves are ~60% of the file (per-engine CI/CD YAML ×5). **(Q3) the review-category / severity / common-findings tables are competent but generic** — the native command already carries them. **The one genuinely Tessera-native, non-superseded, on-path part is the ADR gate** (`Pre-Review ADR Gate`, the `adr-gate.md` sub-file, the ADR-Compliance review dimension) — `docs/adr/` is real and load-bearing here. **HARVEST: (1) split the ADR gate + `adr-gate.md` into a small standalone `adr-gate` skill — this must survive; (2) lift the multi-engine agreement/dedup output format as a design note for the conclave/council work (handoff item 1). CUT the rest — superseded by the native command + Node-only engines + generic tables.** |

*(Batch C DONE — 5/5. code-review sharpens the void's DEFER into a concrete harvest.)*

## Batch D — the downstream stack (web / mobile / UI / testing)

**Discipline for this whole block: these are general-purpose stack skills in a GLOBAL registry serving 20+ repos. "Can't fire in Tessera" is INADMISSIBLE — `flutter` *should* be inert here. The only admissible cuts are: STALE/FALSE (Q1), SUPERSEDED (Q2), or GENERIC-FILLER-a-model-already-has (Q3). "On-path downstream" (Q4) is KEEP-only.**

**Structural note that governs the whole block:** per Finding #1, `tessera/skills/` and `~/.claude/skills/` are byte-identical copies; the GLOBAL one is what serves the 20+ downstream repos. So a KEEP here means "valid downstream-stack skill, belongs in the global registry" — it does **not** endorse the duplicate *local* `tessera/skills/` copy, which is a separate distribution finding, not a per-skill value question.

### Batch D-1 — TS / React / Node / UI (6)

| skill | verdict | content-grounded reason |
|---|---|---|
| **typescript** | **KEEP (cold, downstream-stack)** | Current and correct: flat eslint config, `strictTypeChecked`, discriminated-union `Result`, branded types, const assertions, Zod. **Q3 additive, not filler** — it encodes *enforceable house conventions* (core/infra split, named-exports-only, `max-lines-per-function: 20` wired into eslint) a model won't apply by default. Not stale, not superseded, on-path downstream. Void CUT it on reachability; inadmissible. |
| **react-web** | **KEEP (cold, downstream-stack)** | Comprehensive and current (hooks, React Query, Zustand, RHF+Zod, Playwright). The Test-First-for-components enforcement + the core/components/pages structure are real, opinionated guidance beyond model baseline. KEEP. |
| **react-native** | **KEEP (cold, downstream-stack) — minor FIX** | Sound RN patterns (Pressable, Platform.select, ios/android split). **One Q1 staleness:** line 189 imports `renderHook` from `@testing-library/react-hooks`, a package **deprecated/merged** into `@testing-library/react-native`. Not cut-worthy — a one-line FIX. Otherwise KEEP. |
| **nodejs-backend** | **KEEP (cold, downstream-stack)** | Solid, current: repository pattern (Kysely), DI at composition root, domain-error hierarchy, Zod-validated config, unit+integration split. Correct and additive. KEEP. |
| **ui-web** | **KEEP (cold, downstream-stack)** | **Higher-value than baseline:** the WCAG-AA contrast section carries *specific measured ratios* (`gray-400 on white = 2.6:1 FAILS`, safe pairings with hexes) that models do NOT reliably recall — this is exactly the kind of concrete threshold a skill should encode. Plus glassmorphism variants, 8px grid, focus-state rules. KEEP. |
| **ui-mobile** | **KEEP (cold, downstream-stack)** | Same shape as ui-web for RN: 44pt touch targets, measured contrast pairs, iOS/Android platform tables, native-driver animation rules, VoiceOver/TalkBack labels. Concrete and additive. KEEP. *(Its `paths:` includes `**/*.dart` — a mild over-claim onto Flutter, worth trimming, but not a content cut.)* |

*(Batch D-1 done — 6 KEEP. Every one was a void-table CUT resting purely on reachability.)*

### Batch D-2 — testing / PWA / mobile-native (6)

| skill | verdict | content-grounded reason |
|---|---|---|
| **ui-testing** | **MERGE → ui-web + ui-mobile** | Content is good but it is *explicitly a companion* — its header literally says "*Load with: ui-web.md or ui-mobile.md*", and its Tailwind contrast tables **duplicate** the ones already in `ui-web`/`ui-mobile`. Its unique parts (the pre-flight visibility/touch/state checklist, `eslint-plugin-jsx-a11y`, the `@axe-core/playwright` violations test) are worth keeping. **MERGE the unique pre-flight checklist + automated-a11y snippets into ui-web and ui-mobile; drop the duplicated contrast tables.** Not a cut — union of good parts preserved. |
| **playwright-testing** | **KEEP (downstream-stack)** | High-quality, current E2E guide: role-based locator priority, Page Object Model, storageState auth setup, network mocking, trace viewer, and an opinionated "Dead Link Detection (REQUIRED)" crawler. Accurate to current Playwright API. Additive, not filler. KEEP. |
| **pwa-development** | **KEEP (downstream-stack)** | Comprehensive and correct: manifest fields, SW lifecycle, the five caching strategies, Workbox (Vite plugin + manual SW), background sync, push, share_target, Lighthouse checklist. Current 2026 PWA practice. KEEP. |
| **flutter** | **KEEP (downstream-stack) — minor version-refresh** | The rubric's own example skill ("flutter SHOULD be inert here"). Content is solid and current-idiom: Riverpod 2 Notifier/AsyncValue, Freezed sealed unions, go_router redirect guard, mocktail + ProviderScope overrides. **Only FIX surface:** pins are ~a year old (`go_router ^13`, `flutter 3.16`, `flutter_lints ^3`) — behind, not wrong. KEEP. |
| **android-java** | **KEEP (downstream-stack) — minor version-refresh** | Honest Java-specific MVVM (ViewModel/LiveData, ViewBinding, Retrofit callbacks, Espresso). The callback style is dated but that IS idiomatic Java Android — the skill correctly targets the language. `compileSdk 34` is one cycle behind (35). Not stale enough to cut. KEEP. |
| **android-kotlin** | **KEEP (downstream-stack) — minor version-refresh** | Current, high-quality: Coroutines/Flow, StateFlow ViewModel, Compose + Material3, Hilt/KSP, MockK + Turbine + `MainDispatcherRule`. `compileSdk 34` / Compose BOM `2024.01` are ~a year old pins. KEEP. |

**Cross-cutting observation for the whole stack block (D-1 + D-2):** the recurring real defect is **version-pin drift** (SDK/library versions ~a year old), which is a *maintenance/refresh* task on the global library, **not** a per-skill cut. Worth a standing "refresh stack-skill pins quarterly" note — which is exactly what `framework-evaluation`'s cadence principle (#16) is for.

*(Batch D DONE — 12 skills: 11 KEEP + 1 MERGE. Zero cuts. The void table CUT all 12 on reachability.)*

## Batch E — data / cloud / schema

### E-1 — Firebase / Supabase / DB (4)

| skill | verdict | content-grounded reason |
|---|---|---|
| **firebase** | **KEEP (downstream-stack)** | Current and correct: modular v9+ SDK, denormalization guidance, security-rules with helper functions + validation + `@firebase/rules-unit-testing`, Functions v2, transactions, composite indexes. Accurate 2026 Firebase. `NEXT_PUBLIC_*` for the config is correct (those are public keys). KEEP. |
| **supabase** | **KEEP (downstream-stack)** | High-quality CLI-first workflow: migrations in VCS, RLS policies, `handle_new_user` trigger, edge functions, storage policies, connection-pooling modes, types generation, CI/CD. Current and opinionated ("never touch production directly"). KEEP. |
| **supabase-python** | **FIX (glob over-claim)** — Finding #2 | **Content is fine** — correct FastAPI + SQLAlchemy/SQLModel + supabase-py patterns, async sessions, JWT dep, Alembic. **The defect is the trigger, not the content:** `paths: ["**/*.py", "supabase/**"]` — the bare `**/*.py` auto-loads this FastAPI/Supabase skill on **every one of Tessera's 123 Python files**, and any Python repo without Supabase. **FIX: narrow the glob so it requires a Supabase+FastAPI signal (e.g. `supabase/**` plus a fastapi/sqlmodel indicator), not "any `.py`".** This is a distribution FIX, not a value cut — exactly the `FIX` verdict's definition (over-broad trigger on sound content). |
| **database-schema** | **KEEP (downstream-stack, high-value)** | The most *universally* useful skill in this block — it is a **discipline**, not a stack: "read the schema before writing DB code; use generated types; verify column names." Directly targets a real model failure (mid-session column-name hallucination), multi-stack (Drizzle/Prisma/Supabase/SQLAlchemy type-gen), with a concrete pre-code checklist. Additive and correct. KEEP. |

*(E-1 done.)*

### E-2 — Next.js/Node Supabase + AWS/Azure/Cloudflare + SEO (7)

All read in full. **Every one is current, accurate, and additive** — none earns an admissible cut:

| skill | verdict | content-grounded reason |
|---|---|---|
| **supabase-nextjs** | **KEEP (downstream-stack)** | `@supabase/ssr` + App Router + Drizzle + server actions + auth middleware. **Current to Next.js 15** — explicitly notes `await cookies()` and the "called from Server Component — ignore" cookie pattern. KEEP. |
| **supabase-node** | **KEEP (downstream-stack)** | Express **and** Hono, Drizzle, Zod-validated env + request validation, JWT middleware, centralized error handler. Correct and complete. KEEP. |
| **aws-aurora** | **KEEP (downstream-stack)** | RDS Proxy vs Data API vs direct, Serverless v2 capacity, IAM auth, Secrets Manager, scale-to-zero retry. Accurate AWS. KEEP. |
| **aws-dynamodb** | **KEEP (downstream-stack)** | Single-table design, GSI/LSI, SDK v3, transactions — and **up to date**: documents "Multi-Attribute Composite Keys (Nov 2025+)". KEEP. |
| **azure-cosmosdb** | **KEEP (downstream-stack)** | Partition-key design, the five consistency levels, change feed, RU/cost optimization, TTL. Correct. KEEP. |
| **cloudflare-d1** | **KEEP (downstream-stack)** | D1 + Workers + Drizzle + Wrangler, migrations, `batch` transactions, limits table. Correct (the `compatibility_date = "2024-01-01"` is an example value, not a claim). KEEP. |
| **site-architecture** | **KEEP (downstream-stack) — overlaps web-content** | Technical SEO done *current*: robots for AI crawlers (GPTBot/ClaudeBot/PerplexityBot/Google-Extended), dynamic Next.js sitemap/robots/metadata, **Core Web Vitals uses INP (≤200ms), not the retired FID** — so it's been maintained. Overlaps `web-content` (SEO/GEO); **flag for a possible MERGE decision when web-content is judged in Batch F.** KEEP. |

*(Batch E DONE — 11 skills: 10 KEEP + 1 FIX (supabase-python glob). Zero cuts.)*

## Batch F — downstream-concern grab-bag (the real admissible cuts live here)

### F-1 — meta / framework-adjacent (7)

| skill | verdict | content-grounded reason |
|---|---|---|
| **ai-models** | **CUT** (harvest: provider doc-URL list) | **Admissible on Q1 (stale/false), not reachability.** Header: "**Last Updated: December 2025**"; names `claude-opus-4-5-20251101` as flagship, recommends "Opus 4.5, o3, Gemini 3 Pro", lists Haiku 3.5. **Today is 2026-07-14** — current Claude is Opus 4.8 / Sonnet 5 / Haiku 4.5 / Fable 5, so the Claude section is **factually wrong**. **(Q2) Claude Code now ships a native `claude-api` skill** that is the authoritative model reference and explicitly says *never answer from memory* — it supersedes the Claude portion. A hardcoded model/pricing snapshot is a fast-drifting fact that is a **hazard** in the one repo whose CLAUDE.md reasons carefully about model tiers. **Harvest considered:** the multi-provider doc-URL pointer list (OpenAI/Gemini/Mistral/ElevenLabs/Replicate/Voyage docs) is worth keeping as *live pointers*; the hardcoded ID/price tables are the hazard. CUT. |
| **credentials** | **KEEP (cold, downstream-onboarding)** | Not an admissible cut. Correct, concrete utility for bootstrapping a downstream project's `.env` from a centralized `~/Documents/Access.txt` — key-pattern table, parsers, per-service validation curls. **`base` only *summarizes* this and explicitly defers the detail here** ("See credentials.md for full parsing logic"), so it's a deliberate eager-summary / on-demand-detail split, not dead duplication. On-path for downstream onboarding. KEEP. |
| **session-management** | **HARVEST→CUT** (fossil → Mnemos) | **(Q2) superseded by Mnemos** — the *tool* that automates exactly what this prescribes by hand (checkpoint/resume/archive, tiered summarization). Mnemos ships both here (8 wired hooks) and downstream (via `tessera-new-project`), so the manual-markdown machinery (`_project_specs/session/current-state.md`/`decisions.md`/`archive/`) is superseded on both sides and prescribes files that don't exist. **This is a named fossil-record case:** its Tier-1/2/3 summarization + decision-heuristic is *the ancestor of Mnemos*. **Harvest:** cite the tiered-summarization design in the design-doc / an ADR as Mnemos's lineage, then cut the corpus skill. |
| **code-deduplication** | **HARVEST→CUT** (fossil → icpg) | **(Q2) the `CODE_INDEX.md` capability-index + `/audit-duplicates` is superseded by `icpg query prior`** (which does duplicate-detection with real TF-IDF/Chroma backing) — the rubric names this exact lineage. **Harvest the genuinely good ideas that icpg lacks:** the framing *"the problem isn't duplicate code, it's duplicate PURPOSE — AI reimplements, it doesn't copy-paste"*, the check-before-write discipline, and the file-header/function-doc conventions → fold into `icpg`'s anti-patterns or the design-doc. Then cut. |
| **workspace** | **KEEP (cold) — scope tension flagged** | **Same discipline as `cpg-analysis`, applied consistently.** On the five questions: not stale (Q1), not superseded (Tessera's `bin/tessera-findings` is far narrower — a findings backlog, not contract/topology tracking), not filler (Q3 — it's real machinery: contract extraction, token-budget allocation, freshness tiers, artifact-generation protocol, *not* advice a model just has). The only marks against it — "Tessera is single-repo", artifacts absent, the example header says `Analyzer: maggy/workspace-analysis` — are **applicability/reachability, inadmissible for a cut**, though `/analyze-workspace` + `/sync-contracts` *do* exist in the command set. **Honest tension:** a 971-line multi-repo machine for a scenario Tessera isn't in and shows no roadmap toward — a KEEP-or-relocate scope call for a human, **not** a content cut. |
| **team-coordination** | **KEEP (cold, downstream-team) — Q3-weak** | The weakest-value KEEP in the batch. It's a shared-markdown team-process convention (todo claim annotations, handoff format, ownership table, standup template). **Borderline on Q3** — much of it is process a competent model would suggest unprompted — but it clears the bar because a *consistent* convention (specific file structure + claim-annotation format applied across sessions) is exactly what a model needs told, not derived. Not stale, not superseded. **Flag: a consolidation candidate** — if a single "collaboration" skill is ever built, fold this + the team bits of `session-management` together. KEEP for now. |
| **commit-hygiene** | **KEEP (cold, universal)** | The most broadly applicable in the batch — it governs Tessera's own commits too, not just downstream. Not filler: concrete numeric thresholds (5/10 files, 200/400 lines, defect-rate figures), a runnable size-check script, atomic-commit/stacked-PR patterns, conventional-commit types. A model won't reliably apply "commit at ~200 lines" without being told the threshold. Not stale, not superseded (CLAUDE.md has commit *conventions* but no size discipline). KEEP. |

*(F-1 done — 3 CUT (all Q1-stale / Q2-superseded, zero on reachability) + 4 KEEP.)*

### F-2 — downstream product concerns (6)

All read in full. **All current, additive, none superseded — zero cuts:**

| skill | verdict | content-grounded reason |
|---|---|---|
| **existing-repo** | **KEEP (cold, high-value)** | Universally useful discipline — "understand before modifying, match existing conventions, only add *missing* guardrails." Current tooling (Husky, ESLint-9 flat config, ruff, pre-commit), concrete detection scripts, a 6-week gradual-guardrails timeline. Applies to *any* codebase (including Tessera's own). Not stale, not superseded. KEEP. |
| **project-tooling** | **KEEP (cold, downstream-deploy)** | Correct multi-platform CLI/deploy setup (gh, vercel, supabase, render) with a verify-tooling script and CI/CD templates. Downstream-deployment concern; not stale. Minor CLI-section overlap with `supabase` but different focus (multi-platform deploy vs Supabase workflow). KEEP. |
| **posthog-analytics** | **KEEP (cold, downstream-analytics)** | Comprehensive and current PostHog (js/node/python clients, `identified_only`, feature flags, GDPR opt-in, per-product-type dashboard templates, PostHog-MCP workflow). Concrete event-naming conventions. Not stale, not superseded. KEEP. |
| **web-content** | **KEEP (cold, downstream-content/GEO)** | SEO + GEO (AI-discovery) — schema types, AI-quotable content structure, per-engine (ChatGPT/Perplexity/Claude/Gemini) optimization, E-E-A-T, AI-referrer tracking. **Resolves the site-architecture MERGE flag:** having read both, they're *complementary layers* — `site-architecture` is technical infra (robots/sitemap/meta/CWV), `web-content` is content strategy. Keep both; only the schema-markup *examples* overlap (a minor de-dup, not a merge). KEEP. |
| **user-journeys** | **KEEP (cold, downstream-UX)** | "Specs test features, journeys test experiences" — journey mapping with emotional states + error-recovery emphasis, concrete Playwright journey tests and UX-validator helpers (CLS/load/a11y). Complements `playwright-testing` (the *what* vs the *how*), doesn't duplicate it. KEEP. |
| **ticket-craft** | **KEEP (cold) — one Maggy-adjacent section** | Strong and Claude-Code-native: "a ticket is a prompt", INVEST+**C**(laude-Ready), self-contained tickets (file refs / pattern refs / exact verification commands / constraints), epic-slicing techniques, AI-calibrated story points. **This ethos is Tessera's own** (explicit context + verification). The "Mapping Tickets to Agent Teams" section is Maggy/agent-teams-adjacent — **trim that one section if `agent-teams` is cut**; the rest stands alone. KEEP. |

*(F-2 done — 6 KEEP, 0 cuts.)*

### F-3 — LLM/agent dev + social + Maggy/vendor review (6)

| skill | verdict | content-grounded reason |
|---|---|---|
| **llm-patterns** | **KEEP (cold, downstream-LLM-apps)** | "LLM for logic, code for plumbing" — typed LLM wrapper, Zod-validated structured outputs, prompt versioning, and the genuinely useful **three-tier LLM testing** (mock / fixture / nightly-eval) + cost tracking. Concrete and additive. The `claude-sonnet-4-20250514` in examples is illustrative code, **not** a "current-flagship" claim (unlike `ai-models`), so it's not a staleness cut. KEEP. |
| **agentic-development** | **KEEP (cold, high-value, on-Tessera's-domain)** | Comprehensive agent-building guide (Pydantic AI + Claude Agent SDK — both real), explore-plan-execute-verify, tool design with risk levels, agent-as-tool / handoff, multi-layer guardrails, memory, eval tests. **This is squarely Tessera's own domain** (agent infrastructure). Not stale (model IDs are illustrative), not superseded, not filler. KEEP. |
| **build-in-public** | **HARVEST→CUT** | Admissible: **(Q1) no frontmatter at all** (malformed as a skill); **(Q2) superseded by the live `build-in-public` *plugin*** (present in this session's skill list, Buffer-integrated) — this file is just the plugin's prose doc and even says "the build-in-public plugin follows these practices." **Harvest:** the writing guidance is genuinely good ("letting people watch you work, no hype sludge", the share / never-share lists, per-channel format rules) — fold into the plugin's own docs/config if not already there. Then cut the corpus copy. |
| **agent-teams** | **HARVEST→CUT** — *the batch's hardest call; reasoning made explicit* | **Why this differs from the KEEP-cold calls (`workspace`, `cpg-analysis`):** those are honestly-scoped *generic/opt-in capabilities*; agent-teams is **one specific foreign product's (Maggy) workflow asserted as the universal mandatory default** — its first line: *"Every project initialized with **Maggy** runs as a coordinated team … **This is the default workflow, not optional.**"* That is false for Tessera (no Maggy, uses the Agent tool/Workflow directly; `maggy` CLI absent), and it's the same foreign-product-mandatory pattern already cut in `autonomous-testing`. **AND it's a named fossil:** the strict-TDD task-dependency chain ("structurally impossible to skip steps — task N+1 invisible until N verifies") is *the shape of Tessera's own Stop-hook gate enforcement*. **Harvest:** lift that structural-step-enforcement pattern into the design-doc as kin to the gate/Stop-hook loop; cut the Maggy roster/pipeline + its 6 tracked `agents/*.md` files. *(Cleanup on cut: the `ticket-craft` "agent-teams mapping" section, and the `base`/`iterative-development`/`icpg` references to agent-teams.)* |
| **codex-review** | **HARVEST→CUT** | Essentially a **vendor CLI manual** (OpenAI Codex) — competent, but (Q3) reference the vendor docs + a capable model already carry, and **(Q2) subsumed** by `code-review`'s engine-comparison section (which points here) *and* by Claude Code's **native `/code-review`**; needs `npm i -g @openai/codex` + Node 22 (absent). **Harvest:** the findings JSON-schema + headless CI patterns are reusable for the **conclave/council multi-model work (handoff item 1)** — note them there. Cut the vendor-manual skill. Pairs with `code-review`'s HARVEST→CUT (multi-engine bulk goes, ADR gate stays). |
| **gemini-review** | **HARVEST→CUT** | Same as `codex-review`: vendor CLI manual (Google Gemini), Node-absent, subsumed by `code-review`'s engine section + native `/code-review`. Its benchmark table (SWE-Bench 63.8%, Gemini 2.5-Pro-era) is a cycle behind but that's cited-benchmark context, not the cut basis. **Harvest** the 1M-context "review the whole repo at once" angle → conclave design note. Cut. |

*(Batch F DONE. All 56 skills judged by reading the body. Final tally below.)*

---

# ═══ FINAL TALLY — REAL AUDIT (2026-07-14) ═══

**All 56 `SKILL.md` bodies read in the main thread. Verdicts on the 5 admissible content questions only; reachability (never-invoked / `paths:` can't match here) used for NOTHING.**

| Verdict | Count | Skills |
|---|---|---|
| **KEEP** | **38** | framework-evaluation, polyphony, mnemos, cpg-analysis, typescript, react-web, react-native, nodejs-backend, ui-web, ui-mobile, playwright-testing, pwa-development, flutter, android-java, android-kotlin, firebase, supabase, database-schema, supabase-nextjs, supabase-node, aws-aurora, aws-dynamodb, azure-cosmosdb, cloudflare-d1, site-architecture, credentials, workspace, team-coordination, commit-hygiene, existing-repo, project-tooling, posthog-analytics, web-content, user-journeys, ticket-craft, llm-patterns, agentic-development, iterative-development |
| **FIX** | **3** | council-review (paths `~/bin/`→`bin/`), code-graph (config claims), supabase-python (over-broad `**/*.py` glob) |
| **TRIM** | **3** | base, python, icpg |
| **ADAPT** | **1** | security |
| **MERGE** | **1** | ui-testing → ui-web/ui-mobile |
| **HARVEST→CUT** | **6** | cross-agent-delegation, autonomous-testing, code-review*, session-management, code-deduplication, build-in-public, agent-teams, codex-review, gemini-review |
| **CUT** | **1** | ai-models |

*(\* code-review is HARVEST→CUT-the-bulk / KEEP-the-ADR-gate-as-its-own-skill. The HARVEST→CUT row lists 9 because it aggregates the fossil-harvests and vendor-subsumptions.)*

**Corrected count: 38 KEEP / 46 keep-in-some-form (38 KEEP + 3 FIX + 3 TRIM + 1 ADAPT + 1 MERGE); genuine removals (CUT + HARVEST→CUT) = 10, every one grounded in TRUE-is-false / SUPERSEDED / GENERIC-filler — none on "never invoked" or "paths can't match."**

## The headline, versus the VOID table

- **The void table CUT 47 and kept 9. This audit removes 10 and keeps 46 — a near-exact inversion.**
- **Every one of the 47 void-cuts that this audit reversed was cut on reachability** (0 invocations / `paths:` can't match in Tessera). Reading the bodies showed the overwhelming majority are **current, accurate, additive stack/agent skills** — inert in Tessera *by design* (global registry serving 20+ repos), which the rubric established says nothing about their worth.
- **The 10 real removals cluster into three honest, admissible causes:** **(1) stale/false** — `ai-models` (7-month-old model table); **(2) fossils superseded by Tessera's own machinery** — `session-management`→Mnemos, `code-deduplication`→icpg, `agent-teams`→Stop-hook enforcement, `cross-agent-delegation`→polyphony/icpg (all HARVEST-first); **(3) foreign-product / vendor-manual / superseded-by-native** — `autonomous-testing` (Maggy), `build-in-public` (live plugin), `code-review` bulk + `codex-review` + `gemini-review` (native `/code-review`).
- **Three verdicts flipped materially *because* the body was read against current state:** `council-review` CUT→**FIX** (its backends were repaired in the same prior session — `bin/validate-plan`/`bin/review` now exist); `iterative-development` CUT→**KEEP** (the Stop-hook-exit-2 mechanism is real, non-obvious, and used by Tessera's own gate hooks); `cpg-analysis` CUT→**KEEP** (I caught myself re-cutting it on the absent backend — the exact ADR-0007 error).

## Was the compaction premise vindicated?

**Reading 56 bodies in the main thread was ~200k tokens of genuine, un-padded content-judgment** — exactly the read-heavy work FOCUS-004 always specified, and the opposite of the void session's ~15 shell commands. **This restores the P3 compaction premise the void draft wrongly declared falsified:** the real audit *is* read-heavy. Whether `auto` compaction actually fired this session is recorded by the Mnemos log, not asserted here — but the work was the real thing, incrementally journaled so it survives regardless.

## HARVEST manifest (do these BEFORE any cut — the base-skill licence demands it)

1. `ai-models` → keep the provider **doc-URL pointer list** (live links, not hardcoded IDs) if a multi-provider reference is still wanted.
2. `session-management` → tiered-summarization design → design-doc/ADR as **Mnemos's lineage**.
3. `code-deduplication` → "duplicate PURPOSE not duplicate code" + check-before-write discipline → **icpg** anti-patterns / design-doc.
4. `agent-teams` → **structural step-enforcement via task dependencies** → design-doc as kin to the **Stop-hook gate loop**.
5. `cross-agent-delegation` → (nothing unique; scoring→polyphony, iCPG triad→icpg already hold it — confirm before cut).
6. `autonomous-testing` → discover→gen→evaluate→fix pipeline shape (classification already in `iterative-development`).
7. `build-in-public` → per-channel writing guidance → the live plugin's docs.
8. `code-review` → **the ADR gate + `adr-gate.md` → its own small `adr-gate` skill (MUST survive)**; multi-engine dedup output format → conclave note. **✅ DONE 2026-07-14:** `skills/adr-gate/SKILL.md` created (harvested + Tessera-corrected: fixed the generic `claude-bootstrap`/`decisions.md`/status-vocab errors; wired to real `docs/adr/` + README index + doccheck `adr-index-complete` + supersede-not-edit). Old `skills/code-review/adr-gate.md` deleted; `code-review/SKILL.md` + `design-principles.md` refs repointed. **`code-review` now safe to HARVEST→CUT the bulk.** *(Still owed: multi-engine dedup format → conclave note.)*
9. `codex-review` / `gemini-review` → findings JSON-schema + headless-CI + 1M-context patterns → **conclave/council design note (handoff item 1)**.

## What this means for the framework (the real finding, restated)

The void audit's headline — "6 invocations machine-wide, the inherited corpus contributed one skill ever" — **indicts the framework's distribution and discovery, not the skills.** This content audit confirms it: the corpus is mostly *good, current, downstream-applicable* skills that **cannot reach the repos they're for**, because **`bin/tessera-new-project` ships zero skills**. **The fix is a delivery path (ship skills downstream), not a chainsaw.** Principle #15's "trim on evidence" was satisfied — and the evidence, read at last, says *keep most, cut ten for cause, and go build the pipe.*
