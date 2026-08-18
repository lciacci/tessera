# Contract: degraded event

**Status:** Canonical. Owned by Tessera (the producer). Defined here; consumers conform.

A concrete instance of the generic Tessera hook-event shape (`type` / `ts` / `session_id` /
`source` / structured `data`, one JSON object per line in `.tessera/logs/<session-id>.jsonl`) —
the same channel the gate, spend, and override events already ride, so `tessera-watch` and the
SessionStart surface get it for free.

Emitted by `bin/tessera-degraded` (spec 11). Consumed by `tessera-watch` **P13**.

```jsonc
{
  "type": "degraded",               // discriminator; consumers filter on this
  "ts": "2026-07-26T14:03:11Z",     // ISO 8601 — MAY BE EMPTY, see below
  "session_id": "uuid",
  "source": "spend-guard",          // the component that could not do its job
  "data": {
    "component": "spend-guard",     // closed-ish set: see Components
    "reason": "guard-missing",      // kebab-case, closed vocabulary per component
    "detail": "…/guard.py absent; spend-committing commands are ALLOWED"
  }
}
```

## The distinction this event exists for

| | |
|---|---|
| **"Nothing to do"** | Correct, silent exit. No `.mnemos/`. No gate to scan. **Never emit.** |
| **"I could not do my job"** | **DEGRADED.** Emit, then bail exactly as before. |

Every bug on 2026-07-12 was the second kind, silently treated as the first. The event does not
change any control flow — a hook that failed open still fails open. It only makes the failure
*sayable*.

## Producers

`bin/tessera-degraded`, invoked two ways (A and B below). Downstream projects receive a
copy at *their own* scripts/ directory, under the same name — shipped by
`bin/tessera-new-project`, the same bridge shape as `tessera-escalate`. (Written without
backticks on purpose: it is a downstream location, and doccheck's `referenced-paths-exist`
correctly reads a backticked path as a claim about *this* repo.) Hooks resolve, in order: the
project's `bin/`, then its scripts/ directory, then PATH.

Two distinct producer paths, and the difference matters:

**A. From inside a hook that ran** — the hook started, then hit a bail-out it could not recover
from. Emitted by the hook script itself.

| Component | Reasons currently emitted |
|---|---|
| `spend-guard` | `jq-unavailable`, `guard-missing`, `no-python3`, `cwd-unreachable`, `guard-errored` |
| `spend-backstop` | `jq-unavailable`, `backstop-missing`, `no-python3`, `cwd-unreachable` |
| `gate-scan` | `jq-unavailable`, `no-transcript-path`, `scanner-missing`, `no-python3`, `cwd-unreachable` |
| `mnemos-checkpoint` | `toolchain-unreachable`, `checkpoint-failed` |
| `tessera-watch` | `runner-missing`, `runner-crashed` |
| `tessera-findings` | `runner-missing`, `runner-crashed` |
| `decision-surface` | `runner-crashed` |

**`runner-missing` / `runner-crashed` are a THIRD class, added 2026-07-27 by the A5b audit, and
they are the gap B could not cover.** B reports a hook *script* that is missing or unexecutable.
It cannot report a hook that **ran perfectly while the tool it calls is gone or crashed** — and
that was live: `rm bin/tessera-watch` and SessionStart printed a completely normal handoff while
P3, P4, P9 and P11–P15 all went silent at once, because the reporter for every one of them was
the thing deleted. Probed before fixing; all three surfacers were silent.

`runner-crashed` exists separately because the surfacers tested `[ $? -eq 1 ] || exit 0`, which
put "nothing fired" (rc 0) and "a predicate raised" (rc 2) on the same branch: a crashing watcher
read as a healthy one. Guarded by chaos probes 9–11.

**Note for anyone auditing coverage: all three of these hooks had ZERO `degraded` calls before
this.** That absence is exactly what the 2026-07-26 audit misread as missing coverage and got
wrong three times — and here it was right, for a reason no count could distinguish. Only breaking
the component and watching answers the question.

**B. From the wired command, when the hook NEVER RAN** — reason is always `hook-unavailable`.
No code inside a hook can report this, because the hook did not execute; the branch lives in the
`settings.json` command string and is written by `scripts/hooks/report_settings.py`.

The component is derived from the script name, so **B covers every wired hook**, not only the
five spec-11 components: `gate-scan`, `spend-guard`, `spend-backstop`, `decision-surface`,
`watch-surface`, `findings-surface`, `subagent-route-hook`, `tier-classify-hook`, and all seven
`mnemos-*` hooks. Scope is deliberately not an allowlist — see `needs_reporting`'s docstring.

**Two-tier (ADR-0004) commands are in scope too, since 2026-07-26.** The branch is appended after
the whole `if/elif/fi`, so it fires only when the local AND global tiers have both failed. They
were excluded at first on the premise that the global copy makes a missing local file
recoverable — but under the **default `global` distribution no local copy is ever shipped**, so
that branch is the only tier, not a redundancy. The exclusion left all 7 mnemos hooks
fail-silent in every default downstream.

## Why the producer is POSIX `sh` with no external tools

It reports on broken infrastructure, so it may not assume working infrastructure. A hook bailing
because `python3` is gone cannot use python3 to say so; a hook bailing because `jq` is gone
cannot use jq to read its own stdin. That is Standing pattern #1 — *the thing that would tell you
it is broken is also broken* — applied to the reporter itself.

So the producer uses shell builtins only: JSON is parsed with parameter expansion, and `date` and
`mkdir` are **optional**. Chaos probe 5 hides both deliberately and the event must still land.

**Consequence: `ts` may be the empty string.** Consumers must handle it. `tessera-watch` P13 falls
back to the log file's mtime rather than dropping the event — losing the loudest events to a
missing clock would be this spec's own failure mode reproduced inside its fix.

## Known blind spot — named, not silently accepted

The log is **keyed by `session_id`**, so a bail-out that happens *because there is no session id*
has no file to write the complaint into. `[ -z "$SESSION_ID" ] && exit 0` in the Stop hooks is
therefore permanently unreportable through this channel.

This is a property of choosing the session log as the transport, not an oversight. It is
acceptable because a Stop hook without a `session_id` has no transcript to scan and no denial to
disposition either — there is genuinely nothing to do — but it is recorded here so that a future
reader does not mistake the silence for coverage.

## Consumers

- **`tessera-watch` P13** — fires on any *unacknowledged* degraded event in the last
  `DEGRADED_WINDOW_DAYS` (7).
  **Windowed on purpose:** a degraded event is an *incident*, not a standing state. "The guard was
  missing last Tuesday" is history; "the guard is missing now" is the alarm. This is the direct
  lesson of iCPG's drift backlog, which reached 700 undisposed rows because nothing could ever
  leave the open set — a counter that only increments is indistinguishable from a broken detector.

  ~~Windowing means P13 needs no disposition verb to stay honest.~~ **That was this contract's
  claim until 2026-08-18, and it was wrong in one specific way — struck rather than deleted,
  because the reasoning above it still holds and is why the ack is a watermark rather than an open
  set.** The window distinguishes old from recent. It cannot distinguish *recent and live* from
  *recent and already fixed*, so a condition resolved the day it was reported keeps firing for the
  remainder of its 7 days. Measured cost (ADR-0025): 14 of 16 degraded events ever written came
  from one detector, and G-a graduated on the streak with no right answer available — snoozing
  would have blinded P13 to new events, and waiting it out is what trains a reader to ignore the
  channel. **A channel that trains its reader to ignore it cannot carry an autonomy precondition.**

- **`degraded_ack`** — the disposition, added by ADR-0027. `scripts/degraded_ack.py` writes a
  watermark per `(component, reason)`; P13 honours it **only for events recorded before the ack's
  own `ts`**. That is the spend contract's grant/dismiss rule, and it is what makes the verb safe
  to hand the model: an ack cannot suppress a break that has not happened yet, so unlike a snooze
  it can never blind the predicate. Acks are watermarks, not an open set, so nothing accumulates
  and the iCPG failure mode above cannot recur through them.

  **BLANK-`ts` EVENTS FOLLOW A DIFFERENT RULE, AND IT IS A CEILING — stated here because the
  sentence above is not true of them, and a narrowing that lives only in the source is standing
  pattern #12.** An event with no `ts` (chaos probe 5 hides `date`) has no clock to compare, and
  its mtime fallback is a fact about the *file*, which the ack itself mutates by being appended
  to it. So those are acknowledged by POSITION — an ack later in the **same log file**.
  `degraded_ack.py` writes to the *current* session's log while P13 surfaces at the *next*
  session's start, so in practice a blank-`ts` event from a prior session **cannot be
  acknowledged at all** and will fire until the 7-day window rolls off. That is tolerable
  because it errs toward reporting and because a missing `date` is rare outside the chaos
  probes — but it is a real limit, not a rule, and the honest fix is for `tessera-degraded` to
  always carry a stamp.

  ```jsonc
  {
    "type": "degraded_ack",
    "ts": "2026-08-18T20:41:00Z",     // THE WATERMARK — not decoration
    "session_id": "uuid",
    "source": "model",
    "data": {"component": "standing-patterns", "reason": "block-missing", "note": "…"}
  }
  ```

  `--note` is required (≥25 chars) for the same reason `restore/emit.py` requires evidence: a bare
  verdict is the failure mode. An ack naming a `(component, reason)` that has **never** written a
  degraded event is **refused** — otherwise a typo leaves a watermark indistinguishable from a
  deliberate disposition.

  **Where a suppression is visible, precisely.** When P13 fires with a partial ack, the detail
  names the count. When acks silence it entirely, the detail says so — but **that string reaches
  nobody**: `append_log()` records fired/crashed predicate *names* only, and `render()` has no
  section for a quiet predicate, so a non-fired detail is computed and discarded (measured
  2026-08-18; ADR-0027 §3 records why it is a stated ceiling rather than a fix). The durable trail
  is the `degraded_ack` event itself, whose `note` sits in the same session log beside the events
  it covers. A suppression is always reconstructable; it is not announced.
- **SessionStart surface** — prints fired watcher predicates, so a degraded event from the
  previous session is reported at the start of the next one. That is spec 11's bar: *break a
  component on purpose, and Tessera tells you within one session, without a human asking.*

## Verification

`bin/tessera-degraded --self-test` covers the flag path, the stdin-derived path, quote escaping,
and the refusal to write without a session id. The integration is covered by `chaos/test_chaos.py`
(`bin/tessera-chaos`), which scaffolds a real downstream, breaks one component, and asserts the
event lands — the real path to the real audience, not a model of it.
