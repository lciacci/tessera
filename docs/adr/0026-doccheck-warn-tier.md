# ADR-0026: doccheck gains a warn tier — a gate cannot enforce a fact it cannot see

- **Date:** 2026-08-18
- **Status:** Accepted
- **Decision driver:** Human disposition. Queue item 9 asked for a posture, not for work. Lorenzo's instruction: *"do the warn tier in doccheck, I just wanted a way to know if I needed to update the html page."* The gate had been built to coerce an action when the ask was for a signal.
- **Executed:** 2026-08-18 — `scripts/doccheck.py` (`WARN_ONLY`, `_split`, `_render_warnings`, `check_warn_tier_membership_is_declared`, `render`, `main`), `.githooks/pre-commit`, `bin/tessera-watch` (`p8_doc_drift`), `scripts/test_doccheck.py`, `docs/contracts/doc-claims.md`, `CLAUDE.md`.

---

## The contradiction

Two checks written in the same commit range held opposite postures for the same class of fact.

`promo-deploy-marker-is-current` **blocked** every commit touching `docs/promo/index.html`
until a human uploaded the page to a foreign host and ran `--stamp-deploy`. ADR-0012 adopted
sqlfluff **warn-only** for exactly the class the promo check is in — unverifiable,
human-dependent — on the reasoning that *a gate that only cries wolf gets bypassed, and then it
protects nothing.* doccheck had no warn tier, so the promo check took the only posture available
to it rather than the one its own nature called for.

**An inconsistency introduced by accident should not be resolved by accident.** Hence a record.

## What made it more than a style disagreement

Two measured facts, neither of which was in the framing of the problem.

**1. The two promo checks COMPOSE into a standing tax on ordinary work.**
`promo-adr-timeline-is-complete` requires every ADR on disk to have a row on the promo timeline.
So writing an ADR forces an edit to `docs/promo/index.html`; that edit changes the body hash;
the deploy marker then refuses the ADR commit. **11 of the 15 commits that have ever touched
that page are ADR commits.** The gate was not sitting on a promo-publishing act — it was sitting
on the critical path of the repo's own decision record, and the only escapes were `--no-verify`
(which drops all 53 checks) or a false stamp.

**2. Blocking coerced nothing a warning would not.**
The check's own docstring says it: nothing here reaches the host, so the marker records a
**claim**. The block is dischargeable by `--stamp-deploy` alone, with no upload. Blocking
therefore does not buy enforcement — it buys friction, and it makes the false stamp the cheapest
path under time pressure. That is the `restore_injected` shape the docstring itself names: a
party marking its own homework. The honest goal was always the narrower one the docstring
states — *make forgetting loud* — and that is a signal's job.

## Decision

**`doccheck.WARN_ONLY` is a third posture: report, do not block.** `{check name: why it cannot
honestly block}` — a dict and not a set, so the reason is structurally required.

### 1. The admission bar, which is the whole safeguard

A check belongs in the tier only when **this repo cannot verify the fact it asserts**, so
blocking buys no enforcement. A check whose subject is checkable in-repo does not qualify,
however annoying its red is.

This is stated as a bar and enforced as one because standing pattern #6 — *green is only
meaningful if failing it actually stops something* — is the argument **against** this ADR, and
it is a good argument. A warn tier is where reds go to die. The bar is what keeps it from
becoming the place to put any check somebody is tired of seeing, and
`warn-tier-membership-is-declared` asserts every entry names a live check and carries a reason.

**`promo-adr-timeline-is-complete` stays blocking, deliberately.** It asserts something
checkable in-repo, its remedy is an edit, and it is the half that actually caught the published
page being 13 decisions behind. Splitting the two is the point: the in-repo half keeps its teeth.

### 2. Warnings print on the GREEN path

The pre-commit hook printed nothing at all on exit 0. A warn tier under that hook would have
run, reported, and reached nobody — standing pattern #9 built fresh. The hook now emits the
warning section on success, matched against `render()`'s header string so a renamed check cannot
silence it, and a test asserts the two files agree on that string.

### 3. A warn-tier check that CRASHES still blocks

The tier is about a claim this repo cannot verify, not about a check being allowed to break.
ADR-0022 is untouched, and `main()` reads the partition through one splitter (`_split`) shared
with `render()` — three copies of `name in WARN_ONLY` is how a tier ends up applied in the report
and not in the exit code.

### 4. `tessera-watch` P8 stays silent on warnings — a narrowing, said out loud

Left alone, P8 would have flattened every warn-tier finding into `violations`: session start goes
red and the message calls it a *false doc claim*, which is the wrong label (#12) and half-undoes
this decision. P8 now excludes them, read through `getattr(doccheck, "WARN_ONLY", ())` so the six
downstream copies that predate the tier are not turned into crashed predicates (#5).

**The consequence is a real reduction in coverage and is written here rather than left implicit:
the warn tier's only channel is the pre-commit hook.** That is defensible because the hook fires
while you are editing the file — the highest-attention moment — and re-fires on every commit
while the marker is stale. It is not defensible by silence.

## Verification

Re-planted **in** the code under test, not beside it (#10), and measured in both directions on
one identical stale tree:

| Probe | Result |
|---|---|
| Stale marker, **pre-change** doccheck (`git show HEAD:` copy) | exit **1** — blocks |
| Stale marker, post-change doccheck | exit **0**, `🟡 1 warning(s) — reported, not blocking` |
| Stale marker, real `git commit` | **commit succeeded**, warning on stderr |
| Stale marker **+** a planted `referenced-paths-exist` violation | hook exit **1**, `COMMIT BLOCKED` headline correct, warning rendered alongside |
| `WARN_ONLY` key typo'd to a non-existent check | exit 1 — `warn-tier-membership-is-declared` fires |
| `WARN_ONLY` reason blanked | exit 1 — `warn-tier-membership-is-declared` fires |
| P8 with the marker stale | `fired: False` — quiet, as decided |
| P8 with the tier emptied (an older downstream's shape) | `fired: True`, *"1 false doc claim"* — the exclusion is load-bearing |

## Re-evaluate when

- **A second check is proposed for the tier.** One member is not a tier, it is an exception with
  machinery. If the second candidate does not clear the admission bar on its own terms, the
  honest answer is that this should have been a special case.
- **The tier is ever used to clear a red rather than to describe a fact.** That is the failure
  mode this ADR is betting against, and it will look like a reasonable one-line diff.
- **The promo page stays stale for more than a session or two.** That is the evidence that the
  commit-time channel is too weak and P8 (or a watch predicate) has to carry it after all.
