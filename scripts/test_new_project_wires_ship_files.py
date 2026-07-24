"""A scaffolded project must SHIP a file for every hook it wires local-only.

FOUND 2026-07-24. The B hook (tessera-decision-surface) was wired into the scaffold's
settings.base.json but its file was never added to tessera-new-project — so a fresh project
carried a hook command pointing at a script that did not exist. Guarded by `[ -x ]`, so it
silently no-ops: dead feature, present-looking wiring. The "ship both halves or neither" rule
the scaffold enforces for the gate recorder and spend guard, violated. It was caught only by a
fleet back-fill accident, not a check — so, a check.

THE RULE, and it needs no allowlist. A hook command carries the ADR-0004 two-tier fallback
(`elif $HOME/.claude/templates/X`) OR it does not:
  - WITH the fallback  -> the local file is OPTIONAL (global tier resolves via the global copy).
  - WITHOUT it (local-only) -> the local file MUST ship, or the hook is dead on a fresh project.
This checks the REAL scaffold output, not a proxy for it (e.g. grepping cp commands) — the pain
is "the file did not ship", so the test asserts exactly that. It runs in the suite, not
doccheck/pre-commit, because it scaffolds a project (subprocess); doccheck stays pure-read.
"""
import json
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCAFFOLD = REPO / "bin" / "tessera-new-project"
_TOKEN = re.compile(r'"(?:\$\{CLAUDE_PROJECT_DIR:-\.\}/)?((?:\.claude/scripts|hooks)/[A-Za-z0-9._-]+)"')


def _scaffold(tmp_path, name="toy"):
    out = subprocess.run([str(SCAFFOLD), str(tmp_path / name), name, "standard"],
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    return tmp_path / name


def _commands(settings: dict):
    sl = settings.get("statusLine") or {}
    if sl.get("type") == "command":
        yield sl.get("command", "")
    for groups in (settings.get("hooks") or {}).values():
        for group in groups:
            for hook in group.get("hooks", []):
                yield hook.get("command", "")


def _local_only_scripts(cmd: str) -> list[str]:
    """Local hook-script paths in a command that has NO global-templates fallback."""
    if "$HOME/.claude/templates" in cmd:
        return []                       # fallback present -> local file optional
    return [m.group(1) for m in _TOKEN.finditer(cmd)]


def test_every_local_only_wired_hook_ships_its_file(tmp_path):
    target = _scaffold(tmp_path)
    settings = json.loads((target / ".claude" / "settings.json").read_text())
    missing = []
    for cmd in _commands(settings):
        for rel in _local_only_scripts(cmd):
            if not (target / rel).exists():
                missing.append(rel)
    assert not missing, (
        f"scaffold wires local-only hook(s) with no shipped file: {missing} — "
        f"add the file to bin/tessera-new-project (ship both halves)")


def test_the_check_would_have_caught_the_decision_surface_bug(tmp_path):
    """Not vacuous: delete the decision-surface file from a scaffold and confirm the rule fires.
    Guards against the check silently passing because its detector is broken."""
    target = _scaffold(tmp_path)
    (target / ".claude" / "scripts" / "tessera-decision-surface.sh").unlink()
    settings = json.loads((target / ".claude" / "settings.json").read_text())
    flagged = [rel for cmd in _commands(settings)
               for rel in _local_only_scripts(cmd) if not (target / rel).exists()]
    assert any("tessera-decision-surface.sh" in r for r in flagged), flagged


if __name__ == "__main__":
    import sys
    sys.exit(subprocess.call([sys.executable, "-m", "pytest", __file__, "-q"]))
