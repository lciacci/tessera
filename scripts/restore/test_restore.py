"""Tests for the restore receipt (T2, ADR-0015).

The load-bearing one is `test_end_to_end_*`: three parties (harness offer, model receipt,
Stop-hook scan) only mean something if the loop actually closes. Everything else guards a
specific way it degrades back into `restore_injected` — one party certifying itself.
"""
from __future__ import annotations

import json
import os
from argparse import Namespace

import pytest

import emit
import offer
import paths
import scan


@pytest.fixture(autouse=True)
def _isolated_root(tmp_path, monkeypatch):
    """TESSERA_ROOT is read at call time precisely so a test can do this."""
    monkeypatch.setenv("TESSERA_ROOT", str(tmp_path))
    (tmp_path / ".tessera" / "logs").mkdir(parents=True)
    yield tmp_path


def _log(session="s1"):
    return paths.log_path(session)


def _write(session, *events):
    with _log(session).open("a") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")


def _transcript(tmp_path, *, turns=0, edits=0):
    p = tmp_path / "t.jsonl"
    lines = []
    for i in range(turns):
        content = [{"name": "Edit", "type": "tool_use"}] if i < edits else [{"type": "text"}]
        lines.append(json.dumps({"type": "assistant", "message": {"content": content}}))
    p.write_text("\n".join(lines))
    return str(p)


# ── the harness side records only what it can know ────────────────────────────────────

def test_offer_claims_bytes_and_fields_but_never_delivery():
    ev = offer.build_offer({"goal": "g", "active_constraints": ["c"], "task_narrative": ""},
                           1234, session_id="s1")
    assert ev["type"] == "restore_offered"
    assert ev["data"]["bytes"] == 1234
    assert ev["data"]["fields"] == ["goal", "active_constraints"]  # empty narrative excluded
    blob = json.dumps(ev)
    assert "delivered" not in blob and "injected" not in blob, (
        "the harness must not claim delivery — that is the `restore_injected` bug verbatim")


def test_offer_is_silent_without_a_session_id(monkeypatch):
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    assert offer.main([]) == 0


def test_offer_is_silent_with_no_checkpoint(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s1")
    assert offer.main([]) == 0
    assert not _log().exists(), "nothing was offered, so nothing may be owed"


# ── the receipt cannot be a bare verdict ──────────────────────────────────────────────

def _args(**kw):
    base = dict(sufficient=False, insufficient=False, missing=None, used=None, rederived=None)
    base.update(kw)
    return Namespace(**base)


def test_bare_verdict_is_rejected():
    """THE guard. A one-keystroke --sufficient is as worthless as restore_injected."""
    assert "concrete" in emit.validate(_args(sufficient=True, used=""))
    assert "concrete" in emit.validate(_args(sufficient=True, used="fine"))


def test_evidence_is_required_in_BOTH_directions():
    """'it worked' needs proof as much as 'it did not' — otherwise the cheap path is a lie."""
    assert emit.validate(_args(insufficient=True, missing="goal", rederived="x")) is not None
    assert emit.validate(
        _args(sufficient=True, used="used the goal and all three constraints verbatim")) is None


def test_exactly_one_verdict_and_a_closed_missing_enum():
    assert "exactly one" in emit.validate(_args())
    assert "exactly one" in emit.validate(_args(sufficient=True, insufficient=True))
    ok_evidence = "had to re-read active.md to find what was already done"
    assert "--missing" in emit.validate(
        _args(insufficient=True, missing="vibes", rederived=ok_evidence))
    assert "meaningless" in emit.validate(
        _args(sufficient=True, missing="goal", used=ok_evidence))


# ── the backstop asks only when an answer could mean something ────────────────────────

def test_scan_silent_when_no_restore_was_offered(tmp_path):
    assert scan.verdict([], 50, 5) is None


def test_scan_silent_once_answered(tmp_path):
    events = [{"type": "restore_offered", "data": {}}, {"type": "restore_receipt"}]
    assert scan.verdict(events, 50, 5) is None


def test_scan_silent_on_a_session_that_never_loaded_the_checkpoint(tmp_path):
    """Decision (b): every session restores, so an unconditional demand taxes all ~121 and
    trains a reflex. A session with no edits and few turns has no evidence to give."""
    assert scan.verdict([{"type": "restore_offered", "data": {}}], turns=5, edits=0) is None


@pytest.mark.parametrize("turns,edits", [(5, 1), (25, 0)])
def test_scan_fires_on_an_unanswered_offer_after_real_work(turns, edits):
    msg = scan.verdict([{"type": "restore_offered", "data": {"bytes": 9, "fields": ["goal"]}}],
                       turns, edits)
    assert msg is not None
    assert "RESTORE RECEIPT OWED" in msg
    assert "insufficient' is a finding, not a failure" in msg, (
        "must not bias toward the reflexive answer it exists to prevent")


def test_scan_stops_nagging(tmp_path):
    events = [{"type": "restore_offered", "data": {}}] + \
             [{"type": "restore_scan_fired"}] * scan.MAX_FIRES_PER_SESSION
    assert scan.verdict(events, 50, 5) is None


def test_transcript_work_counts_turns_and_edits(tmp_path):
    assert scan.transcript_work(_transcript(tmp_path, turns=7, edits=3)) == (7, 3)
    assert scan.transcript_work("/nonexistent") == (0, 0)


# ── the loop must actually close ──────────────────────────────────────────────────────

def test_end_to_end_offer_then_nag_then_receipt_then_quiet(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s1")
    (tmp_path / ".mnemos").mkdir()
    (tmp_path / ".mnemos" / "checkpoint-latest.json").write_text(
        json.dumps({"goal": "g", "active_constraints": ["c"], "task_narrative": "n"}))
    transcript = _transcript(tmp_path, turns=30, edits=4)

    assert offer.main([]) == 0                                    # harness records the offer
    assert scan.main(["scan", transcript, "s1"]) == 1             # unanswered -> Stop blocks
    assert emit.main(["--sufficient", "--used",
                      "goal and all three constraints; resumed with no re-reading",
                      "--session", "s1"]) == 0                    # model answers
    assert scan.main(["scan", transcript, "s1"]) == 0             # and is not asked again

    types = [json.loads(l)["type"] for l in _log().read_text().splitlines()]
    assert types.count("restore_offered") == 1
    assert types.count("restore_receipt") == 1
    assert "restore_scan_fired" in types, "the ask itself must be auditable"


def test_end_to_end_records_an_insufficient_verdict(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s2")
    assert emit.main(["--insufficient", "--missing", "progress", "--rederived",
                      "checkpoint had the goal but not what was already done",
                      "--session", "s2"]) == 0
    ev = json.loads(_log("s2").read_text().splitlines()[-1])
    assert ev["data"] == {"sufficient": False, "missing": "progress",
                          "evidence": "checkpoint had the goal but not what was already done"}
