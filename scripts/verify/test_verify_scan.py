#!/usr/bin/env python3
"""Tests for the verify-scan Stop-hook detector (spec 12).

The detector is a recall net: session touched a safety path AND an assistant
turn claimed done/fixed/closed AND no verification event is logged for the
session. Fail-LOUD is the contract here — this is the one hook that must not
fail open (spec 12, ADR-0006 tier 4).
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import scan  # noqa: E402


def _write_transcript(path: Path, entries: list[dict]) -> str:
    path.write_text("\n".join(json.dumps(e) for e in entries))
    return str(path)


def _assistant_text(text: str) -> dict:
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}


def _edit(file_path: str) -> dict:
    return {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "tool_use", "name": "Edit", "input": {"file_path": file_path}}
            ]
        },
    }


def _bash(command: str) -> dict:
    return {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "tool_use", "name": "Bash", "input": {"command": command}}
            ]
        },
    }


@pytest.fixture()
def logs(tmp_path, monkeypatch):
    d = tmp_path / "logs"
    d.mkdir()
    monkeypatch.setattr(scan, "LOGS", d)
    return d


# --- safety-path detection -------------------------------------------------

def test_edit_on_safety_path_detected(tmp_path, logs):
    t = _write_transcript(tmp_path / "t.jsonl", [_edit("/repo/scripts/spend/guard.py")])
    assert scan.touched_safety_paths(t) == ["scripts/spend/"]


def test_bash_touching_safety_path_detected(tmp_path, logs):
    t = _write_transcript(tmp_path / "t.jsonl", [_bash("chmod +x .claude/scripts/foo.sh")])
    assert scan.touched_safety_paths(t) == [".claude/scripts/"]


def test_non_safety_edit_not_detected(tmp_path, logs):
    t = _write_transcript(tmp_path / "t.jsonl", [_edit("/repo/docs/observatory.md")])
    assert scan.touched_safety_paths(t) == []


def test_sidechain_entries_ignored(tmp_path, logs):
    entry = _edit("/repo/scripts/spend/guard.py")
    entry["isSidechain"] = True
    t = _write_transcript(tmp_path / "t.jsonl", [entry])
    assert scan.touched_safety_paths(t) == []


# --- done-claim detection ----------------------------------------------------

def test_done_claim_detected(tmp_path, logs):
    t = _write_transcript(tmp_path / "t.jsonl", [_assistant_text("The guard is fixed and green.")])
    assert scan.made_done_claim(t)


def test_neutral_text_is_not_a_claim(tmp_path, logs):
    t = _write_transcript(tmp_path / "t.jsonl", [_assistant_text("Reading the transcript now.")])
    assert not scan.made_done_claim(t)


# --- verification-logged check ----------------------------------------------

def test_verification_event_counts_as_logged(logs):
    (logs / "s1.jsonl").write_text(json.dumps({"type": "verification"}) + "\n")
    assert scan.verification_logged("s1")


def test_skip_event_counts_as_logged(logs):
    ev = {"type": "verification", "data": {"skipped": True}}
    (logs / "s1.jsonl").write_text(json.dumps(ev) + "\n")
    assert scan.verification_logged("s1")


def test_other_events_do_not_count(logs):
    (logs / "s1.jsonl").write_text(json.dumps({"type": "suggestion_gate"}) + "\n")
    assert not scan.verification_logged("s1")


def test_missing_log_is_not_logged(logs):
    assert not scan.verification_logged("nope")


# --- firing logic -------------------------------------------------------------

def _full_transcript(tmp_path):
    return _write_transcript(
        tmp_path / "t.jsonl",
        [_edit("/repo/scripts/spend/guard.py"), _assistant_text("Fixed. Suite green.")],
    )


def test_fires_on_safety_touch_plus_claim_no_log(tmp_path, logs, capsys):
    t = _full_transcript(tmp_path)
    assert scan.main([t, "s1"]) == 1
    assert "tessera-verify" in capsys.readouterr().err


def test_quiet_when_verification_logged(tmp_path, logs):
    (logs / "s1.jsonl").write_text(json.dumps({"type": "verification"}) + "\n")
    t = _full_transcript(tmp_path)
    assert scan.main([t, "s1"]) == 0


def test_quiet_without_done_claim(tmp_path, logs):
    t = _write_transcript(tmp_path / "t.jsonl", [_edit("/repo/scripts/spend/guard.py")])
    assert scan.main([t, "s1"]) == 0


def test_quiet_without_safety_touch(tmp_path, logs):
    t = _write_transcript(tmp_path / "t.jsonl", [_assistant_text("All done, fixed.")])
    assert scan.main([t, "s1"]) == 0


def test_fire_cap(tmp_path, logs):
    t = _full_transcript(tmp_path)
    fired = sum(scan.main([t, "s1"]) for _ in range(scan.MAX_FIRES_PER_SESSION + 2))
    assert fired == scan.MAX_FIRES_PER_SESSION


# --- fail-loud ---------------------------------------------------------------

def test_unreadable_transcript_fails_loud(tmp_path, logs, capsys):
    """Missing transcript → detector cannot rule out an unverified safety change.

    Contrast with gate-scan, which fails open. Spec 12: 'This is the one hook
    that should NOT fail open.'
    """
    assert scan.main([str(tmp_path / "missing.jsonl"), "s1"]) == 1
    assert "BROKEN" in capsys.readouterr().err


def test_fail_loud_is_capped_too(tmp_path, logs):
    missing = str(tmp_path / "missing.jsonl")
    fired = sum(scan.main([missing, "s1"]) for _ in range(scan.MAX_FIRES_PER_SESSION + 2))
    assert fired == scan.MAX_FIRES_PER_SESSION


def test_missing_args_fails_loud(logs, capsys):
    assert scan.main([]) == 1
    assert "BROKEN" in capsys.readouterr().err
