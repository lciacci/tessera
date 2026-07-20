"""Self-check for the gate-event recorder.

Run from this dir: python3 test_gate_emit.py

Asserts build_event produces a contract-shaped event (docs/contracts/gate-event.md):
discriminator, null should_fire, no invented score/threshold, optional note.
"""

import json

from emit import build_event


def demo() -> None:
    e = build_event(True, "refactor", "make contract canonical",
                    session_id="sess-1", ts="2026-06-23T18:25:00Z")

    # Top-level shape.
    assert e["type"] == "suggestion_gate"
    assert e["session_id"] == "sess-1"
    assert e["ts"] == "2026-06-23T18:25:00Z"
    assert e["source"] == "suggestion-gate-recorder"

    d = e["data"]
    assert d["fired"] is True                 # strict boolean, not truthy
    assert d["suggestion_kind"] == "refactor"
    assert d["note"] == "make contract canonical"
    assert d["should_fire"] is None           # labeled post-hoc, never invented
    assert "score" not in d                    # no scorer → absent, not faked
    assert "threshold" not in d

    # held + no note: note omitted entirely, fired is a real False.
    h = build_event(False, "compact", None, session_id="s")
    assert h["data"]["fired"] is False
    assert "note" not in h["data"]

    # retro: present-and-true only when set — absent means ts IS the gate moment.
    assert "retro" not in e["data"]
    r = build_event(True, "scope", None, session_id="s", retro=True)
    assert r["data"]["retro"] is True

    # Round-trips as one JSONL line.
    assert json.loads(json.dumps(e)) == e

    print("ok")


if __name__ == "__main__":
    demo()
