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
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DEGRADED = ROOT / "bin" / "tessera-degraded"
LOGS = ROOT / ".tessera" / "logs"



def test_the_session_id_is_stripped_inside_the_suite():
    """Pins the conftest. If someone deletes that fixture this fails loudly, rather than
    the journal quietly refilling for weeks the way it did between the two instances."""
    assert os.environ.get("CLAUDE_CODE_SESSION_ID") is None, (
        "CLAUDE_CODE_SESSION_ID is set inside the test suite — emit() is live and any test "
        "reaching it writes real events to .tessera/logs/. See scripts/conftest.py."
    )


def test_driving_a_real_event_writer_as_a_subprocess_writes_no_production_event():
    """THE regression, at the level it actually failed: a real binary, a real subprocess.

    RE-POINTED 2026-08-18. The original vehicle was `tessera-spend-guard.sh`, retired with the
    rest of the in-band spend guard by ADR-0029. **The property is not spend-specific and
    outlives it** — `.tessera/logs/` is the shared channel for gate, override, restore,
    degraded and whatever a downstream adds next, and the bug travelled through the *subprocess
    inheriting the environment*, not through anything about spend. So the vehicle moved to
    `bin/tessera-degraded`: a real binary, run as a subprocess, that writes to the same log
    keyed by session id and refuses to write without one.

    Deliberately runs under the suite's OWN environment — re-setting the session id here would
    defeat the fixture under test and assert the opposite of the property.

    HONEST LIMIT, unchanged by the re-point: on a machine with no ambient
    `CLAUDE_CODE_SESSION_ID` this cannot fail, so it is weaker than
    `test_the_session_id_is_stripped_inside_the_suite` above, which pins the mechanism
    directly. It is kept because it is the only one that exercises the PATH the bug travelled.
    """
    before = {p.name for p in LOGS.glob("*.jsonl")} if LOGS.is_dir() else set()

    r = subprocess.run([str(DEGRADED), "--component", "audit-log-probe",
                        "--reason", "suite-pollution-probe",
                        "--detail", "asserting the suite writes no production event"],
                       text=True, capture_output=True, cwd=ROOT)

    # ASSERT THE PATH WAS ACTUALLY EXERCISED, not merely that nothing appeared. Found in
    # review 2026-08-18: the first re-point checked only `after == before`, and
    # `tessera-degraded` ends in `exit 0` unconditionally ("never fail the caller") while
    # exiting 64 on a usage error BEFORE touching the log. So a renamed flag would make the
    # subprocess write nothing, the equality would hold, and this test would pass green over
    # zero coverage — the "true report, no coverage" shape (#12), inside the test that exists
    # to pin a silent failure. The message proves the writer REACHED the session-key branch
    # that the stripped env var is supposed to starve.
    assert "no session id; cannot record" in (r.stderr + r.stdout), (
        f"the probe did not reach the session-key branch — this test is exercising nothing. "
        f"rc={r.returncode} stdout={r.stdout!r} stderr={r.stderr!r}")

    after = {p.name for p in LOGS.glob("*.jsonl")} if LOGS.is_dir() else set()
    assert after == before, (
        f"the suite created {sorted(after - before)} — a test manufactured a real event in "
        f"the production journal. That is the 2026-07-12 bug through the subprocess door: "
        f"the env var must be stripped before the subprocess can inherit it."
    )
