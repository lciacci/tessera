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

An explicit head is a claim about the past, so it is **verified** — two ways, both `rc=2` with
nothing written. A ref that does not resolve **to a commit** is refused; `changed_since_review`
will happily diff from whatever it is given, and a stamp against a phantom is worse than no
stamp. A commit that is **not an ancestor of HEAD** is refused too: it is resolvable, so the
first check passes, and then the report's own ancestor guard returns nothing forever while
`latest()` keeps serving that stamp by timestamp. Silence is indistinguishable from "nothing
changed since the review", and a sha pasted from another branch's review round is the easy way
in — which "copy the sha the review saw" makes likely.

**An explicit head is a claim about a COMMIT, not about the tree on top of it**, so it never
captures uncommitted work: `uncommitted` is empty on every explicit stamp. The first version
keyed on "is the named commit HEAD", which comes apart in the documented workflow — the fix is
uncommitted for a window, stamping during it is natural, and the fix was then recorded as
reviewed. Nothing is lost: a reviewer of an uncommitted tree runs `stamp.py` with no flag.

A mistyped flag is refused rather than absorbed. `stamp.py --haed <sha>` used to drop the unknown
token and let the sha fall through as the positional BASE, writing an rc=0 stamp against a
phantom base — routing around the very check `_main` performs on the base. **Extra positionals
are refused for the same reason** (`stamp.py origin/main <sha>` silently dropped the sha), and a
bare-hex base with no `--head` gets a loud note rather than a refusal: `stamp.py <sha>` reads as
"base = that sha, head = HEAD", which is the fix stamped as reviewed, and the two intentions are
indistinguishable from argv alone.

**A base that is the branch you are ON is refused** — keyed on which REF it is, not which commit
it points at today. The first version compared `rev-parse base` with `rev-parse HEAD`, which
**blocked the documented primary path**: branch off a synced `main`, review the uncommitted tree,
run bare `stamp.py`, and `origin/main` equals HEAD, so it refused to stamp at all. The premise
holds only for refs that advance with the local branch. **Reflog-relative bases (`@{-1}`,
`HEAD@{1}`) are refused too** — a comment claimed the HEAD-anchored pattern covered them and it
never did.

*(Superseded phrasing, kept because the narrowing matters:)* **A base that resolves to HEAD** — the spelling check below
was one keystroke from useless. On branch `main`, `stamp.py main --head <sha>` makes the outgoing
range `main...HEAD`, empty forever, so the report is filtered to nothing on every push and
nothing reports it stale. Not exotic: `bin/tessera-new-project` scaffolds into a repo made by
bare `git init` with no remote, so `origin/main` does not resolve there and naming the current
branch is the obvious workaround.

**A HEAD-anchored base is refused.** `head` is resolved to a sha because a stamp records history;
`base` is deliberately kept as a *ref* so `origin/main` keeps tracking as others push. That is
right for symbolic refs and wrong for HEAD-relative ones. Measured: `--head <R>` with
`base=HEAD~1` re-resolves at push time to the *fix* commit, so the unreviewed fix is subtracted;
`base=HEAD` makes the outgoing range `HEAD...HEAD`, empty forever, so the hook goes permanently
silent while nothing reports it stale.

**`had_uncommitted` is absent on an explicit stamp, not `false`.** `dirty` is never computed
there, so `false` would assert something about a working tree the code did not look at.

`explicit_head` is recorded because the two cases are not equally trustworthy: a defaulted head
means *"whatever HEAD was when someone remembered"*, an explicit one means someone named the
commit under review. Without the field the log rows are identical.

## Reading the report

**The stamp used is the newest one that is an ANCESTOR of HEAD**, not the newest one written.
`latest()` returned the newest anywhere, so a stamp taken on another branch shadowed a usable
one: stamp `feature-a`, later stamp `feature-b`, return to `feature-a`, commit the terminal fix —
empty report, and the hook claiming to be blind while a good stamp for that line sat right there.
The same defect produced the inverse noise on any unrelated branch. `latest_usable()` picks the
newest ancestor, and when there is none the fall-through is the deliberate no-stamp silence.

`pre-push` speaks only when it has something specific: **a review is on record AND HEAD has moved
past it.** Absence of a stamp is absence of evidence, and it does not report that — measured
2026-08-17, 3 stamps against 47 session logs, so warning on "no review recorded" would have fired
on the majority of pushes and taken the useful branch down with it.

`changed_since_review` narrows four ways, and each is load-bearing:

1. **Subtract the stamp's `uncommitted` list — ONLY that, and only while its CONTENT is
   unchanged.** The review target is often an
   uncommitted tree, so the normal flow is review → stamp → commit those exact files → push, and
   those files would otherwise be a guaranteed false positive.
   **It subtracted the whole `files` list until 2026-08-19, which cancelled `--head` for its
   dominant case:** a fix made in response to review findings almost always re-edits a file the
   review looked at, every such file is in `base...reviewed`, so the terminal fix was filtered
   out and the report went silent. Files already *committed* at stamp time cannot reappear in
   `head..HEAD` unless edited again — which is exactly what is worth reporting. Legacy rows
   written before the `uncommitted` field keep the wide subtraction they were recorded under —
   decided by the FIELD's presence, never by a missing entry. Inside a pinned stamp an entry
   with no pin means "we could not establish what was reviewed", and the rule for that is prefer
   the noise. A **deleted** file is the common case (`hash-object` cannot pin one), and reading
   it as legacy bought permanent silence: reviewed deletion, committed, then re-added with
   entirely unreviewed content, never reported on any push.
   **The subtraction is BLOB-PINNED**, and unpinned it was permanent: each dirty file's content
   hash is recorded, and the file is subtracted only while HEAD still holds what the reviewer
   saw. Measured 2026-08-19 — a file dirty at stamp time stayed subtracted after being re-edited
   twice, so F-004's terminal fix went unreported on this, the primary path. Round 1 fixed that
   shape for `files` and left it live here; the explicit-head test could not see it.
2. **Intersect with the outgoing range** (`base...HEAD`). `head..HEAD` is "everything since the
   review", which over-reports the moment the stamped commit sits behind the base — stamp, pull,
   push, and every commit someone else already pushed is listed as unreviewed by you.
3. **Say nothing when the stamp is not an ancestor of HEAD — but say SO loudly.** Stamp on a
   branch, switch away, push, and `head..HEAD` would enumerate everything since the merge-base.
   `cat-file` only catches a commit that is *gone*, which is why the ancestor test is separate.
   **An empty report had three causes and one voice until 2026-08-19** — nothing changed, the
   commit is gone, HEAD moved off its line — so "you are clear" and "I am blind" printed
   identically. An `--amend` or a rebase after stamping produces the second permanently, because
   `latest()` keeps serving that stamp. `staleness_note()` names it and `pre-push` prints a
   one-line **review anchor is blind** note — **and that branch was DEAD CODE for one commit.**
   `staleness_note` returns None whenever a usable stamp exists, so the note is reachable only
   when `changed_since_review` found nothing usable; testing `st is None` first swallowed every
   case. Two fixes that individually made sense cancelled the feature between them. The hook's
   branch ORDER is now the thing under test, by a test that runs the hook. Still not blocking, and **bounded to 7 days**: a
   stale stamp is never replaced on its own, so an unbounded note is true on every push forever
   — P13's shape, on the same channel as the useful report, in the hook whose header rejects
   always-true signals. A recent orphaned stamp is news; an old one is indistinguishable from no
   stamp, which this hook is already silent about.
   **A failed diff RAISES** rather than returning an empty list, onto `pre-push`'s existing
   "review-anchor check unavailable" channel. The first fix returned `[]`, which is the same
   silence one layer in — caught by re-planting it and finding no test could tell the
   difference.
4. **Report against the base the STAMP was recorded under**, not the caller's default. `pre-push`
   always passes `origin/main`; a stamp taken against `origin/release` would otherwise be
   reported against an unrelated outgoing range.

## Known limits — stated so they are not mistaken for coverage

1. **Untracked files are never claimed as reviewed.** `git diff` does not report them, and
   sweeping them in with `ls-files --others --exclude-standard` cannot distinguish a new module
   the reviewer read from a scratch file sitting in the tree. **The two error directions are not
   symmetrical:** the report subtracts the stamp's `uncommitted` list, so over-claiming silently
   drops a real finding while under-claiming costs a false positive in a warn-only hook. Prefer
   the noise.
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
