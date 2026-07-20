# Spec 11: Fail-open detection — make Tessera report its own failure

**Status:** pending as a systematic build — **but its thesis got its first live confirmation and
first partial delivery on 2026-07-20** (spec 16 / PR #38): the Stop-hook ingest pipe failed open
with no trace for 3 days and read as clean data. The remedy shipped there is this spec's pattern
applied to one pipe: a per-run trace (`claude_sessions.classifier_status`) + a loud watcher
(`tessera-watch` P11, including the transcripts-vs-store diff that catches crash-before-write —
the shape no status column can see). The systematic sweep across the OTHER fail-open paths
(hooks, spend guard, gate scan, escalations) remains this spec's open scope.
**Priority:** Tier 1. It gates the trustworthiness of every other verdict the framework produces.
**Effort:** Small mechanism, medium substance. One focused session, possibly two.
**Source:** `docs/observatory.md` → "Fail-open everywhere — Tessera cannot tell you when it is broken"

---

## The problem, in one line

**Tessera is indistinguishable from healthy when it is broken.**

On 2026-07-12, eight bugs were found in one session and **not one of them announced itself.**
F-001 silently no-op'd checkpoints for weeks. The hook fallback silently *succeeded* on an
unmanaged interpreter. **The spend guard failed OPEN on python 3.9 — an unauthorized GPU boot
proceeded.** The spend backstop shipped *disabled* to every clone. A downstream hook had a typo
and had never once run. `doccheck` reported "0 false claims" while three live, wired hooks ran
the toolchain on a bare interpreter.

Every individual fail-open is defensible, and most were deliberate:

> *"A backstop that can wedge a session gets ripped out, and then it protects nothing."*
> *"A hook that wedges every Bash call is its own outage."*

Both true. The **cumulative** property is what nobody chose: there is no signal anywhere in the
stack that distinguishes *"nothing is wrong"* from *"the thing that would tell you is also broken."*
The detectors fail open too — **a green detector looks exactly like a working one.**

## THE BAR — the exit condition, and it is binary

> **Break a component on purpose, and Tessera tells you within one session, without a human
> asking.**

**Nothing in the framework today meets this bar.** Every one of the probes below is currently a
silent pass. That is the spec.

---

## The distinction the whole design turns on

Every fail-open site is one of two things, and only one matters:

| | |
|---|---|
| **"Nothing to do"** | Correct, silent exit. No checkpoint file exists. No gate to scan. **Leave alone.** |
| **"I could not do my job"** | **DEGRADED.** Must be loud. No `jq`. No `python3`. Guard missing. Toolchain unreachable. Wrong cwd. |

**Every bug on 2026-07-12 was the second kind, silently treated as the first.**

Measured surface: 54 bail-out exits across 13 hooks, 42 `2>/dev/null` swallows. **Do not
instrument all of them.** The statusline bailing out is not a safety event.

---

## Scope: FIVE components, not fifty-four sites

Instrument only where a silent failure is an actual loss:

| Component | What a silent failure costs |
|---|---|
| **spend guard** | **unguarded GPU spend** — this one already bit, and failed *open* |
| **spend backstop** | denials vanish undispositioned; the safety net never fires |
| **gate-scan** | gates go unlogged; the calibration corpus silently truncates |
| **Mnemos hooks** | checkpoints lost, or written through the wrong interpreter |
| **doccheck / pre-commit** | lying commits land |

---

## ORDERING — and the order is the point

### 1. Write the chaos tests FIRST. Watch them all fail. ← **do not skip this**

A `break-it-on-purpose` suite. For each component: break it, assert the framework reports it
within one session, unprompted.

```
rm -rf .venv                       → does anything say so?
corrupt scripts/spend/guard.py     → does anything say so?
typo a hook path in settings.json  → does anything say so?   (tess-dashboard: it didn't, for weeks)
PATH=/usr/bin:/bin   (python 3.9)  → does anything say so?   (the guard failed OPEN, silently)
remove jq from PATH                → does anything say so?
chmod -x a hook script             → does anything say so?
```

**Today, every one of those is a silent pass.** Writing the tests first means watching them go
RED *before* any mechanism exists.

> **This ordering is not style. It is the correction for how 2026-07-12 went wrong.** That
> session built a detector, then *verified the fix with the detector that had the hole*, three
> times, and reported green each time. Three independent verifications refuted it. **A detector
> you certify a fix with must be tested against that fix's own failure mode, or it is a mirror,
> not an instrument.**
>
> The base skill has said RED-before-GREEN the entire time. It was ignored. This is the one
> place it is not optional.
>
> **If a future session proposes building the mechanism first, push back and point here.**

### 2. The mechanism — genuinely small

- **`tessera-degraded`** — a helper that appends a `degraded` event to
  `.tessera/logs/<session>.jsonl`. Same shape as the gate/spend events; **the channel already
  exists**, so this is ~20 lines and no new concepts.
- **`tessera-watch` P10** — fires on any `degraded` event. ~15 lines. The SessionStart surface
  already prints watcher output, so surfacing is free.

### 3. Classify the ~15 bail-outs inside those five components

*Could-not-do-my-job* emits `degraded`. *Nothing-to-do* stays quiet. **This is where the
judgment lives**, and it is the only part that cannot be mechanical.

### 4. Downstream

Bundle with the portable-doccheck work (handoff item 2) — both ship via
`bin/tessera-new-project`, and today proved the framework ships guards to downstreams *without*
the checkers that verify they are wired ("ship both halves or neither", violated one layer up).

---

## Where this ratholes — named in advance

- **Trying to instrument all 54 sites.** It will balloon. Hold the line at five components.
- **Building the mechanism before the chaos tests**, then certifying it with itself. **That is
  the exact failure mode of the session that produced this spec.** It is the single most likely
  way this goes wrong.

## Success criteria

1. Every probe in the chaos suite **fails before the mechanism exists** (watched, not assumed).
2. Every probe **passes after**, i.e. breaking the component produces a `degraded` event AND
   surfaces at SessionStart.
3. `tessera-watch` P10 fires on any degraded event and is quiet otherwise.
4. The **spend guard on python 3.9** case is covered — it is the one that already failed open.
5. An **independent session** confirms the bar, not the session that built it.

## Depends on

- Nothing. The event channel, the watcher, and the SessionStart surface all already exist.

## Consequence for autonomy

ADR-0005 named three preconditions for unsupervised operation and all three were declared met on
2026-07-12. Two were then found broken by adversarial verification — **not by the framework.**
Until this spec ships, **any readiness claim Tessera makes about itself is unverifiable**, which
is the real reason autonomy is further off than ADR-0005 implies.
