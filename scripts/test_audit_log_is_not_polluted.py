"""A test must never become evidence about the thing it tests.

The 2026-07-12 instance: `guard.main()` -> `_log_denial()` -> `emit()` keys on
`CLAUDE_CODE_SESSION_ID`, which IS set under a real session, so 26 of that session's 31
`spend_denied` events were manufactured by pytest — an 84%-polluted friction journal and a
backstop poised to fire on its own tests. Fixed at the root with `scripts/spend/conftest.py`.

**It came back on 2026-07-27, through a door that fix could not reach.**
`test_hook_cwd_anchoring.py` runs the real `tessera-spend-guard.sh` as a SUBPROCESS across four
cwds; a subprocess inherits the environment, so every `bin/tessera-test` wrote four real
denials into the live journal. Twelve were found in one session's log.

**These tests assert the PROPERTY, not the artifact.** Checking "does a conftest.py exist" is
the proxy this repo has retired three times over (standing pattern #3) — and it would have
scored the 07-12 fix as complete while the subprocess door stood open. The hypothesis on
07-27 was in fact "the chaos suite lacks a conftest", which was WRONG: chaos measured clean and
the polluter was a top-level file that no artifact-count would have implicated. Only running
the thing found it.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
GUARD = ROOT / ".claude" / "scripts" / "tessera-spend-guard.sh"
LOGS = ROOT / ".tessera" / "logs"

needs_jq = pytest.mark.skipif(shutil.which("jq") is None, reason="hook requires jq")


def test_the_session_id_is_stripped_inside_the_suite():
    """Pins the conftest. If someone deletes that fixture this fails loudly, rather than
    the journal quietly refilling for weeks the way it did between the two instances."""
    assert os.environ.get("CLAUDE_CODE_SESSION_ID") is None, (
        "CLAUDE_CODE_SESSION_ID is set inside the test suite — emit() is live and any test "
        "reaching it writes real events to .tessera/logs/. See scripts/conftest.py."
    )


@needs_jq
def test_driving_the_real_spend_guard_writes_no_production_event():
    """THE regression, at the level it actually failed: a real hook, a real subprocess.

    Deliberately runs under the suite's OWN environment — re-setting the session id here
    would defeat the fixture under test and assert the opposite of the property. Snapshots
    `.tessera/logs/` and requires it unchanged.

    HONEST LIMIT: on a machine with no ambient `CLAUDE_CODE_SESSION_ID` this cannot fail, so
    it is weaker than `test_the_session_id_is_stripped_inside_the_suite` above, which pins the
    mechanism directly. It is kept because it is the only one that exercises the *path* the
    bug travelled — hook, subprocess, inherited env — and because it fails exactly where the
    bug bit: a suite run inside a real Claude Code session.
    """
    before = {p.name for p in LOGS.glob("*.jsonl")} if LOGS.is_dir() else set()

    payload = json.dumps({
        "session_id": "probe", "cwd": str(ROOT),
        "tool_name": "Bash", "tool_input": {"command": "terraform apply"},
    })
    rc = subprocess.run(["bash", str(GUARD)], input=payload, text=True,
                        capture_output=True, cwd=ROOT).returncode
    assert rc == 2, "the guard did not deny — this test is not exercising the deny path"

    after = {p.name for p in LOGS.glob("*.jsonl")} if LOGS.is_dir() else set()
    assert after == before, (
        f"the suite created {sorted(after - before)} — a test manufactured a spend_denied "
        f"event in the production journal. That is the 2026-07-12 bug through the subprocess "
        f"door: the env var must be stripped before the subprocess can inherit it."
    )
