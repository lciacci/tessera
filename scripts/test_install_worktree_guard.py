#!/usr/bin/env python3
"""Regression: a disposable checkout must not repoint the machine's global links.

THE BUG (2026-07-21). `bin/tessera-verify` spawns a headless verifier in a temp git
worktree with --dangerously-skip-permissions. That agent ran `./install.sh` to falsify a
claim, and install.sh's `ln -sf "$root/.venv/bin/$c" "$HOME/.local/bin/$c"` aimed the
machine's console scripts at the worktree. The worktree was then reaped, leaving all four —
mnemos, icpg, polyphony, skill-lint — DANGLING into
/var/folders/.../T/tessera-verify-0iipykaq/.venv/bin/.

Tessera itself never noticed: its hooks try `.venv/bin/mnemos` BEFORE `command -v mnemos`,
so the local venv masked it. Any downstream project without a local venv gets F-001 exactly
— `command -v` hits a dangling symlink and every hook fails open into silence. The tool
built to verify claims was quietly breaking the toolchain it verifies with.

Root cause: tessera-verify's isolation is structural for the SOURCE TREE and absent for
$HOME. The guard lives in install.sh, not tessera-verify, so it protects every caller —
including install.sh run by hand from a throwaway worktree.
"""
import re
import subprocess
from pathlib import Path

INSTALL_SH = Path(__file__).parent.parent / "install.sh"


def _git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def test_linked_worktree_is_detectable_by_dotgit_being_a_file(tmp_path):
    """The signal install.sh guards on must be real git behavior, not a belief about it.

    install.sh deliberately does NOT shell out to `git rev-parse` here — it is running
    before/around toolchain setup and a subprocess is one more thing to fail. It relies on
    git's on-disk shape instead: a linked worktree's `.git` is a FILE (`gitdir: ...`), a
    real checkout's is a DIRECTORY. If git ever changes that, this test fails loudly rather
    than the guard silently never firing.
    """
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-q")
    _git(main, "config", "user.email", "t@t")
    _git(main, "config", "user.name", "t")
    (main / "f").write_text("x")
    _git(main, "add", "f")
    _git(main, "commit", "-qm", "c")

    wt = tmp_path / "wt"
    _git(main, "worktree", "add", "--detach", str(wt), "HEAD")

    assert (main / ".git").is_dir(), "real checkout: .git must be a directory"
    assert (wt / ".git").is_file(), "linked worktree: .git must be a file"


def test_global_link_loop_is_guarded_by_the_worktree_check():
    """The `ln -sf` into $HOME must sit inside the linked-worktree guard.

    ponytail: this reads install.sh's text rather than executing it. Running the real thing
    would build a uv venv per test — minutes, network, and it mutates $HOME, which is the
    very blast radius under test. The ceiling is honest: this catches the loop being moved
    back out of the guard (the regression that actually happened), not a subtly wrong guard.
    Upgrade path if that bites: stub uv/python on PATH and run installer() under a fake HOME.
    """
    src = INSTALL_SH.read_text()

    guard = re.search(r'if \[ -f "\$root/\.git" \].*?\n  else\n(.*?)\n  fi\n', src, re.S)
    assert guard, "linked-worktree guard missing from install.sh"

    assert 'ln -sf "$root/.venv/bin/$c" "$HOME/.local/bin/$c"' in guard.group(1), (
        "the ~/.local/bin console-script links escaped the linked-worktree guard — "
        "a reaped tessera-verify worktree will leave them dangling again"
    )
    # Exactly one such loop: a second, unguarded copy would reintroduce the bug.
    assert src.count('"$HOME/.local/bin/$c"') == 1


if __name__ == "__main__":
    import sys

    sys.exit(subprocess.call([sys.executable, "-m", "pytest", __file__, "-q"]))
