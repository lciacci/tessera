# ADR-0019: Close the iCPG loop — author intent deliberately, record it automatically, never the reverse

- **Date:** 2026-07-27
- **Status:** Accepted
- **Executed:** 2026-07-27 — `scripts/icpg/__main__.py`, `scripts/icpg/test_intent_lifecycle.py`, `.claude/scripts/icpg-session-base.sh`, `.claude/scripts/icpg-stop-record.sh`, `.claude/scripts/icpg-inject-context.sh`, `.claude/settings.json`, `commands/icpg-intent.md`, `templates/icpg-session-base.sh`, `templates/icpg-stop-record.sh`, `templates/icpg-inject-context.sh`, `hooks/icpg-record-intent`.
- **Decision driver:** Q1 — *"does the agent actually populate ReasonNodes and contracts well in practice?"* (`docs/design-principles.md`) — has been open for weeks with exactly one non-bootstrap data point, and it was unanswerable rather than unanswered: nothing recorded intent during real work.

---

## Decision

**Step 0 (state the intent) stays deliberate. Step 6 (record what it touched) becomes automatic. Never the reverse.**

Four pieces:

1. **`icpg create` gains repeatable `--invariant` / `--precondition` / `--postcondition`**, and opens the intent as **`executing`**.
2. **`icpg fulfil <id>`** closes an intent — agent-invoked, fail-loud.
3. **`icpg-stop-record.sh`** links the session's symbols to the single executing intent, anchored on a session-start SHA.
4. **`icpg-inject-context.sh`** asks for an intent when none is executing — once per session.

---

## Why the recording half was not merely unwired

`icpg record` had never run. Three components existed and none fit the others:

| component | state |
|---|---|
| `hooks/icpg-record-intent` | calls `icpg record --reason "<free text>" --file <p> --auto-invariants` |
| the actual CLI | `--reason <ID> [--base] [--edge-type]` — no `--file`, no `--auto-invariants` |
| `templates/icpg-stop-record.sh` | reads `.icpg/.current-intent`, a **file path**, and passes it as `--reason` |

None was wired, which is why nobody found out. F-001's shape one level worse: F-001 ran on the wrong interpreter, this would fail on any interpreter, kept invisible because nothing called it.

**A prior session had already diagnosed this and left the verdict in the file's own header** — including *"even repaired, it should not be wired here"*, because it auto-created ReasonNodes from commit messages, which is git-history bootstrap under another name and would have generated more inferred intent *"while looking like progress."* That header prescribed the fix: *"the recording half this repo actually needs is AUTHORED intent … which is a workflow change, not a hook."*

**This ADR follows that verdict rather than overruling it.** The file is kept, not deleted — it is the only written record of the flow, and ADR-0007 governs. Its diagnosis is what shaped the replacement.

## Why step 0 is never automated

Automating `create` would answer Q1 by making it unanswerable. Q1 asks whether the **agent** states intent; a hook doing it proves only that a hook ran. That is the proxy trap this repo has retired four predicates over (standing pattern #3).

So the loop splits by **judgement vs bookkeeping**:

- **Judgement** — *what am I trying to achieve, in what scope, under what contracts* → agent-invoked (`/icpg-intent`), and *"this intent is done"* is the same kind of judgement → agent-invoked (`icpg fulfil`).
- **Bookkeeping** — *which symbols changed while that intent was open* → mechanical, hooked.

## The four decisions, and what each rejected

**(a) `create` opens as `executing`, not `proposed`.** The default was `proposed` and only `record` promoted — so the recorder, which keys on the executing intent, could never see a freshly stated one. Record needed an executing intent and only record could make one. You do not state an intent you are not about to work on.

**(b) Two or more executing intents → record nothing, and report `degraded`.** Rejected most-recent-wins: a wrong intent link is worse than none, because drift then measures against fiction. Reported rather than silent, so *"recorded nothing"* is distinguishable from *"nothing to record"* — the fail-open distinction spec 11 exists for.

**(c) The step-0 prompt fires only when zero intents are executing, once per session.** Ungated it fires on every edit and becomes wallpaper, which is how a real signal dies.

Keyed on **no executing intent**, deliberately *not* on "this file has no intent context" — `query context` answers from CREATES edges regardless of status, so a file touched by a long-fulfilled intent still returns context. The first implementation nested the prompt under "no context for this file" and could therefore only fire on files with no intent history at all. **An old fulfilled intent does not excuse changing code without saying why now.**

**(d) An explicit close verb, not auto-close at session end.** Without any close verb, `executing` only grows and (b) makes the recorder permanently silent after the second intent — the design would close step 6 and re-open the ambiguity one session later. Auto-closing was rejected because it would make `executing` mean "most recent session" rather than "being worked on".

## The base anchor

`record` diffs against a base. HEAD-relative bases (`HEAD`, `HEAD~1`) are relative to **git's** state, not the **session's**, and are wrong in three ordinary cases: several commits in a session (`HEAD~1` catches only the last), a rebase or merge (different lineage — conflict-resolution files get attributed to your intent), and a branch switch.

So `icpg-session-base.sh` stamps the SHA at SessionStart. If it later becomes unreachable, the recorder **goes quiet and reports `degraded`** — it never falls back to a guess.

## Consequences

- Q1 becomes answerable: intents authored during real work are distinguishable from the 10 bootstrap-inferred ones by `source` and by having hand-authored contracts.
- `decision` drift gains real inputs for the first time — it evaluates predicates, and until now nothing could author one.
- **`/icpg-intent` documented flags that never existed** (`--file`, a prose `--invariants`). Corrected. A predicate that does not parse is silently unevaluable, which is how a contract tier can look present and be absent.
- The recorder is honest about silence: zero intents → quiet by design; ambiguous or broken → `degraded`.
- **This does not answer Q1.** It makes it askable. The evidence is a real downstream task, and the verdict needs sessions that were not spent building the instrument.

## Biases named

- **Momentum.** Seventh consecutive commit on Tessera's own organs, and "one more enabling piece" is exactly what momentum says. The counterweight: this one is *prerequisite* to the downstream work, not a substitute — without it, real work generates no Q1 evidence.
- **Reflex to delete.** I moved to delete `hooks/icpg-record-intent` as dead code and was wrong: it carries a decision record and an explicit `ADR-0007` preservation note. Reading it changed the design — the header's verdict is this ADR's spine. Nearly cutting the artifact that shaped the fix is worth recording.

## References

- `docs/design-principles.md` — Q1, and the nine-step workflow adopted as a principle
- `skills/icpg/SKILL.md` — *"Step 0 is non-negotiable for autonomous agents"*
- `docs/adr/0006-instrumentation-not-control.md` — why the prompt asks and never blocks
- `docs/adr/0007-skill-corpus-prune.md` — harvest before you cut
- `docs/contracts/degraded-event.md` — the channel the recorder reports through
