#!/usr/bin/env python3
"""Tests for bin/tessera-verify — the falsifier, invocable (spec 12).

All tests are API-free: the claude spawn is monkeypatched; worktree tests use a
real throwaway git repo. The one thing these tests cannot certify is the
verifier's judgment — that is what --self-test and the recorded manual
acceptance run are for (spec 12 criteria 1 and 5).
"""
import importlib.machinery
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_loader(
    "tessera_verify",
    importlib.machinery.SourceFileLoader(
        "tessera_verify", str(Path(__file__).parent.parent / "bin" / "tessera-verify")
    ),
)
tv = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tv)


@pytest.fixture()
def logs(tmp_path, monkeypatch):
    d = tmp_path / "logs"
    monkeypatch.setattr(tv, "LOGS", d)
    return d


# --- prompt ------------------------------------------------------------------

def test_prompt_contains_every_claim():
    p = tv.build_prompt(["claim A", "claim B"])
    assert "claim A" in p and "claim B" in p


def test_prompt_carries_the_attack_instructions():
    p = tv.build_prompt(["x"]).lower()
    assert "false" in p            # assume claims false until proven
    assert "comment" in p          # comments are untrustworthy
    assert "landmine" in p         # plant a case the checker should catch
    assert "do not fix" in p       # report only
    assert "verdict 1:" in p       # strict output format


# --- verdict parsing ----------------------------------------------------------

def test_parse_verdicts_reads_all_claims():
    out = (
        "VERDICT 1: CONFIRMED\nEVIDENCE 1: ran X, saw Y\n"
        "VERDICT 2: REFUTED\nEVIDENCE 2: ran Z, guard allowed the boot\n"
    )
    v = tv.parse_verdicts(out, 2)
    assert v[0] == {"verdict": "CONFIRMED", "evidence": "ran X, saw Y"}
    assert v[1]["verdict"] == "REFUTED"


def test_missing_verdict_is_no_verdict():
    v = tv.parse_verdicts("VERDICT 1: CONFIRMED\n", 2)
    assert v[1]["verdict"] == "NO_VERDICT"


def test_garbage_output_is_all_no_verdict():
    v = tv.parse_verdicts("I feel good about this change!", 1)
    assert v[0]["verdict"] == "NO_VERDICT"


# --- event -------------------------------------------------------------------

def test_event_shape(logs):
    ev = tv.build_event(
        claims=["c1"],
        verdicts=[{"verdict": "REFUTED", "evidence": "e"}],
        session_id="s1",
    )
    assert ev["type"] == "verification"
    assert ev["session_id"] == "s1"
    assert ev["source"] == "tessera-verify"
    assert ev["data"]["claims"][0] == {"text": "c1", "verdict": "REFUTED", "evidence": "e"}
    assert ev["data"]["skipped"] is False


def test_append_event_writes_session_log(logs):
    ev = tv.build_event(claims=[], verdicts=[], session_id="s1", skipped=True, reason="r")
    path = tv.append_event(ev)
    assert path == logs / "s1.jsonl"
    on_disk = json.loads(path.read_text())
    assert on_disk["data"]["skipped"] is True
    assert on_disk["data"]["reason"] == "r"


# --- stats -------------------------------------------------------------------

def _log_verification(logs, sid, verdicts, skipped=False):
    ev = tv.build_event(
        claims=[f"c{i}" for i in range(len(verdicts))],
        verdicts=[{"verdict": v, "evidence": ""} for v in verdicts],
        session_id=sid,
        skipped=skipped,
    )
    tv.append_event(ev)


def test_stats_counts_and_author_error_rate(logs):
    _log_verification(logs, "s1", ["CONFIRMED", "REFUTED"])
    _log_verification(logs, "s2", ["PARTIAL"])
    _log_verification(logs, "s3", [], skipped=True)
    s = tv.stats_summary(logs)
    assert s["confirmed"] == 1
    assert s["refuted"] == 1
    assert s["partial"] == 1
    assert s["skips"] == 1
    # author error rate: (refuted + partial) / judged
    assert s["author_error_rate"] == pytest.approx(2 / 3)


def test_stats_empty_logs(logs):
    s = tv.stats_summary(logs)
    assert s["author_error_rate"] is None


# --- worktree ----------------------------------------------------------------

@pytest.fixture()
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=r, check=True)
    subprocess.run(["git", "-C", str(r), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(r), "config", "user.name", "t"], check=True)
    (r / "tracked.txt").write_text("v1\n")
    subprocess.run(["git", "-C", str(r), "add", "."], check=True)
    subprocess.run(["git", "-C", str(r), "commit", "-qm", "init"], check=True)
    return r


def test_worktree_carries_uncommitted_and_untracked_state(repo):
    (repo / "tracked.txt").write_text("v2-uncommitted\n")
    (repo / "untracked.txt").write_text("new\n")
    wt = tv.make_worktree(repo)
    try:
        assert (wt / "tracked.txt").read_text() == "v2-uncommitted\n"
        assert (wt / "untracked.txt").read_text() == "new\n"
    finally:
        tv.remove_worktree(repo, wt)
    assert not wt.exists()
    # source tree untouched
    assert (repo / "tracked.txt").read_text() == "v2-uncommitted\n"


def test_worktree_mutations_never_reach_source_tree(repo):
    wt = tv.make_worktree(repo)
    try:
        (wt / "tracked.txt").write_text("LANDMINE\n")
    finally:
        tv.remove_worktree(repo, wt)
    assert (repo / "tracked.txt").read_text() == "v1\n"


# --- run / skip / self-test end-to-end (spawn mocked) --------------------------

def _mock_spawn(monkeypatch, output):
    calls = {}

    def fake(prompt, cwd, model, timeout):
        calls["prompt"], calls["cwd"] = prompt, cwd
        return output

    monkeypatch.setattr(tv, "spawn_verifier", fake)
    return calls


def _mock_worktree(monkeypatch, tmp_path):
    wt = tmp_path / "wt"
    wt.mkdir()
    monkeypatch.setattr(tv, "make_worktree", lambda root: wt)
    monkeypatch.setattr(tv, "remove_worktree", lambda root, w: None)
    return wt


def test_run_all_confirmed_exits_0(tmp_path, logs, monkeypatch):
    _mock_worktree(monkeypatch, tmp_path)
    _mock_spawn(monkeypatch, "VERDICT 1: CONFIRMED\nEVIDENCE 1: ok\n")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s1")
    assert tv.main(["--claim", "the guard blocks unauthorized boots"]) == 0
    logged = json.loads((logs / "s1.jsonl").read_text())
    assert logged["data"]["claims"][0]["verdict"] == "CONFIRMED"


def test_run_refuted_exits_1_and_logs(tmp_path, logs, monkeypatch):
    _mock_worktree(monkeypatch, tmp_path)
    _mock_spawn(monkeypatch, "VERDICT 1: REFUTED\nEVIDENCE 1: boot proceeded\n")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s1")
    assert tv.main(["--claim", "the guard blocks unauthorized boots"]) == 1


def test_no_verdict_exits_1(tmp_path, logs, monkeypatch):
    """A verifier that returns nothing usable must not read as green."""
    _mock_worktree(monkeypatch, tmp_path)
    _mock_spawn(monkeypatch, "everything seems fine")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s1")
    assert tv.main(["--claim", "x"]) == 1


def test_skip_records_skipped_event(logs, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s1")
    assert tv.main(["skip", "--reason", "detector over-count: only a clarifying question"]) == 0
    logged = json.loads((logs / "s1.jsonl").read_text())
    assert logged["data"]["skipped"] is True


def test_self_test_passes_when_landmine_refuted(tmp_path, logs, monkeypatch):
    _mock_worktree(monkeypatch, tmp_path)
    calls = _mock_spawn(monkeypatch, "VERDICT 1: REFUTED\nEVIDENCE 1: file is 15k bytes\n")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s1")
    assert tv.main(["--self-test"]) == 0
    assert "doccheck.py" in calls["prompt"]  # the planted-false claim reached the verifier


def test_self_test_fails_when_landmine_survives(tmp_path, logs, monkeypatch):
    """CONFIRMED on a known-false claim means the verifier is broken."""
    _mock_worktree(monkeypatch, tmp_path)
    _mock_spawn(monkeypatch, "VERDICT 1: CONFIRMED\nEVIDENCE 1: looks empty to me\n")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s1")
    assert tv.main(["--self-test"]) == 1
