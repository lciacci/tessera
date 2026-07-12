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
