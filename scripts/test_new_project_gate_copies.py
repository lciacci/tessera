"""The scaffold's copied gate scripts must be self-contained (import-closed).

Caught live 2026-07-20 (first ADR-0009/0010 downstream validation): spec 15
made test_gate_emit import remap_kind, the scaffold's cp list wasn't updated,
and every fresh downstream shipped a broken gate test suite. The cp enum in
bin/tessera-new-project is a hand-maintained list that drifts from the gate
dir's real import graph — so run the copied tests in a real scaffold output.
"""
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCAFFOLD = REPO / "bin" / "tessera-new-project"


def test_scaffolded_gate_tests_run_standalone(tmp_path):
    target = tmp_path / "toy"
    out = subprocess.run([str(SCAFFOLD), str(target), "toy", "standard"],
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr

    gate = target / "scripts" / "gate"
    env = dict(os.environ, CLAUDE_CODE_SESSION_ID="scaffold-test")
    for test in sorted(gate.glob("test_*.py")):
        r = subprocess.run([sys.executable, test.name], cwd=gate, env=env,
                           capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, f"{test.name} failed in scaffold:\n{r.stderr}"
