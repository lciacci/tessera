# Contract: doc claims

**Status:** active (2026-07-11)
**Implementation:** `scripts/doccheck.py` · surfaced by `bin/tessera-watch` P8 · tests in `scripts/test_doccheck.py`

## The problem

Between 2026-07-09 and 2026-07-11, six doc-drift bugs were found in Tessera. All six were
found the same way: **Lorenzo got suspicious and asked "all docs updated?"** All six were
fixed by hand, and none left a check behind — so the next one was found by suspicion too.

The human was the detector. That is a principle **#17** failure one level up: #17 says
anything whose value depends on being *seen* must ride a non-model channel. Here the
**verification itself** rode on recall — the model's, when updating; the human's, when
auditing.

And it degrades in the worst possible direction. Suspicion is a depleting resource: **the
better the framework gets, the less it gets questioned, so drift accumulates fastest exactly
when trust is highest.** Trust is the failure mode. The check must be mechanical *because*
Tessera is earning enough confidence for the human to stop being the check.

The lesson was already known and already written down — and that is the damning part.
`docs/design-principles.md` recorded it in prose on 2026-07-09:

> *"Lesson: when a doc claims N layers, `ls` all N."*

The `ls` was never built. Drift then recurred five more times. **A prose lesson is precisely
the thing #17 says does not work**, and it failed here on the very doc that defines #17.

## What is checked

Not "docs agree with code" — that is unbounded and AI-complete. The narrow, tractable class
that covers all six real bugs: **a doc asserts something checkable about the repo, and
nothing checks it.**

| Check | Bug it regresses |
|---|---|
| `referenced-paths-exist` — **the formal `ls`.** Every repo path named in a doc's inline code exists on disk. | Docs named `mnemos-compact-recovery.sh` — a script that did not exist — across three docs for ~6 weeks. |
| `adr-index-complete` — every ADR on disk is listed in `docs/adr/README.md`. | ADR 0005 was written and never indexed. |
| `compaction-threshold-qualified` — any doc stating the Mnemos trial threshold says the events are **non-manual**. | 3 docs stated "≥3 `compaction_fired`" after trigger-tagging landed, inviting hand-run tests to deliver the trial's verdict. |
| `gate-recording-not-recall` — if the gate-scan Stop hook is wired, no doc may still claim gate recording rides model recall. | `gate-event.md` understated its own guarantee for days, telling readers to distrust a working channel. |

## Scope — and why the exclusions ARE the design

A first cut checked every `.md` and produced **98 violations, ~95% false**. That is not a
tuning problem, it is a category error: four doc classes make **no claim about current disk
state**, and checking them is meaningless.

| Excluded | Why |
|---|---|
| `_project_specs/` | Specs describe work **not yet built**. Naming an absent file is the *point*. |
| `.claude/skills/` | Generic instructions for **downstream** projects ("create a TDD-loop check script *in your project*"), not claims about Tessera. |
| `CHANGELOG.md` | Historical. It correctly names files that were later deleted. |
| `docs/adr/` | Immutable record. An ADR describes the world **as it was**. |

**A checker that cries wolf gets ignored, and an ignored checker is worse than none — it
looks like coverage.** Precision over recall, deliberately. `doccheck.py` carries two
exemption sets, and every entry states its reason:

- `PATH_ALLOWLIST` — runtime-created paths, other repos' files (the observatory *evaluates*
  GSD, it does not contain it), and claims about downstream projects.
- `PLANNED_PATHS` — **designed in docs, never built.** Kept separate from the allowlist so
  the debt stays legible rather than silently forgiven. `design-principles.md` describes
  `.tessera/config.yml` and `.tessera/third-party-scope.yml` in the *present tense* and
  neither exists; a reader (or a future Claude) goes looking for a file that was never
  written. Either build them or reword to the conditional.

## Where it is enforced — two channels, because one was not enough

| Channel | When | Effect |
|---|---|---|
| **`.githooks/pre-commit`** | every `git commit`, by human or agent | **blocks the commit** |
| **`tessera-watch` P8** | session start | surfaces existing red |

The pre-commit gate exists because P8 alone was not enough. On 2026-07-11, commit `8589280`
was pushed **with doccheck red**: the verify command was chained with `&&`, doccheck's exit 1
short-circuited it, and the `git commit` on the next line ran anyway. The checker worked
perfectly and **nothing was listening.** Red could be pushed and discovered a session later —
by which point it is in the history.

> **Green is only meaningful if failing it actually stops something.**

Two design points, both learned the hard way the same day:

- **The hook lives in `.githooks/`, not `.git/hooks/`.** `.git/hooks/` is **not tracked** — a
  hook installed there exists on one disk and nowhere else, so a fresh clone silently gets no
  gate. `install.sh` points git at the tracked directory (`core.hooksPath`) **and `verify()`
  asserts it stayed pointed**, because a gate that is present but unwired is the worst state
  of all: it looks like coverage and enforces nothing. `test_git_is_actually_pointed_at_the_tracked_hooks`
  guards the same thing from the test suite.
- **It fails open on CATASTROPHIC failure, closed on a violation AND on a crashed check.**
  *(Amended 2026-08-10; this clause previously read "fails open on a crash" without
  qualification, and that stopped being true the day `run()` gained per-check isolation.)*
  The distinction is what broke: `run()` used to be a bare dict comprehension, so one raising
  check took the process down and **0 of 45 reported**. Each check is now isolated, so a crash
  is *named, localised, and beside 44 working results* — which makes it an ordinary blocking
  finding, printed in its own section so the headline never calls a broken check a false doc
  claim. **Only whole-run failure still fails open** — this module unparseable, `render()`
  raising, a traceback carrying no recognisable verdict. That is the case "must not wedge every
  commit" was actually written for, and the consequence is worth stating plainly rather than
  hiding behind "fails open": **in that state the hook prints a warning and lets every commit
  through**, so the gate is bypassed exactly when the checker is most broken. It prints loudly
  either way, because a silent checker is indistinguishable from a passing one.

Bypass with `git commit --no-verify`. It is a gate, not a jail — but the bypass is now a
decision you make on purpose, which is the entire point of a suggestion-gate (principle #12).

### The warn tier — checks that report and do not block (ADR-0026, 2026-08-18)

`doccheck.WARN_ONLY` is `{check name: why it cannot honestly block}`. Its findings render in
their own section (`N warning(s) — reported, not blocking:`), do not affect the exit status,
and **print on the green path too** — the pre-commit hook used to print nothing at all on
exit 0, which would have made the tier a mechanism that ran and reached nobody.

**The admission bar is narrow and it is the whole safeguard:** a check belongs here only when
*this repo cannot verify the fact it asserts*, so blocking buys no enforcement — only friction.
A check whose subject is checkable in-repo does **not** qualify, however annoying its red is.
`warn-tier-membership-is-declared` asserts every entry names a live check and states a reason;
the reason is required structurally (a dict, not a set) because a tier whose entries need no
justification is just a list of checks somebody wanted to stop seeing.

Two boundaries worth stating, because both were decided rather than inherited:

- **A warn-tier check that CRASHES still blocks.** The tier is about a claim this repo cannot
  verify, not about a check being allowed to break. ADR-0022 is untouched.
- **`tessera-watch` P8 stays silent on warnings.** P8 reports claims the repo can *verify* are
  false; left alone it would have filed a warning under "false doc claim", which is the wrong
  label. That is a real narrowing of P8's coverage and it is stated here rather than implied:
  **the warn tier's only channel is the pre-commit hook**, which fires while you are editing
  the file — not a session later.

| Member | Why it cannot block |
|---|---|
| `promo-deploy-marker-is-current` | the upload is off-repo and by hand; nothing here reaches the host |

**Known limit:** doccheck reads the **working tree**, not the index. On a partial commit
(staged subset + dirty tree) it judges content that is not exactly what you are committing.
Accepted deliberately — nearly every commit here is `git add -A`, and fixing it properly needs
a temp checkout of the index. Revisit if a partial commit ever slips something through.

## The standing rule

**Every doc-drift bug a human finds becomes an assertion in `doccheck.py` and a regression
test in `test_doccheck.py`.**

This is the base skill's bug-fix workflow (write the failing test *before* the fix), applied
to docs — a workflow we followed zero times out of six. Fixing the instance and not the class
is what created the loop.

The rule is also how we learn the checker has rotted into theater: **if a human finds a
doc-drift bug that no check covers, that is a finding about `doccheck.py`, not just the doc.**
A checker whose assertion count stops growing while bugs keep appearing is decoration.

## Known limits

- Covers maybe **60–70%** of the drift class. Prose claims that are not mechanically
  checkable still need reading. The point is not total coverage — it is to spend the human's
  suspicion on the hard 30% instead of on things a grep catches.
- Assertions are string- and path-shaped. A doc reworded around a check will silently detach.
  Mitigation is the standing rule, not cleverness: the next human-found bug re-anchors it.
- Fails **open**. If `doccheck` raises, P8 reports "unavailable" and does not block.
