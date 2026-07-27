"""Self-checks for commit-subject capture.

Run: python3 -m mnemos.test_commit_subject  (prints 'ok' on success)

Guards the defect found 2026-07-27 by T2's FIRST `insufficient` restore receipt —
the first defect that instrument has ever surfaced, and it had been degrading every
restore.

`detect_git_commit` extracted the message from the Bash command TEXT, which cannot be
done correctly: the shell has already expanded and consumed the quoting by the time a
PostToolUse hook sees anything. On this repo's own commit forms it produced

    git commit -m "$(cat <<'EOF' ...   ->  '$(cat <<'
    git commit -m "$MSG"               ->  '$MSG'
    git commit -F - <<'MSG' ...        ->  None

Those strings became ResultNodes, ResultNodes become the checkpoint's "Progress So
Far", and the checkpoint is what a session resumes from. One checkpoint listed
`$(cat <<` eleven times and `$MSG` three times as its record of the work done.

The fix is to ask git. These tests drive REAL repos through `git commit` in each
troublesome form rather than asserting on a parser, because the parser is what was
wrong — a test written against it would have encoded the same misunderstanding.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from .auto_nodes import COMMIT_FRESH_SECONDS, _committed_subject, detect_git_commit

OK = "1 file changed, 1 insertion(+)"


def _repo() -> Path:
    path = Path(tempfile.mkdtemp())
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)
    return path


def _commit(repo: Path, shell_command: str) -> None:
    (repo / "f.txt").write_text(str(len(shell_command)))
    subprocess.run(["git", "add", "f.txt"], cwd=repo, check=True)
    subprocess.run(["bash", "-c", shell_command], cwd=repo, check=True,
                   capture_output=True)


def _subject_for(shell_command: str) -> str | None:
    repo = _repo()
    _commit(repo, shell_command)
    return detect_git_commit(
        "Bash", {"command": shell_command}, OK, str(repo)
    )


def test_heredoc_commit_is_captured():
    """`git commit -F -` with a non-EOF delimiter returned None before — the shape this
    repo uses for every real commit message, so the checkpoint lost them silently."""
    got = _subject_for("git commit -q -F - <<'MSG'\nfix(x): the real subject\n\nbody\nMSG")
    assert got == "fix(x): the real subject", got


def test_command_substitution_does_not_leak_shell_syntax():
    """Produced the literal '$(cat <<' — the -m regex stopped at the quote around the
    heredoc delimiter."""
    got = _subject_for(
        'git commit -q -m "$(cat <<\'EOF\'\ndocs: substituted subject\nEOF\n)"'
    )
    assert got == "docs: substituted subject", got
    assert "$(" not in (got or "")


def test_unexpanded_variable_does_not_leak():
    """Produced the literal '$MSG'."""
    got = _subject_for('M="feat: from a variable"; git commit -q -m "$M"')
    assert got == "feat: from a variable", got
    assert "$" not in (got or "")


def test_plain_dash_m_still_works():
    """The form that always worked must keep working — this is a widening, not a swap."""
    got = _subject_for('git commit -q -m "docs: a normal one"')
    assert got == "docs: a normal one", got


def test_a_failed_commit_records_nothing():
    repo = _repo()
    assert detect_git_commit("Bash", {"command": "git commit -m x"},
                             "nothing to commit, working tree clean", str(repo)) is None


def test_a_non_commit_command_records_nothing():
    repo = _repo()
    assert detect_git_commit("Bash", {"command": "git status"}, OK, str(repo)) is None


def test_a_stale_head_is_not_reported_as_this_commit():
    """The cross-repo guard. `git log -1` answers about THIS repo, and this repo commits
    into siblings constantly. A commit made elsewhere must yield None, not some unrelated
    older subject from here — a plausible wrong answer is worse than no answer."""
    repo = _repo()
    (repo / "f.txt").write_text("x")
    subprocess.run(["git", "add", "f.txt"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "chore: committed long ago"],
        cwd=repo, check=True,
        env={"PATH": "/usr/bin:/bin", "HOME": str(repo),
             "GIT_AUTHOR_DATE": "2020-01-01T00:00:00", "GIT_COMMITTER_DATE": "2020-01-01T00:00:00",
             "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"},
    )
    assert _committed_subject(str(repo)) is None


def test_not_a_repo_is_quiet():
    assert _committed_subject(tempfile.mkdtemp()) is None


def test_freshness_window_is_stated_not_implied():
    assert COMMIT_FRESH_SECONDS > 0


if __name__ == '__main__':
    test_heredoc_commit_is_captured()
    test_command_substitution_does_not_leak_shell_syntax()
    test_unexpanded_variable_does_not_leak()
    test_plain_dash_m_still_works()
    test_a_failed_commit_records_nothing()
    test_a_non_commit_command_records_nothing()
    test_a_stale_head_is_not_reported_as_this_commit()
    test_not_a_repo_is_quiet()
    test_freshness_window_is_stated_not_implied()
    print('ok')
