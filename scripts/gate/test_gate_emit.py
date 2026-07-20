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

    # Kind vocabulary (spec 15): CLI rejects unknown kinds, fail-closed, exit 2.
    import os
    from emit import KINDS, main
    os.environ.setdefault("CLAUDE_CODE_SESSION_ID", "test-session")
    assert main(["--fired", "--kind", "refactor", "--dry-run"]) == 2  # pre-enum kind
    assert main(["--fired", "--kind", KINDS[0], "--dry-run"]) == 0

    # Remap: legacy → canonical with raw kept; canonical and unknown untouched.
    from remap_kind import remap_line
    legacy = json.dumps({"type": "suggestion_gate", "data":
                         {"suggestion_kind": "design-decision", "should_fire": None}})
    new, change = remap_line(legacy)
    d = json.loads(new)["data"]
    assert d["suggestion_kind"] == "design" and d["suggestion_kind_raw"] == "design-decision"
    assert change == "design-decision→design"
    assert remap_line(new)[1] is None                 # idempotent — _raw present
    mystery = json.dumps({"type": "suggestion_gate", "data": {"suggestion_kind": "zzz"}})
    assert remap_line(mystery) == (mystery, "unknown:zzz")  # reported, not guessed

    # Round-trips as one JSONL line.
    assert json.loads(json.dumps(e)) == e

    print("ok")


if __name__ == "__main__":
    demo()
