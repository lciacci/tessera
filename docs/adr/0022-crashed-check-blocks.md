# ADR-0022: A crashed doccheck check blocks the commit — isolation changes what "fails open" should mean

- **Date:** 2026-08-10
- **Status:** Accepted
- **Decision driver:** `scripts/doccheck.py`'s `run()` was a one-line dict comprehension, so any check that raised took the whole process down and **0 of 46 reported**. One new check hit that three times in a row in a single session — an unguarded `read_text()`, then an `exists()`-only guard (a directory and `chmod 000` both exist and raise), then an `OSError`-only guard (`UnicodeDecodeError` subclasses `ValueError`) — each fix committed under a comment claiming the *class* was handled.
- **Executed:** 2026-08-10 — `scripts/doccheck.py` (`run_detailed`, `run`, `render`, `main`), `.githooks/pre-commit`, `bin/tessera-watch` (`p8_doc_drift`), `scripts/test_doccheck.py`, `scripts/test_tessera_watch.py`, `docs/contracts/doc-claims.md`, `CLAUDE.md`. Verified end-to-end against a planted broken check through all three consumers, and each of the three pre-commit paths (crash-only, false-claim-only, both) exercised separately.

---

## The question

Per-check isolation is uncontroversial: a checker whose 46th check can silence the other 45 is
not a checker. The contested half is what the **commit gate** should then do.

`.githooks/pre-commit` carried a written rule — *"A crashing checker must not wedge every commit
in the repo"* — and honoured it by treating any unrecognised output as "could not run" and
exiting 0. Isolation does not merely interact with that rule; it **invalidates the reasoning
behind it**, because the failure it was written for no longer exists in the same form.

## Decision

**A crashed check is a blocking finding. Only whole-run failure fails open.**

### 1. `run()` isolates each check, and crashes travel on their own channel

`run_detailed()` returns `{name: (findings, exception_or_None)}`. `run()` stays as a flattening
wrapper for callers that only ask "is anything wrong".

A marker string in the findings list (`"check crashed: …"`) was **rejected**: every consumer
would then re-derive the classification by substring, which is the naming-convention keying
standing pattern #10's corollary exists about. The distinction is structural or it is not
reliable.

### 2. A crashed check blocks — this reverses the pre-commit's written rule

The old rule was authored when a crash killed the **whole run**, leaving nothing to report and
nothing to act on; wedging every commit on that would have been indefensible. After isolation the
same event is *named, localised, and sitting beside 45 working results*. That is an ordinary
defect with an owner, and `--no-verify` remains the documented escape.

**Stated as a reversal rather than a clarification, deliberately.** The rule was written down, it
was reasoned, and it is now overridden — recording that as a smooth continuation would hide the
fact that a decision changed.

### 3. Catastrophic failure still fails open, and the consequence is named

An unparseable `doccheck.py`, an exception in `render()`, or a traceback carrying no recognisable
verdict still allows the commit with a warning. That is the case the original rule was really
for.

**The consequence is written plainly in the contract rather than left inside the phrase "fails
open": in that state the hook lets every commit through, so the gate is bypassed exactly when the
checker is most broken.** A hedge broad enough to absorb its own worst case is standing pattern
#12's second instance, and this one is stated so it cannot become a ceiling by accident.

### 4. `render()` prints crashes in their own section

Folding them into the violation count would make the headline — *"docs make N claims that are no
longer true"* — itself an untrue claim about what happened. The pre-commit headline branches
three ways for the same reason, including the both-at-once case.

### 5. P8 reports a crashed check as **fired**, not **crashed**

`crashed` in `tessera-watch.evaluate()` means *this predicate could not run*. A check body raising
is something P8 successfully **determined**, and naming the culprit is strictly more informative
than the pre-isolation behaviour, which lost all other results and could not say which check
failed. P8 reaches the new channel through `getattr`, because this file also runs against
downstream copies of `doccheck.py` that predate isolation.

## Consequences

- One broken check now stops every commit until fixed. Accepted: it is named, localised, and
  `--no-verify` exists. The pre-isolation alternative was worse and quieter.
- The gate is *more* blocking than before in the common case and *equally* permissive in the
  catastrophic one — an intentional asymmetry, now documented in `docs/contracts/doc-claims.md`.
- Adding a check is a new opportunity to break the gate. Isolation makes that a named finding
  instead of a blackout, which is the point.
- **Two silent regressions this would have caused, both caught before shipping, both from the
  same cause — the existing readers keyed on the old channel.** P8's loud path was *built on*
  `run()` raising, so isolation alone would have downgraded every crash to an ordinary fire; and
  the pre-commit grep keyed on `"claim(s) that are no longer true"`, so crashes printing their own
  section would have sailed straight through the gate this ADR exists to close. **When you add a
  channel, enumerate who reads the old one.**

## Alternatives considered

- **Keep fail-open for crashes; rely on P8 at SessionStart.** Rejected: P8 fires once per session,
  so a broken check could persist across many commits, and the gate that blocks is the one that
  makes green mean something (principle: *green is only meaningful if failing it actually stops
  something*).
- **Warn on first crash, block on recurrence.** Rejected: it adds persisted state the gate does not
  currently have, and a stateful gate reasons badly on a fresh clone — a path this repo has already
  been bitten by twice in one week.
- **Isolate and SKIP crashed checks silently.** Rejected outright, and it is the tempting one: it
  converts a crash into a silence, which is strictly worse than the crash and is this repo's
  signature failure mode.
- **Fix the exception types at each call site instead of isolating.** That is what the three
  consecutive row-fixes were. A check's author can always miss one more exception type; the fourth
  was `UnicodeDecodeError`, found by an adversarial pass, not by the author.

## Re-evaluate triggers

- **A legitimately-crashing check wedges work repeatedly.** If `--no-verify` starts appearing in
  commit messages, the blocking half is mispriced and the recurrence design deserves a second look.
- **A catastrophic failure reaches `main`.** The fail-open branch is deliberate but untested in
  anger; if a wholly-broken doccheck ever ships green, the trade needs re-pricing rather than
  re-explaining.
- **A downstream project's `doccheck.py` diverges far enough that P8's `getattr` fallback goes
  stale.** The fallback assumes older copies have `run()`; if the downstream API moves again, that
  assumption is the thing that breaks quietly.
