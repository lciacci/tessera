"""The spend audit writer's PATH — anchoring and session-id sanitisation.

There was no test file for `event.py` at all, which is part of how the anchoring bug
below survived: the spend suite tested the guard's decisions and the backstop's counter,
never where the record of those decisions was written.
"""
from __future__ import annotations

import json
from pathlib import Path

import event


def test_audit_path_is_anchored_to_the_repo_not_the_cwd(tmp_path, monkeypatch):
    """`guard.py` runs on PreToolUse(Bash), so its cwd is the SESSION cwd — which any
    `cd` moves. With `Path(".tessera/logs")` a `spend_denied` emitted after the agent
    changed directory landed in a subdirectory, invisible to every reader anchored at the
    repo root.

    This is the same defect `bin/tessera-degraded` records fixing for the REPORTER on
    2026-07-26 ("the spend guard's fail-open was correctly reported, into
    `scripts/.tessera/logs/`, where P13 will never see it"). The audit writer for the
    spend control itself was left behind — standing pattern #11."""
    monkeypatch.setenv("TESSERA_ROOT", str(tmp_path))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "sess-anchor")
    monkeypatch.chdir(tmp_path / "..") if (tmp_path / "..").exists() else None

    path = event.emit("spend_denied", {"probe": True})
    assert path is not None
    assert path.is_absolute(), "a relative audit path follows the cwd"
    assert path == tmp_path / ".tessera" / "logs" / "sess-anchor.jsonl"
    assert json.loads(path.read_text().splitlines()[0])["type"] == "spend_denied"


def test_a_session_id_that_is_a_path_cannot_escape_the_log_dir(tmp_path, monkeypatch):
    """The observatory's accepted-risk entry fired its own revisit trigger on
    2026-08-10. Severity is unchanged — every source is the harness or this repo's own
    hooks — but the "harness-only" premise it rested on is no longer true, so the
    reduction to a single path component is applied here rather than argued about."""
    monkeypatch.setenv("TESSERA_ROOT", str(tmp_path))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "../../../escaped")

    path = event.emit("spend_denied", {"probe": True})
    assert path is not None
    assert ".." not in str(path)
    assert path.parent == tmp_path / ".tessera" / "logs"
    assert path.name == "escaped.jsonl"


def test_no_session_id_writes_nothing_rather_than_guessing(tmp_path, monkeypatch):
    """The log is session-keyed; without a key there is no honest place to put the row.
    Returning None is the existing contract — pinned so a future 'unknown.jsonl'
    fallback has to be a deliberate decision."""
    monkeypatch.setenv("TESSERA_ROOT", str(tmp_path))
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    assert event.emit("spend_denied", {"probe": True}) is None


def test_an_audit_failure_never_raises(tmp_path, monkeypatch):
    """"Never raises: an audit-log failure must never change a spend decision" is the
    function's own contract. Point the root at an unwritable location and confirm."""
    monkeypatch.setenv("TESSERA_ROOT", "/proc/nonexistent-unwritable")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "sess-x")
    assert event.emit("spend_denied", {"probe": True}) is None


def test_emit_accepts_an_explicit_session(tmp_path, monkeypatch):
    """ADR-0016 made `dismiss` human-only via the guard's deny list; emit() keyed on
    CLAUDE_CODE_SESSION_ID, which exists only in the AGENT's environment. The two halves excluded
    each other and the failure was silent. `--session` is the bridge."""
    import event
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    monkeypatch.setenv("TESSERA_SPEND_LOGS", str(tmp_path / ".tessera" / "logs"))
    assert event.emit("spend_dismissed", {"x": 1}) is None, "no session and no override -> no write"
    p = event.emit("spend_dismissed", {"x": 1}, session_id="explicit-session")
    assert p is not None and p.name == "explicit-session.jsonl"
