"""Checks for scripts/degraded_ack.py. Run: pytest scripts/test_degraded_ack.py

The P13 half of this feature is tested in test_tessera_watch.py; this is the producer.
Every test plants the failure it guards — a guard tested only against the fixed code is
decoration that passes (standing pattern #10).
"""
import json
import os
from pathlib import Path

import degraded_ack as da


def _root(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setenv("TESSERA_ROOT", str(tmp_path))
    (tmp_path / ".tessera" / "logs").mkdir(parents=True)
    return tmp_path


def _write(root: Path, name: str, *events) -> None:
    (root / ".tessera" / "logs" / name).write_text(
        "".join(json.dumps(e) + "\n" for e in events))


def _degraded(component="standing-patterns", reason="block-missing") -> dict:
    return {"type": "degraded", "ts": "2026-08-16T10:00:00Z",
            "data": {"component": component, "reason": reason}}


def _args(component="standing-patterns", reason="block-missing", note="x" * 40):
    class A:
        pass
    a = A()
    a.component, a.reason, a.note = component, reason, note
    return a


def test_root_ignores_cwd_and_honours_the_override(tmp_path, monkeypatch):
    """The anchor must match the key. These write .tessera/logs/<session>.jsonl, keyed by
    session, so resolving against cwd is wrong by construction — 2026-07-24 split the gate
    log 4/2 exactly that way and 2026-07-26 let a `cd` silence the spend guard."""
    monkeypatch.chdir(tmp_path)
    assert da.root() == Path(__file__).resolve().parents[1]
    monkeypatch.setenv("TESSERA_ROOT", str(tmp_path))
    assert da.root() == tmp_path


def test_known_pairs_collects_across_logs_and_ignores_other_event_types(tmp_path, monkeypatch):
    root = _root(tmp_path, monkeypatch)
    _write(root, "a.jsonl", _degraded(), {"type": "gate", "data": {"kind": "design"}})
    _write(root, "b.jsonl", _degraded("spend-guard", "guard-missing"))
    _write(root, "watch.jsonl", _degraded("never", "read"))
    assert da.known_pairs() == {
        ("standing-patterns", "block-missing"), ("spend-guard", "guard-missing")}


def test_an_ack_naming_no_recorded_degraded_event_is_refused(tmp_path, monkeypatch):
    """THE TYPO GUARD, and the reason it is worth code rather than a docstring.

    A mistyped --component/--reason writes a watermark for a pair that has never failed.
    It suppresses nothing today, so nothing looks wrong — and it sits in the log
    indistinguishable from a real ack, ready to be read as a deliberate disposition later.
    That is a fail-open of the quietest kind, in the verb built to reduce noise.
    """
    root = _root(tmp_path, monkeypatch)
    _write(root, "a.jsonl", _degraded())
    err = da.validate(_args(component="standing-pattern"), da.known_pairs())   # missing 's'
    assert err and "refusing to watermark nothing" in err
    assert "standing-patterns/block-missing" in err, "the error must name what IS on record"
    assert da.validate(_args(), da.known_pairs()) is None


def test_a_bare_ack_with_no_reasoning_is_refused(tmp_path, monkeypatch):
    """Same argument as restore/emit.py's evidence floor: a one-keystroke disposition is
    as worthless as the self-reported `restore_injected` line was. The floor is a speed
    bump, not a wall — it cannot stop a determined filler and is not trying to."""
    root = _root(tmp_path, monkeypatch)
    _write(root, "a.jsonl", _degraded())
    err = da.validate(_args(note="fixed"), da.known_pairs())
    assert err and "reasoning" in err


def test_main_writes_a_watermark_event_to_the_session_log(tmp_path, monkeypatch):
    root = _root(tmp_path, monkeypatch)
    _write(root, "a.jsonl", _degraded())
    rc = da.main(["--component", "standing-patterns", "--reason", "block-missing",
                  "--note", "block re-anchored in active.md; re-planted and verified",
                  "--session", "sess1"])
    assert rc == 0
    written = [json.loads(line) for line in
               (root / ".tessera" / "logs" / "sess1.jsonl").read_text().splitlines()]
    assert len(written) == 1
    event = written[0]
    assert event["type"] == "degraded_ack"
    assert event["source"] == "model"
    assert event["data"]["component"] == "standing-patterns"
    assert event["ts"].endswith("Z"), "P13 parses Z; a naive stamp is the silent-miss case"


def test_main_refuses_without_a_session_id(tmp_path, monkeypatch):
    """The log is keyed by session. Writing to a file named for the empty string would be
    a real event nothing ever reads — see degraded-event.md's named blind spot."""
    root = _root(tmp_path, monkeypatch)
    _write(root, "a.jsonl", _degraded())
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    rc = da.main(["--component", "standing-patterns", "--reason", "block-missing",
                  "--note", "block re-anchored in active.md; re-planted and verified"])
    assert rc == 2


def test_main_refuses_an_unknown_pair_before_writing_anything(tmp_path, monkeypatch):
    """Validation must precede the write, or the refusal still leaves the watermark."""
    root = _root(tmp_path, monkeypatch)
    _write(root, "a.jsonl", _degraded())
    rc = da.main(["--component", "typo", "--reason", "block-missing",
                  "--note", "this should not be recorded anywhere at all",
                  "--session", "sess2"])
    assert rc == 2
    assert not (root / ".tessera" / "logs" / "sess2.jsonl").exists()
