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
- **Surface decisions before committing them.** Multi-step changes warrant a brief "here's what I'd do, OK to proceed?" — especially for design changes, structural decisions, anything irreversible. When you surface such a gate, **also record it**: `python3 scripts/gate/emit.py --fired --kind <kind> --note "<what you proposed>"` (use `--held` if you considered surfacing one but decided it wasn't warranted). This is principle #12's recorder dogfooding itself — the log is a friction journal, reviewable in tess-dashboard. Forgetting to log a gate is itself a finding, not a failure. See `docs/contracts/gate-event.md`.
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

- **SessionStart** — `mnemos-session-start.sh` loads any prior checkpoint, restores session continuity
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

Tessera is a framework. It has no test or build commands of its own; downstream Tessera-using projects will have their own. For working in this repo:

- `git status` / `git diff` / `git log` — standard repo operations
- File operations under the `.claude/`, `.tessera/`, `docs/`, `skills/`, `commands/` directories

Downstream Tessera-using projects will have their own command sections in their own CLAUDE.md files.
