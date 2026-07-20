"""Predicate checks for bin/tessera-watch. Run: pytest scripts/test_tessera_watch.py"""
import json
from importlib.util import module_from_spec, spec_from_loader
from importlib.machinery import SourceFileLoader
from pathlib import Path

_path = Path(__file__).resolve().parent.parent / "bin" / "tessera-watch"
_loader = SourceFileLoader("tessera_watch", str(_path))
_spec = spec_from_loader(_loader.name, _loader)
tw = module_from_spec(_spec)
_loader.exec_module(tw)


def _root(tmp_path: Path) -> Path:
    (tmp_path / ".claude" / "scripts").mkdir(parents=True)
    (tmp_path / "templates").mkdir()
    (tmp_path / "bin").mkdir()
    (tmp_path / ".claude" / "skills").mkdir()
    return tmp_path


def test_p1_in_sync_when_templates_match(tmp_path):
    root = _root(tmp_path)
    (root / ".claude" / "scripts" / "h.sh").write_text("echo hi\n")
    (root / "templates" / "h.sh").write_text("echo hi\n")
    fired, _ = tw.p1_hook_drift(root)
    assert fired is False


def test_p1_fires_when_hook_missing_from_templates(tmp_path):
    root = _root(tmp_path)
    (root / ".claude" / "scripts" / "h.sh").write_text("echo hi\n")  # no templates/ copy
    fired, detail = tw.p1_hook_drift(root)
    assert fired is True and "h.sh" in detail


def test_p1_fires_when_content_differs(tmp_path):
    root = _root(tmp_path)
    (root / ".claude" / "scripts" / "h.sh").write_text("echo NEW\n")
    (root / "templates" / "h.sh").write_text("echo OLD\n")
    assert tw.p1_hook_drift(root)[0] is True


def test_p3_counts_only_compaction_fired_events(tmp_path):
    root = _root(tmp_path)
    log = root / ".mnemos" / "compaction-log.jsonl"
    log.parent.mkdir()
    lines = [
        {"event": "compaction_fired"},
        {"event": "restore_injected"},      # not counted
        {"event": "compaction_fired"},
        {"event": "compaction_fired"},
    ]
    log.write_text("\n".join(json.dumps(x) for x in lines) + "\nNOT JSON\n")
    fired, detail = tw.p3_compaction(root)
    assert fired is True and "3 real compaction_fired" in detail  # ≥3, malformed line ignored


def test_p3_absent_log_is_zero_not_error(tmp_path):
    assert tw.p3_compaction(_root(tmp_path))[0] is False


def test_p5_counts_skill_dirs(tmp_path):
    root = _root(tmp_path)
    for i in range(3):
        (root / ".claude" / "skills" / f"s{i}").mkdir()
    fired, detail = tw.p5_skills(root)
    assert fired is False and "3 skills" in detail  # 3 < 60


def _firelog(root: Path, runs: list[list[str]]) -> None:
    log = root / ".tessera" / "logs" / "watch.jsonl"
    log.parent.mkdir(parents=True)
    log.write_text("".join(json.dumps({"ts": "t", "fired": r}) + "\n" for r in runs))


def test_ga_holds_below_three_runs(tmp_path):
    root = _root(tmp_path)
    _firelog(root, [["P3 mnemos-trial"], ["P3 mnemos-trial"]])  # only 2
    assert tw.g_a_consecutive(root)[0] is False


def test_ga_fires_on_three_consecutive_core_fires(tmp_path):
    root = _root(tmp_path)
    _firelog(root, [["P3 mnemos-trial"]] * 3)
    fired, detail = tw.g_a_consecutive(root)
    assert fired is True and "P3 mnemos-trial" in detail


def test_ga_ignores_gap_in_last_three(tmp_path):
    root = _root(tmp_path)
    _firelog(root, [["P3 mnemos-trial"], [], ["P3 mnemos-trial"]])  # cleared mid-window
    assert tw.g_a_consecutive(root)[0] is False


def test_ga_ignores_non_core_persistence(tmp_path):
    root = _root(tmp_path)
    _firelog(root, [["G-a graduation:snooze"]] * 3)  # only a graduation label, no P*
    assert tw.g_a_consecutive(root)[0] is False


import os
import time


def _sessions_db(root: Path, ids: list[str], statuses: list[str | None] | None = None) -> None:
    import sqlite3
    (root / ".mnemos").mkdir(exist_ok=True)
    conn = sqlite3.connect(root / ".mnemos" / "mnemo.db")
    conn.execute("CREATE TABLE claude_sessions (id TEXT, last_ingested_at TEXT, "
                 "classifier_status TEXT)")
    st = statuses or [None] * len(ids)
    conn.executemany("INSERT INTO claude_sessions VALUES (?,?,?)",
                     [(i, f"2026-07-{20 - n:02d}T00:00:00Z", s)
                      for n, (i, s) in enumerate(zip(ids, st))])
    conn.commit(); conn.close()


def _transcript(tdir: Path, sid: str, age_h: float, size: int = 20_000) -> None:
    tdir.mkdir(parents=True, exist_ok=True)
    p = tdir / f"{sid}.jsonl"
    p.write_bytes(b"x" * size)
    mtime = time.time() - age_h * 3600
    os.utime(p, (mtime, mtime))


def test_p11_fires_on_uningested_recent_transcript(tmp_path):
    root = _root(tmp_path)
    tdir = tmp_path / "transcripts"
    _transcript(tdir, "aaaa1111-dead", age_h=24)
    _sessions_db(root, ["other-session"])
    fired, detail = tw.p11_ingest_pipe(root, tdir)
    assert fired is True and "aaaa1111" in detail and "DEAD" in detail


def test_p11_quiet_when_all_ingested(tmp_path):
    root = _root(tmp_path)
    tdir = tmp_path / "transcripts"
    _transcript(tdir, "s1", age_h=24)
    _sessions_db(root, ["s1"], ["ran"])
    assert tw.p11_ingest_pipe(root, tdir)[0] is False


def test_p11_excludes_live_session_and_husks_and_history(tmp_path):
    root = _root(tmp_path)
    tdir = tmp_path / "transcripts"
    _transcript(tdir, "live", age_h=0.2)            # < 1h — may still be open
    _transcript(tdir, "husk", age_h=24, size=100)   # < min bytes
    _transcript(tdir, "old", age_h=24 * 30)         # > 7d — history
    _sessions_db(root, [])
    assert tw.p11_ingest_pipe(root, tdir)[0] is False


def test_p11_fires_on_fallback_streak(tmp_path):
    root = _root(tmp_path)
    tdir = tmp_path / "transcripts"
    tdir.mkdir()
    _sessions_db(root, ["s1", "s2", "s3"],
                 ["regex-only:import-error"] * 3)
    fired, detail = tw.p11_ingest_pipe(root, tdir)
    assert fired is True and "regex-only" in detail


def test_p11_streak_broken_by_a_ran(tmp_path):
    root = _root(tmp_path)
    tdir = tmp_path / "transcripts"
    tdir.mkdir()
    _sessions_db(root, ["s1", "s2", "s3"],
                 ["regex-only:ollama-down", "ran", "regex-only:ollama-down"])
    assert tw.p11_ingest_pipe(root, tdir)[0] is False


def test_p11_budget_exhausted_is_not_a_fallback(tmp_path):
    # A bulk sweep shares one wall-clock budget — later sessions run out. The
    # classifier partially ran; that is not the silent-death shape P11 hunts.
    root = _root(tmp_path)
    tdir = tmp_path / "transcripts"
    tdir.mkdir()
    _sessions_db(root, ["s1", "s2", "s3"], ["budget-exhausted"] * 3)
    assert tw.p11_ingest_pipe(root, tdir)[0] is False


def test_p11_no_dir_or_db_is_quiet(tmp_path):
    assert tw.p11_ingest_pipe(_root(tmp_path), tmp_path / "nope")[0] is False


def test_evaluate_returns_one_result_per_predicate(tmp_path):
    results = tw.evaluate(_root(tmp_path))
    assert len(results) == len(tw.PREDICATES)
    assert all({"predicate", "fired", "detail"} <= r.keys() for r in results)


if __name__ == "__main__":
    import sys
    import subprocess
    sys.exit(subprocess.call(["pytest", "-q", __file__]))


def _gate_event(ts, should_fire=None):
    return json.dumps({"type": "suggestion_gate", "ts": ts, "data": {"should_fire": should_fire}})


def test_p7_ignores_pre_backstop_gates(tmp_path):
    """The pre-backstop corpus is 61-91% truncated — labeling it calibrates on a biased sample."""
    logs = tmp_path / ".tessera" / "logs"
    logs.mkdir(parents=True)
    (logs / "s.jsonl").write_text("\n".join(_gate_event("2026-07-01T00:00:00Z") for _ in range(50)))
    fired, detail = tw.p7_gate_labels(tmp_path)
    assert fired is False
    assert "0 unlabeled" in detail


def test_p7_fires_on_enough_honest_unlabeled_gates(tmp_path):
    logs = tmp_path / ".tessera" / "logs"
    logs.mkdir(parents=True)
    n = tw.GATE_LABEL_MIN
    (logs / "s.jsonl").write_text("\n".join(_gate_event("2026-08-01T00:00:00Z") for _ in range(n)))
    fired, _ = tw.p7_gate_labels(tmp_path)
    assert fired is True


def test_p7_ignores_already_labeled_gates(tmp_path):
    logs = tmp_path / ".tessera" / "logs"
    logs.mkdir(parents=True)
    n = tw.GATE_LABEL_MIN
    (logs / "s.jsonl").write_text(
        "\n".join(_gate_event("2026-08-01T00:00:00Z", should_fire=True) for _ in range(n))
    )
    fired, _ = tw.p7_gate_labels(tmp_path)
    assert fired is False


def _compaction(trigger=None):
    e = {"ts": 1.0, "event": "compaction_fired"}
    if trigger:
        e["trigger"] = trigger
    return json.dumps(e)


def test_p3_excludes_manual_test_compactions(tmp_path):
    """A hand-run /compact TESTS the recovery layer; it is not evidence about it.

    Without this, three deliberate test compactions would deliver the Mnemos trial's
    verdict on manufactured data — the P2 failure exactly.
    """
    m = tmp_path / ".mnemos"
    m.mkdir()
    (m / "compaction-log.jsonl").write_text("\n".join(_compaction("manual") for _ in range(5)))
    fired, detail = tw.p3_compaction(tmp_path)
    assert fired is False
    assert "0 real" in detail and "5 manual" in detail


def test_p3_counts_auto_compactions(tmp_path):
    m = tmp_path / ".mnemos"
    m.mkdir()
    (m / "compaction-log.jsonl").write_text("\n".join(_compaction("auto") for _ in range(3)))
    assert tw.p3_compaction(tmp_path)[0] is True


def test_p3_counts_untagged_legacy_entries_as_real(tmp_path):
    """Entries predating the tagging (2026-07-11) were necessarily auto compactions."""
    m = tmp_path / ".mnemos"
    m.mkdir()
    (m / "compaction-log.jsonl").write_text("\n".join(_compaction() for _ in range(3)))
    assert tw.p3_compaction(tmp_path)[0] is True


# ── P3: an unclassifiable compaction must NOT become evidence ─────────────────

def test_p3_does_not_count_an_unreadable_trigger_as_real(tmp_path):
    """`trigger: "unknown"` is the PreCompact hook's DEFAULT — it means the tagger ran and
    could not classify the event. P3 lumped it into `else: real += 1`, silently promoting a
    measurement FAILURE into evidence for a kill/keep trial. That is the exact contamination
    the trigger-tagging fix was built to prevent, arriving through the one door nobody watched.

    It was live: a compaction fired 2026-07-12 tagged `unknown`, and P3 read it as `1 real`."""
    log = tmp_path / ".mnemos"; log.mkdir()
    (log / "compaction-log.jsonl").write_text(
        '{"event":"compaction_fired","trigger":"unknown"}\n'
        '{"event":"compaction_fired","trigger":"manual"}\n'
    )
    fired, note = tw.p3_compaction(tmp_path)
    assert fired is False
    assert "0 real" in note
    assert "UNCLASSIFIABLE" in note, "an unreadable trigger must be reported LOUDLY, not hidden"


def test_p3_counts_auto_and_pre_tagging_entries_as_real(tmp_path):
    """A MISSING key is a pre-2026-07-11 entry — necessarily an auto compaction. That is
    different from an explicit "unknown", and must still count."""
    log = tmp_path / ".mnemos"; log.mkdir()
    (log / "compaction-log.jsonl").write_text(
        '{"event":"compaction_fired","trigger":"auto"}\n'
        '{"event":"compaction_fired"}\n'
    )
    fired, note = tw.p3_compaction(tmp_path)
    assert "2 real" in note


# ── snooze: G-a-earned ack that quiets a predicate for a bounded, auditable window ──
import datetime as _dt
from types import SimpleNamespace


def test_active_snooze_labels_respects_expiry(tmp_path):
    root = _root(tmp_path)
    now = _dt.datetime(2026, 7, 16, tzinfo=_dt.timezone.utc)
    tw._write_snoozes(root, {
        "P7 gate-labels": {"until": (now + _dt.timedelta(days=5)).isoformat(), "reason": "x"},
        "P1 hook-drift": {"until": (now - _dt.timedelta(days=1)).isoformat(), "reason": "old"},
    })
    active = tw.active_snooze_labels(root, now)
    assert "P7 gate-labels" in active       # unexpired
    assert "P1 hook-drift" not in active     # expired → resurfaces


def test_resolve_label_unique_vs_ambiguous():
    assert tw._resolve_label("P7") == "P7 gate-labels"
    assert tw._resolve_label("nonexistent-xyz") is None


def test_snoozed_fired_predicate_reads_as_not_firing():
    results = [{"predicate": "P7 gate-labels", "fired": True, "snoozed": True,
                "detail": "56 unlabeled", "snooze_until": "2026-08-15T00:00:00+00:00",
                "snooze_reason": "dead backlog"}]
    out = tw.render(results)
    assert "💤" in out and "🔴" not in out
    assert not any(r["fired"] and not r["snoozed"] for r in results)  # exit-0 condition


def test_manage_snooze_sets_with_reason(tmp_path):
    root = _root(tmp_path)
    now = _dt.datetime(2026, 7, 16, tzinfo=_dt.timezone.utc)
    args = SimpleNamespace(snooze="P7", days=30, reason="dead backlog", snooze_clear=None, snooze_list=False)
    msg = tw.manage_snooze(root, args, now)
    assert "P7 gate-labels" in msg and "P7 gate-labels" in tw._load_snoozes(root)


def test_manage_snooze_refuses_without_reason(tmp_path):
    root = _root(tmp_path)
    args = SimpleNamespace(snooze="P7", days=30, reason="", snooze_clear=None, snooze_list=False)
    msg = tw.manage_snooze(root, args, _dt.datetime(2026, 7, 16, tzinfo=_dt.timezone.utc))
    assert "refus" in msg.lower() and tw._load_snoozes(root) == {}   # nothing written


def test_manage_snooze_clear(tmp_path):
    root = _root(tmp_path)
    tw._write_snoozes(root, {"P7 gate-labels": {"until": "2026-08-15T00:00:00+00:00", "reason": "x"}})
    args = SimpleNamespace(snooze=None, days=30, reason="", snooze_clear="P7", snooze_list=False)
    msg = tw.manage_snooze(root, args, _dt.datetime(2026, 7, 16, tzinfo=_dt.timezone.utc))
    assert "cleared" in msg and tw._load_snoozes(root) == {}


def test_g_a_ignores_a_snoozed_predicate(tmp_path):
    # G-a must not keep nagging about a predicate whose remedy (snooze) is already applied,
    # even while the historical fire-log still shows it fired.
    root = _root(tmp_path)
    log = root / ".tessera" / "logs" / "watch.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("".join(json.dumps({"fired": ["P7 gate-labels"]}) + "\n" for _ in range(3)))
    assert tw.g_a_consecutive(root)[0] is True   # fires without a snooze
    future = (_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(days=30)).isoformat()
    tw._write_snoozes(root, {"P7 gate-labels": {"until": future, "reason": "acked"}})
    assert tw.g_a_consecutive(root)[0] is False  # snooze = remedy applied → G-a quiets
