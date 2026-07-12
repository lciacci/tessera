# Contract — escalation packet

An **escalation** is what a suggestion-gate becomes when nobody is there to dispose of it.

Principle #12 is *Claude proposes, user disposes* — which structurally requires a human
present. Running unsupervised, there is no disposer. The agent then has three bad options
(spec 07): silently continue and compound the problem, exit with a confused summary that
isn't actionable, or page a human for everything. An escalation packet is the fourth:
**stop, package what you tried and what you need decided, queue it, keep the trail.**

This is the *asynchronous* form of the gate. The gate is synchronous — it blocks and asks.
The escalation persists and waits.

## Storage

One JSON file per escalation: `.tessera/escalations/<id>.json`. Committed, not gitignored —
an escalation is a work item awaiting a human decision, and it must survive a machine, a
branch, and a session. (Contrast `.tessera/logs/`, which is session telemetry and is ignored.)

## Packet

```json
{
  "id": "esc-20260711-224500",
  "ts": "2026-07-11T22:45:00Z",
  "agent": "claude-opus-4-8",
  "session_id": "dbf99d68-...",
  "severity": "blocking",
  "category": "missing_dependency",
  "summary": "One or two sentences. What is stuck, and why it cannot self-resolve.",
  "tried": [
    "Attempted X — failed because Y",
    "Attempted Z — partial, left W in place"
  ],
  "options": [
    "Option A: revert to <sha>, human decides",
    "Option B: accept and update the postcondition"
  ],
  "refs": ["commit:abc123", "file:path/to/thing.py", "checkpoint:.mnemos/checkpoint-latest.json"],
  "status": "open"
}
```

### Field semantics

- `severity` — `blocking` | `high` | `medium` | `low`. **`blocking` is the only one v1 emits**:
  the agent cannot proceed. The others exist so a future graded escalation has somewhere to
  land; no routing reads them yet, and none is invented until something does.
- `category` — free string, not an enum. The April-2026 spec enumerated five categories tied
  to specs 02/03/04/06; four of those specs do not exist, so an enum would be fiction.
- `tried` — **required, non-empty.** A packet with no `tried` is a complaint, not an escalation.
  This is the field that makes it actionable, and the one an exit-with-confused-summary omits.
- `options` — what the human is being asked to choose between. May be empty (sometimes the
  agent genuinely has no proposal), but empty is a weaker packet — say so in the summary.
- `status` — see below.

## Status vocabulary

Parsed by `bin/tessera-escalate`. Everything before the first `:` is the state.

| Status | Meaning |
|--------|---------|
| `open` | Raised, awaiting a human decision. Shows in the default queue. |
| `resolved:<note>` | A human decided. `<note>` records the decision. Hidden unless `--all`. |
| `abandoned:<reason>` | Went stale or self-resolved. Hidden unless `--all`. |

A packet with **no** status is treated as `open` — unknown counts as needs-attention, never
silently dropped. (Same rule as `docs/contracts/findings.md`, for the same reason.)

## Producers

- **Model-invoked** (v1, current): the agent calls `tessera-escalate raise` when it hits a wall.
- **Auto-triggered** (future): spec 07 wires drift/contract/lock/budget conditions to automatic
  escalation. Four of the five named triggers depend on unbuilt specs (02/03/04/06) — deferred
  until those exist rather than wired to vapor.

### Known #17 exposure, stated honestly

A model-invoked producer rides model recall — the exact failure the gate recorder had
(~85% miss) before its Stop-hook backstop shipped on 2026-07-11.

~~Escalation is **less** exposed than gate-recording was, because a blocked agent cannot
proceed: the failure mode is not silence but "exits with a summary that isn't a packet."~~
~~**Backstop trigger:** the first real unsupervised run.~~

**Falsified by spec 06, and the backstop is BUILT (2026-07-12).** The premise above was that a
blocked agent *cannot proceed*, so it must say something. Spec 06's spend guard broke that: it
denies **one tool call**. The agent is free to do other work, take an offline path, or simply
move on — and the denial disappears with it. **The failure mode became silence**, which is
exactly what the deferral was predicated on being impossible.

The trigger was never "the first unsupervised run" in substance; it was *"the moment a block
stops halting the agent."* Spec 06 was that moment.

**Shape:** Stop hook `.claude/scripts/tessera-spend-backstop.sh` → `scripts/spend/backstop.py`.
A denial must end in one of two places, and it checks which:

| denied → | verdict |
|---|---|
| a human granted an envelope (`spend_authorized` *after* the denial) | ✓ the supervised path |
| an escalation packet was raised this session | ✓ the unsupervised path |
| **neither** | ✗ the block vanished silently — **exit 2** |

**Better-conditioned than the gate-scan.** That one reads a text heuristic and over-counts on
purpose, with the model as precision filter. This reads `spend_denied` — a *logged event*. There
is nothing to adjudicate away: if it fires, something really was denied and really was never
dispositioned. The only legitimate quiet disposition is *"that was a false positive of the
guard's patterns"*, which the hook explicitly invites — a backstop that forces a bogus packet is
worse than none.

Loop-safe: honors `stop_hook_active`, caps at 3 fires/session, fails open on every error path.

**Still model-invoked, and still exposed:** the *content* of the packet. The backstop guarantees
a denial gets answered for; it cannot guarantee the answer is a good summary. That is the
residual, and it is the one ADR-0005 actually named.

## Consumers

```
tessera-escalate list             # open queue (exit 1 if any open)
tessera-escalate list --all       # every packet, any status
tessera-escalate list --json      # machine output (tess-dashboard, watcher)
```

Surfacing rides `bin/tessera-watch` as a predicate (`open_escalations`) rather than a fourth
SessionStart hook — the watcher already exists to surface conditions at session start.
