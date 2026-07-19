#!/usr/bin/env python3
"""Tests for should_fire passive extraction (scripts/gate/label.py).

The qwen boundary is mocked — no network in CI. Covers the disposition join,
the label write-back, and the two invariants that matter: a classifier verdict
never overwrites a human label, and Ollama junk leaves should_fire null.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import label  # noqa: E402


def _yes(prompt, **kw):
    return "yes"


def _no(prompt, **kw):
    return "no"


def _dt(s):
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def test_parse_ts_handles_z_and_offset_and_junk():
    assert label._parse_ts("2026-07-19T16:00:00Z") is not None
    assert label._parse_ts("2026-07-19T16:00:00.5+00:00") is not None
    assert label._parse_ts("not-a-date") is None
    assert label._parse_ts(None) is None


def test_find_disposition_picks_first_turn_after_gate():
    turns = [(_dt("2026-07-19T15:00:00"), "before"),
             (_dt("2026-07-19T16:05:00"), "go ahead"),
             (_dt("2026-07-19T16:10:00"), "later")]
    gate = _dt("2026-07-19T16:00:00")
    assert label.find_disposition(turns, gate) == "go ahead"


def test_find_disposition_none_when_nothing_after():
    turns = [(_dt("2026-07-19T15:00:00"), "before")]
    assert label.find_disposition(turns, _dt("2026-07-19T16:00:00")) is None


def test_human_turns_excludes_injected_and_tool_results(tmp_path):
    t = tmp_path / "t.jsonl"
    t.write_text("\n".join(json.dumps(e) for e in [
        {"type": "user", "timestamp": "2026-07-19T16:00:00Z",
         "message": {"content": "real prompt"}},
        {"type": "user", "isMeta": True, "timestamp": "2026-07-19T16:01:00Z",
         "message": {"content": "hook feedback"}},
        {"type": "user", "promptSource": "system", "timestamp": "2026-07-19T16:02:00Z",
         "message": {"content": "task notification"}},
        {"type": "user", "timestamp": "2026-07-19T16:03:00Z",
         "message": {"content": [{"type": "tool_result"}]}},
    ]))
    turns = label.human_turns(str(t))
    assert [x[1] for x in turns] == ["real prompt"]


def test_classify_parses_and_fails_open():
    assert label.classify_should_fire("n", "I choose A", generate=_yes) is True
    assert label.classify_should_fire("n", "just go", generate=_no) is False
    assert label.classify_should_fire("n", "x", generate=lambda *a, **k: "") is None
    thinker = lambda *a, **k: "<think>hmm</think> yes"
    assert label.classify_should_fire("n", "x", generate=thinker) is True


def _gate(ts, note, **data):
    return {"type": "suggestion_gate", "ts": ts, "session_id": "s",
            "data": {"fired": True, "suggestion_kind": "k", "note": note,
                     "should_fire": None, **data}}


def test_label_one_fills_null_gate():
    ev = _gate("2026-07-19T16:00:00Z", "do X or Y?")
    turns = [(_dt("2026-07-19T16:05:00"), "let's do Y")]
    assert label._label_one(ev, turns, generate=_yes) is True
    d = ev["data"]
    assert d["should_fire"] is True
    assert d["should_fire_basis"] == "let's do Y"
    assert d["labeled_by"] == "classifier"
    assert "labeled_ts" in d


def test_label_one_never_overwrites_human_label():
    # should_fire already set by a human — must not touch it.
    ev = _gate("2026-07-19T16:00:00Z", "n", should_fire=False,
               should_fire_basis="human said no")
    turns = [(_dt("2026-07-19T16:05:00"), "obviously yes")]
    assert label._label_one(ev, turns, generate=_yes) is False
    assert ev["data"]["should_fire"] is False
    assert ev["data"]["should_fire_basis"] == "human said no"


def test_label_one_skips_prior_classifier_pass():
    ev = _gate("2026-07-19T16:00:00Z", "n", should_fire=True, labeled_by="classifier")
    assert label._label_one(ev, [], generate=_yes) is False


def test_label_one_no_disposition_is_noop():
    ev = _gate("2026-07-19T16:00:00Z", "n")
    assert label._label_one(ev, [], generate=_yes) is False
    assert ev["data"]["should_fire"] is None


def test_label_gate_log_end_to_end(tmp_path):
    log = tmp_path / "s.jsonl"
    lines = [
        _gate("2026-07-19T16:00:00Z", "null gate"),
        _gate("2026-07-19T16:00:00Z", "human gate", should_fire=True,
              should_fire_basis="kept"),
        {"ts": "2026-07-19T16:00:00Z", "fired": []},  # scan record, not a gate
    ]
    log.write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    turns = [(_dt("2026-07-19T16:05:00"), "go with option A")]
    n = label.label_gate_log(log, turns, generate=_yes)
    assert n == 1
    got = [json.loads(x) for x in log.read_text().splitlines()]
    assert got[0]["data"]["should_fire"] is True          # null gate labeled
    assert got[0]["data"]["labeled_by"] == "classifier"
    assert got[1]["data"]["should_fire_basis"] == "kept"  # human gate untouched
    assert "labeled_by" not in got[1]["data"]
    assert got[2] == {"ts": "2026-07-19T16:00:00Z", "fired": []}  # scan line intact


def test_label_gate_log_idempotent(tmp_path):
    log = tmp_path / "s.jsonl"
    log.write_text(json.dumps(_gate("2026-07-19T16:00:00Z", "g")) + "\n")
    turns = [(_dt("2026-07-19T16:05:00"), "yes do it")]
    assert label.label_gate_log(log, turns, generate=_yes) == 1
    assert label.label_gate_log(log, turns, generate=_yes) == 0  # already labeled


# --- eval_should_fire ---------------------------------------------------
import eval_should_fire as ev  # noqa: E402


def _labeled(human, basis="x"):
    return {"note": "n", "should_fire": human, "should_fire_basis": basis}


def test_evaluate_confusion_matrix():
    gates = [_labeled(True), _labeled(True), _labeled(False)]
    # classifier says yes,no,no → TP, FN, TN
    verdicts = iter(["yes", "no", "no"])
    gen = lambda *a, **k: next(verdicts)
    m = ev.evaluate(gates, generate=gen)
    assert (m["tp"], m["fn"], m["tn"], m["fp"]) == (1, 1, 1, 0)
    assert m["mismatches"][0][0] is True and m["mismatches"][0][1] is False


def test_evaluate_skips_classifier_junk():
    m = ev.evaluate([_labeled(True)], generate=lambda *a, **k: "")
    assert m["skipped"] == 1 and m["tp"] == 0
