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
    """Point the store at a tmp dir via TESSERA_ROOT — the env override, not a patched
    module constant. This is what call-time resolution BUYS: the old fixture had to
    monkeypatch `esc.ESCALATIONS`, which worked only because the constant was bound at
    import, and that same binding is what made the real tool read a different queue from
    every subdirectory. The fixture now exercises the production path."""
    monkeypatch.setenv("TESSERA_ROOT", str(tmp_path))
    return tmp_path / ".tessera" / "escalations"


def test_the_store_is_anchored_to_the_repo_not_the_cwd(tmp_path, monkeypatch):
    """The defect the fixture above used to hide: `.tessera/escalations` was a RELATIVE
    path, so `tessera-escalate list` from any subdirectory read an empty queue and
    printed 'No open escalations ✓' while real packets sat unread at the root.
    (arbiter 2026-08-10.)"""
    monkeypatch.delenv("TESSERA_ROOT", raising=False)
    monkeypatch.chdir(tmp_path)
    resolved = esc.escalations_dir()
    assert resolved.is_absolute()
    assert tmp_path not in resolved.parents, "store followed the cwd"
    assert resolved == Path(esc.__file__).resolve().parent.parent / ".tessera" / "escalations"


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


def test_two_raises_in_the_same_second_do_not_overwrite(root):
    """The id is second-resolution and the write used to be `write_text`, so a second
    raise inside one second silently replaced the first — in the tool whose whole
    contract is that nothing is dropped without saying so. (arbiter 2026-08-10.)"""
    a = esc.raise_packet(_args(summary="first"), root=root)
    b = esc.raise_packet(_args(summary="second"), root=root)
    c = esc.raise_packet(_args(summary="third"), root=root)
    assert len({a["id"], b["id"], c["id"]}) == 3, "ids collided"
    on_disk = sorted(p.name for p in root.glob("*.json"))
    assert len(on_disk) == 3, on_disk
    summaries = {json.loads((root / f"{p['id']}.json").read_text())["summary"]
                 for p in (a, b, c)}
    assert summaries == {"first", "second", "third"}


def test_resolving_twice_refuses_rather_than_overwriting_the_decision(root):
    """`resolved:<note>` is the record of a human decision. Overwriting it destroys the
    original with no trace, so the second call must refuse."""
    packet = esc.raise_packet(_args(), root=root)
    esc.resolve_packet(packet["id"], "the real decision", root=root)
    with pytest.raises(esc.AlreadyDisposed):
        esc.resolve_packet(packet["id"], "overwrite attempt", root=root)
    on_disk = json.loads((root / f"{packet['id']}.json").read_text())
    assert on_disk["status"] == "resolved:the real decision"


@pytest.mark.parametrize("bad", ["../../../etc/passwd", "/etc/passwd", "a/b", ""])
def test_an_id_that_is_a_path_is_refused(root, bad):
    """`root / f"{id}.json"` follows `..` out of the store, so a caller-supplied id could
    read and then REWRITE an arbitrary file. An id is not a path."""
    assert esc.resolve_packet(bad, "x", root=root) is None


def test_missing_status_counts_as_open(root):
    """Unknown counts as needs-attention, never silently dropped (findings rule)."""
    assert esc._state({"id": "x"}) == "open"


def test_load_all_survives_a_corrupt_packet(root):
    esc.raise_packet(_args(), root=root)
    (root / "corrupt.json").write_text("{not json")
    assert len(esc.load_all(root=root)) == 1


def test_list_exits_1_while_any_open(root, monkeypatch, capsys):
    esc.raise_packet(_args(), root=root)
    assert esc.cmd_list(argparse.Namespace(all=False, json=False)) == 1
    assert "1 open" in capsys.readouterr().out


def test_list_exits_0_when_queue_is_clear(root, monkeypatch, capsys):
    packet = esc.raise_packet(_args(), root=root)
    esc.resolve_packet(packet["id"], "done", root=root)
    assert esc.cmd_list(argparse.Namespace(all=False, json=False)) == 0
    assert "No open escalations" in capsys.readouterr().out


def test_resolved_hidden_by_default_shown_with_all(root, monkeypatch, capsys):
    packet = esc.raise_packet(_args(), root=root)
    esc.resolve_packet(packet["id"], "done", root=root)
    esc.cmd_list(argparse.Namespace(all=True, json=True))
    assert len(json.loads(capsys.readouterr().out)) == 1
