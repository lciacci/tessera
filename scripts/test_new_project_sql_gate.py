"""The SQL gate must ship complete, stay silent when idle, and shout when broken (ADR-0012).

Three invariants, each with a specific failure behind it:

1. SHIP BOTH HALVES. `lint.sh` without `.sqlfluff` runs stock rules — 89% whitespace noise on
   real SQL (ADR-0011's measurement). And `lint.sh` without a pre-commit hook to invoke it is a
   gate nothing calls. Downstream projects get no hook otherwise (doccheck is framework-only),
   so all three must ship together or the gate is theatre. This is the same rule the gate
   recorder and spend guard follow, and the same one the findings channel violated on 2026-07-21.

2. SILENT WHEN THERE IS NOTHING TO DO. The gate ships to every project, including the four
   downstreams with zero SQL. If it were chatty there, it would be turned off.

3. LOUD WHEN IT CANNOT DO ITS JOB. Spec 11's distinction. A linter that silently skips looks
   exactly like a linter that passed — F-001, the dead ingest pipe, and the falsifier were all
   that shape within eight days.

Deliberately NOT tested here: a live sqlfluff run. It needs a network fetch on cold `uvx` cache
and would make the suite flaky for weak evidence. Verified by hand on settempo and a scratch
repo at adoption time (ADR-0012).
"""
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCAFFOLD = REPO / "bin" / "tessera-new-project"


def _scaffold(tmp_path, name="toy"):
    target = tmp_path / name
    out = subprocess.run([str(SCAFFOLD), str(target), name, "standard"],
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    return target


def test_scaffold_ships_all_three_halves(tmp_path):
    target = _scaffold(tmp_path)

    lint = target / "scripts" / "sql" / "lint.sh"
    config = target / ".sqlfluff"
    hook = target / ".githooks" / "pre-commit"

    assert lint.is_file() and os.access(lint, os.X_OK), "lint.sh missing or not executable"
    assert config.is_file(), "no .sqlfluff — the gate would run stock rules (89% noise)"
    assert hook.is_file() and os.access(hook, os.X_OK), "no pre-commit hook — nothing invokes the gate"
    assert "scripts/sql/lint.sh" in hook.read_text(), "the hook does not call the gate"

    # The config's whole point: layout excluded, dialect explicit.
    body = config.read_text()
    assert "exclude_rules = layout" in body
    assert "dialect" in body

    hooks_path = subprocess.run(["git", "-C", str(target), "config", "core.hooksPath"],
                                capture_output=True, text=True).stdout.strip()
    assert hooks_path == ".githooks", f"core.hooksPath is {hooks_path!r}; the hook will never run"


def test_gate_is_silent_when_no_sql_is_staged(tmp_path):
    """It ships to every project. In the ones with no SQL it must say nothing at all."""
    target = _scaffold(tmp_path)
    (target / "readme.txt").write_text("not sql\n")
    subprocess.run(["git", "-C", str(target), "add", "-A"], capture_output=True)

    r = subprocess.run([str(target / "scripts" / "sql" / "lint.sh")],
                       cwd=target, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0
    assert r.stdout.strip() == ""
    assert r.stderr.strip() == "", f"chatty when idle: {r.stderr!r}"


def test_gate_shouts_when_it_cannot_run(tmp_path):
    """No sqlfluff, no uvx, but staged SQL: must warn loudly AND still allow the commit."""
    target = _scaffold(tmp_path)
    (target / "s.sql").write_text("select 1;\n")
    subprocess.run(["git", "-C", str(target), "add", "-A"], capture_output=True)

    env = dict(os.environ, PATH="/usr/bin:/bin")
    r = subprocess.run([str(target / "scripts" / "sql" / "lint.sh")],
                       cwd=target, capture_output=True, text=True, timeout=60, env=env)
    assert r.returncode == 0, "warn-only: must never block, even when degraded"
    assert "DEGRADED" in r.stderr, f"failed silently — the exact bug this guards: {r.stderr!r}"
    assert "s.sql" in r.stderr, "must name the files it did not check"


if __name__ == "__main__":
    sys.exit(subprocess.call([sys.executable, "-m", "pytest", __file__, "-q"]))
