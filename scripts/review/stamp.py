#!/usr/bin/env python3
"""Record what a code review actually saw, so "changed since" is answerable at push time.

WHY THIS EXISTS. conclave F-004: "the review gate covers the draft and never the fix." The edits
made in response to a review are the highest-risk part of a change — written under time pressure,
in areas already known to be delicate, by the author who got them wrong once — and in the common
sequence review -> fix -> commit -> push, nothing ever reviews them.

WHAT THE EVIDENCE ACTUALLY SUPPORTS, which is narrower than F-004 claims. Measured on the
2026-08-17 session: three review rounds, and rounds 1 and 2 WERE re-reviewed, because each round
targeted `origin/main..HEAD` — the accumulating unpushed range — rather than the working diff.
Only the LAST round's fixes escaped, and only because they were pushed. So the hole is the
TERMINAL fix, and the variable that creates it is the push, not the fixing.

WHY THIS IS NOT A BLOCKING GATE, deliberately, and against F-004's own suggested fix (1). "Your
most recent edits are unreviewed" is true by construction every time you stop, so a hook firing on
it detects the end of a session rather than a defect. This repo has already priced that lesson:
P13 has no acknowledgment state, fires on correct-but-spent conditions, and G-a fires on its
streak with no right answer available. A signal that is always true is one you learn to dismiss.
It also regresses — every re-review leaves its own fixes unreviewed — so there is no fixed point
to gate on.

WHAT IT DOES INSTEAD. Records the range a review covered; `.githooks/pre-push` reports the set
difference at the outward boundary. A set difference terminates where a recursion does not, and
the output is a fact ("3 files changed since the review saw them") for a human to dispose of.
Warn-only — the posture ADR-0012 already set for sqlfluff.

KNOWN GAP, found the day this shipped: a stamp records the range a review was TOLD to cover,
not the range the author meant. On 2026-08-17 `/code-review high 0b27332` was invoked meaning
"since that commit"; the skill read it as "that commit" and returned six findings, all correct and
all already fixed one commit later. Nothing here would have caught that — the stamp would have
faithfully recorded the wrong scope. It is the same certified-at/changed-since gap one level up:
the certifier's own scope is unverified. Cheap partial remedy if it recurs: have the reviewer
report the ref range it resolved, and compare that against the stamp.

KNOWN LIMITS — stated here because a narrowing that lives only in the source is standing
pattern #12, and this module's output is what anyone actually reads:

1. **Untracked files are never claimed as reviewed.** `git diff` does not report them, and
   sweeping them in with `ls-files --others` cannot tell a new module the reviewer read from a
   scratch file in the tree. The two error directions are not symmetrical —
   `changed_since_review` SUBTRACTS the stamped list, so over-claiming silently drops a real
   finding while under-claiming only costs a false positive in a warn-only hook. Prefer noise.
2. **A stamp records the range a review was TOLD to cover, not the range it actually read.**
   On 2026-08-17 `/code-review high 0b27332` was invoked meaning "since that commit"; the skill
   read it as "that commit". Nothing here would catch that — the stamp would faithfully record
   the wrong scope. `--head` narrows the gap between what was reviewed and what is recorded; it
   does not close the gap between what was asked for and what was read.
3. **Stamping rides model recall.** Measured 2026-08-17: 3 stamps against 47 session logs. That
   is why `pre-push` is silent when no stamp exists — absence of a stamp is absence of
   evidence, and a branch that fires on the majority of pushes is one people learn to dismiss.

Contract: `docs/contracts/review-stamp.md`.

Stdlib-only: imported by a git hook that runs without the venv.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
EVENT = "review_stamped"


def _log_path() -> Path:
    session = os.environ.get("CLAUDE_CODE_SESSION_ID", "manual")
    d = ROOT / ".tessera" / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{session}.jsonl"


def _git(*args: str) -> str:
    try:
        out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=15)
    except Exception:
        return ""
    return out.stdout.strip()


def _git_lines(*args: str) -> "list[str] | None":
    """Lines of stdout, or None when git FAILED — the distinction `_git` throws away.

    `_git` returns "" for both an empty answer and a broken command, and a caller that tests
    truthiness silently treats "git could not tell me" as "there is nothing". That is the
    fail-open shape this repo keeps paying for, and it bit the base-intersection below within a
    day of it being written (review, 2026-08-19)."""
    try:
        out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                             text=True, timeout=15)
    except Exception:
        return None
    if out.returncode != 0:
        return None
    return [line for line in out.stdout.strip().splitlines() if line]


def _git_ok(*args: str) -> bool:
    """True when the git command exits 0. `_git` returns stdout, which is empty for the
    predicates (`merge-base --is-ancestor`) whose whole answer is the exit code."""
    try:
        return subprocess.run(["git", *args], cwd=ROOT,
                              capture_output=True, timeout=15).returncode == 0
    except Exception:
        return False


def record(base: str = "origin/main", head: "str | None" = None) -> int:
    """Stamp the review's coverage: the commit it saw and the files in that range.

    `head` DEFAULTS TO HEAD AND MUST NOT BE FORCED TO IT. The documented workflow is "stamp
    after each review", but the real order is review -> fix -> commit -> stamp, and by then
    HEAD is the FIX. Hit live 2026-08-17: a review covering `cc5d2b3` was stamped as covering
    `5fb4dcb`, which no reviewer had seen — the anchor whose job is "what has no review looked
    at" recording the opposite, by default.

    Then three times in one session on 2026-08-19, which is what got this built: three review
    rounds on one branch, and not one of them could be stamped, because each round's fixes
    moved HEAD before there was anything to record. The reviews happened and the record of
    what they covered does not exist and cannot be reconstructed. `pre-push` on that branch
    reported its files as unreviewed against a stamp from the PREVIOUS session.

    An explicit head is a claim about the past, so it is verified: a ref that does not resolve
    is refused rather than stamped, for the same reason `_main` refuses an unresolvable base —
    `changed_since_review` will happily diff from whatever it is given, and a stamp against a
    phantom is worse than no stamp.

    `explicit` is recorded because the two cases are not equally trustworthy: a defaulted head
    means "whatever HEAD was when someone remembered", an explicit one means someone named the
    commit under review. A reader of the log can tell them apart; without the field they are
    identical rows.
    """
    if head is None:
        head = _git("rev-parse", "HEAD")
        explicit = False
    else:
        resolved = _git("rev-parse", "--verify", "--quiet", f"{head}^{{commit}}")
        if not resolved:
            print(f"head ref {head!r} does not resolve to a commit — refusing to stamp",
                  file=sys.stderr)
            return 2
        # AND IT MUST BE REACHABLE FROM HERE. A resolvable-but-unreachable sha — pasted from
        # another branch's review round, which the documented workflow ("copy the sha the review
        # saw") makes easy — is accepted by the check above, and then `changed_since_review`
        # hits its own ancestor guard and returns nothing. `latest()` keeps serving that stamp
        # by timestamp, so EVERY subsequent push is silent, and silent is indistinguishable from
        # "nothing changed since the review". Refused here for the same reason a phantom head is:
        # a stamp that cannot be reported against is worse than no stamp, and the failure is
        # quiet rather than loud. (Review, 2026-08-19.)
        if not _git_ok("merge-base", "--is-ancestor", resolved, "HEAD"):
            print(f"head {resolved[:12]} is not an ancestor of HEAD — refusing to stamp. "
                  f"A stamp off this line of history mutes pre-push silently.", file=sys.stderr)
            return 2
        head, explicit = resolved, True
    if not head:
        print("not a git repo, or no HEAD", file=sys.stderr)
        return 1
    files = [f for f in _git("diff", "--name-only", f"{base}...{head}").splitlines() if f]
    # THE WORKING TREE BELONGS TO *NOW*, NOT TO AN ARBITRARY PAST COMMIT. `record()` stores the
    # dirty diff because the review target is usually an uncommitted tree — true when stamping
    # HEAD, and false when stamping a commit from an hour ago, where today's uncommitted edits
    # were not in front of any reviewer. Including them would inflate the stamp's coverage,
    # which is the one direction that matters: `changed_since_review` SUBTRACTS the stamped
    # file list, so an over-claiming stamp silences real findings.
    # STAGED COUNTS AS UNCOMMITTED, and it did not until 2026-08-19. `git diff --name-only` is
    # UNSTAGED ONLY, so reviewing a tree that had been `git add`-ed — which is most of them,
    # since staging is how you decide what the review is about — recorded `had_uncommitted:
    # false` and an empty dirty list. Those files then reappeared in `changed_since_review` the
    # moment they were committed, as false positives, in the one branch whose whole job is
    # saying what no review has seen. Found by writing this module's first test; nothing else
    # would have, because the field it corrupts is only read one function away.
    # `checkpoint.py:_get_git_state` already read both, which is the usual shape of this repo's
    # defects: the correct version was next door.
    at_head = (not explicit) or head == _git("rev-parse", "HEAD")
    dirty = []
    if at_head:
        for args in (("diff", "--name-only"), ("diff", "--cached", "--name-only")):
            dirty += [f for f in _git(*args).splitlines() if f]
        dirty = sorted(set(dirty))
    event = {
        "type": EVENT,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "session_id": os.environ.get("CLAUDE_CODE_SESSION_ID", "manual"),
        "source": "review-stamp",
        "data": {"base": base, "head": head, "files": sorted(set(files + dirty)),
                 "uncommitted": dirty, "had_uncommitted": bool(dirty),
                 "explicit_head": explicit},
    }
    with _log_path().open("a") as fh:
        fh.write(json.dumps(event) + "\n")
    how = "explicit" if explicit else "HEAD"
    print(f"review stamped: {head[:12]} ({how}) over "
          f"{len(event['data']['files'])} file(s) vs {base}")
    return 0


def latest() -> "dict | None":
    """The newest stamp across all session logs. None when no review is on record."""
    best = None
    logs = ROOT / ".tessera" / "logs"
    if not logs.is_dir():
        return None
    for f in sorted(logs.glob("*.jsonl")):
        try:
            lines = f.read_text().splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("type") == EVENT and (best is None or e.get("ts", "") > best.get("ts", "")):
                best = e
    return best


def changed_since_review(base: str = "origin/main") -> "tuple[dict | None, list[str]]":
    """(stamp, files in the outgoing range that changed after the stamp's HEAD)."""
    stamp = latest()
    if stamp is None:
        return None, []
    head = stamp["data"]["head"]
    if not _git("cat-file", "-t", head):
        return stamp, []            # stamped commit is gone (rebase); nothing honest to say
    # A stamp whose commit is not an ANCESTOR of HEAD describes a different line of history —
    # stamp on a branch, switch, push, and `stamp_head..HEAD` enumerates everything since the
    # merge-base and calls it unreviewed. `cat-file` only catches a commit that is GONE.
    if not _git_ok("merge-base", "--is-ancestor", head, "HEAD"):
        return stamp, []
    changed = [f for f in _git("diff", "--name-only", f"{head}..HEAD").splitlines() if f]
    # `base` WAS AN UNUSED PARAMETER UNTIL 2026-08-19 (queue item 8c), and giving it a job is
    # what the explicit-head fix makes possible. `head..HEAD` is "everything since the review",
    # which over-reports the moment the stamped commit is behind the base ref — stamp, pull,
    # push, and every commit someone else already pushed is listed as unreviewed by you. The
    # question this hook asks is narrower: what is about to become PUBLIC that no review saw.
    # So intersect with the outgoing range. When the stamp is at or ahead of base this is a
    # no-op, which is the common case and why the defect was invisible.
    # `is not None`, NOT truthiness. An EMPTY outgoing range is a real answer — everything is
    # already public, so nothing is owed a review — and the correct report is nothing. Testing
    # truthiness skipped the filter in that case and fell back to the un-narrowed `head..HEAD`,
    # re-reporting commits that had already been pushed. Failure is the other branch and keeps
    # the wider report, because a filter that cannot be computed must not silently narrow.
    outgoing = _git_lines("diff", "--name-only", f"{base}...HEAD")
    if outgoing is not None:
        changed = [f for f in changed if f in set(outgoing)]
    # SUBTRACT ONLY THE UNCOMMITTED FILES, and this distinction is the whole feature.
    #
    # The subtraction exists for the primary path: review an UNCOMMITTED tree, stamp, commit
    # those exact files, push. Those files are in `head..HEAD` afterwards and the review did see
    # them, so reporting them is a guaranteed false positive. (Review, 2026-08-17.)
    #
    # But subtracting the WHOLE stamped list cancels `--head` for its dominant case. A fix made
    # in response to review findings almost always re-edits a file the review looked at — that
    # IS the terminal fix this mechanism exists to catch — and every such file is in
    # `base...reviewed`, so the wide subtraction filtered it out and `pre-push` said nothing.
    # Measured 2026-08-19: review touches a.py, stamp --head A, fix re-edits a.py, report is
    # EMPTY. The suite missed it because its fixture added a NEW file, which is the one shape
    # that survives. (Review round 1 on this branch.)
    #
    # Files already COMMITTED at stamp time cannot reappear in `head..HEAD` unless they were
    # edited again, which is precisely what is worth reporting. Only the dirty set can produce
    # the false positive, so only the dirty set is subtracted.
    #
    # `files` is the fallback for stamps written before `uncommitted` existed: those are all
    # defaulted-head rows, and the wide subtraction is what they were recorded under.
    data = stamp["data"]
    seen = set(data["uncommitted"]) if "uncommitted" in data else set(data.get("files", ()))
    return stamp, [f for f in changed if f not in seen]


def _main(argv: "list[str]") -> int:
    if any(a in ("-h", "--help") for a in argv):
        print("usage: stamp.py [BASE_REF] [--head SHA]   (default origin/main, HEAD)\n\n"
              "Records what a code review covered. Run AFTER a review completes.\n"
              "--head names the commit the review actually SAW. Use it whenever you have\n"
              "already committed the fixes: the normal order is review -> fix -> commit ->\n"
              "stamp, and by then HEAD is the fix, not what anyone reviewed.\n"
              "`.githooks/pre-push` reports what changed since.")
        return 0
    head = None
    rest = []
    it = iter(argv)
    for a in it:
        if a == "--head":
            head = next(it, None)
            if head is None:
                print("--head needs a value", file=sys.stderr)
                return 2
        elif a.startswith("--head="):
            head = a.split("=", 1)[1]
        elif not a.startswith("-"):
            rest.append(a)
    args = rest
    base = args[0] if args else "origin/main"
    # A base that does not resolve produced a stamp claiming coverage vs `--help` on the first
    # run. A stamp is a claim about SCOPE; a claim against a ref that does not exist is worse
    # than no claim, because `changed_since_review` will happily diff from it.
    if not _git("rev-parse", "--verify", "--quiet", base):
        print(f"base ref {base!r} does not resolve — refusing to stamp", file=sys.stderr)
        return 2
    return record(base, head)


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
