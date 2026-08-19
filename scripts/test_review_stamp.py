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
    assert ev["data"]["had_uncommitted"] is False


def test_stamping_head_explicitly_still_captures_the_working_tree(tmp_path, monkeypatch):
    """The primary path: review an UNCOMMITTED tree, stamp, commit, push. Naming HEAD
    explicitly must behave exactly like defaulting to it — otherwise the flag punishes being
    precise, and the dirty files reappear in `changed_since_review` as false positives."""
    repo = _repo(tmp_path, monkeypatch)
    head = _commit(repo, "a.py")
    (repo / "wip.py").write_text("wip\n")
    _run(repo, "add", "-A")

    assert stamp.record(head=head) == 0
    ev = _events(repo)[-1]
    assert "wip.py" in ev["data"]["files"]
    assert ev["data"]["had_uncommitted"] is True


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

    st, changed = stamp.changed_since_review()
    assert st is not None and changed == []


# ── the CLI surface ────────────────────────────────────────────────────────────────────────

def test_cli_accepts_both_head_spellings_and_a_positional_base(tmp_path, monkeypatch):
    repo = _repo(tmp_path, monkeypatch)
    reviewed = _commit(repo, "a.py")
    _commit(repo, "b.py")
    for argv in (["--head", reviewed], [f"--head={reviewed}"], ["main", "--head", reviewed]):
        assert stamp._main(argv) == 0
        assert _events(repo)[-1]["data"]["head"] == reviewed


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
