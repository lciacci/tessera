"""Hooks must resolve the PROJECT ROOT, never the session cwd.

2026-07-26: a plain `cd scripts` in a Bash call moved the session cwd, and
`tessera-spend-guard.sh` resolved `scripts/scripts/spend/guard.py` -> absent ->
**spend-committing commands ALLOWED**. The deny-by-default gate on external spend was
switched off by a directory change. Six hooks shared the pattern.

Spec 11 worked — it emitted `degraded` instead of failing silently. But `tessera-degraded`
resolved its destination the same way, so the report landed in `scripts/.tessera/logs/`,
where `tessera-watch` P13 reading the repo root never sees it. The alarm fired into an empty
room. **A degraded reporter that a directory change can silence is not a reporter.**

Two guards here, because a source-level check and a behavioural one fail differently:
the regex catches a NEW hook reintroducing the pattern; the subprocess tests catch the
anchor itself breaking.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
HOOKS = ROOT / ".claude" / "scripts"
# The `_anchor_root` CARRIER these two tests extract from. Was `tessera-spend-guard.sh`
# until 2026-08-18 (ADR-0029 retired it); `_anchor_root` is a shared idiom across five
# hooks, so the function under test is unchanged — only the file it is read out of.
ANCHOR_CARRIER = HOOKS / "tessera-gate-scan.sh"
DEGRADED = ROOT / "bin" / "tessera-degraded"

# The exact shape that shipped the bug: project dir taken straight from session cwd.
_UNANCHORED = re.compile(r'PROJECT_DIR="\$\{CWD:-\$PWD\}"')



def _extract_anchor_root(hook: Path) -> str:
    """Pull the shipped `_anchor_root` out of a hook so tests run the real thing."""
    lines = hook.read_text().splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("_anchor_root() {"))
    end = next(i for i, l in enumerate(lines[start:], start) if l == "}")
    return "\n".join(lines[start:end + 1])


def test_no_hook_derives_its_project_dir_from_the_session_cwd():
    """Class-level guard. A new hook copying the old idiom reintroduces the fail-open."""
    offenders = [p.name for p in sorted(HOOKS.glob("*.sh"))
                 if _UNANCHORED.search(p.read_text())]
    assert not offenders, (
        f"{offenders} take PROJECT_DIR from the session cwd; a Bash `cd` silences them")


def test_degraded_reports_to_the_project_root_not_the_cwd(tmp_path):
    """The report must reach the room the alarm is read in — P13 reads the project root."""
    log = ROOT / ".tessera" / "logs" / "anchor-pytest.jsonl"
    log.unlink(missing_ok=True)
    subprocess.run(
        [str(DEGRADED), "--component", "anchor-pytest", "--reason", "cwd-shift",
         "--session", "anchor-pytest", "--project", str(ROOT / "scripts" / "gate")],
        capture_output=True, cwd=ROOT, check=False)
    try:
        assert log.exists(), "degraded event did not land at the project root"
        assert not (ROOT / "scripts" / "gate" / ".tessera").exists(), "leaked into the subdir"
    finally:
        log.unlink(missing_ok=True)


def test_root_marker_cannot_be_forged_by_a_stray_tessera_dir(tmp_path):
    """The first fix used `.tessera/` as the root marker and FAILED — because the bug it
    fixes creates stray `.tessera/logs/` directories in whatever cwd was current, and one
    of those under scripts/ was found first. A bug that manufactures false markers for its
    own fix. The marker is now `.git` (any type — a worktree's is a FILE) or a `.tessera/`
    that actually holds `project.yml`."""
    real = tmp_path / "proj"
    (real / ".tessera").mkdir(parents=True)
    (real / ".tessera" / "project.yml").write_text("name: proj\n")
    decoy = real / "sub"
    (decoy / ".tessera" / "logs").mkdir(parents=True)   # stray log dir, not a root

    # Extract the SHIPPED function rather than restating it — an embedded copy would drift
    # from the hooks and quietly start testing something nobody runs.
    script = f'{_extract_anchor_root(ANCHOR_CARRIER)}\n_anchor_root "{decoy}"\nprintf %s "$_root"\n'
    out = subprocess.run(["sh", "-c", script], capture_output=True, text=True).stdout
    assert out == str(real), f"stray .tessera/ forged a root: {out!r}"


def test_anchor_root_falls_back_rather_than_yielding_empty(tmp_path):
    """No marker anywhere must return the input, not "" — an empty project dir would make
    every path resolve against / and fail open in a new way."""
    script = f'{_extract_anchor_root(ANCHOR_CARRIER)}\n_anchor_root "{tmp_path}"\nprintf %s "$_root"\n'
    out = subprocess.run(["sh", "-c", script], capture_output=True, text=True).stdout
    assert out == str(tmp_path)
