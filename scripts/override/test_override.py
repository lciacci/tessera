"""Tests for the override mechanism: scanner, emitter, report."""

from __future__ import annotations

import json

import pytest

from emit import Override, build_event
from report import format_table, load_overrides, parse_since
from scan import find_overrides, scan_files


# ── scanner ──────────────────────────────────────────────────────────────────

def test_find_tdd_skip_reason():
    src = '# tessera:tdd-skip-reason="DI scaffolding"\n'
    [ov] = find_overrides(src, "a.py")
    assert (ov.rule, ov.annotation_kind, ov.line, ov.reason) == (
        "tdd", "skip-reason", 1, "DI scaffolding")


def test_find_security_skip_reason_in_js_comment():
    [ov] = find_overrides('  // tessera:security-skip-reason="legacy ORM"', "x.js")
    assert ov.rule == "security" and ov.reason == "legacy ORM"


def test_find_ignore_line_has_empty_reason():
    [ov] = find_overrides("foo() // tessera:quality-gates-ignore-line", "x.ts")
    assert ov.annotation_kind == "ignore-line" and ov.reason == ""


def test_line_numbers_and_multiple():
    src = "clean\n# tessera:tdd-skip-reason=\"a\"\nmore\n// tessera:security-ignore-line\n"
    found = find_overrides(src, "f")
    assert [(o.line, o.rule) for o in found] == [(2, "tdd"), (4, "security")]


def test_no_false_positive_on_plain_text():
    assert find_overrides("just a normal tdd comment about tessera\n", "f") == []


def test_scan_files_missing_file_is_silent(tmp_path):
    assert scan_files([str(tmp_path / "nope.py")]) == []


# ── emitter ──────────────────────────────────────────────────────────────────

def test_build_event_shape():
    ov = Override("tdd", "skip-reason", "a.py", 42, "why")
    ev = build_event(ov, session_id="sess", ts="2026-06-26T00:00:00Z")
    assert ev["type"] == "override"
    assert ev["source"] == "override-scanner"
    assert ev["session_id"] == "sess"
    assert ev["data"] == {
        "rule": "tdd", "annotation_kind": "skip-reason",
        "file": "a.py", "line": 42, "reason": "why",
    }
    json.dumps(ev)  # serializable


# ── report ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("s,seconds", [
    ("1w", 7 * 86400), ("30d", 30 * 86400), ("24h", 86400)])
def test_parse_since_ok(s, seconds):
    assert parse_since(s).total_seconds() == seconds


def test_parse_since_rejects_junk():
    with pytest.raises(ValueError):
        parse_since("soon")


def _write_log(d, name, events):
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text("\n".join(json.dumps(e) for e in events) + "\n")


def test_load_overrides_filters_type_and_window(tmp_path):
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    recent = now.isoformat().replace("+00:00", "Z")
    old = (now - timedelta(days=400)).isoformat().replace("+00:00", "Z")
    _write_log(tmp_path, "s.jsonl", [
        {"type": "override", "ts": recent, "data": {"rule": "tdd", "file": "a", "line": 1}},
        {"type": "override", "ts": old, "data": {"rule": "tdd", "file": "b", "line": 2}},
        {"type": "suggestion_gate", "ts": recent, "data": {}},  # wrong type
    ])
    rows = load_overrides(tmp_path, now - timedelta(weeks=1))
    assert len(rows) == 1 and rows[0]["file"] == "a"


def test_format_table_empty():
    assert format_table([]) == "No overrides in window."
