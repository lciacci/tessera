# Contract: review stamp

**Status:** live 2026-08-19 · **Decided by:** conclave F-004 (the finding), ADR-0012 (the
warn-only posture it borrows) · **Answers:** *what is about to become public that no review has
looked at?*

---

## The question

**conclave F-004: "the review gate covers the draft and never the fix."** The edits made in
response to a review are the highest-risk part of a change — written under time pressure, in
areas already known to be delicate, by the author who got them wrong once — and in the common
sequence review → fix → commit → push, nothing ever reviews them.

## What the evidence actually supports, which is narrower than F-004 claims

Measured on the 2026-08-17 session: three review rounds, and rounds 1 and 2 **were** re-reviewed,
because each round targeted `origin/main..HEAD` — the accumulating unpushed range — rather than
the working diff. Only the **last** round's fixes escaped, and only because they were pushed.

So the hole is the **terminal** fix, and the variable that creates it is **the push**, not the
fixing. That is why this rides `pre-push` and nothing else.

## Why it is not a gate

**"Your most recent edits are unreviewed" is true by construction every time you stop**, so a
hook firing on it detects the end of a session rather than a defect. It also regresses — every
re-review leaves its own fixes unreviewed — so there is no fixed point to gate on.

This repo has already priced that lesson: P13 fired on correct-but-spent conditions until
ADR-0027 gave it an acknowledgment, and G-a fires on its streak with no right answer available.
**A signal that is always true is one you learn to dismiss.** Warn-only, the posture ADR-0012 set
for sqlfluff.

## The two halves

| | Written by | Claims |
|---|---|---|
| `review_stamped` event | **you**, via `python3 scripts/review/stamp.py` | the commit a review saw, and the files in that range |
| the report | **`.githooks/pre-push`** | the set difference at the outward boundary |

A set difference terminates where a recursion does not, and the output is a fact — *"3 files
changed since the review saw them"* — for a human to dispose of.

## Stamping

```bash
# You reviewed the working tree and have not committed yet — the primary path.
python3 scripts/review/stamp.py

# You reviewed, then fixed, then committed. THIS IS THE COMMON CASE and the flag exists for it.
python3 scripts/review/stamp.py --head cc5d2b3

# A different base ref.
python3 scripts/review/stamp.py origin/release --head cc5d2b3
```

**`--head` names the commit the review actually SAW.** Without it, `record()` stamps
`rev-parse HEAD`, and by the time you remember to stamp, HEAD is the *fix*.

- **Hit live 2026-08-17:** a review covering `cc5d2b3` was stamped as covering `5fb4dcb`, which
  no reviewer had seen. The anchor whose job is *"what has no review looked at"* recorded the
  opposite, by default.
- **Then three times in one session on 2026-08-19**, which is what got the flag built: three
  review rounds on one branch, and **not one could be stamped**, because each round's fixes moved
  HEAD before there was anything to record. `pre-push` on that branch reported its files as
  unreviewed against a stamp from the *previous session*.

An explicit head is a claim about the past, so it is **verified**: a ref that does not resolve to
a commit is refused rather than stamped, `rc=2`, nothing written. `changed_since_review` will
happily diff from whatever it is given, and a stamp against a phantom is worse than no stamp.

`explicit_head` is recorded because the two cases are not equally trustworthy: a defaulted head
means *"whatever HEAD was when someone remembered"*, an explicit one means someone named the
commit under review. Without the field the log rows are identical.

## Reading the report

`pre-push` speaks only when it has something specific: **a review is on record AND HEAD has moved
past it.** Absence of a stamp is absence of evidence, and it does not report that — measured
2026-08-17, 3 stamps against 47 session logs, so warning on "no review recorded" would have fired
on the majority of pushes and taken the useful branch down with it.

`changed_since_review` narrows three ways, and each is load-bearing:

1. **Subtract what the stamp already saw.** The review target is usually an uncommitted tree, so
   the normal flow is review → stamp → commit those exact files → push. Diffing `head..HEAD`
   alone names files the review *did* see, which is a guaranteed false positive on the primary
   path.
2. **Intersect with the outgoing range** (`base...HEAD`). `head..HEAD` is "everything since the
   review", which over-reports the moment the stamped commit sits behind the base — stamp, pull,
   push, and every commit someone else already pushed is listed as unreviewed by you.
3. **Say nothing when the stamp is not an ancestor of HEAD.** Stamp on a branch, switch away,
   push, and `head..HEAD` would enumerate everything since the merge-base. `cat-file` only
   catches a commit that is *gone*, which is why the ancestor test is separate.

## Known limits — stated so they are not mistaken for coverage

1. **Untracked files are never claimed as reviewed.** `git diff` does not report them, and
   sweeping them in with `ls-files --others --exclude-standard` cannot distinguish a new module
   the reviewer read from a scratch file sitting in the tree. **The two error directions are not
   symmetrical:** the report subtracts the stamped list, so over-claiming silently drops a real
   finding while under-claiming costs a false positive in a warn-only hook. Prefer the noise.
   *(Staged files DO count — they did not until 2026-08-19, when writing this module's first
   test found that `record()` read only the unstaged diff.)*
2. **A stamp records the range a review was TOLD to cover, not the range it read.** On 2026-08-17
   `/code-review high 0b27332` was invoked meaning "since that commit"; the skill read it as
   "that commit" and returned six findings, all correct and all already fixed one commit later.
   Nothing here would catch that — the stamp would faithfully record the wrong scope. `--head`
   narrows the gap between what was *reviewed* and what is *recorded*; it does not touch the gap
   between what was *asked for* and what was *read*. Cheap partial remedy if it recurs: have the
   reviewer report the ref range it resolved, and compare against the stamp.
3. **Stamping rides model recall** — principle #17's known exposure, accepted here because the
   failure mode is a missing stamp (silence) rather than a wrong one. There is no Stop-hook
   backstop and building one would re-create the always-true signal this contract rejects.

## Relationship to the re-review rule

`CLAUDE.md` carries the convention — *after applying review findings, re-review before
committing*. **That rule is the model-side half and this contract is the framework half**, and
they are deliberately not the same mechanism: the rule shapes how a session works, the stamp
records what happened so the push can report a fact.

conclave wrote the finding on 2026-08-15 and recommended building nothing yet; Tessera then hit
the same pattern on 08-17 and built a mechanism a day after conclave had decided not to. **That
is conclave F-002's "no peer channel" defect scoring the framework itself**, and it is recorded
here rather than smoothed over. What survives from conclave's argument is the standard it set:
*a rule documented and SKIPPED is what licenses automating it — you cannot skip a rule nobody
wrote.*
