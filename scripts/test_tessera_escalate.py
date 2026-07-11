#!/usr/bin/env python3
"""Tests for tessera-escalate — the gate's asynchronous form (spec 07)."""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_loader(
    "tessera_escalate",
    importlib.machinery.SourceFileLoader(
        "tessera_escalate", str(Path(__file__).parent.parent / "bin" / "tessera-escalate")
    ),
)
esc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(esc)


@pytest.fixture()
def root(tmp_path, monkeypatch):
    d = tmp_path / "escalations"
    monkeypatch.setattr(esc, "ESCALATIONS", d)
    return d


def _args(**kw):
    base = dict(category="test", summary="stuck", tried=["tried X — failed"], option=[],
                ref=[], severity="blocking")
    base.update(kw)
    return argparse.Namespace(**base)


def test_raise_writes_open_packet(root):
    packet = esc.raise_packet(_args(), root=root)
    on_disk = json.loads((root / f"{packet['id']}.json").read_text())
    assert on_disk["status"] == "open"
    assert on_disk["tried"] == ["tried X — failed"]
    assert on_disk["severity"] == "blocking"


def test_tried_is_required():
    """A packet with no attempts is a complaint, not an escalation."""
    assert esc.cmd_raise(_args(tried=[])) == 2


def test_resolve_records_the_decision(root):
    packet = esc.raise_packet(_args(), root=root)
    resolved = esc.resolve_packet(packet["id"], "reverted, see abc123", root=root)
    assert resolved["status"] == "resolved:reverted, see abc123"
    assert "resolved_ts" in resolved
    assert esc._state(resolved) == "resolved"


def test_resolve_unknown_id_is_an_error(root):
    assert esc.resolve_packet("esc-nope", "x", root=root) is None


def test_missing_status_counts_as_open(root):
    """Unknown counts as needs-attention, never silently dropped (findings rule)."""
    assert esc._state({"id": "x"}) == "open"


def test_load_all_survives_a_corrupt_packet(root):
    esc.raise_packet(_args(), root=root)
    (root / "corrupt.json").write_text("{not json")
    assert len(esc.load_all(root=root)) == 1


def test_list_exits_1_while_any_open(root, monkeypatch, capsys):
    monkeypatch.setattr(esc, "ESCALATIONS", root)
    esc.raise_packet(_args(), root=root)
    assert esc.cmd_list(argparse.Namespace(all=False, json=False)) == 1
    assert "1 open" in capsys.readouterr().out


def test_list_exits_0_when_queue_is_clear(root, monkeypatch, capsys):
    monkeypatch.setattr(esc, "ESCALATIONS", root)
    packet = esc.raise_packet(_args(), root=root)
    esc.resolve_packet(packet["id"], "done", root=root)
    assert esc.cmd_list(argparse.Namespace(all=False, json=False)) == 0
    assert "No open escalations" in capsys.readouterr().out


def test_resolved_hidden_by_default_shown_with_all(root, monkeypatch, capsys):
    monkeypatch.setattr(esc, "ESCALATIONS", root)
    packet = esc.raise_packet(_args(), root=root)
    esc.resolve_packet(packet["id"], "done", root=root)
    esc.cmd_list(argparse.Namespace(all=True, json=True))
    assert len(json.loads(capsys.readouterr().out)) == 1
