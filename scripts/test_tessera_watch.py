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


def test_p2_counts_tessera_verbs_against_threshold(tmp_path):
    root = _root(tmp_path)
    (root / "bin" / "tessera-a").write_text("")
    assert tw.p2_tess_verbs(root)[0] is False  # 1 < 2
    (root / "bin" / "tessera-b").write_text("")
    assert tw.p2_tess_verbs(root)[0] is True   # 2 >= 2


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
    assert fired is True and "3 compaction_fired" in detail  # ≥3, malformed line ignored


def test_p3_absent_log_is_zero_not_error(tmp_path):
    assert tw.p3_compaction(_root(tmp_path))[0] is False


def test_p5_counts_skill_dirs(tmp_path):
    root = _root(tmp_path)
    for i in range(3):
        (root / ".claude" / "skills" / f"s{i}").mkdir()
    fired, detail = tw.p5_skills(root)
    assert fired is False and "3 skills" in detail  # 3 < 60


def test_evaluate_returns_one_result_per_predicate(tmp_path):
    results = tw.evaluate(_root(tmp_path))
    assert len(results) == len(tw.PREDICATES)
    assert all({"predicate", "fired", "detail"} <= r.keys() for r in results)


if __name__ == "__main__":
    import sys
    import subprocess
    sys.exit(subprocess.call(["pytest", "-q", __file__]))
