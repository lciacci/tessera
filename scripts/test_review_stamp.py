"""First tests for scripts/review/stamp.py. Run: pytest scripts/test_review_stamp.py

THE MODULE HAD NONE UNTIL 2026-08-19, which is worth stating rather than quietly fixing: it is
the record of what a code review covered, `.githooks/pre-push` is its only consumer, and both
shipped unguarded. The defect that motivated these tests — `record()` stamping `rev-parse HEAD`
regardless of what the review saw — is not subtle and would have been caught by any test that
asked "what does this record when HEAD has moved".

Real git repos in tmp_path, not mocks. `record` and `changed_since_review` are almost entirely
`git` invocations; mocking them would test the mock. `stamp.ROOT` is the single seam — every
`_git` call and `_log_path()` resolve through it — so pointing it at a scratch repo redirects
the module wholesale.
"""
import json
import subprocess
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

import pytest

_path = Path(__file__).resolve().parent / "review" / "stamp.py"
_loader = SourceFileLoader("review_stamp", str(_path))
_spec = spec_from_loader(_loader.name, _loader)
stamp = module_from_spec(_spec)
_loader.exec_module(stamp)


def _run(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True).stdout.strip()


def _repo(tmp_path, monkeypatch):
    """A scratch repo with a `main` branch and an `origin/main` ref to diff against.

    `origin/main` is a plain local ref, not a remote: `changed_since_review` only ever reads it
    with `git diff`, so a real remote would buy nothing and cost network."""
    repo = tmp_path / "r"
    repo.mkdir()
    for cmd in (("init", "-q", "-b", "main"), ("config", "user.email", "t@t"),
                ("config", "user.name", "t")):
        _run(repo, *cmd)
    # `.tessera/` IS GITIGNORED HERE BECAUSE IT IS GITIGNORED IN THE REAL REPO. `record()`
    # writes its log under ROOT, which is this scratch repo, so without this every `git add -A`
    # commits the stamp log and it shows up in `changed_since_review` as a phantom finding.
    # A fixture that does not mirror the ignore rules of the thing it stands in for produces
    # failures that look like defects — two of these tests failed that way first.
    (repo / ".gitignore").write_text(".tessera/\n")
    (repo / "seed.txt").write_text("seed\n")
    _run(repo, "add", "-A")
    _run(repo, "commit", "-qm", "seed")
    _run(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    monkeypatch.setattr(stamp, "ROOT", repo)
    return repo


def _commit(repo, name, body="x\n"):
    (repo / name).write_text(body)
    _run(repo, "add", "-A")
    _run(repo, "commit", "-qm", name)
    return _run(repo, "rev-parse", "HEAD")


def _events(repo):
    logs = repo / ".tessera" / "logs"
    out = []
    for f in sorted(logs.glob("*.jsonl")):
        out += [json.loads(line) for line in f.read_text().splitlines() if line]
    return out


# ── record(): what commit does a stamp claim? ──────────────────────────────────────────────

def test_record_defaults_to_head_and_says_so(tmp_path, monkeypatch):
    repo = _repo(tmp_path, monkeypatch)
    sha = _commit(repo, "a.py")
    assert stamp.record() == 0
    ev = _events(repo)[-1]
    assert ev["data"]["head"] == sha
    assert ev["data"]["explicit_head"] is False, (
        "a defaulted head means 'whatever HEAD was when someone remembered'; without the flag "
        "it is indistinguishable in the log from a named one")


def test_record_stamps_the_commit_a_review_actually_saw(tmp_path, monkeypatch):
    """THE DEFECT, in one test. Review covers `a.py`, the fix lands as `b.py`, THEN the stamp
    runs — the real order. Without --head the stamp claims the fix commit, which no reviewer
    saw, and `changed_since_review` then reports nothing outstanding."""
    repo = _repo(tmp_path, monkeypatch)
    reviewed = _commit(repo, "a.py")
    fix = _commit(repo, "b.py")
    assert reviewed != fix

    assert stamp.record(head=reviewed) == 0
    ev = _events(repo)[-1]
    assert ev["data"]["head"] == reviewed
    assert ev["data"]["explicit_head"] is True
    assert ev["data"]["files"] == ["a.py"], "the stamp must list what the review saw, not the fix"

    st, changed = stamp.changed_since_review()
    assert changed == ["b.py"], "the fix commit is exactly what no review has looked at"


def test_record_without_head_hides_the_fix_it_should_report(tmp_path, monkeypatch):
    """The counterfactual, asserted rather than described — this is what the old code did on
    every run, and it is why the flag exists. Kept as a live test so the defect cannot return
    quietly: if `record()` ever goes back to forcing HEAD, the test above starts failing and
    this one keeps passing, which is the pair that identifies the regression."""
    repo = _repo(tmp_path, monkeypatch)
    _commit(repo, "a.py")
    _commit(repo, "b.py")
    assert stamp.record() == 0
    _, changed = stamp.changed_since_review()
    assert changed == [], "stamping HEAD after the fix reports the fix as reviewed"


@pytest.mark.parametrize("bad", ["deadbeef", "no-such-branch", ""])
def test_record_refuses_a_head_that_does_not_resolve(tmp_path, monkeypatch, bad):
    """A stamp is a claim about SCOPE. `changed_since_review` will diff from whatever it is
    handed, so a stamp against a phantom is worse than no stamp — the same reasoning `_main`
    already applied to an unresolvable base."""
    repo = _repo(tmp_path, monkeypatch)
    _commit(repo, "a.py")
    assert stamp.record(head=bad) == 2
    assert _events(repo) == [], "a refused stamp must write nothing at all"


def test_record_refuses_a_tree_ish_that_is_not_a_commit(tmp_path, monkeypatch):
    """`rev-parse --verify` alone accepts a tree or a blob. `HEAD^{commit}` is what makes the
    check mean 'names a commit' rather than 'names an object'."""
    repo = _repo(tmp_path, monkeypatch)
    _commit(repo, "a.py")
    tree = _run(repo, "rev-parse", "HEAD^{tree}")
    assert stamp.record(head=tree) == 2
    assert _events(repo) == []


# ── record(): the working tree belongs to now ──────────────────────────────────────────────

def test_explicit_past_head_does_not_absorb_todays_uncommitted_edits(tmp_path, monkeypatch):
    """An over-claiming stamp is the dangerous direction: `changed_since_review` SUBTRACTS the
    stamped file list, so a file wrongly listed as reviewed is silently dropped from the
    report. Today's dirty tree was in front of no reviewer of an hour-old commit."""
    repo = _repo(tmp_path, monkeypatch)
    reviewed = _commit(repo, "a.py")
    _commit(repo, "b.py")
    (repo / "dirty.py").write_text("uncommitted\n")
    _run(repo, "add", "-A")

    assert stamp.record(head=reviewed) == 0
    ev = _events(repo)[-1]
    assert "dirty.py" not in ev["data"]["files"]
    assert "had_uncommitted" not in ev["data"], (
        "OMITTED, not False: `dirty` is never computed on the explicit path, so False would "
        "assert a fact about a working tree the code did not look at — indistinguishable in "
        "the log from 'the tree was clean'. This module exists because `restore_injected` was "
        "a log line the hook wrote about itself")


def test_an_explicit_head_never_absorbs_the_working_tree(tmp_path, monkeypatch):
    """PREMISE REVERSED 2026-08-19, and the original was a real defect.

    This test used to assert the opposite — that naming HEAD explicitly should behave exactly
    like defaulting to it, "otherwise the flag punishes being precise". Wrong, and the way it
    is wrong is the whole feature: **an explicit head is a claim about a COMMIT, not about the
    tree sitting on top of it.**

    The documented order is review -> fix -> commit -> stamp, and the fix is UNCOMMITTED for a
    window. Stamping during that window with `--head <reviewed-sha>` — precise, documented
    usage — recorded the fix as `uncommitted`, `changed_since_review` subtracted it, and
    pre-push went silent about the exact edit this mechanism exists to catch. Probed before
    fixing. Nothing is lost by the narrowing: a reviewer of an uncommitted tree runs
    `stamp.py` with no flag, which is what the default is for.

    Falsify by restoring `at_head = (not explicit) or head == _git("rev-parse", "HEAD")`."""
    repo = _repo(tmp_path, monkeypatch)
    head = _commit(repo, "a.py", "v1 — reviewed\n")
    (repo / "a.py").write_text("v2 — the fix, not yet committed\n")
    _run(repo, "add", "-A")

    assert stamp.record(head=head) == 0
    ev = _events(repo)[-1]
    assert ev["data"]["uncommitted"] == [], "an explicit stamp covers a commit, not a tree"
    assert "had_uncommitted" not in ev["data"]

    _run(repo, "commit", "-qm", "the terminal fix")
    _, changed = stamp.changed_since_review()
    assert changed == ["a.py"], "the fix must survive to the report"


def test_a_staged_tree_counts_as_uncommitted(tmp_path, monkeypatch):
    """FOUND BY WRITING THIS SUITE, not by review. `record()` read `git diff --name-only`,
    which reports UNSTAGED changes only — so reviewing a tree that had been `git add`-ed
    recorded `had_uncommitted: false` and an empty dirty list, and those files came back as
    false positives in `changed_since_review` as soon as they were committed.

    Staging is how you decide what a review is ABOUT, so this is the normal case, not an edge
    one. A MODIFIED tracked file is asserted alongside the staged one because they come from
    two different git commands and a fix covering only one would look correct.

    Falsify by dropping the `--cached` pass in `record()`."""
    repo = _repo(tmp_path, monkeypatch)
    _commit(repo, "a.py", "orig\n")
    (repo / "staged.py").write_text("staged\n")
    _run(repo, "add", "staged.py")
    (repo / "a.py").write_text("modified\n")          # tracked, unstaged

    assert stamp.record() == 0
    ev = _events(repo)[-1]
    assert "staged.py" in ev["data"]["files"], "a `git add`-ed file was in front of the reviewer"
    assert "a.py" in ev["data"]["files"], "an unstaged modification is still uncommitted"
    assert ev["data"]["had_uncommitted"] is True


def test_untracked_files_are_NOT_claimed_as_reviewed(tmp_path, monkeypatch):
    """A DELIBERATE LIMIT, asserted so it is a decision rather than an oversight.

    `git diff` never reports untracked files, so a brand-new uncommitted file is absent from
    the stamp even if a reviewer read it — and it will therefore show up as "changed since the
    review saw it" once committed. That is a false positive in a warn-only hook.

    Sweeping them in with `ls-files --others --exclude-standard` was considered and REJECTED:
    it cannot distinguish a new module the reviewer read from a scratch file sitting in the
    tree, so it would claim coverage nobody gave. The two error directions are not
    symmetrical — `changed_since_review` SUBTRACTS the stamped list, so over-claiming silently
    drops a real finding while under-claiming costs noise. Prefer the noise.

    Found by writing this suite: the first version of the staged test asserted an untracked
    file would be recorded, and it was wrong about the code AND about what the code should do."""
    repo = _repo(tmp_path, monkeypatch)
    _commit(repo, "a.py")
    (repo / "brand-new.py").write_text("new\n")

    assert stamp.record() == 0
    ev = _events(repo)[-1]
    assert "brand-new.py" not in ev["data"]["files"]


# ── changed_since_review(): `base` earned its keep ─────────────────────────────────────────

def test_changed_since_review_ignores_commits_already_on_the_base_ref(tmp_path, monkeypatch):
    """QUEUE ITEM 8c. `base` was an unused parameter, so the diff was `head..HEAD` — everything
    since the review — which over-reports the moment the stamped commit sits behind the base.
    Stamp, then fetch someone else's work into the base, and their files are listed as
    unreviewed by you.

    This hook asks what is about to become PUBLIC that no review saw, so the answer must be
    intersected with the outgoing range. Falsify by deleting the `outgoing` filter in
    `changed_since_review`: `theirs.py` reappears."""
    repo = _repo(tmp_path, monkeypatch)
    reviewed = _commit(repo, "mine.py")
    assert stamp.record(head=reviewed) == 0

    # Someone else's commit lands on the base ref, and locally on top of the stamp.
    theirs = _commit(repo, "theirs.py")
    _run(repo, "update-ref", "refs/remotes/origin/main", theirs)
    _commit(repo, "mine2.py")

    _, changed = stamp.changed_since_review()
    assert changed == ["mine2.py"], (
        "theirs.py is on the base ref — it is not what this push makes public")


def test_changed_since_review_subtracts_what_the_stamp_already_saw(tmp_path, monkeypatch):
    """Pre-existing behaviour, guarded because the `base` change is the first edit to this
    function since it was written and an unguarded neighbour is where the next defect lands.
    The primary workflow reviews an uncommitted tree, so those files appear in BOTH the stamp
    and the later `head..HEAD` diff — a guaranteed false positive if not subtracted."""
    repo = _repo(tmp_path, monkeypatch)
    _commit(repo, "a.py")
    (repo / "wip.py").write_text("wip\n")
    _run(repo, "add", "-A")
    assert stamp.record() == 0
    _run(repo, "commit", "-qm", "the reviewed tree")

    _, changed = stamp.changed_since_review()
    assert changed == [], "committing exactly what was reviewed leaves nothing outstanding"


def test_a_fix_that_RE_EDITS_a_reviewed_file_is_reported(tmp_path, monkeypatch):
    """THE DOMINANT CASE, and `--head` was inert for it until 2026-08-19.

    A fix made in response to review findings almost always re-edits a file the review looked
    at — that IS the terminal fix this mechanism exists to catch. `changed_since_review`
    subtracted the WHOLE stamped file list, and every such file is in `base...reviewed`, so it
    was filtered out and `pre-push` said nothing.

    The suite missed it because `test_record_stamps_the_commit_a_review_actually_saw` fixes a
    NEW file (`b.py`), which is the one shape that survives the wide subtraction. Guard written
    for the shape that does not.

    Falsify by widening `seen` back to `data["files"]`."""
    repo = _repo(tmp_path, monkeypatch)
    _commit(repo, "a.py", "v1 — what the review read\n")
    reviewed = _run(repo, "rev-parse", "HEAD")
    assert stamp.record(head=reviewed) == 0

    _commit(repo, "a.py", "v2 — the fix nobody has reviewed\n")
    _, changed = stamp.changed_since_review()
    assert changed == ["a.py"], (
        "re-editing a reviewed file is the terminal fix, not something the review covered")


def test_a_pre_uncommitted_field_stamp_still_subtracts_its_whole_file_list(tmp_path, monkeypatch):
    """Backward compatibility, and it is not decoration: every stamp written before 2026-08-19
    lacks `uncommitted` and was recorded under the wide subtraction. Reading those rows under
    the new narrow rule would surface files their review genuinely saw."""
    repo = _repo(tmp_path, monkeypatch)
    _commit(repo, "a.py")
    assert stamp.record() == 0

    logs = repo / ".tessera" / "logs"
    log = next(iter(logs.glob("*.jsonl")))
    ev = json.loads(log.read_text().splitlines()[-1])
    del ev["data"]["uncommitted"]                      # a stamp from before the field existed
    ev["data"]["files"] = ["a.py"]
    log.write_text(json.dumps(ev) + "\n")

    _commit(repo, "a.py", "changed later\n")
    _, changed = stamp.changed_since_review()
    assert changed == [], "legacy rows keep the semantics they were written under"


def test_an_empty_outgoing_range_reports_nothing(tmp_path, monkeypatch):
    """`if outgoing:` conflated "nothing is outgoing" with "git could not answer", so an empty
    range SKIPPED the filter and fell back to the un-narrowed `head..HEAD` — re-reporting
    commits that were already public. Empty is a real answer and its report is empty.

    Falsify by changing `if outgoing is not None:` back to `if outgoing:`."""
    repo = _repo(tmp_path, monkeypatch)
    reviewed = _commit(repo, "a.py")
    assert stamp.record(head=reviewed) == 0
    pushed = _commit(repo, "b.py")
    _run(repo, "update-ref", "refs/remotes/origin/main", pushed)   # it is now public

    _, changed = stamp.changed_since_review()
    assert changed == [], "nothing is outgoing, so nothing is owed a review"


def test_a_base_git_cannot_resolve_keeps_the_WIDER_report(tmp_path, monkeypatch):
    """`_git_lines` exists only to tell "git failed" from "the answer is empty", and nothing
    exercised the failure branch — re-planting `returncode != 0` away left all 22 green.

    The direction matters and is the point of the helper: a filter that CANNOT be computed must
    not silently narrow the report. Swallowing the failure as an empty list would make the
    intersection drop everything, and this hook going quiet is indistinguishable from it having
    nothing to say.

    Falsify by making `_git_lines` return `[]` instead of `None` on a non-zero exit."""
    repo = _repo(tmp_path, monkeypatch)
    reviewed = _commit(repo, "a.py")
    assert stamp.record(head=reviewed) == 0
    _commit(repo, "b.py")

    _, changed = stamp.changed_since_review(base="no-such-base-ref")
    assert changed == ["b.py"], (
        "git could not compute the outgoing range, so the report must stay wide rather than "
        "quietly empty")


def test_record_refuses_a_head_that_is_not_an_ancestor_of_HEAD(tmp_path, monkeypatch):
    """A resolvable-but-unreachable sha — pasted from another branch's review round, which the
    documented "copy the sha the review saw" workflow makes easy — used to be accepted. Then
    `changed_since_review` hit its ancestor guard and returned nothing, and `latest()` kept
    serving that stamp by timestamp, so EVERY later push was silent. Silent is
    indistinguishable from "nothing changed since the review"."""
    repo = _repo(tmp_path, monkeypatch)
    _run(repo, "checkout", "-q", "-b", "other")
    elsewhere = _commit(repo, "other.py")
    _run(repo, "checkout", "-q", "main")
    _commit(repo, "main.py")

    assert stamp.record(head=elsewhere) == 2
    assert _events(repo) == [], "a stamp that cannot be reported against must not be written"


def test_changed_since_review_is_silent_when_no_review_is_on_record(tmp_path, monkeypatch):
    repo = _repo(tmp_path, monkeypatch)
    _commit(repo, "a.py")
    st, changed = stamp.changed_since_review()
    assert st is None and changed == []


def test_changed_since_review_says_nothing_when_the_stamped_commit_is_not_an_ancestor(
        tmp_path, monkeypatch):
    """Stamp on a branch, switch away, push: `stamp_head..HEAD` would enumerate everything
    since the merge-base and call it unreviewed. `cat-file` only catches a commit that is GONE,
    which is why the ancestor test exists separately."""
    repo = _repo(tmp_path, monkeypatch)
    _run(repo, "checkout", "-q", "-b", "side")
    side = _commit(repo, "side.py")
    assert stamp.record(head=side) == 0
    _run(repo, "checkout", "-q", "main")
    _commit(repo, "main.py")

    # `latest_usable()` skips it entirely now, so the report falls through to the deliberate
    # no-stamp silence rather than returning a stamp it cannot use. `latest()` still sees it,
    # which is what `staleness_note` reads. (Round 4.)
    st, changed = stamp.changed_since_review()
    assert st is None and changed == []
    assert stamp.latest() is not None


def test_pre_push_is_told_when_the_stamp_is_off_this_line_of_history(tmp_path, monkeypatch):
    """AN EMPTY REPORT HAD THREE CAUSES AND ONE VOICE. `changed_since_review` returns [] when
    nothing changed, when the stamped commit is gone, and when HEAD has moved off its line —
    and `pre-push` printed nothing for all three, so "you are clear" and "I am blind" were the
    same output. An `--amend` or a rebase after stamping produces the second PERMANENTLY,
    because `latest()` keeps serving that stamp by timestamp and stamping rides recall.

    The record-time guard covers stamp time only; this covers HEAD leaving afterwards.

    Falsify by making `staleness_note` return None unconditionally."""
    repo = _repo(tmp_path, monkeypatch)
    reviewed = _commit(repo, "a.py")
    assert stamp.record(head=reviewed) == 0
    assert stamp.staleness_note(stamp.latest()) is None, "a healthy stamp is not stale"

    _run(repo, "commit", "-q", "--amend", "-m", "amended out from under the stamp")
    _commit(repo, "c.py")
    _, changed = stamp.changed_since_review()
    assert changed == []
    note = stamp.staleness_note(stamp.latest())
    assert note is not None and "BLIND" in note, (
        "silence here is indistinguishable from 'nothing changed since the review'")


def test_the_report_uses_the_base_the_stamp_was_recorded_under(tmp_path, monkeypatch):
    """`pre-push` always calls `changed_since_review()` with the default `origin/main`, while
    `record()` stores the base actually used and the contract documents
    `stamp.py origin/release --head <sha>`. Reporting a release-line stamp against main's
    outgoing range drops files whose HEAD content matches main's merge-base.

    Falsify by using the `base` parameter instead of `stamp['data']['base']`."""
    repo = _repo(tmp_path, monkeypatch)
    _run(repo, "update-ref", "refs/remotes/origin/release", "HEAD")   # release stays at seed
    reviewed = _commit(repo, "a.py")
    assert stamp.record(base="origin/release", head=reviewed) == 0
    _commit(repo, "b.py")
    # main is level with HEAD, so NOTHING is outgoing relative to main — the two bases now
    # disagree, which is what makes this a discriminating test. Against the stamp's own base
    # (release, still at seed) both files are outgoing; against main, neither is.
    _run(repo, "update-ref", "refs/remotes/origin/main", "HEAD")

    _, changed = stamp.changed_since_review()          # caller's default is origin/main
    assert changed == ["b.py"], (
        "the stamp was taken against origin/release; reporting it against main's outgoing "
        "range drops the finding entirely")


def test_record_refuses_a_base_with_no_merge_base(tmp_path, monkeypatch):
    """`git diff base...head` exits non-zero when the two have no common ancestor, and the
    fail-open `_git` returned "" — so the stamp was written with `files: []`, recording "git
    could not tell me" as "there is nothing". The same shape `_git_lines` was added for, left
    on the old helper one function away in the same diff."""
    repo = _repo(tmp_path, monkeypatch)
    _commit(repo, "a.py")
    _run(repo, "checkout", "-q", "--orphan", "orphan")
    _run(repo, "commit", "-q", "--allow-empty", "-m", "unrelated history")
    orphan = _run(repo, "rev-parse", "HEAD")
    _run(repo, "checkout", "-q", "main")

    assert stamp.record(base=orphan) == 2
    assert _events(repo) == []


def test_a_dirty_file_stops_being_subtracted_once_its_content_changes(tmp_path, monkeypatch):
    """ROUND 1'S DEFECT, STILL LIVE ON THE PRIMARY PATH until round 3.

    The dirty set is subtracted so that committing the reviewed tree unchanged is not a false
    positive. Unpinned, that subtraction is PERMANENT: probed 2026-08-19, a file dirty at stamp
    time stayed subtracted after being re-edited twice, so F-004's terminal fix went unreported
    on the path the contract calls primary. `test_a_fix_that_RE_EDITS_a_reviewed_file_is_reported`
    only covers the explicit-head path and could not see it.

    The blob hash is the discriminator — subtract while HEAD holds what the reviewer saw, report
    the moment it differs. Falsify by dropping `uncommitted_blobs` from `record()`."""
    repo = _repo(tmp_path, monkeypatch)
    _commit(repo, "a.py", "v0\n")
    (repo / "a.py").write_text("v1 — the reviewed tree\n")
    _run(repo, "add", "-A")
    assert stamp.record() == 0

    _run(repo, "commit", "-qm", "commit exactly what was reviewed")
    _, changed = stamp.changed_since_review()
    assert changed == [], "the reviewed content, committed unchanged, is not a finding"

    _commit(repo, "a.py", "v2 — the fix nobody reviewed\n")
    _, changed = stamp.changed_since_review()
    assert changed == ["a.py"], "re-editing it is a new edit and must be reported"


def test_a_failed_primary_diff_is_LOUD_not_empty(tmp_path, monkeypatch):
    """`_git_lines` exists to tell "git failed" from "the answer is empty", and the report's own
    primary diff was left on the fail-open `_git` — so a failed diff produced `[]`, pre-push
    printed nothing, and `staleness_note` stayed quiet because `cat-file` and `merge-base` both
    succeeded. "I am blind" rendered as "you are clear".

    THE FIRST FIX WAS ALSO WRONG and re-planting is what showed it: it returned `[]`, which is
    the same silence one layer in. It raises now, onto the channel `.githooks/pre-push` already
    has for it ("review-anchor check unavailable").

    Stubbed at the module's own seam rather than by corrupting a repo: the failure is an I/O or
    object-store error that cannot be constructed reliably, and what is under test is this
    module's RESPONSE to it, not git's behaviour."""
    repo = _repo(tmp_path, monkeypatch)
    reviewed = _commit(repo, "a.py")
    assert stamp.record(head=reviewed) == 0
    _commit(repo, "b.py")

    real = stamp._git_lines
    def only_the_primary_diff_fails(*args):
        return None if any(".." in a and "..." not in a for a in args) else real(*args)
    monkeypatch.setattr(stamp, "_git_lines", only_the_primary_diff_fails)

    with pytest.raises(RuntimeError, match="silent rather than empty"):
        stamp.changed_since_review()


def test_a_head_anchored_base_is_refused(tmp_path, monkeypatch):
    """`head` is resolved to a sha because a stamp records history; `base` is kept as a REF so
    `origin/main` keeps tracking. That is right for symbolic refs and wrong for HEAD-relative
    ones, whose meaning moves with HEAD.

    Probed: `base=HEAD~1` re-resolves at push time to the FIX commit, so the unreviewed fix is
    subtracted; `base=HEAD` makes the outgoing range `HEAD...HEAD`, empty forever, so pre-push
    is permanently silent while `staleness_note` reports nothing wrong."""
    repo = _repo(tmp_path, monkeypatch)
    _commit(repo, "a.py")
    sha = _run(repo, "rev-parse", "HEAD")
    for bad in ("HEAD", "HEAD~1", "HEAD^", "@", "@~2"):
        assert stamp.record(base=bad, head=sha) == 2, bad
    assert _events(repo) == []
    assert stamp.record(base="origin/main", head=sha) == 0, "symbolic refs still work"


def test_the_blind_note_stops_after_a_week(tmp_path, monkeypatch):
    """A stale stamp is never replaced on its own — stamping rides model recall — so an
    unbounded note is true on every push forever. That is P13's shape, on the same channel as
    the useful report, in the hook whose own header rejects always-true signals.

    Recent stale stamp = news (re-stamp). Old stale stamp = indistinguishable from no stamp,
    which this hook is deliberately silent about."""
    repo = _repo(tmp_path, monkeypatch)
    reviewed = _commit(repo, "a.py")
    assert stamp.record(head=reviewed) == 0
    _run(repo, "commit", "-q", "--amend", "-m", "amended out from under the stamp")

    st = stamp.latest()
    assert stamp.staleness_note(st) is not None, "a fresh orphaned stamp is news"

    old = dict(st)
    old["ts"] = "2026-01-01T00:00:00Z"
    assert stamp.staleness_note(old) is None, (
        "past the window it is old news and reads as 'no review on record'")


def test_a_deleted_file_is_not_subtracted_just_because_it_has_no_blob_pin(tmp_path, monkeypatch):
    """ROUND 3'S PIN INTRODUCED THIS. A missing pin was read as "the stamp predates pinning" and
    subtracted unconditionally — the exact over-claim the pin was added to stop.

    A DELETED file is the common trigger: `git rm a.py` puts it in `diff --cached --name-only`,
    `hash-object` exits 128, and no entry is written. Reproduced: review a tree deleting a.py,
    stamp, commit, then re-add a.py with entirely unreviewed content — never reported, on any
    push, forever.

    Legacy is now decided by the FIELD's presence. Inside a pinned stamp a missing pin means
    "we could not establish what was reviewed", and this module's rule for that is prefer the
    noise. Falsify by reading `pinned is None` as legacy again."""
    repo = _repo(tmp_path, monkeypatch)
    _commit(repo, "a.py", "v0\n")
    _run(repo, "rm", "-q", "a.py")
    assert stamp.record() == 0
    ev = _events(repo)[-1]
    assert "a.py" in ev["data"]["uncommitted"]
    assert "a.py" not in ev["data"]["uncommitted_blobs"], "hash-object cannot pin a deletion"

    _run(repo, "commit", "-qm", "the reviewed deletion")
    _commit(repo, "a.py", "brand new, unreviewed content\n")
    _, changed = stamp.changed_since_review()
    assert changed == ["a.py"], "an unpinnable entry must not buy permanent silence"


def test_an_unreadable_working_tree_refuses_the_stamp(tmp_path, monkeypatch):
    """THE THIRD SITE OF ONE SHAPE, and the third time a fail-open branch shipped unguarded
    because a git failure is not constructible in a fixture. `_git` cannot tell "the tree is
    clean" from "git could not answer" — index.lock contention, a corrupt index — and the stamp
    would be written asserting `uncommitted: []` about a tree nothing read. That is the
    `restore_injected` shape this module cites as its founding lesson.

    Two sibling call sites were moved off `_git` in rounds 2 and 3; this one was missed twice.
    Stubbed at the module's own seam, like the primary-diff guard, because what is under test is
    this module's RESPONSE to a failure, not git's behaviour."""
    repo = _repo(tmp_path, monkeypatch)
    _commit(repo, "a.py")
    # BOTH HELPERS ARE STUBBED, and that is the point. The first version patched `_git_lines`
    # only — so re-planting the fail-open (which calls `_git`) left the test GREEN, because the
    # guard shared its seam with the implementation instead of asserting the property. The
    # property is "if the working-tree read fails, refuse", whichever helper does the reading.
    # EXACT arg tuples, not a prefix match. `args[:2] == ("diff", "--name-only")` also catches
    # the THREE-argument `files` diff (`diff --name-only base...head`), so `record()` returned 2
    # through that guard instead and the test passed for the wrong reason — green against the
    # re-plant. Found by running the stub by hand and reading which message printed.
    TREE = (("diff", "--name-only"), ("diff", "--cached", "--name-only"))
    real_lines, real_git = stamp._git_lines, stamp._git
    def lines(*args):
        return None if args in TREE else real_lines(*args)
    def plain(*args):
        return "" if args in TREE else real_git(*args)
    monkeypatch.setattr(stamp, "_git_lines", lines)
    monkeypatch.setattr(stamp, "_git", plain)

    assert stamp.record() == 2
    assert _events(repo) == [], "a stamp claiming a tree it could not read must not be written"


def test_a_stamp_from_another_branch_does_not_shadow_a_usable_one(tmp_path, monkeypatch):
    """`latest()` returned the newest stamp ANYWHERE. Reproduced: stamp feature-a, later stamp
    feature-b, return to feature-a, commit the terminal fix — the report was empty and the hook
    claimed to be blind, while a perfectly usable stamp for this line of history sat right
    there. The same defect produced the inverse noise: on any unrelated branch every push
    printed a blind note with no action available.

    `latest_usable()` picks the newest ANCESTOR. Falsify by pointing `changed_since_review` back
    at `latest()`."""
    repo = _repo(tmp_path, monkeypatch)
    _run(repo, "checkout", "-q", "-b", "feature-a")
    reviewed_a = _commit(repo, "fa.py", "v1\n")
    assert stamp.record(head=reviewed_a) == 0

    _run(repo, "checkout", "-q", "main")
    _run(repo, "checkout", "-q", "-b", "feature-b")
    reviewed_b = _commit(repo, "fb.py")
    assert stamp.record(head=reviewed_b) == 0          # newer, but on another line

    _run(repo, "checkout", "-q", "feature-a")
    _commit(repo, "fa.py", "v2 — the terminal fix\n")
    st, changed = stamp.changed_since_review()
    assert st["data"]["head"] == reviewed_a, "the usable stamp for THIS branch must win"
    assert changed == ["fa.py"]
    assert stamp.staleness_note(stamp.latest()) is None, (
        "a usable stamp exists, so the blind note must stay quiet")


def test_a_base_that_resolves_to_HEAD_is_refused_however_it_is_spelled(tmp_path, monkeypatch):
    """The HEAD-anchored guard tested SPELLING, so the failure it prevents was one keystroke
    away: on branch `main`, `stamp.py main --head <sha>` makes the outgoing range `main...HEAD`
    — empty forever, report silent on every push, nothing reporting it stale.

    Not exotic. `bin/tessera-new-project` scaffolds into a repo made by bare `git init` with no
    remote, so `origin/main` does not resolve there and naming the current branch is the obvious
    workaround. The suite previously asserted `["main", "--head", sha]` as VALID usage, which is
    why nothing had noticed."""
    repo = _repo(tmp_path, monkeypatch)
    sha = _commit(repo, "a.py")
    branch = _run(repo, "rev-parse", "--abbrev-ref", "HEAD")
    assert stamp.record(base=branch, head=sha) == 2
    assert _events(repo) == []


def test_restamping_within_the_same_second_wins(tmp_path, monkeypatch):
    """`ts` has one-second resolution and the tie-break was strict `>`, so two stamps in the
    same second resolved to the FIRST. Re-stamping is the documented remedy for a blind or wrong
    stamp, and it silently no-op'd."""
    repo = _repo(tmp_path, monkeypatch)
    a = _commit(repo, "a.py")
    b = _commit(repo, "b.py")
    assert stamp.record(head=a) == 0
    assert stamp.record(head=b) == 0
    assert stamp.latest()["data"]["head"] == b, "the correction must win"


# ── the CLI surface ────────────────────────────────────────────────────────────────────────

def test_cli_accepts_both_head_spellings_and_a_positional_base(tmp_path, monkeypatch):
    repo = _repo(tmp_path, monkeypatch)
    reviewed = _commit(repo, "a.py")
    _commit(repo, "b.py")
    # `origin/main`, NOT `main`. The suite used to assert `["main", "--head", reviewed]` as
    # valid usage — certifying the degenerate case, since on branch `main` that makes the
    # outgoing range `main...HEAD`, empty forever, and the report silent on every push. Caught
    # by review round 4; the guard that now refuses it is the fix, and this line was the reason
    # nothing had noticed.
    for argv in (["--head", reviewed], [f"--head={reviewed}"], ["origin/main", "--head", reviewed]):
        assert stamp._main(argv) == 0
        assert _events(repo)[-1]["data"]["head"] == reviewed


def test_cli_refuses_an_unknown_flag_instead_of_eating_its_argument(tmp_path, monkeypatch):
    """A TYPO MUST NOT BECOME A BASE REF. The first parser silently DROPPED any unrecognised
    `-` token, so `--haed <sha>` dropped the flag and let the sha fall through as the positional
    base: `review stamped: 1350ddb5 (HEAD) over 0 file(s) vs 1350ddb5...`, rc=0, the fix stamped
    as reviewed against a phantom base. `_main` refuses an unresolvable base for exactly this
    reason, and a mistyped flag routed around that guard.

    New failure mode in this feature: before `--head` there was no sha argument to mistype."""
    repo = _repo(tmp_path, monkeypatch)
    sha = _commit(repo, "a.py")
    assert stamp._main(["--haed", sha]) == 2
    assert _events(repo) == [], "a typo must not write a stamp at all"


def test_cli_refuses_extra_positionals(tmp_path, monkeypatch):
    """`stamp.py origin/main <sha>` silently dropped the sha and stamped HEAD as reviewed — the
    outcome `--head` exists to prevent, reached by forgetting the flag. The `--haed` fix closed
    this for FLAGS only."""
    repo = _repo(tmp_path, monkeypatch)
    sha = _commit(repo, "a.py")
    assert stamp._main(["origin/main", sha]) == 2
    assert _events(repo) == []


def test_cli_warns_when_a_bare_sha_is_being_used_as_the_base(tmp_path, monkeypatch, capsys):
    """`stamp.py <sha-the-review-saw>` reads as "base = that sha, head = HEAD" — the fix stamped
    as reviewed. Not refused, because a sha is a legitimate base and the two intentions are
    indistinguishable from argv alone; loud, then proceed."""
    repo = _repo(tmp_path, monkeypatch)
    sha = _commit(repo, "a.py")
    _commit(repo, "b.py")
    assert stamp._main([sha]) == 0
    assert "you want --head" in capsys.readouterr().err


def test_cli_refuses_a_dangling_head_flag(tmp_path, monkeypatch):
    repo = _repo(tmp_path, monkeypatch)
    _commit(repo, "a.py")
    assert stamp._main(["--head"]) == 2
    assert _events(repo) == []


def test_cli_still_refuses_an_unresolvable_base(tmp_path, monkeypatch):
    """Pre-existing guard, kept under test because the argument parser was rewritten around it
    and a positional that stops being recognised would silently restore the defect it closed."""
    repo = _repo(tmp_path, monkeypatch)
    _commit(repo, "a.py")
    assert stamp._main(["no-such-base"]) == 2
    assert _events(repo) == []
