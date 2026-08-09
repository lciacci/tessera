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
import shutil
import subprocess
import sys
import tempfile
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
    monkeypatch.setattr(tv, "logs_dir", lambda: d)
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
        return stdout, {}

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


def test_partial_verdict_file_returns_none_so_the_fallback_still_runs(tmp_path):
    """Inverted 2026-08-09. This test used to assert the gaps were FILLED with NO_VERDICT.

    It was asserting the behaviour `read_verdict_file`'s own docstring disclaims two lines
    above the return — "None (not a partial list) on ANY problem… returning a half-filled
    list here would let a malformed file read as 'some claims had no verdict'". Code and
    comment disagreed, and the test sided with the code, which is how the disagreement
    survived review in the file that tells its verifier the docstrings here are marketing.

    The cost of the old behaviour was not just the missing fallback: the result carried the
    "file" channel label — trusted — while two thirds of it was a fabricated NO_VERDICT.
    """
    f = tmp_path / "v.json"
    _write_verdicts(f, [{"n": 1, "verdict": "CONFIRMED", "evidence": "e"}])
    assert tv.read_verdict_file(f, 3) is None


def test_out_of_range_numbering_does_not_misattribute_a_verdict(tmp_path):
    """The worst case the completeness check kills: a WRONG verdict, not a missing one.

    A verifier numbering from 0 on a 2-claim run wrote n=0 and n=1. `by_n` was non-empty so
    the old code returned a list, and `by_n.get(1)` — meant for claim 1 — picked up the entry
    the verifier had written for claim 2. Measured: `[REFUTED, NO_VERDICT]`, i.e. claim 1
    reported REFUTED on the strength of claim 2's evidence. A falsifier that answers the
    wrong question with confidence is worse than one that says nothing.
    """
    f = tmp_path / "v.json"
    _write_verdicts(f, [{"n": 0, "verdict": "CONFIRMED", "evidence": "claim 1's evidence"},
                        {"n": 1, "verdict": "REFUTED", "evidence": "claim 2's evidence"}])
    assert tv.read_verdict_file(f, 2) is None


def test_wholly_out_of_range_numbering_returns_none(tmp_path):
    f = tmp_path / "v.json"
    _write_verdicts(f, [{"n": 99, "verdict": "CONFIRMED", "evidence": "e"}])
    assert tv.read_verdict_file(f, 2) is None


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

def _mock_spawn(monkeypatch, output, metrics=None):
    calls = {}

    def fake(prompt, cwd, model, timeout):
        calls["prompt"], calls["cwd"] = prompt, cwd
        return output, (metrics or {})

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


# --- the anchor is the repo, not the cwd (2026-08-09) -------------------------------


def test_repo_root_ignores_which_subdirectory_you_are_standing_in(repo, monkeypatch):
    (repo / "deep" / "nested").mkdir(parents=True)
    monkeypatch.chdir(repo / "deep" / "nested")
    assert tv.repo_root().resolve() == repo.resolve()
    assert tv.logs_dir().resolve() == (repo / ".tessera" / "logs").resolve()


def test_worktree_carries_untracked_state_when_run_from_a_subdirectory(repo, monkeypatch):
    """The tier-1 property degraded silently one directory down.

    `git diff HEAD` emits repo-root-relative paths but `git ls-files --others` emits
    SUBDIR-relative ones, and they were joined against the worktree root either way. Measured
    before the fix: `sub/inside.txt` landed at the worktree ROOT as `inside.txt`, and
    `outside.txt` was never copied at all — while the tool reported nothing wrong.

    Anchoring on the git toplevel is what makes the two halves agree, so this drives
    `cmd_run`'s real path (`repo_root()`) rather than passing the root in by hand.
    """
    (repo / "sub").mkdir()
    (repo / "sub" / "inside.txt").write_text("I\n")
    (repo / "outside.txt").write_text("O\n")
    monkeypatch.chdir(repo / "sub")

    wt = tv.make_worktree(tv.repo_root())
    try:
        assert (wt / "sub" / "inside.txt").read_text() == "I\n", "untracked file misplaced"
        assert (wt / "outside.txt").read_text() == "O\n", "untracked file outside cwd dropped"
        assert not (wt / "inside.txt").exists(), "copied to the worktree root by subdir path"
    finally:
        tv.remove_worktree(tv.repo_root(), wt)


# --- a half-built worktree cleans up after itself (2026-08-09) ----------------------


def test_failed_worktree_creation_leaves_no_temp_dir(tmp_path, monkeypatch):
    """`git worktree add` fails on a repo with no commits. The mkdtemp already happened."""
    bare = tmp_path / "nocommits"
    bare.mkdir()
    subprocess.run(["git", "init", "-q", str(bare)], check=True)
    spool = tmp_path / "spool"
    spool.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(spool))

    with pytest.raises(subprocess.CalledProcessError):
        tv.make_worktree(bare)
    assert list(spool.iterdir()) == [], "orphaned temp dir from a half-built worktree"


def test_failure_after_the_worktree_exists_also_deregisters_it(repo, tmp_path, monkeypatch):
    """The worse half: past `worktree add`, a raise orphans a .git/worktrees admin record too.

    Those records are what `remove_worktree`'s trailing `prune` exists to clear, and a leaked
    one persists long after the directory is gone.
    """
    (repo / "untracked.txt").write_text("x\n")
    spool = tmp_path / "spool"
    spool.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(spool))
    monkeypatch.setattr(shutil, "copy2", _raise_disk_full)

    with pytest.raises(OSError):
        tv.make_worktree(repo)
    assert list(spool.iterdir()) == []
    listed = subprocess.run(["git", "-C", str(repo), "worktree", "list"],
                            capture_output=True, text=True, check=True).stdout
    assert "tessera-verify-" not in listed, f"orphaned worktree registration:\n{listed}"


def _raise_disk_full(*_a, **_kw):
    raise OSError("no space left on device")


# --- the log is UTF-8 by declaration, not by locale (2026-08-09) --------------------


def test_non_ascii_survives_a_write_read_round_trip(logs, monkeypatch):
    """`append_event` writes with ensure_ascii=False, so the bytes really are UTF-8.

    Both ends used to rely on `locale.getpreferredencoding(False)`. On darwin that is UTF-8
    even under `LC_ALL=C LANG=C` (measured), so this cannot fail here — which is exactly why
    it needed pinning rather than trusting: 32 of the live log files already carry non-ASCII,
    so the first non-UTF-8 host would have hit it on the first `stats` call.
    """
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s1")
    claim = "the ⚠ banner fires — naïve résumé, 日本語"
    tv.append_event(tv.build_event([claim], [{"verdict": "CONFIRMED", "evidence": "ran ✓"}],
                                   "s1", verdict_channel=tv.CHANNEL_FILE))
    assert (logs / "s1.jsonl").read_bytes().decode("utf-8")
    assert _last_event(logs)["data"]["claims"][0]["text"] == claim
    assert tv.stats_summary(logs)["confirmed"] == 1


def test_a_non_utf8_verdict_file_is_unusable_not_fatal(tmp_path):
    """The contract is "None on ANY problem". Undecodable bytes are a problem, and used to
    escape the except clause entirely — UnicodeDecodeError is a ValueError, not an OSError."""
    f = tmp_path / "v.json"
    f.write_bytes(b'{"verdicts": [{"n": 1, "verdict": "CONFIRMED", "evidence": "\xff\xfe"}]}')
    assert tv.read_verdict_file(f, 1) is None


# --- what the run cost (2026-08-09) -------------------------------------------------
#
# 27 judged runs in the live log, not one carrying a cost. The one tool in the repo that
# spends real money on demand recorded nothing about it, and metered API spend is deliberately
# outside the spend guard, so nothing else was going to.

# Trimmed from a REAL `claude -p --output-format json` run, not invented. The shape is an
# external contract this repo does not control; a fabricated fixture would test our idea of it.
REAL_ENVELOPE = json.dumps({
    "is_error": False, "duration_api_ms": 2070, "num_turns": 1, "stop_reason": "end_turn",
    "session_id": "bec0c80f", "total_cost_usd": 0.0118004,
    "usage": {"input_tokens": 10, "output_tokens": 59},
    "permission_denials": [], "subtype": "success", "result": "probe-ok",
    "type": "result", "duration_ms": 1330,
})


def test_the_real_cli_envelope_yields_text_and_metrics():
    text, metrics = tv.parse_cli_envelope(REAL_ENVELOPE)
    assert text == "probe-ok"
    assert metrics["total_cost_usd"] == 0.0118004
    assert metrics["num_turns"] == 1
    assert metrics["duration_ms"] == 1330
    assert metrics["stop_reason"] == "end_turn"
    assert "permission_denials" not in metrics  # empty list is not a denial


def test_permission_denials_are_counted():
    """2026-07-21: the nested spawn was refused by the permission classifier, silently."""
    env = json.loads(REAL_ENVELOPE)
    env["permission_denials"] = [{"tool": "Bash"}, {"tool": "Write"}]
    assert tv.parse_cli_envelope(json.dumps(env))[1]["permission_denials"] == 2


def test_a_non_json_envelope_costs_the_metrics_never_the_verdicts(tmp_path):
    """The CLI's output shape is not ours. Losing it must degrade to the old behaviour."""
    plain = "VERDICT 1: CONFIRMED\nEVIDENCE 1: ran the thing\n"
    text, metrics = tv.parse_cli_envelope(plain)
    assert text == plain
    assert metrics == {}
    assert tv.parse_verdicts(text, 1)[0]["verdict"] == "CONFIRMED"


def test_json_without_a_result_field_falls_back_to_raw_stdout():
    body = json.dumps({"type": "result", "num_turns": 3})
    text, metrics = tv.parse_cli_envelope(body)
    assert text == body
    assert metrics["num_turns"] == 3


def test_the_cost_lands_on_the_event(tmp_path, logs, monkeypatch):
    _mock_worktree(monkeypatch, tmp_path)
    _mock_spawn(monkeypatch, "VERDICT 1: CONFIRMED\nEVIDENCE 1: ok\n",
                metrics={"total_cost_usd": 1.23, "num_turns": 9, "subtype": "success"})
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s1")
    tv.main(["--claim", "x"])
    assert _last_event(logs)["data"]["run"]["total_cost_usd"] == 1.23


def test_a_run_with_no_metrics_records_no_run_field(tmp_path, logs, monkeypatch):
    """Absent must stay distinguishable from zero — the `unrecorded` lesson, again."""
    _mock_worktree(monkeypatch, tmp_path)
    _mock_spawn(monkeypatch, "VERDICT 1: CONFIRMED\nEVIDENCE 1: ok\n")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s1")
    tv.main(["--claim", "x"])
    assert "run" not in _last_event(logs)["data"]


# --- the console is UTF-8 too, not just the log (2026-08-09, found by the falsifier) -------

ASCII_CONSOLE = {"PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0", "LC_ALL": "C", "LANG": "C"}


def _repo_with_message_channel_event(tmp_path):
    """A repo whose log holds a final-message event — the state that makes stats print ⚠."""
    r = tmp_path / "repo"
    (r / ".tessera" / "logs").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(r)], check=True)
    ev = {"type": "verification", "ts": "2026-08-09T00:00:00Z", "session_id": "x",
          "source": "tessera-verify",
          "data": {"claims": [{"text": "a claim", "verdict": "CONFIRMED", "evidence": "e"}],
                   "self_test": False, "skipped": False, "model": "opus",
                   "verdict_channel": "final-message"}}
    (r / ".tessera" / "logs" / "x.jsonl").write_text(json.dumps(ev) + "\n")
    return r


def _stats_under(env_extra, cwd):
    import os
    tool = str(Path(__file__).parent.parent / "bin" / "tessera-verify")
    return subprocess.run([sys.executable, tool, "stats"], cwd=cwd,
                          env={**os.environ, **env_extra}, capture_output=True)


def test_the_warning_banner_survives_a_forced_ascii_console(tmp_path):
    """Subprocess, because this is about the interpreter's stdio encoding, not our strings.

    The banner is the only output that carries a non-ASCII glyph, so before this fix `stats`
    crashed precisely and only when it had a fragile-channel run to report.
    """
    r = _repo_with_message_channel_event(tmp_path)
    done = _stats_under(ASCII_CONSOLE, r)
    assert done.returncode == 0, done.stderr.decode("utf-8", "replace")
    assert "⚠" in done.stdout.decode("utf-8"), done.stdout


def test_a_non_ascii_claim_prints_under_a_forced_ascii_console(tmp_path, logs, monkeypatch):
    """The other half: cmd_run echoes each claim back, and claims are free text.

    The first version of this test ran under pytest's own stdout — already UTF-8 capable — so
    it passed with the fix REMOVED. It asserted nothing about an ASCII console despite its
    name: #10's fiction, written into the guard for a bug found by the falsifier, in the same
    session that inverted a different test for the same reason. Now it binds stdout to a real
    ascii-encoded stream, which is what makes it fail without `force_utf8_console`.
    """
    import io
    _mock_worktree(monkeypatch, tmp_path)
    _mock_spawn(monkeypatch, "VERDICT 1: CONFIRMED\nEVIDENCE 1: ok\n")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s1")

    ascii_console = io.TextIOWrapper(io.BytesIO(), encoding="ascii", errors="strict")
    monkeypatch.setattr(sys, "stdout", ascii_console)
    assert tv.main(["--claim", "café — naïve 日本語"]) == 0
    ascii_console.flush()
    assert "café" in ascii_console.buffer.getvalue().decode("utf-8")


def test_reconfigure_failure_never_takes_the_run_down():
    """This function exists to prevent a crash; it must not become one."""
    class Hostile:
        def reconfigure(self, **_kw):
            raise ValueError("underlying buffer has been detached")

    saved = sys.stdout
    sys.stdout = Hostile()
    try:
        tv.force_utf8_console()   # must not raise
    finally:
        sys.stdout = saved
