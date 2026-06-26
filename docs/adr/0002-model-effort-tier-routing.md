# ADR-0002: Model effort-tier routing via dispatch-time hooks (not a running agent)

- **Date:** 2026-06-26
- **Status:** Accepted
- **Decision driver:** Project decision — "should an agent recommend and change the model based on the work needed?"

> This is an internal architecture decision, not an external-tool evaluation, so
> it uses the classic ADR form (Context / Decision / Alternatives / Consequences /
> Re-evaluate) rather than `_template.md` (which is shaped for framework evals like
> ADR-0001).

---

## Context

The opening question was whether to build a **running agent** that recommends and
switches the model per task. Investigating Claude Code's actual mechanics changed
the shape of the answer:

- **The model binds at fixed dispatch points**, not continuously: main-session
  start (`/model`, `settings.json`), subagent spawn (agent frontmatter or the
  Agent tool's `model` param), and workflow `agent(prompt, {model})`.
- **A subagent cannot change its own model mid-life**, and **the main-thread model
  cannot be hot-swapped mid-turn by a hook.** A continuous "watcher" could *observe*
  but could not *apply* — and monitoring every turn costs tokens to find savings.
- Existing infra (`route-task-hook`, UserPromptSubmit) already classified each
  prompt into 11 **cross-provider** tiers and **injected delegation instructions**
  ("you MUST run `~/bin/deepseek`…"), caching the tier to
  `~/.claude/routing-cache.json`. It **couples classification with delegation** — and
  the delegation hijacks framework-dev sessions by telling Claude to shell work out
  to other CLIs. It also depends on a local classifier (Ollama/qwen or keyed CLIs)
  that was absent on a fresh machine, so it fell through to a bare `CLAUDE` fallback.

CLAUDE.md requires consequential decisions to live in an ADR, not just commit
messages — hence this record for what shipped in `6.45.0`/`6.46.0`.

---

## Decision

1. **Reject the running-agent / daemon model.** Recommendation is computed at the
   prompt boundary; **application happens only at dispatch gates** (subagent spawn,
   workflow call). For the main thread the tier is **advisory** (suggest `/model`).

2. **Split the Claude tier** in `route-task-hook`: the single `CLAUDE` becomes
   `CLAUDE_HAIKU` / `CLAUDE_SONNET` / `CLAUDE_OPUS` (effort tiers *within* Claude —
   haiku = mechanical bulk, sonnet = standard, opus = architecture/security/hard).

3. **Add `subagent-route-hook`** (PreToolUse, matcher `Task|Agent`): reads the
   cached tier and rewrites a spawned subagent's `model` via
   `hookSpecificOutput.updatedInput`. Explicit `model` on the call always wins;
   non-Claude tiers / missing cache / empty input are no-ops; fails open. (Verified
   against Claude Code docs that PreToolUse hooks can rewrite tool input.)

4. **Dogfood combo B (cache-only) in Tessera**: a new `tier-classify-hook`
   classifies each prompt into the three Claude tiers via local qwen and writes the
   cache **without** `route-task-hook`'s cross-provider delegation or minimax
   pre-analysis. Framework-dev gets live tiers with no delegation hijack.

5. **Classifier = `qwen2.5-coder:3b` (local, Ollama)** with **few-shot + token-only
   output + temperature 0** — a 3B model parrots the middle tier under a descriptive
   prompt but discriminates reliably when asked for the bare token. Small + fast is
   the requirement because classification runs on **every** prompt.

---

## Alternatives considered

| Alternative | Verdict | Why |
|---|---|---|
| Running watcher agent that swaps models | Rejected | Can't apply mid-flight; monitoring cost exceeds the savings it finds |
| Python keyword `recommend_tier()` as primary | Rejected (kept as fallback idea) | Heuristics misclassify novel phrasing; local qwen gives real judgment at ~equal setup |
| Full `route-task-hook` wired into Tessera (combo D) | Rejected | Cross-provider delegation hijacks framework-dev; +3–5s minimax/prompt. Right for a general work machine, wrong here |
| Bigger classifier (`qwen3-coder:30b`, 19GB) | Rejected | A 3-way label-pick doesn't need a code-gen frontier model; 10× resources, ~0 gain |

---

## Consequences

**Positive**
- Subagents auto-route to the right effort tier — cheaper mechanical work, stronger
  hard work, no manual `/model`.
- Cache-only keeps framework-dev sessions clean (no "delegate to deepseek" noise).
- Mechanism is deterministic, testable, and opt-in per the `hooks/` convention.

**Negative / costs**
- **~2–8s/prompt** local-qwen latency in Tessera sessions (fails open to
  `CLAUDE_SONNET` if Ollama is down).
- **haiku/sonnet boundary is fuzzy** at 3B (OPUS — the escalation that matters — is
  reliable).
- Cache is **per-last-prompt, not per-subagent**; a cheap subagent under an OPUS
  prompt inherits opus unless the call sets `model` explicitly.
- **Main-thread application stays impossible** (harness limitation) — advisory only.

**Bias noted:** novelty/excitement bias toward building the routing system.
Mitigated by repeatedly surfacing that the main thread can't actually hot-swap, and
by choosing the lazy cache-only combo over the full cross-provider build.

---

## Re-evaluate trigger conditions

- Claude Code exposes a way to set the **main-session** model mid-turn from a hook →
  revisit the advisory-only stance for the main thread.
- haiku/sonnet misclassification observed to cost real quality/money → bump to
  `qwen2.5-coder:7b` or add boundary few-shot examples.
- Per-subagent accuracy matters (cache-as-proxy proves wrong) → classify the
  subagent's own prompt at dispatch instead of reusing the prompt-level cache.
- Workflow dispatch wants tiering → wire the cached tier into `agent({model})`.
- Next cadence review: **2026-09-24** (90 days).

---

## References

- Commits `89d62aa`, `3cb445e`; CHANGELOG `6.45.0` / `6.46.0`.
- `hooks/route-task-hook`, `hooks/subagent-route-hook`, `hooks/tier-classify-hook`.
- `docs/design-principles.md` — pass 3.4 (hidden hooks directory).
- `docs/observatory.md` — "Thinking-models-specific prompt patterns" (routing
  precondition now met by this ADR).
