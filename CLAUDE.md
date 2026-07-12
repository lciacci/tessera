# CLAUDE.md — Tessera Framework

This file gives Claude Code project-specific guidance when working in this repo. It's the framework-development CLAUDE.md, not a downstream-project template. When ready, a downstream-project template will live at `templates/tessera/CLAUDE.md.template`.

## What this repo is

This is the Tessera framework itself. Working here means evolving the framework — adding skills, refining design decisions, capturing ADRs, updating the observatory, debugging hooks. Tessera is not a downstream application; it's the meta-tool that helps build downstream applications.

Source-of-truth references:

- `docs/design-principles.md` — the design doc. Why Tessera is what it is. Read first when something feels unclear.
- `docs/adr/` — Architecture Decision Records. Each numbered, dated, immutable once accepted.
- `docs/observatory.md` — concepts on the radar but not yet decided. Lighter than ADRs; complementary.
- `.tessera/project.yml` — declares Tessera's own profile (standard). Profile model is original IP.

## Skills

@.claude/skills/base/SKILL.md
@.claude/skills/iterative-development/SKILL.md
@.claude/skills/mnemos/SKILL.md
@.claude/skills/security/SKILL.md

Four skills are eagerly loaded. Everything else lives in `.claude/skills/` and loads on-demand when relevant — either by path matching (skill frontmatter `paths:`), explicit invocation, or contextual discovery. The `framework-evaluation` skill specifically activates when evaluating external tools/frameworks (`/evaluate-framework` command).

This set is a starting point per principle #15 (skill defaults as starting points). Trim or expand based on evidence in subsequent sessions; the design doc's framework-evaluation section is where the reasoning for changes gets recorded.

## Working conventions

These describe how Lorenzo works. They're the most important section of this file.

- **Push back when you see drift.** Don't perform agreement. If a decision seems wrong or unstated assumptions seem loaded, surface that — not as a refusal, as honest feedback.
- **"Batching" is a one-word signal.** When Lorenzo says "batching," it means Claude is bundling decisions into prose instead of surfacing them as numbered choices. Stop, list the decisions, ask before committing.
- **Surface decisions before committing them.** Multi-step changes warrant a brief "here's what I'd do, OK to proceed?" — especially for design changes, structural decisions, anything irreversible. This is an accepted *convention*: it shapes how the model works, which principle #17 explicitly permits.
- **Also record each surfaced gate — a separate step, now backstopped.** `python3 scripts/gate/emit.py --fired --kind <kind> --note "<what you proposed>"` (use `--held` if you weighed surfacing one but decided against). The log is principle #12's friction journal, reviewable in tess-dashboard. **The #17 gap is closed (2026-07-11):** the recording used to ride pure model recall and missed ~85% of gates under real work; a Stop hook (`.claude/scripts/tessera-gate-scan.sh` → `scripts/gate/scan.py`) now counts gate-shaped turns in the transcript, diffs against the session's gate log, and exits 2 on a gap so you *must* adjudicate before finishing. **The hook's detector is a recall net, not an oracle — you are the precision filter.** When it fires, log the gates you genuinely surfaced and say plainly which detected turns were only clarifying questions. It stays quiet on a gap of 1 (its noise floor), so keep logging as you go; a forgotten gate is still a finding, not a failure. See `docs/contracts/gate-event.md`.
- **When you fix a doc that had gone stale, leave a check behind.** `python3 scripts/doccheck.py` asserts the machine-checkable claims Tessera's docs make about their own repo (paths that must exist, the ADR index, live thresholds, and that every `.tessera/*.yml` is actually *git-tracked* — existence is a local fact, tracked is the shared one). It is enforced by a **pre-commit hook** (`.githooks/pre-commit`) that **blocks the commit**, and surfaced by `tessera-watch` **P8** at session start. The hook exists because P8 alone let a red commit through: *green is only meaningful if failing it actually stops something.* Override with `git commit --no-verify` when you mean it. Between 2026-07-09 and 07-11, six doc-drift bugs were found — *every one* because Lorenzo got suspicious and asked "all docs updated?", and every one fixed without a check, so the next was found the same way. **The standing rule: every doc-drift bug a human finds becomes an assertion in `scripts/doccheck.py` and a regression test in `scripts/test_doccheck.py`.** If you ever find one that no check covers, that is a finding about the checker, not just the doc — say so. See `docs/contracts/doc-claims.md`.
- **When you are blocked and cannot proceed, raise an escalation — don't just say so and stop.** `tessera-escalate raise --category <cat> --summary "<what's stuck>" --tried "<attempt — how it failed>" --option "<what to choose between>"`. This is the suggestion-gate's *asynchronous* form: #12 needs a human to dispose, and one isn't always there. `--tried` is required — a packet with no attempts is a complaint, not an escalation. Open packets surface at session start via the watcher (`P6`). Resolve with `tessera-escalate resolve <id> --note "<the decision>"`. See `docs/contracts/escalation.md`.
- **Use numbered lists for decision points.** Pacing matters; binary "A or B" questions are easier to answer than dense paragraphs with embedded choices.
- **Name biases you notice in your own reasoning.** Confirmation bias, sunk-cost, excitement, familiarity, anchoring — if you catch yourself, say so. Honesty about bias is part of the trail.
- **Brief acknowledgments, not effusive ones.** "Done," "Confirmed," "Clean" beats "Excellent! That's a great choice!"
- **Flag confidence levels.** Be explicit about what you know vs. what you're inferring vs. what you're guessing.
- **Tone is direct, not performative.** No witty-coworker framing, no jokes shoehorned in. Real moments warrant real responses.

## GSD coexistence

Global `~/.claude/` contains Open GSD's hook infrastructure (per ADR-0001). Project-local settings in `.claude/settings.json` merge with global per Claude Code's documented semantics — arrays concatenate, so both GSD's and Tessera's hooks fire on matching events (SessionStart, PostToolUse). The `statusLine` is overridden by Tessera's project-local config.

If conflicts emerge (state collisions, performance issues, noise), options are documented in ADR-0001's re-evaluate triggers.

## Hook lifecycle (Mnemos)

The hooks in `.claude/settings.json` invoke scripts in `.claude/scripts/`:

- **SessionStart** — `mnemos-session-start.sh` loads any prior checkpoint, restores session continuity; `tessera-findings-surface.sh` runs `bin/tessera-findings` and injects the un-transferred downstream findings backlog (silent when nothing is open). This is the framework learning from its own downstreams without human recall — see `docs/contracts/findings.md`.
- **PreCompact** — `mnemos-pre-compact.sh` writes an emergency checkpoint before compaction
- **PreToolUse** — `mnemos-post-compact-inject.sh` checks for post-compaction restore; `mnemos-pre-edit.sh` (Edit/Write matcher) checks fatigue and intent context
- **PostToolUse** — `mnemos-post-tool.sh` logs tool outcomes
- **Stop** — `mnemos-stop-checkpoint.sh` writes a session checkpoint; `mnemos-stop-ingest.sh` ingests the transcript and scores haze

When you see `MNEMOS CHECKPOINT` in your context, it was injected by a hook. Announce it briefly, resume from the checkpoint, don't re-derive what the checkpoint states. If no checkpoint fires on session resume but `.mnemos/` exists, run `mnemos resume` to check for prior state.

## Model tier advisory

The `tier-classify-hook` (UserPromptSubmit) classifies each prompt into a Claude effort tier via local qwen. Subagents auto-route to it; the main thread sees tier mismatch in the statusline as `⚑tier:<model>` (e.g., `⚑tier:opus Ctx:45%`). No input needed — the statusline flag surfaces it automatically on mismatch, is quiet on match. Fails open to SONNET when Ollama is down.

**Switching models mid-session isn't free — batch it.** Prompt caches are model-scoped: a `/model` switch invalidates the entire cached prefix (tools + system + messages), so the first turn on the new model reprocesses the whole conversation as fresh input at ~1× instead of the usual ~0.1× cache-read — roughly a 10× input-cost spike on that one turn, then back to normal. (Independent of the 5-min cache TTL.) So the flag is *advisory, not auto-switch*: obeying it every prompt and flip-flopping Opus↔Haiku turn-by-turn pays that reread tax on every switch, dwarfing any per-token savings. Right read: switch at natural breakpoints in batches — drop to the cheaper tier for a *run* of mechanical work, do it all, switch back. The flag tells you the task shape; you decide if the batch is big enough to be worth one reread.

## Don't

- Don't modify `.env` files or anything matching `.env.*` (also enforced by settings.json deny list)
- Don't add packages without checking if existing deps cover the need
- Don't put secrets in any committed file
- Don't edit ADRs once accepted. Write a superseding ADR instead. The original stays as historical record.
- Don't put consequential decisions in commit messages alone — capture them in the design doc, an ADR, or the observatory
- Don't reorder or renumber compounding principles in `docs/design-principles.md`. Principles are referenced by number throughout the doc; renumbering breaks the trail.

## Commands

- **`tessera-test`** — run the full suite. Reads `test:` from `.tessera/config.yml`, so **never guess the test command** — in any Tessera project, this is it. (No test count is quoted here on purpose: a hardcoded number drifts on every test added, and the claim that actually matters — *no suite is silently skipped* — is checked structurally, below.) Here it runs `scripts/run-tests.sh`, which runs each suite in a *separate process*: `scripts/gate/`, `scripts/override/` and `scripts/spend/` carry colliding same-directory module names (two `emit.py`, two `scan.py`) and cannot share one pytest process. **Do not "simplify" it to a bare `pytest scripts/`** — that fails collection, and the previous workaround (enumerating files) silently ran half the suite while reporting green. That trap is now checked: doccheck's `ignored-test-suites-are-run` asserts every `--ignore`d suite is invoked somewhere, so dropping one can no longer exit green.
- **`tessera-authorize`** — grant a run-scoped external-spend envelope. **An agent cannot boot a GPU (or any spend-committing command) without one** — `scripts/spend/guard.py` runs on PreToolUse(Bash) and denies by default. Cost-*reducing* commands (teardown, stop, `enable_gpu=false`) are **never** blocked; a spend gate must never be able to block the exit. Blocked with no human present → raise a `spend_unauthorized` escalation; do not route around it. `tessera-authorize grant --usd 20 --ttl 4h --note "..."`. See `docs/contracts/spend-authorization.md`.
- **`tessera-watch`** — evaluate the observatory's machine-checkable triggers. Also runs at SessionStart.
- **`python3 scripts/doccheck.py`** — assert the docs' checkable claims. Enforced by `.githooks/pre-commit`.
- **`./install.sh`** — idempotent; its `verify()` is the machine-known-good check.
- `git status` / `git diff` / `git log` — standard repo operations.

**The toolchain lives in a uv-managed venv (`.venv/`), built by `./install.sh`. F-001 is closed.**

Bare `python3` is whatever Homebrew currently points it at, and Homebrew re-points it whenever a *dependent* formula moves — 3.14 arrived because **ollama** wanted it. That is F-001: hooks called Mnemos through bare `python3`, the import silently failed, every checkpoint write no-op'd for weeks, and it confounded the entire Mnemos trial ("the graph is empty" read as *unused* when it meant *unreachable*).

So: **an interpreter is a path, not a name.** A name is a lookup through a mutable, ordered PATH that four package managers write to. This is not theoretical — on 2026-07-12 `uv python install` shimmed `python3.13` into `~/.local/bin`, *ahead of* Homebrew, and `run-tests.sh`'s `python3.13` pin silently became a different interpreter with no pytest.

- **Needs the toolchain** (`mnemos`, `icpg`, `polyphony`, `pytest`, any third-party import) → reach it by **path**: `.venv/bin/python`. Never by name.
- **Stdlib-only** (`scripts/doccheck.py`, `scripts/gate/*.py`, `scripts/spend/*.py`) → bare `python3` is fine, and these are deliberately kept stdlib-only *so that it is*.

That split is now **enforced**, not merely intended: doccheck's `no-bare-python3-with-toolchain-import` fails if any hook invokes bare `python3` on code importing a venv-only module. The venv fixes today's resolution; that check is what stops the next landmine. `tessera-watch` **P9** asserts the interpreter your hooks actually resolve can import the toolchain, and that its base is not owned by a package manager.

Downstream Tessera-using projects declare their own `test:` in their own `.tessera/config.yml`.
