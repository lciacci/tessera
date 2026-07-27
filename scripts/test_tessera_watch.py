"""Predicate checks for bin/tessera-watch. Run: pytest scripts/test_tessera_watch.py"""
import datetime as _dt
import json
from importlib.util import module_from_spec, spec_from_loader
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import SimpleNamespace

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
    _firelog(root, [["P3 mnemos-compaction-trial"], ["P3 mnemos-compaction-trial"]])  # only 2
    assert tw.g_a_consecutive(root)[0] is False


def test_ga_fires_on_three_consecutive_core_fires(tmp_path):
    root = _root(tmp_path)
    _firelog(root, [["P3 mnemos-compaction-trial"]] * 3)
    fired, detail = tw.g_a_consecutive(root)
    assert fired is True and "P3 mnemos-compaction-trial" in detail


def test_ga_ignores_gap_in_last_three(tmp_path):
    root = _root(tmp_path)
    _firelog(root, [["P3 mnemos-compaction-trial"], [], ["P3 mnemos-compaction-trial"]])  # cleared mid-window
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


def _skilldir(base: Path, *skills: str, body: str = "b") -> Path:
    for s in skills:
        d = base / s
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(body)
    return base


def test_p12_quiet_when_mirror_matches(tmp_path):
    root = _root(tmp_path)
    _skilldir(root / "skills", "a", "b")
    g = _skilldir(tmp_path / "global", "a", "b")
    assert tw.p12_skill_registry_drift(root, g)[0] is False


def test_p12_fires_on_zombie_and_stale(tmp_path):
    root = _root(tmp_path)
    _skilldir(root / "skills", "a")
    g = _skilldir(tmp_path / "global", "a", "zombie")      # global-only dir
    (g / "a" / "SKILL.md").write_text("OLD BODY")          # divergent content
    fired, detail = tw.p12_skill_registry_drift(root, g)
    assert fired is True and "zombie" in detail and "differs" in detail


def test_p12_fires_on_unsynced_repo_addition(tmp_path):
    root = _root(tmp_path)
    _skilldir(root / "skills", "a", "new-skill")
    g = _skilldir(tmp_path / "global", "a")
    fired, detail = tw.p12_skill_registry_drift(root, g)
    assert fired is True and "repo-only: new-skill" in detail


def test_p12_missing_dirs_quiet(tmp_path):
    assert tw.p12_skill_registry_drift(_root(tmp_path), tmp_path / "nope")[0] is False


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


# --- P4: F-003 drift is measured in bytes, not project count (2026-07-21) --------------


def _downstream(root, name, hooks: dict):
    """A downstream project: .tessera/project.yml + optional local hook copies."""
    p = root / name
    (p / ".tessera").mkdir(parents=True)
    (p / ".tessera" / "project.yml").write_text("profile: standard\n")
    if hooks:
        (p / ".claude" / "scripts").mkdir(parents=True)
        for fname, body in hooks.items():
            (p / ".claude" / "scripts" / fname).write_text(body)
    return p


def test_p4_ignores_projects_with_no_local_copies(tmp_path, monkeypatch):
    """The regression: settempo (hook_distro global, 0 copies) tripped the old count
    predicate while adding zero drift surface. Project count is not drift."""
    home = tmp_path / "home"
    (home / ".claude" / "templates").mkdir(parents=True)
    (home / ".claude" / "templates" / "mnemos-pre-compact.sh").write_text("current\n")
    monkeypatch.setattr(tw.Path, "home", classmethod(lambda cls: home))

    root = tmp_path / "tessera"
    root.mkdir()
    for n in ("a", "b", "c", "d", "e"):
        _downstream(tmp_path, n, {})

    fired, msg = tw.p4_downstream(root)
    assert fired is False, msg
    assert "in sync" in msg


def test_p4_fires_on_byte_drift_and_names_the_file(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".claude" / "templates").mkdir(parents=True)
    (home / ".claude" / "templates" / "mnemos-pre-compact.sh").write_text("current\n")
    monkeypatch.setattr(tw.Path, "home", classmethod(lambda cls: home))

    root = tmp_path / "tessera"
    root.mkdir()
    _downstream(tmp_path, "fresh", {"mnemos-pre-compact.sh": "current\n"})
    _downstream(tmp_path, "stale", {"mnemos-pre-compact.sh": "OLD\n"})

    fired, msg = tw.p4_downstream(root)
    assert fired is True
    assert "stale/mnemos-pre-compact.sh" in msg
    assert "fresh/" not in msg, "an in-sync copy must not be reported as drift"


def test_p4_flags_a_local_copy_with_no_global_source(tmp_path, monkeypatch):
    """Orphaned: nothing can ever sync it, so it drifts forever in silence."""
    home = tmp_path / "home"
    (home / ".claude" / "templates").mkdir(parents=True)
    monkeypatch.setattr(tw.Path, "home", classmethod(lambda cls: home))

    root = tmp_path / "tessera"
    root.mkdir()
    _downstream(tmp_path, "orphan", {"mnemos-ghost.sh": "x\n"})

    fired, msg = tw.p4_downstream(root)
    assert fired is True
    assert "orphaned" in msg and "orphan/mnemos-ghost.sh" in msg


def test_p4_can_go_green(tmp_path, monkeypatch):
    """A predicate that cannot be resolved teaches you to ignore the watcher (see P9)."""
    home = tmp_path / "home"
    (home / ".claude" / "templates").mkdir(parents=True)
    (home / ".claude" / "templates" / "mnemos-pre-compact.sh").write_text("current\n")
    monkeypatch.setattr(tw.Path, "home", classmethod(lambda cls: home))

    root = tmp_path / "tessera"
    root.mkdir()
    proj = _downstream(tmp_path, "p", {"mnemos-pre-compact.sh": "OLD\n"})
    assert tw.p4_downstream(root)[0] is True

    (proj / ".claude" / "scripts" / "mnemos-pre-compact.sh").write_text("current\n")
    assert tw.p4_downstream(root)[0] is False


# ── P3: restore integrity (ADR-0015; was "count compaction events") ────────────────────
#
# The predicate changed shape because its premise was false. It counted compaction —
# ~3 events — for a restore path that runs on EVERY session start (~121). What follows
# harvests the tally invariants worth keeping and replaces the retired gating ones.


def _mnemos(tmp_path):
    m = tmp_path / ".mnemos"
    m.mkdir(exist_ok=True)
    return m


def _checkpoint(tmp_path, *, pad=0, drop=()):
    data = {"goal": "g" + "x" * pad, "active_constraints": ["c"], "task_narrative": "n"}
    for f in drop:
        data.pop(f, None)
    (_mnemos(tmp_path) / "checkpoint-latest.json").write_text(json.dumps(data))
    return tmp_path


def _compaction(trigger=None, probe=None):
    e = {"ts": 1.0, "event": "compaction_fired"}
    if trigger:
        e["trigger"] = trigger
    if probe is not None:
        e["payload_probe"] = probe
    return json.dumps(e)


def test_p3_fires_when_checkpoint_exceeds_the_delivery_budget(tmp_path):
    """THE observed defect, 2026-07-26. checkpoint.py joined every never-evict GoalNode,
    the field hit 11,119 chars, the payload passed the SessionStart output limit, and the
    harness spilled it to a file and handed the model a 2KB preview — so Constraints,
    Progress, Key Files and Git State never arrived. It degraded all ~121 restores, not
    the 3 compactions the old predicate watched."""
    root = _checkpoint(tmp_path, pad=tw.RESTORE_BUDGET_BYTES)
    fired, detail = tw.p3_restore_integrity(root)
    assert fired is True
    assert "over the" in detail and "SPILL" in detail
    assert "EVERY session start" in detail, "must not re-frame this as a compaction-only bug"


def test_p3_quiet_on_a_deliverable_checkpoint_but_claims_no_verdict(tmp_path):
    """Green here means the payload survives delivery — NOT that restore works.

    That distinction is the whole reason this predicate is a guard rather than the trial:
    reading it as a verdict would mint proxy #5 after P2 (verb count), old-P4 (project
    count) and sqlfluff (file existence). If the message ever stops saying so, the next
    reader inherits the same category error the old P3 encoded."""
    fired, detail = tw.p3_restore_integrity(_checkpoint(tmp_path))
    assert fired is False
    assert "NOT a verdict" in detail and "T2" in detail


def test_p3_fires_when_a_required_field_is_missing(tmp_path):
    for field in tw.RESTORE_REQUIRED_FIELDS:
        root = _checkpoint(tmp_path, drop=(field,))
        fired, detail = tw.p3_restore_integrity(root)
        assert fired is True and field in detail, f"{field} dropped silently"


def test_p3_fires_when_checkpoint_is_absent_but_mnemos_exists(tmp_path):
    _mnemos(tmp_path)
    fired, detail = tw.p3_restore_integrity(tmp_path)
    assert fired is True and "NOTHING to deliver" in detail


def test_p3_fires_on_unparseable_checkpoint(tmp_path):
    (_mnemos(tmp_path) / "checkpoint-latest.json").write_text("{not json")
    fired, detail = tw.p3_restore_integrity(tmp_path)
    assert fired is True and "not valid JSON" in detail


def test_p3_not_applicable_without_a_mnemos_dir(tmp_path):
    """A project with no .mnemos/ has not opted in. Firing there makes P3 noise on every
    downstream that never installed Mnemos."""
    fired, detail = tw.p3_restore_integrity(tmp_path)
    assert fired is False and "not installed" in detail


def test_p3_tally_distinguishes_manual_unknown_and_auto(tmp_path):
    """HARVESTED from the retired gating tests. The counts no longer decide anything, but
    they are the only evidence about T3, so a tally that miscounts is still a broken
    instrument — just a demoted one."""
    root = _checkpoint(tmp_path)
    (_mnemos(tmp_path) / "compaction-log.jsonl").write_text("\n".join([
        _compaction("manual"), _compaction("manual"), _compaction("unknown"),
        _compaction("auto"), _compaction(),  # no key = pre-tagging legacy, counts as auto
    ]))
    _, detail = tw.p3_restore_integrity(root)
    assert "compaction 2 auto / 2 manual / 1 unclassifiable" in detail


def test_p3_tally_ignores_other_events_and_malformed_lines(tmp_path):
    root = _checkpoint(tmp_path)
    (_mnemos(tmp_path) / "compaction-log.jsonl").write_text(
        _compaction("auto") + '\n{"event":"restore_injected"}\nNOT JSON\n')
    _, detail = tw.p3_restore_integrity(root)
    assert "compaction 1 auto" in detail


def test_p3_unknown_no_longer_fires_but_stays_auditable(tmp_path):
    """DELIBERATE REVERSION, and the reasoning must survive or this reads as a regression.

    A previous session made `unknown`-with-no-real FIRE, because the warning lived in a
    message that `render()` would never print — pattern #9 inside the watcher, and two
    unclassifiable events sat invisible for a fortnight. That fix was right for what was
    then an open question.

    It is no longer open. The harness sends an EMPTY PreCompact payload
    (`payload_probe {"len": 2, "keys": []}`, proven 2026-07-26), so `unknown` is a STANDING,
    UNFIXABLE state — and a predicate that fires forever on one is noise people learn to
    skip, which is how a real alarm gets missed. ADR-0015 demotes it to informational.

    The visibility the old fix bought is NOT given back: `--json` emits `detail` for
    non-fired predicates too, so the tally stays auditable. What replaces the alarm is the
    EVENT — a probe reporting keys — asserted in the next test."""
    root = _checkpoint(tmp_path)
    (_mnemos(tmp_path) / "compaction-log.jsonl").write_text(
        "\n".join([_compaction("unknown"), _compaction("unknown")]))
    fired, detail = tw.p3_restore_integrity(root)
    assert fired is False, "a standing unfixable state must not alarm on every run"
    assert "2 unclassifiable" in detail, (
        "…but it must stay in the message, which --json surfaces even when not fired — "
        "otherwise this silently re-creates the invisible-warning bug it replaces")


def test_p3_fires_when_payload_probe_reports_keys(tmp_path):
    """The event that reopens T3. If the harness ever starts sending a PreCompact payload,
    compaction frequency becomes answerable here for the first time — ADR-0015's
    re-evaluate trigger, and the one compaction fact still worth an alarm."""
    root = _checkpoint(tmp_path)
    (_mnemos(tmp_path) / "compaction-log.jsonl").write_text(
        _compaction("unknown", probe={"len": 3, "keys": ["trigger", "session_id"]}))
    fired, detail = tw.p3_restore_integrity(root)
    assert fired is True
    assert "session_id" in detail and "ADR-0015" in detail


def test_p3_empty_probe_does_not_fire(tmp_path):
    """`{"keys": []}` is the CURRENT state — it must not fire, or P3 alarms forever."""
    root = _checkpoint(tmp_path)
    (_mnemos(tmp_path) / "compaction-log.jsonl").write_text(
        _compaction("unknown", probe={"len": 2, "keys": []}))
    assert tw.p3_restore_integrity(root)[0] is False
