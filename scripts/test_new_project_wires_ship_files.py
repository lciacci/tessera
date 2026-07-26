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
import os
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


def _missing(target):
    settings = json.loads((target / ".claude" / "settings.json").read_text())
    return [rel for cmd in _commands(settings)
            for rel in _local_only_scripts(cmd) if not (target / rel).exists()]


def test_local_only_wired_hooks_ship_and_the_rule_is_not_vacuous(tmp_path):
    """One scaffold (a subprocess), both assertions. Pass case: every local-only wired hook
    ships its file. Not-vacuous: deleting decision-surface.sh makes the rule fire — proving a
    real local-only hook is present and evaluated, not a green from finding nothing to check."""
    target = _scaffold(tmp_path)
    assert not _missing(target), (
        f"scaffold wires local-only hook(s) with no shipped file — add to bin/tessera-new-project")
    surface = target / ".claude" / "scripts" / "tessera-decision-surface.sh"
    assert surface.exists(), "precondition: a local-only hook must exist for the rule to bite"
    surface.unlink()
    assert any("tessera-decision-surface.sh" in r for r in _missing(target)), \
        "rule did not fire on a deleted local-only file — the check is vacuous"


def _degraded_callers(target: Path) -> list[str]:
    """Shipped hooks that invoke the spec-11 degraded reporter."""
    scripts = target / ".claude" / "scripts"
    return [p.name for p in sorted(scripts.glob("*.sh"))
            if "tessera-degraded" in p.read_text(errors="replace")]


def _reporter_resolves(target: Path) -> bool:
    """The resolution order the hooks actually use: project bin/, then project scripts/."""
    return any((target / d / "tessera-degraded").is_file() and
               os.access(target / d / "tessera-degraded", os.X_OK)
               for d in ("bin", "scripts"))


def test_hooks_that_report_degraded_ship_the_reporter(tmp_path):
    """Spec 11, one layer down from the rule above: a hook can ship its own file and still be
    half-shipped, because its REPORTER did not come with it.

    Every spec-11 bail-out is `degraded ...; exit 0`. If bin/tessera-new-project stops copying
    tessera-degraded, the resolver finds nothing, the function returns 0, and every one of those
    bail-outs silently reverts to the bare `exit 0` it replaced — the framework ships the guards
    without the thing that reports the guards failing. That is the exact "ship both halves or
    neither" violation spec 11 was written about, and it would leave no trace: the hooks still
    exist, still run, still exit 0. Asserts the real scaffold output, not a grep of cp lines.
    """
    target = _scaffold(tmp_path)
    callers = _degraded_callers(target)
    assert callers, "precondition: the scaffold must ship at least one degraded-reporting hook"
    assert _reporter_resolves(target), (
        f"{len(callers)} shipped hook(s) call tessera-degraded ({', '.join(callers)}) but the "
        f"reporter is not in the scaffolded project — every 'I could not do my job' bail-out is "
        f"silently a bare exit 0. Add it to bin/tessera-new-project.")

    # Not vacuous: remove the reporter and the rule must fire.
    (target / "scripts" / "tessera-degraded").unlink()
    assert not _reporter_resolves(target), \
        "rule did not fire with the reporter deleted — the check is vacuous"


if __name__ == "__main__":
    import sys
    sys.exit(subprocess.call([sys.executable, "-m", "pytest", __file__, "-q"]))
