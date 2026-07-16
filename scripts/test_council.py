"""bin/validate-plan — an UNAVAILABLE reviewer must never be counted as a vote.

WHY THIS EXISTS (2026-07-13, FOCUS-004):

`validate-plan` resolved its reviewers as `~/bin/deepseek` and `~/bin/gemini`. `~/bin/` does
not exist on this machine — the working wrappers live in `tessera/bin/` and are on PATH. So
every reviewer raised FileNotFoundError, `run_reviewer` caught it, returned `approved: False`,
and the council reported:

    {"verdict": "CHANGES_NEEDED", "approvals": "0/3",
     "reason": "[Errno 2] No such file or directory: '/Users/…/bin/deepseek'"}

Two distinct bugs, and the second is the dangerous one:

  1. PATH BUG — a hardcoded absolute path where a PATH lookup was needed. (F-001 in a mirror:
     there, a *name* drifted and we needed a path; here a *path* was wrong and we needed the
     name.)

  2. FAIL-WRONG — "the binary is not installed" was scored as "this reviewer voted
     CHANGES_NEEDED". A missing backend became DISSENT. That is ADR-0006's fail-wrong: the
     mechanism returns a confident verdict that is an artifact of its own brokenness, and
     nothing says so. Fixing only (1) would HIDE (2) — the council would start returning 2/3,
     look healthy, and keep miscounting any absent reviewer as a "no".

The contract these tests pin:
  - an unavailable reviewer is EXCLUDED from the panel, never counted as a vote
  - the threshold CLAMPS to the number of reviewers that actually resolved
  - the exclusion is LOUD — `unavailable` in the JSON, a warning on stderr
  - ZERO reviewers available => hard fail, non-zero exit, and NO verdict. A council with no
    reviewers must refuse to answer, not answer "CHANGES_NEEDED".
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
VALIDATE_PLAN = REPO / "bin" / "validate-plan"

APPROVE_STUB = "#!/bin/sh\necho 'APPROVED: looks fine'\n"
REJECT_STUB = "#!/bin/sh\necho 'CHANGES_NEEDED: needs work'\n"

# A reviewer that is INSTALLED, RUNS, and BLOWS UP. This is the state the first fix missed:
# `shutil.which()` proves a binary EXISTS, not that it WORKS. Caught only by driving the real
# council (2026-07-13) — the real `deepseek` exited with `ModuleNotFoundError: httpx` and the
# real `gemini-cli` with "Gemini CLI not found", and BOTH were scored as reviewers voting NO.
BROKEN_STUB = "#!/bin/sh\necho 'ModuleNotFoundError: No module named httpx' >&2\nexit 1\n"


def _stub(bin_dir: Path, name: str, body: str) -> None:
    p = bin_dir / name
    p.write_text(body)
    p.chmod(0o755)


def _run(bin_dir: Path, plan: Path, *args: str) -> tuple[int, dict | None, str]:
    """Invoke validate-plan with PATH pointing ONLY at bin_dir. Returns (rc, json, stderr)."""
    env = dict(os.environ, PATH=str(bin_dir), HOME=str(bin_dir.parent))
    proc = subprocess.run(
        [sys.executable, str(VALIDATE_PLAN), *args, str(plan)],
        capture_output=True, text=True, env=env, timeout=60,
    )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        payload = None
    return proc.returncode, payload, proc.stderr


@pytest.fixture
def plan(tmp_path: Path) -> Path:
    p = tmp_path / "plan.md"
    p.write_text("# Plan\nAdd a field to a struct.\n")
    return p


@pytest.fixture
def bin_dir(tmp_path: Path) -> Path:
    d = tmp_path / "bin"
    d.mkdir()
    return d


def test_missing_reviewer_is_not_counted_as_a_no_vote(bin_dir, plan):
    """THE BUG. Two reviewers approve, one is not installed => APPROVED, not 2/3-and-rejected."""
    _stub(bin_dir, "deepseek", APPROVE_STUB)
    _stub(bin_dir, "gemini-cli", APPROVE_STUB)
    # codex deliberately absent

    rc, out, _ = _run(bin_dir, plan, "--threshold", "2")

    assert out is not None, "expected a JSON verdict"
    assert out["verdict"] == "APPROVED", f"a missing reviewer was scored as dissent: {out}"
    assert out["approvals"] == "2/2", "the absent reviewer must not appear in the denominator"
    assert rc == 0


def test_unavailable_reviewers_are_reported_loudly(bin_dir, plan):
    """A silent exclusion is just a quieter fail-open. It must be visible in the payload."""
    _stub(bin_dir, "deepseek", APPROVE_STUB)
    _stub(bin_dir, "gemini-cli", APPROVE_STUB)

    _, out, err = _run(bin_dir, plan, "--threshold", "2")

    assert "codex" in out.get("unavailable", []), "absent reviewer must be named in the JSON"
    assert "codex" in err, "absent reviewer must be announced on stderr"


def test_threshold_clamps_to_available_reviewers(bin_dir, plan):
    """threshold=3 with only 1 reviewer installed must not be unsatisfiable-by-construction."""
    _stub(bin_dir, "deepseek", APPROVE_STUB)

    rc, out, _ = _run(bin_dir, plan, "--threshold", "3")

    assert out["threshold"] == 1, "threshold must clamp to the reviewers that actually resolved"
    assert out["verdict"] == "APPROVED"
    assert rc == 0


def test_zero_reviewers_refuses_to_answer(bin_dir, plan):
    """A council with no reviewers must NOT return CHANGES_NEEDED. It must refuse."""
    rc, out, err = _run(bin_dir, plan)  # nothing stubbed at all

    assert rc != 0, "must exit non-zero"
    assert out is None or "verdict" not in out, (
        "a council with zero reviewers returned a verdict — this is the fail-wrong"
    )
    assert "no reviewers" in err.lower()


def test_a_crashing_reviewer_is_not_counted_as_a_no_vote(bin_dir, plan):
    """THE HALF-FIX BUG. Installed + ran + crashed is NOT dissent. It is a broken instrument."""
    _stub(bin_dir, "deepseek", APPROVE_STUB)
    _stub(bin_dir, "gemini-cli", BROKEN_STUB)  # exists, runs, explodes

    rc, out, err = _run(bin_dir, plan, "--threshold", "1")

    assert out["approvals"] == "1/1", (
        f"a crashing reviewer was scored as a NO vote: {out}"
    )
    assert "gemini-cli" in out.get("broken", []), "a broken reviewer must be named in the JSON"
    assert "gemini-cli" in err, "a broken reviewer must SCREAM on stderr"
    assert out["verdict"] == "APPROVED"
    assert rc == 0


def test_all_reviewers_broken_refuses_to_answer(bin_dir, plan):
    """If every instrument is broken, the council must refuse — not report unanimous dissent."""
    _stub(bin_dir, "deepseek", BROKEN_STUB)
    _stub(bin_dir, "gemini-cli", BROKEN_STUB)

    rc, out, err = _run(bin_dir, plan, "--threshold", "1")

    assert rc != 0, "must exit non-zero"
    assert out is None or "verdict" not in out, (
        "every reviewer crashed and the council still returned a verdict — fail-wrong"
    )
    assert "no reviewers" in err.lower() or "broken" in err.lower()


def test_a_real_no_vote_still_rejects(bin_dir, plan):
    """The guard must not turn into a rubber stamp: an installed reviewer's NO still counts."""
    _stub(bin_dir, "deepseek", APPROVE_STUB)
    _stub(bin_dir, "gemini-cli", REJECT_STUB)

    rc, out, _ = _run(bin_dir, plan, "--threshold", "2")

    assert out["verdict"] == "CHANGES_NEEDED", "a genuine dissent must still block"
    assert out["approvals"] == "1/2"
    assert rc != 0
