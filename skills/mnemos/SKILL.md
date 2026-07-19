---
name: mnemos
description: Task-scoped memory lifecycle — typed MnemoGraph prevents lossy context compaction by treating facts/decisions/code-refs/handoffs as distinct node types with per-type eviction policies
when-to-use: "When you need durable working memory across compactions — checkpoint decisions, preserve task handoffs, or audit what was remembered"
user-invocable: false
effort: high
---

# Mnemos — Task-Scoped Memory Lifecycle

## What It Does

Mnemos prevents lossy context compaction from destroying the structured knowledge you need most. It treats your working memory as a **typed graph** (MnemoGraph) where different types of knowledge have different eviction policies:

- **GoalNodes** and **ConstraintNodes** are NEVER evicted — they survive all compaction
- **ResultNodes** are compressed (summary kept) before eviction
- **ContextNodes** are evictable when their activation weight drops
- **CheckpointNodes** persist to disk for session resume

## Fatigue Model

Mnemos monitors 4 dimensions of "agent fatigue" — all passively observed from hook data, no manual input needed:

| Dimension | Weight | Signal Source | What It Measures |
|-----------|--------|--------------|-----------------|
| Token utilization | 0.40 | Statusline JSON | How full the context window is |
| Scope scatter | 0.25 | PreToolUse file paths | How many directories the agent is bouncing between |
| Re-read ratio | 0.20 | PreToolUse Read calls | How often the agent re-reads files it already read (context loss) |
| Error density | 0.15 | PostToolUse outcomes | What fraction of tool calls are failing (agent struggling) |

Fatigue states and actions:

| State | Score | Action |
|-------|-------|--------|
| FLOW | 0.0–0.4 | Normal operation |
| COMPRESS | 0.4–0.6 | Micro-consolidation runs (compress 3 ResultNodes, evict 1 cold ContextNode) |
| PRE-SLEEP | 0.6–0.75 | Checkpoint written, consolidation runs |
| REM | 0.75–0.9 | Emergency checkpoint, consider wrapping up |
| EMERGENCY | 0.9+ | Checkpoint written, hand off immediately |

## How To Use

### Automatic (hooks handle everything):
1. **Statusline** writes `fatigue.json` on every API call
2. **PreToolUse** hook reads fatigue before every edit, auto-checkpoints at 0.60+
3. **PreCompact** hook writes emergency checkpoint, compaction marker, a `compaction_fired` log line, and tells summarizer what to preserve
4. **SessionStart** (no matcher, so it fires on `startup`, `resume`, *and* `compact`) runs `mnemos-session-start.sh`, which loads the last checkpoint — this is the primary restore on all three sources
5. **PreToolUse fallback** (no matcher) detects the compaction marker on the first tool call and re-injects if SessionStart didn't fire
6. **Stop** hook writes final checkpoint for next session

### Post-Compaction Recovery (Three-Layer Defense):
When Claude Code compacts the context (~83% full), Mnemos uses three layers:
- **Layer 1 (PreCompact)**: Outputs strong preservation instructions with inline checkpoint content for the summarizer. Writes `.mnemos/just-compacted` marker and appends `compaction_fired` to `.mnemos/compaction-log.jsonl`.
- **Layer 2 (SessionStart, unmatched)**: **Primary re-injection.** `mnemos-session-start.sh` fires on every SessionStart source — including `compact` — and prints the checkpoint before the agent acts. It does *not* gate on source and does *not* consume the marker.
- **Layer 3 (PreToolUse fallback)**: `mnemos-post-compact-inject.sh` fires on the first tool call, consumes the marker, injects, and appends `restore_injected` (or `restore_missed_stale` if >5min elapsed). Safety net for the case where Layer 2's output was dropped, and the only layer that fires if the post-compaction turn is pure text with no tool call.

**Two known wrinkles, both benign:**
- Layer 2 doesn't consume the marker, so Layer 3 also fires on the next tool call. The checkpoint gets injected twice. Redundant, not harmful.
- There is no `mnemos-compact-recovery.sh` and no SessionStart `"compact"` matcher. Earlier docs described both; neither ever existed. Layer 2's role is played by the unmatched `mnemos-session-start.sh`. Coverage is intact — only the naming was wrong. (Corrected 2026-07-09.)

The result: after compaction, you'll see a restore block — `MNEMOS SESSION RESUME` (Layer 2) and/or `CONTEXT RESTORED AFTER COMPACTION` (Layer 3) — with your goal, constraints, what you were working on, and progress. Resume from there.

**What's actually been observed (2026-07-11, first-ever compaction, hand-run `/compact`):** Layer 2
delivered — goal, constraints, and a fresh checkpoint landed in post-compaction context, and the
summarizer honored the PreCompact preservation block. Layer 3 logged `restore_injected` and consumed
the marker, but its injected text was never *seen* reaching the model: the plumbing is confirmed, the
injection is not. Treat Layer 2 as the load-bearing one.

**Update (2026-07-16, supersedes the 07-15 reading below):** both gaps re-checked.
- **Fatigue is LIVE, not degraded.** `fatigue.json` carries real token metrics (`source: statusline`);
  `mnemos fatigue` computes all four dims — token-util 0.27 (wt 0.40), composite 0.11 FLOW. The 07-15
  all-`None` reading was **transient** (statusline JSON not received that session), not a real defect.
- **Compaction DOES fire here — without a `trigger`.** The 07-12 `trigger: unknown` event was a *non-manual*
  PreCompact firing (a `restore_injected` followed 23 s later), so the "harness never opens this door"
  read below was too strong. The harness fires PreCompact via its own summarization path, which sends no
  Claude Code `{trigger}` — hence `unknown`. An `auto` (context-full) event has still never been seen, and
  a ~200k overfill produced none, so P3 can't complete here. **DECISION: judge the compaction-recovery half
  on a real Claude Code CLI session; the fatigue half is judged here (it works).** PreCompact now logs a
  key-only `payload_probe` on `unknown` events to learn what the harness sends. See `docs/observatory.md`
  → "Mnemos compaction vehicle" (2026-07-16 update).

**Original 07-15 reading (kept for the trail, now corrected above):** a session deliberately overfilled to
~200k tokens produced **zero** `compaction_fired` events, and `fatigue.json` read all-`None` (fatigue
*degraded*, token-util blind). Both were session-local artifacts, not standing defects.

### Is the compaction-recovery layer actually working?
`.mnemos/compaction-log.jsonl` is the durable record — the marker is deleted on
consumption and leaves no trace, and `checkpoints` has no trigger column, so this
file is the *only* evidence that compaction ever fired. Tally it with:

```bash
python3 -c "
import json,collections
c=collections.Counter((json.loads(l)['event'], json.loads(l).get('trigger','-')) for l in open('.mnemos/compaction-log.jsonl'))
print(dict(c))"
```

`compaction_fired` with no matching `restore_injected` means the recovery layer
is failing. Zero lines means compaction has never fired — which is *not* evidence
the layer is useless, only that it is untested.

**`trigger` is load-bearing, not decoration.** `auto` = context filled up: the real
event this layer exists for. `manual` = a hand-run `/compact`, i.e. a **test** of the
layer. A test is never evidence about the thing it tests — so `tessera-watch` P3 (the
Mnemos kill/keep verdict) counts only non-manual events. Without this split, three
deliberate test compactions would trip the trial's verdict on data we manufactured.
Compact by hand as often as you like; it cannot contaminate the trial.

### Manual CLI:
```bash
mnemos init                    # Initialize .mnemos/
mnemos status                  # Show node counts + fatigue
mnemos fatigue                 # Detailed fatigue breakdown
mnemos checkpoint --force      # Write checkpoint now
mnemos resume                  # Output checkpoint for context
mnemos consolidate             # Run micro-consolidation
mnemos nodes --type goal       # List active GoalNodes
mnemos add goal "Build auth"   # Add a GoalNode
mnemos bridge-icpg             # Import iCPG ReasonNodes
mnemos ingest-claude --all     # Ingest Claude Code transcripts (see below)
mnemos haze --recent 10        # Show per-session haziness scores
```

## Claude Transcript Ingestion & Haziness

Mnemos can ingest Claude Code session transcripts (the per-session JSONL under
`~/.claude/projects/`) and score each session's **haziness** — a measure of how
much the agent struggled. The `Stop` hook does this automatically on session
exit; it is also available manually.

**What's stored:** only structural fields (roles, tool names, file paths, error
flags, timestamps) plus a **redacted, 200-char preview** of each turn. Full
content is never persisted, and secrets (API keys, tokens, PEM blocks, JWTs,
credentials) are redacted before anything touches disk.

**Haziness** is a weighted score over five dimensions, each in `[0,1]`:

| Dimension | Weight | What it measures |
|-----------|--------|------------------|
| correction_density | 0.30 | User corrections per eligible user turn |
| redo_ratio | 0.25 | Edits re-touched after an error |
| first_try_error_rate | 0.20 | Edits followed by errors within 3 turns |
| orphan_tool_use_rate | 0.15 | Tool calls with no matching result |
| backtrack_norm | 0.10 | `git revert`/`reset --hard`/`restore` calls |

The composite maps to a band: `clear` < 0.25 ≤ `cloudy` < 0.50 ≤ `hazy` < 0.75 ≤ `lost`.

**Correction detection + typing (spec 13).** `correction_density` counts user turns that push back on
the agent — caught by a keyword regex plus a recall-first local-qwen classifier over the turns the regex
misses (fails open to the regex; `qwen3:8b` + `think=false`, override via `MNEMOS_CORRECTION_MODEL`).
Each detected correction is then **typed** — `misunderstood / defied / overreached / wrong` — stored in
`claude_turns.correction_type`. **Typing is a diagnostic view, NOT a sixth dimension**: it never changes
the composite. See it with `mnemos haze --session <id> --explain` (a `CORRECTION TYPES` rollup + per-turn
`CORRECT:<type>` markers). `mnemos ingest-claude --reclassify --session <id>` re-runs both on history.

```bash
mnemos ingest-claude --all              # ingest every transcript + score
mnemos ingest-claude --session <id>     # one session by id
mnemos ingest-claude --transcript <f>   # a specific JSONL file
mnemos haze --recent 10                 # table of recent sessions
mnemos haze --session <id>              # per-dimension breakdown
```

Ingestion is idempotent (resumes via `last_line_offset`). **Opt out per project**
with `touch .mnemos/claude-log.disabled`.

## Agent Instructions

When working on a task:

1. **Create a GoalNode** at the start: `mnemos add goal "what you're trying to achieve" --task-id session-1`
2. **Add ConstraintNodes** for invariants: `mnemos add constraint "API backward compatibility" --scope src/api/`
3. **Check fatigue** before long operations: `mnemos fatigue`
4. **Checkpoint at sub-goal boundaries**: `mnemos checkpoint`
5. **On session resume**: the SessionStart hook automatically loads your checkpoint

## iCPG Integration

Mnemos bridges with iCPG (Intent-Augmented Code Property Graph):
- `mnemos bridge-icpg` imports active ReasonNodes as GoalNodes
- Postconditions/invariants become ConstraintNodes
- Checkpoint includes iCPG state (active intent, unresolved drift)

## Storage

Everything lives in `.mnemos/` (gitignored):
- `mnemo.db` — SQLite MnemoGraph
- `fatigue.json` — Live token metrics (updated per API call by statusline)
- `signals.jsonl` — Behavioral signal log (appended by PreToolUse + PostToolUse hooks)
- `checkpoint-latest.json` — Most recent checkpoint
- `checkpoints/` — Archived checkpoints
