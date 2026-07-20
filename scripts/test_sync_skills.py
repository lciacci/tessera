"""bin/tessera-sync-skills — mirror semantics (ADR-0010).

Runs the real script against a temp destination (TESSERA_GLOBAL_SKILLS
override): must copy the repo registry, DELETE foreign entries (the additive
cp -r predecessor kept 10 cut skills alive in global), and be idempotent.
"""
import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SYNC = REPO / "bin" / "tessera-sync-skills"


def _run(dst: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, TESSERA_GLOBAL_SKILLS=str(dst))
    return subprocess.run([str(SYNC), *args], env=env, capture_output=True,
                          text=True, timeout=60)


def test_sync_mirrors_and_deletes_zombies(tmp_path):
    dst = tmp_path / "global-skills"
    zombie = dst / "cut-skill"
    zombie.mkdir(parents=True)
    (zombie / "SKILL.md").write_text("i was cut in ADR-0008")

    out = _run(dst)
    assert out.returncode == 0, out.stderr
    assert not zombie.exists(), "mirror must delete what the repo removed"
    repo_skills = {p.name for p in (REPO / "skills").iterdir() if p.is_dir()}
    dst_skills = {p.name for p in dst.iterdir() if p.is_dir()}
    assert dst_skills == repo_skills

    again = _run(dst)
    assert again.returncode == 0
    assert "already in sync" in again.stderr


def test_dry_run_changes_nothing(tmp_path):
    dst = tmp_path / "global-skills"
    zombie = dst / "cut-skill"
    zombie.mkdir(parents=True)
    (zombie / "SKILL.md").write_text("x")

    out = _run(dst, "--dry-run")
    assert out.returncode == 0, out.stderr
    assert zombie.exists(), "--dry-run must not delete"
    assert "deleting" in out.stdout
