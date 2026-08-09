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


def test_prompt_names_the_verdict_file_and_says_why():
    """The file channel only works if the verifier is told the exact path AND told why the
    final message cannot be trusted. A model that thinks the two channels are equivalent will
    skip the one that costs it a tool call."""
    p = tv.build_prompt(["x"], "/tmp/wt/tessera-verdicts.json")
    assert "/tmp/wt/tessera-verdicts.json" in p
    assert "stop hook" in p.lower()      # WHY the final message is unreliable
    assert '"verdicts"' in p             # the exact JSON shape


# --- the verdict FILE channel (2026-07-26) ------------------------------------------
#
# Three real runs returned zero usable verdicts. The verifier had done the work every time;
# its own verify-scan Stop hook fired afterwards and that skip acknowledgment replaced the
# final message, which is what parse_verdicts reads. A file cannot be overwritten that way.


def _write_verdicts(path, entries):
    path.write_text(json.dumps({"verdicts": entries}))


def _last_event(logs_dir):
    return json.loads((logs_dir / "s1.jsonl").read_text().splitlines()[-1])


def _run_with_fake_verifier(tmp_path, monkeypatch, *, stdout, verdict_file,
                            preexisting_verdict_file=None, claims=("a claim",)):
    """Drive cmd_run with a stubbed worktree and spawn.

    `preexisting_verdict_file` is planted BEFORE main() runs, standing in for the stale file
    that make_worktree would copy in from the source tree. `verdict_file` is written by the
    fake spawn, standing in for the verifier writing it during its turn. The distinction is
    the whole point of the unlink guard.
    """
    wt = tmp_path / "wt"
    wt.mkdir(exist_ok=True)
    target = wt / tv.VERDICT_FILENAME
    if preexisting_verdict_file is not None:
        _write_verdicts(target, preexisting_verdict_file)

    monkeypatch.setattr(tv, "make_worktree", lambda root: wt)
    monkeypatch.setattr(tv, "remove_worktree", lambda root, w: None)

    def fake(prompt, cwd, model, timeout):
        if verdict_file is not None:
            _write_verdicts(target, verdict_file)
        return stdout

    monkeypatch.setattr(tv, "spawn_verifier", fake)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s1")
    argv = []
    for c in claims:
        argv += ["--claim", c]
    return tv.main(argv)


def test_verdict_file_is_read_in_claim_order(tmp_path):
    f = tmp_path / "v.json"
    _write_verdicts(f, [{"n": 2, "verdict": "REFUTED", "evidence": "ran X"},
                        {"n": 1, "verdict": "CONFIRMED", "evidence": "ran Y"}])
    v = tv.read_verdict_file(f, 2)
    assert [x["verdict"] for x in v] == ["CONFIRMED", "REFUTED"]
    assert v[1]["evidence"] == "ran X"


def test_missing_verdict_file_returns_none_not_empty(tmp_path):
    """None means 'use the fallback channel'. An empty list would read as 'the verifier
    answered, with nothing' — the exact conflation this change removes."""
    assert tv.read_verdict_file(tmp_path / "absent.json", 1) is None


def test_malformed_verdict_file_returns_none(tmp_path):
    for body in ("not json at all", '{"verdicts": "a string"}', '["wrong", "shape"]', "{}"):
        f = tmp_path / "v.json"
        f.write_text(body)
        assert tv.read_verdict_file(f, 1) is None, body


def test_invented_verdict_word_is_not_a_verdict(tmp_path):
    """A verifier that answers MOSTLY_FINE has not answered. Silently accepting an unknown
    word would let a non-verdict count as a judgement."""
    f = tmp_path / "v.json"
    _write_verdicts(f, [{"n": 1, "verdict": "MOSTLY_FINE", "evidence": "vibes"}])
    assert tv.read_verdict_file(f, 1) is None


def test_partial_verdict_file_fills_gaps_with_no_verdict(tmp_path):
    f = tmp_path / "v.json"
    _write_verdicts(f, [{"n": 1, "verdict": "CONFIRMED", "evidence": "e"}])
    v = tv.read_verdict_file(f, 3)
    assert [x["verdict"] for x in v] == ["CONFIRMED", "NO_VERDICT", "NO_VERDICT"]


def test_file_channel_wins_over_the_final_message(tmp_path, logs, monkeypatch):
    """When both channels disagree, the file is authoritative — that is the whole change."""
    _run_with_fake_verifier(
        tmp_path, monkeypatch,
        stdout="VERDICT 1: CONFIRMED\nEVIDENCE 1: the message says fine\n",
        verdict_file=[{"n": 1, "verdict": "REFUTED", "evidence": "the file says broken"}],
    )
    ev = _last_event(logs)
    assert ev["data"]["verdict_channel"] == "file"
    assert ev["data"]["claims"][0]["verdict"] == "REFUTED"


def test_falls_back_to_final_message_and_records_the_channel(tmp_path, logs, monkeypatch):
    """The fallback must still work — but it must be VISIBLE in the event, so a silent
    regression to the fragile channel can be seen rather than inferred."""
    _run_with_fake_verifier(
        tmp_path, monkeypatch,
        stdout="VERDICT 1: CONFIRMED\nEVIDENCE 1: e\n",
        verdict_file=None,
    )
    ev = _last_event(logs)
    assert ev["data"]["verdict_channel"] == "final-message"
    assert ev["data"]["claims"][0]["verdict"] == "CONFIRMED"


def test_stale_verdict_file_cannot_be_read_as_this_runs_verdicts(tmp_path, logs, monkeypatch):
    """THE BUG THIS FIX ALMOST SHIPPED.

    make_worktree copies UNTRACKED files from the source tree into the worktree, so a stale
    tessera-verdicts.json in the repo root arrives inside the worktree. Without the unlink it
    would be read as authoritative and report CONFIRMED for a verifier that wrote nothing —
    the falsifier failing open, reintroduced by the fix for the falsifier failing open.
    """
    _run_with_fake_verifier(
        tmp_path, monkeypatch,
        stdout="the verifier said nothing parseable",
        verdict_file=None,
        preexisting_verdict_file=[{"n": 1, "verdict": "CONFIRMED", "evidence": "STALE"}],
    )
    ev = _last_event(logs)
    claim = ev["data"]["claims"][0]
    assert claim["verdict"] == "NO_VERDICT", "a stale file was read as this run's verdict"
    assert "STALE" not in json.dumps(ev)


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

def _log_verification(logs, sid, verdicts, skipped=False, channel=None):
    ev = tv.build_event(
        claims=[f"c{i}" for i in range(len(verdicts))],
        verdicts=[{"verdict": v, "evidence": ""} for v in verdicts],
        session_id=sid,
        skipped=skipped,
        verdict_channel=channel,
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


def test_stats_breaks_out_the_verdict_channel(logs):
    _log_verification(logs, "s1", ["CONFIRMED"], channel=tv.CHANNEL_FILE)
    _log_verification(logs, "s2", ["CONFIRMED"], channel=tv.CHANNEL_MESSAGE)
    assert tv.stats_summary(logs)["channels"] == {tv.CHANNEL_FILE: 1, tv.CHANNEL_MESSAGE: 1}


def test_the_message_channel_warning_fires_on_what_cmd_run_actually_writes(
    tmp_path, logs, monkeypatch, capsys
):
    """End-to-end writer→reader, because a fabricated literal is how this broke.

    The previous version of the test above built its fixture with `channel="message"` — a
    value NO code path can produce — while `cmd_run` wrote `"final-message"` and `cmd_stats`
    warned on `"message"`. Both halves passed their tests and the ⚠ regression banner could
    never fire: the detector for the exact failure this tool was rewritten to survive was
    dead, in the file whose premise is that channel. Standing pattern #1, and #10 for the
    guard that missed it.

    So this test names no channel literal at all. It drives the real fallback path — a
    verifier that answers but writes no verdict file — and asserts the banner appears. Rename
    or re-inline the constant and it still holds; break writer/reader agreement and it fails.
    """
    _mock_worktree(monkeypatch, tmp_path)  # an empty worktree: no tessera-verdicts.json
    _mock_spawn(monkeypatch, "VERDICT 1: CONFIRMED\nEVIDENCE 1: ok\n")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s1")
    tv.main(["--claim", "x"])

    logged = json.loads((logs / "s1.jsonl").read_text())
    assert logged["data"]["verdict_channel"] == tv.CHANNEL_MESSAGE, "not the fallback path"

    capsys.readouterr()
    tv.cmd_stats(None)
    out = capsys.readouterr().out
    assert "⚠" in out, f"a message-channel run did not raise the regression banner:\n{out}"


def test_a_run_with_no_recorded_channel_is_not_counted_as_message(logs):
    """The bucket that stops the stat from manufacturing a regression.

    `verdict_channel` was added by the 2026-07-26 fix, so every run before it has no
    channel field — 16 of them in the live log against 4 that do. Folding those into
    `message` would render as "4 file / 16 message": a reader sees the failure mode the
    fix was written to prevent, dominating the numbers, and concludes it came undone.
    The absent field means *not measured*, which is the same distinction P3's `unknown`
    and haziness's `≥` prefix both exist to preserve — a verdict must not rest on what
    the instrument could not read.
    """
    _log_verification(logs, "s1", ["CONFIRMED"])  # no channel — predates the field
    _log_verification(logs, "s2", ["CONFIRMED"], channel="file")
    channels = tv.stats_summary(logs)["channels"]
    assert channels == {"unrecorded": 1, "file": 1}
    assert "message" not in channels, "an unmeasured run was counted as a regression"


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


# --- the verifier failing to run is not a verdict (2026-07-21) -----------------------


def test_nonzero_exit_raises_did_not_run(monkeypatch):
    """A refused/failed spawn must not degrade into an empty string.

    `spawn_verifier` used to `return result.stdout` and discard returncode and stderr, so a
    spawn that never ran returned "" and parse_verdicts rendered NO_VERDICT — the falsifier
    failing open, inside the tool built to catch fail-opens.
    """
    def fake_run(*a, **k):
        return subprocess.CompletedProcess(a[0], 1, stdout="", stderr="blocked by classifier")

    monkeypatch.setattr(tv.subprocess, "run", fake_run)
    with pytest.raises(tv.VerifierDidNotRun, match="blocked by classifier"):
        tv.spawn_verifier("p", Path("."), "opus", 10)


def test_exit_zero_with_empty_stdout_raises_did_not_run(monkeypatch):
    """Exit 0 and silence is still no judgement — do not read success into an empty stream."""
    def fake_run(*a, **k):
        return subprocess.CompletedProcess(a[0], 0, stdout="   \n", stderr="")

    monkeypatch.setattr(tv.subprocess, "run", fake_run)
    with pytest.raises(tv.VerifierDidNotRun):
        tv.spawn_verifier("p", Path("."), "opus", 10)


def test_missing_claude_cli_raises_did_not_run(monkeypatch):
    def fake_run(*a, **k):
        raise FileNotFoundError("claude")

    monkeypatch.setattr(tv.subprocess, "run", fake_run)
    with pytest.raises(tv.VerifierDidNotRun, match="not on PATH"):
        tv.spawn_verifier("p", Path("."), "opus", 10)


def test_spawn_failure_exits_2_and_logs_spawn_error(tmp_path, logs, monkeypatch):
    """Exit 2, distinct from 1 (a real REFUTED), and the event carries why."""
    _mock_worktree(monkeypatch, tmp_path)

    def boom(prompt, cwd, model, timeout):
        raise tv.VerifierDidNotRun("claude exited 1: blocked by classifier")

    monkeypatch.setattr(tv, "spawn_verifier", boom)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s1")
    assert tv.main(["--claim", "x"]) == 2
    logged = json.loads((logs / "s1.jsonl").read_text())
    assert "blocked by classifier" in logged["data"]["spawn_error"]
    # Still recorded — silence would be worse — but marked as never-ran.
    assert logged["data"]["claims"][0]["verdict"] == "NO_VERDICT"
