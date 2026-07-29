"""A scaffolded project must be able to RUN the restore-receipt instrument (T2, ADR-0015).

FOUND 2026-07-29, by reading downstream logs rather than code. `restore_offered` was zero
across 34 sessions in 6 projects — 26 of them substantive and therefore owing a receipt.
Cause: `scripts/restore/` was never added to the scaffold. The SessionStart hook probes
`$PWD/scripts/restore/offer.py`, which is correct by this scaffold's own convention
(cf. `scripts/tessera-degraded`); the directory simply never shipped. So T2 — the question
ADR-0015 calls the only one that can produce a verdict on Mnemos's recovery half — could
only ever be answered in tessera itself, the one venue the handoff explicitly calls biased
("a downstream app has no such file; do not read tessera receipts as a general verdict").

WHY THIS TEST AND NOT A `cp`-LINE GREP. The pain is "the instrument cannot run in a
downstream project", so that is what gets asserted: scaffold for real, then drive
offer.py and scan.py inside the scaffold output and check they produce their events.
Counting copied files is the proxy — standing pattern #3, aimed at the auditor.

Deliberately NOT shipping test_restore.py downstream: it imports pytest, which a fresh
scaffold has no venv for. Import-closure is asserted here instead, by importing every
shipped module from the scaffold with a bare interpreter.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCAFFOLD = REPO / "bin" / "tessera-new-project"
SHIPPED = ("paths.py", "offer.py", "emit.py", "scan.py")


def _scaffold(tmp_path, name="toy"):
    out = subprocess.run([str(SCAFFOLD), str(tmp_path / name), name, "standard"],
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    return tmp_path / name


def _run(target, *args, session="restore-scaffold-test", **kw):
    env = dict(os.environ, CLAUDE_CODE_SESSION_ID=session)
    env.pop("TESSERA_ROOT", None)          # the anchor under test is __file__-derived
    return subprocess.run([sys.executable, *args], cwd=target, env=env,
                          capture_output=True, text=True, timeout=60, **kw)


def _events(target, session="restore-scaffold-test"):
    log = target / ".tessera" / "logs" / f"{session}.jsonl"
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]


def test_shipped_restore_modules_import_standalone(tmp_path):
    """Import-closure: every shipped module must load with a bare interpreter, from the
    scaffold, with no package context and no venv. offer/emit/scan each import paths."""
    target = _scaffold(tmp_path)
    restore = target / "scripts" / "restore"
    for mod in SHIPPED:
        assert (restore / mod).is_file(), f"{mod} did not ship into the scaffold"
        r = _run(restore, "-c", f"import {Path(mod).stem}")
        assert r.returncode == 0, f"{mod} is not import-closed in the scaffold:\n{r.stderr}"


def test_offer_records_the_delivery_and_scan_asks_for_the_receipt(tmp_path):
    """The end-to-end property: a downstream project can record an offer and be asked for
    a receipt. Both halves, because either alone is the failure this ships to fix — offer
    without scan is a denominator nothing divides; scan without offer never fires."""
    target = _scaffold(tmp_path)
    (target / ".mnemos").mkdir(exist_ok=True)
    (target / ".mnemos" / "checkpoint-latest.json").write_text(json.dumps({
        "goal": "a downstream goal", "active_constraints": ["c1"],
        "task_narrative": "what was underway",
    }))

    # HARNESS half — offer.py, run the way the SessionStart hook runs it.
    assert _run(target, "scripts/restore/offer.py").returncode == 0
    offers = [e for e in _events(target) if e.get("type") == "restore_offered"]
    assert len(offers) == 1, f"no restore_offered written in the scaffold: {_events(target)}"
    assert offers[0]["data"]["fields"] == ["goal", "active_constraints", "task_narrative"]

    # MODEL half — scan.py must now ask, given a substantive transcript.
    transcript = tmp_path / "tr.jsonl"
    transcript.write_text("".join(
        json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Edit"}]}}) + "\n" for _ in range(3)))
    r = _run(target, "scripts/restore/scan.py", str(transcript), "restore-scaffold-test")
    assert r.returncode != 0, "scan.py did not ask for the receipt after a real offer"
    assert "RESTORE RECEIPT OWED" in r.stderr + r.stdout

    # ...and emit.py must be able to answer it, or the ask is a dead end downstream.
    assert _run(target, "scripts/restore/emit.py", "--insufficient", "--missing", "progress",
                "--rederived", "what had already been done").returncode == 0
    assert any(e.get("type") == "restore_receipt" for e in _events(target))


def test_the_rule_is_not_vacuous(tmp_path):
    """Standing pattern #10: re-plant the real defect. With scripts/restore removed — the
    exact state all six downstreams were in — the offer must not be recordable and the
    Stop hook must report `scanner-missing` rather than exiting quietly into the dark."""
    target = _scaffold(tmp_path)
    (target / ".mnemos").mkdir(exist_ok=True)
    (target / ".mnemos" / "checkpoint-latest.json").write_text(json.dumps({"goal": "g"}))

    for mod in SHIPPED:
        (target / "scripts" / "restore" / mod).unlink()
    _run(target, "scripts/restore/offer.py")
    assert not [e for e in _events(target) if e.get("type") == "restore_offered"], \
        "an offer was recorded with offer.py deleted — the test proves nothing"

    hook = target / ".claude" / "scripts" / "tessera-restore-scan.sh"
    assert hook.is_file(), "the Stop hook must ship, or nothing can report the gap"
    payload = json.dumps({"session_id": "vacuity-probe", "transcript_path": "/dev/null",
                          "cwd": str(target), "stop_hook_active": False})
    subprocess.run([str(hook)], input=payload, cwd=target, capture_output=True,
                   text=True, timeout=60)
    reported = [e for e in _events(target, "vacuity-probe")
                if e.get("type") == "degraded"
                and e["data"]["reason"] == "scanner-missing"]
    assert reported, (
        "the Stop hook exited quietly with scan.py missing — that silence IS the bug this "
        "ships to fix, and it would look exactly like a healthy session")


def test_sessionstart_reports_when_offer_py_resolves_nowhere(tmp_path):
    """The silence that cost 34 sessions. mnemos-session-start.sh probes two paths for
    offer.py and, before 2026-07-29, ended that loop with no `else` — so a project missing
    the module logged *nothing*, identical to a healthy one with nothing to say.

    Runs the REPO copy, placed in the scaffold's own .claude/scripts so its `*/.claude/scripts`
    anchoring resolves to the scaffold (the global-tier copy at ~/.claude/templates deliberately
    does not match that pattern and rides the session cwd instead). Skips rather than fails if
    the mnemos CLI is unreachable: this asserts the hook's reporting, not the toolchain's health,
    and P9 already owns the latter.
    """
    target = _scaffold(tmp_path)
    hook_src = REPO / ".claude" / "scripts" / "mnemos-session-start.sh"
    hook = target / ".claude" / "scripts" / hook_src.name
    hook.write_bytes(hook_src.read_bytes())
    hook.chmod(0o755)
    (target / ".mnemos").mkdir(exist_ok=True)
    (target / ".mnemos" / "checkpoint-latest.json").write_text(json.dumps({
        "goal": "g", "active_constraints": ["c"], "task_narrative": "n"}))

    def run(session):
        env = dict(os.environ, CLAUDE_CODE_SESSION_ID=session)
        subprocess.run([str(hook)], cwd=target, env=env, capture_output=True,
                       text=True, timeout=120)
        return _events(target, session)

    if not any(e.get("type") == "restore_offered" for e in run("probe-healthy")):
        import pytest
        pytest.skip("mnemos CLI unreachable — no checkpoint delivered, nothing to report on")

    # ABSENT — the fleet's actual state for its whole life.
    restore = target / "scripts" / "restore"
    restore.rename(target / "scripts" / "_restore_gone")
    degraded = [e for e in run("probe-missing") if e.get("type") == "degraded"]
    assert any(e["data"]["reason"] == "offer-missing" for e in degraded), (
        "SessionStart delivered a checkpoint, could not record the offer, and said nothing — "
        f"that silence IS the 34-session bug. Events: {degraded}")

    # PRESENT BUT BROKEN — a distinct failure, and the first draft of the fix suppressed it
    # by setting the found-flag on the same line as the interpreter call (arbiter, 2026-07-29).
    # A crashing offer.py must not read as a recorded offer.
    (target / "scripts" / "_restore_gone").rename(restore)
    (restore / "offer.py").write_text("import sys\nsys.exit(3)\n")
    degraded = [e for e in run("probe-failed") if e.get("type") == "degraded"]
    assert any(e["data"]["reason"] == "offer-failed" for e in degraded), (
        "a present-but-failing offer.py was treated as a recorded offer — the reporter is "
        f"suppressed by exactly the fault it exists to report. Events: {degraded}")


if __name__ == "__main__":
    sys.exit(subprocess.call([sys.executable, "-m", "pytest", __file__, "-q"]))
