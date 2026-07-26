# Spec 11: Fail-open detection — make Tessera report its own failure

**Status:** pending as a systematic build — **but its thesis got its first live confirmation and
first partial delivery on 2026-07-20** (spec 16 / PR #38): the Stop-hook ingest pipe failed open
with no trace for 3 days and read as clean data. The remedy shipped there is this spec's pattern
applied to one pipe: a per-run trace (`claude_sessions.classifier_status`) + a loud watcher
(`tessera-watch` P11, including the transcripts-vs-store diff that catches crash-before-write —
the shape no status column can see). The systematic sweep across the OTHER fail-open paths
(hooks, spend guard, gate scan, escalations) remains this spec's open scope.

**Third confirmation, 2026-07-21 (`49b4bbc`) — and it landed in the adversarial verifier itself.**
`bin/tessera-verify`'s `spawn_verifier` did `return result.stdout`, discarding returncode and
stderr; a spawn that never ran returned `""` and rendered as `NO_VERDICT`. Worse,
`scripts/verify/scan.py` counted *any* `verification` event as a disposition — so **a verifier
that never executed silenced the Stop-hook backstop built to catch unverified "it's fixed"
claims.** Found by accident (two claims came back `NO_VERDICT` with no explanation), not by any
detector. Fixed at three layers, plus `raw_excerpt` so an unparseable answer is diagnosable.
*The distinction this spec turns on, again: a spawn failure is "I could not do my job", and it
was being treated as "nothing to do."* Three live instances in eight days — F-001's interpreter,
the dead ingest pipe, and now the falsifier — **every one found by accident.** That is the case
for sweeping deliberately instead of waiting for the fourth.
**STEP 1 IS DONE — the chaos suite exists and the RED baseline is WATCHED, 2026-07-26.**
`chaos/test_chaos.py`, run by `bin/tessera-chaos` (top-level `chaos/`, not `scripts/chaos/` —
run-tests.sh's top-level run is `pytest scripts/`, which would collect these deliberately-red
probes and fail the main suite, while `--ignore`ing them would collide with
`ignored-test-suites-are-run`; outside `scripts/` neither check has to be weakened. Deliberately
outside `tessera-test`;
kept reachable by doccheck `chaos-suite-is-reachable`). Eight probes over all five components,
each scaffolding a REAL downstream with `tessera-new-project` and driving the hook through its
actual stdin/exit-code contract — not a hand-built model of the harness (pattern #9). **Observed,
not assumed:**

```
FAILED  probe_1  corrupt guard.py            → rc=1, spend ALLOWED
FAILED  probe_2  guard.py deleted            → rc=0, EMPTY stderr, spend ALLOWED
FAILED  probe_4  backstop hook chmod -x      → rc=0, silent skip
FAILED  probe_5  jq removed from PATH        → rc=0, gate-scan cannot scan
FAILED  probe_6  gate scan.py deleted        → rc=0, EMPTY stderr, backstop is a no-op
FAILED  probe_7  mnemos unreachable          → rc=0, unmanaged fallback SUCCEEDED
FAILED  probe_8  typo'd wired hook path      → rc=0, hook has never run
passed  probe_3  spend guard on python 3.9   → rc=2, correctly DENIES
7 failed, 1 passed
```

Three findings from writing it, all of which change what step 2 has to do:

1. **Criterion 4's case no longer reproduces — the 3.9 open-failure is FIXED.** On the real
   `/usr/bin/python3` (3.9.6, not a stub) the guard denies correctly; `from __future__ import
   annotations` held. Probe 3 is retained as the regression guard for a bug that already cost
   real spend. A suite that only proves what is broken cannot show when something un-breaks.
2. **The live spend fail-opens are the OTHER bail-outs**, and two are worse than the original:
   a corrupt guard exits 1 and a *deleted* guard exits 0 with empty stderr — and only rc=2
   blocks, so both ALLOW the spend. The deleted case is indistinguishable from "this command
   needed no guarding."
3. **A probe skipped silently and hid a whole component.** Probe 7 targeted a mnemos hook, but
   the default `global` distribution ships no local mnemos copies, so it `skip`ped — component
   4 of 5 uncovered while the run still read as fine. Fixed by scaffolding `--frozen`. *The
   fail-open suite's first fail-open was its own.*

~~**Step 2 (the mechanism) is deliberately NOT built here**~~ — success criterion 5 wants an
independent session to confirm the bar, and the session that builds a detector is the worst
judge of it.

**STEP 2 IS DONE — all 8 probes GREEN, 2026-07-26, and by a different session than the one that
wrote them** (criterion 5 satisfied: the probe author did not build the mechanism).

```
8 passed          ← was 7 failed, 1 passed
```

Folded into `scripts/run-tests.sh` as the `chaos` suite, per the ordering above. What shipped:

- **`bin/tessera-degraded`** — appends a `degraded` event to the session-log channel.
  **POSIX sh, shell builtins only — no jq, sed, grep, awk or python.** It reports on broken
  infrastructure so it may not assume working infrastructure: a hook bailing because `python3`
  is gone cannot use python3 to say so, and one bailing because `jq` is gone cannot use jq to
  read its own stdin. JSON is parsed with parameter expansion; `date` and `mkdir` are optional
  and degrade to a blank `ts` / an existing dir, because probe 5 hides both on purpose.
  Contract: `docs/contracts/degraded-event.md`.
- **`tessera-watch` P13** — fires on any degraded event **in a 7-day window**. Windowed
  deliberately: a degraded event is an *incident*, not a standing state, and the same week this
  shipped, iCPG's drift backlog was found at 700 undisposed rows precisely because nothing could
  ever leave its open set. Windowing means P13 needs no disposition verb to stay honest.
- **~31 bail-outs classified** across four components — loud for jq/scanner/guard/backstop
  missing, no python3, unreachable cwd, `guard.py` exiting a non-verdict code, and the mnemos
  toolchain being unreachable so the checkpoint takes the unmanaged inline fallback (F-001's
  shape: a silent *success*). Quiet for no stdin, `stop_hook_active`, and no `.mnemos/`.
  The spend guard's exit code is passed through unchanged — reporting must never alter the
  allow/deny contract.

**Probes 4 and 8 needed the PROBE fixed first, and that is the finding worth keeping.**
`run_wired` **synthesized** its own command string — `f'if [ -x "{path}" ]; then exec ...; fi;
exit 0'` — hardcoding the fail-open `exit 0` into the test. So the two probes asserted against a
hand-built replica of the wired form, and **no change to the shipped `settings.json` could ever
turn them green**; probe 8 even edited `settings.json` and never read it back. That is this
spec's own pattern #9 ("only the real path proves the real path") violated one layer inside the
suite written to enforce it. Corrected to read the project's real `settings.json`, then —
**critically — the corrected probes were confirmed STILL RED before any settings change**, so the
fix was not certified by a detector edited to accept it. Only then were the three local-only
wired commands given an else-branch that reports `hook-unavailable`.

**Known blind spot, named not buried:** the log is keyed by `session_id`, so a bail-out that
happens *because there is no session id* has no file to write into. Recorded in the contract.

**Still open:** downstream rollout (§4 below) — the fleet has neither `tessera-degraded` nor the
new wired form. `bin/tessera-new-project` ships both to NEW projects; existing ones need
`tessera-sync-harness`. **Plus one hole found by the criterion-5 re-read (2026-07-26): the
two-tier ADR-0004 mnemos commands are excluded from reporting, and under the default `global`
distribution — where no local copy is ever shipped — that leaves every mnemos hook fail-silent
downstream.** Details and the verified one-line fix under success criterion 5.

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
- **`tessera-watch` P13** — fires on any `degraded` event. ~15 lines. The SessionStart surface
  already prints watcher output, so surfacing is free. *(Was written as "P10" — that number was
  taken by the haziness-band trigger, which fired and was retired on 2026-07-20, and P11/P12
  have since landed. Next free number is P13. Corrected 2026-07-22.)*

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

*(All five MET for the framework repo, 2026-07-26. Downstream rollout — §4 — remains open.)*

1. ✅ Every probe in the chaos suite **fails before the mechanism exists** (watched, not assumed).
   *Watched twice: 7-RED at the start of the step-2 session, and again for probes 4/8 after
   `run_wired` was corrected but before the settings change.*
2. ✅ Every probe **passes after**, i.e. breaking the component produces a `degraded` event AND
   surfaces at SessionStart.
3. ✅ `tessera-watch` **P13** fires on any degraded event and is quiet otherwise. *(Was written
   "P10" here while §2 already said P13 — corrected 2026-07-26. P10 was the haziness-band
   trigger, fired and retired 2026-07-20; P11/P12 have since landed.)* *Verified three ways:
   fires on a real event, quiet with no log, and ages out past the 7-day window.*
4. ✅ The **spend guard on python 3.9** case is covered — it is the one that already failed open.
   *Probe 3, retained as a regression guard; it was already passing and still does.*
5. ✅ An **independent session** confirms the bar, not the session that built it. *Step 1 (probes)
   and step 2 (mechanism) were built by different sessions. Note the honest limit: the step-2
   session also **corrected `run_wired`**, so for probes 4 and 8 the probe author and mechanism
   author are the same. Mitigated by confirming the corrected probes RED before the fix — but a
   third session re-reading that correction would be worth more than this note.*
   **A third session did that re-read, 2026-07-26 — verdict: the `run_wired` correction was
   LEGITIMATE, not a weakening. Recorded below.**

### Criterion 5, third-session re-read (2026-07-26)

The gap: `41ad037` corrected `run_wired` *and* shipped the mechanism, so for probes 4 and 8 the
probe author and the mechanism author were the same session. An independent session re-read it.

**The check that settles it — run, not reasoned about.** Revert the *template* (the artifact the
probes scaffold from; reverting `.claude/settings.json` would make it pass trivially) to its
pre-`41ad037` state and run the suite:

```
git checkout 41ad037~1 -- templates/tessera/settings.base.json
bin/tessera-chaos     → 2 failed, 6 passed
                        FAILED probe_4  chmod -x backstop     → rc=0, no degraded event
                        FAILED probe_8  typo'd wired path     → rc=0, no degraded event
git checkout HEAD  -- templates/tessera/settings.base.json
bin/tessera-chaos     → 8 passed
```

Probes 4 and 8 go RED on the old command string and green on the new one; the other six are
unmoved. **The corrected probes still detect exactly the failure they claim to.** A weakened
probe would have stayed green against the reverted template — that is the discriminating
outcome, and it did not happen.

Three independent judgments, each falsified rather than argued:

1. **Real path or replica?** `run_wired` reads the toy's own `.claude/settings.json`, which
   `tessera-new-project` `cp`s verbatim from `templates/tessera/settings.base.json` — the shipped
   downstream artifact, byte for byte, not a second definition. Confirmed by the revert: editing
   the template alone changes the probe's verdict, which is only possible if the probe reads it.
   *Residual, minor:* it runs `commands[0]`, so if a script were ever wired more than once only
   the first copy is exercised; and the framework repo's own `.claude/settings.json` is a
   separate file no probe drives (doccheck's `unrunnable-hooks-report-themselves` covers both,
   so it is checked, just not by the chaos suite).
2. **Can a probe pass while testing nothing?** No. Falsified three ways: calling `run_wired` with
   a name no command references raises the `setup wrong — the probe would be testing nothing`
   assertion (reachable, not decorative); deleting the toy's `scripts/tessera-degraded` — the
   scaffold ships the reporter *there*, not in `bin/` — sends probe 4 back to RED, so the green
   is *earned* by the reporter, not by the harness; and the emitted event names the right
   component and reason (`spend-backstop` / `hook-unavailable`, and for the two hook-internal
   probes `gate-scan/scanner-missing`, `mnemos-checkpoint/toolchain-unreachable`).
   *Two residuals, both narrow.* `assert_reported` accepts **any** degraded event rather than the
   expected component/reason — sound today only because each probe gets a fresh tmp toy and
   drives exactly one command; asserting the reason would make it sound by construction. And the
   not-vacuous guard is a **substring** test, not a reference check: `run_wired(toy, "")` matches
   every command, so the assert stays silent and it runs whichever hook comes first. Unreachable
   from the shipped probes, since each passes a literal script name.
3. **`needs_reporting()`'s scope rule — SECOND HOLE FOUND. See below.**

**FINDING (open): the two-tier ADR-0004 hooks are excluded, and for the default distribution
that exclusion is backwards.**

`needs_reporting` returns `None` for any command containing `$HOME/.claude/templates`, on the
stated grounds that *"a missing local file resolves through the global copy and the hook still
runs."* That premise holds only while the global copy exists — and under the **default `global`
distribution the local copy is deliberately never shipped**, so the fallback is not a redundancy,
it is the *only* tier. Observed on a real scaffold:

```
toy scaffolded default → local .claude/scripts/mnemos-stop-checkpoint.sh: ABSENT (by design)
run the wired command with an empty $HOME
  → rc=0, stdout '', stderr '', degraded events: []
```

Every mnemos hook in every downstream silently no-ops and nothing says so. That is component 4 of
this spec's own five ("Mnemos hooks — checkpoints lost"), F-001's exact shape, one tier up from
the tess-dashboard typo the module was written for. The fixer and doccheck's detector share the
predicate, so **both are blind to it together** — the consistency guard worked as designed and
propagated the gap.

It is a genuine hole, not a tradeoff: dropping *only* the `GLOBAL_FALLBACK` exclusion (nothing
else — the two-tier command already ends `fi; exit 0`, and `_ANCHORED` matches exactly one
distinct script because the `$HOME` path is unanchored) produces a correct branch, verified both
directions — reports `mnemos-stop-checkpoint / hook-unavailable` when both tiers are gone, and
stays **silent** when the global tier is present (a real global copy still `exec`s and no event
is written). Not fixed here: this session was scoped to judging the correction, and the fix
belongs with the downstream rollout below.

**It is a one-line predicate change but NOT a one-line fix** — recorded so the next session does
not discover it mid-flight. Because the predicate is *shared*, widening it immediately makes
doccheck's `unrunnable-hooks-report-themselves` flag the 7 two-tier commands in
`templates/tessera/settings.base.json`, and flips
`scripts/hooks/test_report_settings.py::test_global_fallback_command_is_out_of_scope` to RED —
that test encodes the very rule being retired. The full change is therefore: drop the exclusion,
run the fixer over the shipped settings, retire/invert that unit test, and roll the new command
bodies to the fleet. The detector going red *first* is correct behaviour, not collateral: it is
the check finding real fail-silent hooks the moment it is allowed to see them.

*Checked and NOT a hole:* `tessera-verify-scan.sh` is excluded by the `_TRAILING_EXIT` shape
guard, but it already ends `echo 'VERIFY-SCAN BROKEN…' >&2; exit 2` — loud by hand. Correct
outcome; note the predicate reaches it by accident (unrecognised shape) rather than by knowing
it is loud.

## Depends on

- Nothing. The event channel, the watcher, and the SessionStart surface all already exist.

## Consequence for autonomy

ADR-0005 named three preconditions for unsupervised operation and all three were declared met on
2026-07-12. Two were then found broken by adversarial verification — **not by the framework.**
Until this spec ships, **any readiness claim Tessera makes about itself is unverifiable**, which
is the real reason autonomy is further off than ADR-0005 implies.
