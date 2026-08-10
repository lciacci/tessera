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


# ── P14: the global fallback tier (ADR-0004 tier 3) ────────────────────────────────────
#
# The edge nothing guarded. On 2026-07-26 ~/.claude/templates/ held 7 stale hooks and was
# missing tessera-decision-surface.sh outright, so the 07-24 channel fix had reached NO
# downstream project — while P4 reported "all in sync", because P4 measures downstream
# copies AGAINST this tier. Uniform staleness reads as agreement.


def _tier3(tmp_path, home, *, files, owner=None):
    """Build a fake repo + fake ~/.claude/templates and point Path.home() at it."""
    root = tmp_path / "repo"
    (root / ".claude" / "scripts").mkdir(parents=True)
    for name, body in files["live"].items():
        (root / ".claude" / "scripts" / name).write_text(body)
    tier3 = home / ".claude" / "templates"
    tier3.mkdir(parents=True)
    for name, body in files["global"].items():
        (tier3 / name).write_text(body)
    (home / ".claude" / ".bootstrap-dir").write_text(str(owner if owner else root))
    return root


def test_p14_quiet_when_the_global_tier_matches(tmp_path, monkeypatch):
    home = tmp_path / "home"
    root = _tier3(tmp_path, home, files={"live": {"a.sh": "x"}, "global": {"a.sh": "x"}})
    monkeypatch.setattr(tw.Path, "home", staticmethod(lambda: home))
    fired, detail = tw.p14_global_tier_drift(root)
    assert fired is False and "byte-identical" in detail


def test_p14_fires_on_a_stale_global_copy(tmp_path, monkeypatch):
    """THE regression: the fix exists in the repo and has shipped to nobody."""
    home = tmp_path / "home"
    root = _tier3(tmp_path, home, files={"live": {"a.sh": "NEW"}, "global": {"a.sh": "old"}})
    monkeypatch.setattr(tw.Path, "home", staticmethod(lambda: home))
    fired, detail = tw.p14_global_tier_drift(root)
    assert fired is True and "STALE" in detail and "a.sh" in detail
    assert "P4 will read 'all in sync'" in detail, (
        "must warn that the sibling predicate is green against a stale reference")


def test_p14_fires_on_a_hook_missing_from_the_global_tier(tmp_path, monkeypatch):
    """tessera-decision-surface.sh was absent entirely — and P4's mnemos-*.sh glob could
    never have seen it, so 'missing' needs its own assertion, not just 'differs'."""
    home = tmp_path / "home"
    root = _tier3(tmp_path, home, files={"live": {"a.sh": "x", "b.sh": "y"},
                                         "global": {"a.sh": "x"}})
    monkeypatch.setattr(tw.Path, "home", staticmethod(lambda: home))
    fired, detail = tw.p14_global_tier_drift(root)
    assert fired is True and "MISSING" in detail and "b.sh" in detail


def test_p14_stays_silent_when_another_repo_owns_the_global_tier(tmp_path, monkeypatch):
    """Silent elsewhere rather than wrong elsewhere — another checkout may legitimately own
    the tier, and this predicate must not order it to overwrite someone else's install."""
    home = tmp_path / "home"
    root = _tier3(tmp_path, home, files={"live": {"a.sh": "NEW"}, "global": {"a.sh": "old"}},
                  owner=tmp_path / "some-other-repo")
    monkeypatch.setattr(tw.Path, "home", staticmethod(lambda: home))
    fired, detail = tw.p14_global_tier_drift(root)
    assert fired is False and "owned by" in detail


def test_p14_quiet_when_the_tier_is_not_installed(tmp_path, monkeypatch):
    home = tmp_path / "home"; home.mkdir()
    monkeypatch.setattr(tw.Path, "home", staticmethod(lambda: home))
    assert tw.p14_global_tier_drift(tmp_path)[0] is False


# ── P9's second consumer: icpg ─────────────────────────────────────────────────────────
#
# P9's invariant is "does the interpreter the CONSUMER resolves have what it imports?" and
# mnemos was the only consumer ever checked. mnemos-pre-edit.sh also shells out to `icpg`
# for the intent/constraint/drift half. If icpg breaks, that half vanishes silently and the
# hook reads as "this file has no intents" — F-001's confound verbatim (empty ≠ unreachable).


def _icpg_repo(tmp_path, *, with_db=True):
    root = _root(tmp_path)
    (root / ".venv" / "bin").mkdir(parents=True)
    if with_db:
        (root / ".icpg").mkdir()
        (root / ".icpg" / "reason.db").write_text("x")
    return root


def _past_the_mnemos_checks(tmp_path, monkeypatch, root, *, icpg):
    """Clear P9's mnemos gates so the test actually reaches the icpg branch.

    THE PROBE IS STUBBED, AND THAT IS THE POINT. This used to write a fake `mnemos` whose
    shebang was `sys.executable` and let P9 really run `<interp> -c "import mnemos"` — which
    only clears the gate when the interpreter running pytest happens to have mnemos
    installed. On a fresh clone's bare venv it does not, so P9 returned at the EARLIER gate
    ("...CANNOT import mnemos — F-001 exactly") and the assertions below were about a branch
    that never ran. It failed loudly rather than silently, so it was never a false green —
    but the suite could not tell "the icpg branch regressed" from "your venv lacks mnemos".

    The docstring it replaces worried about exactly this ("which is how a vacuous test
    looks") and closed the shebang-readability half while leaving importability ambient. A
    test's premise must not rest on an unstated property of whichever interpreter runs it
    (#4, one level up from interpreters-are-paths). So the mnemos import is stubbed to
    succeed and the base_prefix to a manager-independent path; the icpg probe is left REAL,
    because it is the thing under test.
    """
    import sys
    fake = tmp_path / "mnemos"
    fake.write_text(f"#!{sys.executable}\n")
    monkeypatch.setattr(tw.shutil, "which",
                        lambda n: icpg if n == "icpg" else str(fake))
    (root / ".python-version").write_text("3.13\n")
    (root / ".venv" / "bin" / "python").write_text("x")

    real_run = tw.subprocess.run

    def stub(cmd, *a, **k):
        if len(cmd) >= 3 and cmd[1] == "-c" and cmd[2] == "import mnemos":
            return SimpleNamespace(returncode=0, stdout="", stderr=b"")
        if len(cmd) >= 3 and cmd[1] == "-c" and "base_prefix" in cmd[2]:
            return SimpleNamespace(returncode=0, stdout="/uv/managed/base", stderr=b"")
        return real_run(cmd, *a, **k)      # the icpg probe stays REAL

    monkeypatch.setattr(tw.subprocess, "run", stub)


def test_p9_fires_when_a_repo_uses_icpg_but_icpg_is_unresolvable(tmp_path, monkeypatch):
    """THE regression. Silent icpg = the intent half vanishes and reads as 'no intents'."""
    root = _icpg_repo(tmp_path)
    _past_the_mnemos_checks(tmp_path, monkeypatch, root, icpg=None)
    fired, detail = tw.p9_interpreter_drift(root)
    assert fired is True, detail
    assert "icpg" in detail and "silently dead" in detail, detail
    assert "F-001" in detail, "must name the confound, or the next reader re-derives it"


def test_p9_silent_on_repos_that_do_not_use_icpg(tmp_path, monkeypatch):
    """Declare-then-check: a project with no reason.db never used it, so absence is not a
    fault. Firing there would make P9 noisy on every downstream that skipped iCPG."""
    root = _icpg_repo(tmp_path, with_db=False)
    monkeypatch.setattr(tw.shutil, "which", lambda name: None if name == "icpg" else "/bin/true")
    _, detail = tw.p9_interpreter_drift(root)
    assert "icpg" not in detail or "ok" in detail


def test_p9_icpg_branch_is_reachable_when_the_db_is_present(tmp_path, monkeypatch):
    """Non-vacuity: the icpg branch is live code, not a branch nothing can enter.

    IT NO LONGER ASSERTS ON THE REAL REPO, AND THAT WAS THE DEFECT. It read
    `assert (repo/'.icpg'/'reason.db').exists()` — a GITIGNORED runtime artifact made a
    precondition of the repo's own test suite, so a fresh clone was red before anyone
    touched the code. Third instance in one day of the same category error (doccheck's
    referenced-paths-exist, P5's crash on .claude/skills, this).

    The machine claim did not vanish, it MOVED to where machine claims belong: install.sh's
    verify() now asserts .icpg/reason.db, and install.sh now creates it — which is the real
    finding underneath, since nothing had ever owned that file. What stays here is the only
    half a test can answer: given a db, the branch executes.
    """
    root = _icpg_repo(tmp_path)
    _past_the_mnemos_checks(tmp_path, monkeypatch, root, icpg=None)
    _, detail = tw.p9_interpreter_drift(root)
    assert "icpg" in detail, detail
    # ...and it is genuinely the db that opens it: same fixture, no db, no icpg in the answer.
    bare = _icpg_repo(tmp_path / "nodb", with_db=False)
    _past_the_mnemos_checks(tmp_path / "nodb", monkeypatch, bare, icpg=None)
    _, quiet = tw.p9_interpreter_drift(bare)
    assert "silently dead" not in quiet, quiet


# ── P15: the spend backstop's own cap had become a permanent kill switch ───────────────
#
# `.spend-backstop-fires` was a global integer nothing reset; backstop.main() returns 0 once
# it exceeds MAX_FIRES. Found 2026-07-27 at 47 — the backstop that catches a vanished spend
# denial had been silently dead, and rc=0 reads exactly like "nothing to report". The counter
# is per-session now, but a fix is not a signal: this is the paired detector, because the
# failure it guards is the guard being off, which announces nothing by construction.

def _fires_file(root, content: str):
    (root / ".tessera").mkdir(parents=True, exist_ok=True)
    (root / ".tessera" / ".spend-backstop-fires").write_text(content)


def test_p15_quiet_when_the_counter_has_never_been_written(tmp_path):
    assert tw.p15_spend_backstop_suppressed(tmp_path)[0] is False


def test_p15_fires_on_the_legacy_global_counter(tmp_path):
    """A bare `47` is VALID json and arrives as an int, not a parse error — the first
    version of this predicate keyed on ValueError and reported the wrong branch."""
    _fires_file(tmp_path, "47")
    fired, detail = tw.p15_spend_backstop_suppressed(tmp_path)
    assert fired is True
    assert "legacy global counter" in detail


def test_p15_fires_on_unparseable_state(tmp_path):
    _fires_file(tmp_path, "{ not json")
    assert tw.p15_spend_backstop_suppressed(tmp_path)[0] is True


def test_p15_is_quiet_for_a_single_capped_session(tmp_path):
    """One session at the cap is the loop-safety doing its job, not a suppressed backstop.
    Firing here would make the predicate noise on correct behaviour."""
    _fires_file(tmp_path, json.dumps({"s1": 9, "s2": 1}))
    assert tw.p15_spend_backstop_suppressed(tmp_path)[0] is False


def test_p15_fires_when_the_cap_is_hit_across_sessions(tmp_path):
    """Chronic capping means denials are routinely undispositioned, or it is wedging."""
    _fires_file(tmp_path, json.dumps({"s1": 9, "s2": 9, "s3": 1}))
    fired, detail = tw.p15_spend_backstop_suppressed(tmp_path)
    assert fired is True
    assert "2 sessions" in detail


def test_p15_reads_the_cap_from_the_backstop_not_a_copy(tmp_path):
    """A mirrored constant is a second definition. If MAX_FIRES is tuned, P15 must move."""
    spend = tmp_path / "scripts" / "spend"
    spend.mkdir(parents=True)
    (spend / "backstop.py").write_text("MAX_FIRES = 50\n")
    _fires_file(tmp_path, json.dumps({"s1": 9, "s2": 9}))
    assert tw.p15_spend_backstop_suppressed(tmp_path)[0] is False, (
        "P15 used its own copy of the cap instead of the backstop's"
    )


# ── P16: the T2 read-trigger. Guards against reading EARLY, so the tests must drive it
# to the state where it SHOULD fire — asserting only that it is quiet today would pass
# against a predicate that can never fire at all (standing pattern #1, aimed at P16).

def _fleet(tmp_path: Path, receipts: dict[str, int], own: int = 0) -> Path:
    """A tessera root with sibling downstream projects, the shape _downstream_projects globs.
    `receipts` maps project name -> number of restore_receipt events. `own` puts receipts in
    tessera itself, which must never count."""
    root = tmp_path / "fleet" / "tessera"
    for name, n in [("tessera", own), *receipts.items()]:
        project = tmp_path / "fleet" / name
        (project / ".tessera" / "logs").mkdir(parents=True, exist_ok=True)
        (project / ".tessera" / "project.yml").write_text("profile: standard\n")
        lines = [json.dumps({"type": "restore_receipt", "data": {"sufficient": True}})] * n
        # An offer is not a receipt: the harness half must not inflate the model half.
        lines.append(json.dumps({"type": "restore_offered", "data": {"bytes": 10}}))
        (project / ".tessera" / "logs" / "s1.jsonl").write_text("\n".join(lines) + "\n")
    return root


_T0 = tw.T2_SHIPPED
_DAY = _dt.timedelta(days=1)


def test_p16_quiet_while_the_data_is_thin_and_it_is_early(tmp_path):
    root = _fleet(tmp_path, {"a": 2, "b": 1})
    fired, detail = tw.p16_t2_receipts(root, now=_T0 + 3 * _DAY)
    assert fired is False
    assert "too early to read, by design" in detail


def test_p16_fires_when_the_bar_is_met(tmp_path):
    """The load-bearing case. A predicate that only ever tests its quiet branch is
    indistinguishable from one that can never fire."""
    root = _fleet(tmp_path, {"a": 4, "b": 4, "c": 2})
    fired, detail = tw.p16_t2_receipts(root, now=_T0 + 5 * _DAY)
    assert fired is True
    assert "T2 BAR MET" in detail and "GREEN LIGHT" in detail
    assert "a 4, b 4, c 2" in detail


def test_p16_holds_at_two_projects_however_many_receipts(tmp_path):
    """Three projects is not decoration: two cannot separate a venue effect from one
    project's bad checkpoint."""
    root = _fleet(tmp_path, {"a": 20, "b": 20})
    assert tw.p16_t2_receipts(root, now=_T0 + 5 * _DAY)[0] is False


def test_p16_holds_below_the_receipt_bar_across_enough_projects(tmp_path):
    root = _fleet(tmp_path, {"a": 3, "b": 3, "c": 3})
    assert tw.p16_t2_receipts(root, now=_T0 + 5 * _DAY)[0] is False


def test_p16_fires_on_patience_and_names_the_RATE_as_the_finding(tmp_path):
    """Thin data after 30 days is a finding about the ask landing — NOT about Mnemos.
    A message that reads like failure invites the substitution the stopping rule forbids."""
    root = _fleet(tmp_path, {"a": 2})
    fired, detail = tw.p16_t2_receipts(root, now=_T0 + 31 * _DAY)
    assert fired is True
    assert "THE FINDING IS THE RATE, NOT MNEMOS" in detail
    assert "Do NOT read the thin data as a verdict" in detail


def test_p16_never_counts_tesseras_own_receipts(tmp_path):
    """The entire reason this shipped downstream: active.md disqualifies tessera's own
    receipts as evidence, so they must not be able to satisfy the bar."""
    root = _fleet(tmp_path, {"a": 1}, own=50)
    fired, detail = tw.p16_t2_receipts(root, now=_T0 + 5 * _DAY)
    assert fired is False, "tessera's own receipts satisfied a downstream-only bar"
    assert "1/10 receipts" in detail


def test_p16_does_not_count_offers_as_receipts(tmp_path):
    """offer.py is the harness marking its own delivery. Counting it would rebuild
    `restore_injected` — one party certifying itself — one level up."""
    root = _fleet(tmp_path, {"a": 0, "b": 0, "c": 0})
    fired, detail = tw.p16_t2_receipts(root, now=_T0 + 5 * _DAY)
    assert fired is False
    assert "0/10 receipts" in detail


def test_p16_counts_same_named_projects_separately(tmp_path):
    """Cannot happen under today's single-parent glob — asserted anyway because the project
    count is HALF the bar, and a merged counter would undercount distinct projects and hold
    P16 QUIET. A predicate that fails by staying silent must not depend on a property of a
    different function (arbiter, 2026-07-29)."""
    root = tmp_path / "fleet" / "tessera"
    (root / ".tessera").mkdir(parents=True)
    (root / ".tessera" / "project.yml").write_text("profile: standard\n")
    receipt = json.dumps({"type": "restore_receipt", "data": {"sufficient": True}})
    for parent in ("one", "two", "three"):
        project = tmp_path / "fleet" / parent / "api"
        (project / ".tessera" / "logs").mkdir(parents=True)
        (project / ".tessera" / "project.yml").write_text("profile: standard\n")
        (project / ".tessera" / "logs" / "s.jsonl").write_text((receipt + "\n") * 4)

    # Three distinct projects that all happen to be named "api".
    projects = [tmp_path / "fleet" / p / "api" for p in ("one", "two", "three")]
    original = tw._downstream_projects
    tw._downstream_projects = lambda _root: projects
    try:
        fired, detail = tw.p16_t2_receipts(root, now=_T0 + 5 * _DAY)
    finally:
        tw._downstream_projects = original

    assert fired is True, f"three same-named projects collapsed into fewer: {detail}"
    assert "12 downstream restore receipts across 3 projects" in detail


# ─── Two defects arbiter reported 2026-08-07, relayed by hand into active.md item 7, fixed
# 2026-08-09. The reported MITIGATION was measured and did not hold, which is what made them
# urgent: active.md said a crash exits non-zero so the surfacer emits `runner-crashed`,
# "loud, not silent". An unhandled Python exception exits 1 — and the surfacer reads 1 as
# "something fired". A session got `=== OBSERVATORY WATCH ===` over an empty body and NO
# degraded event. Measured before fixing; each test below plants the failure.
def _crashing(_root):
    raise OSError("simulated: log vanished between glob and read")


def test_one_crashing_predicate_does_not_take_down_the_others(tmp_path, monkeypatch):
    root = _root(tmp_path)
    monkeypatch.setattr(tw, "PREDICATES", {"P-boom": _crashing,
                                           "P-ok": lambda r: (False, "fine")})
    results = tw.evaluate(root)
    assert len(results) == 2, results
    assert any(r["predicate"] == "P-ok" and r["detail"] == "fine" for r in results)


def test_a_crashed_predicate_is_marked_and_named(tmp_path, monkeypatch):
    """It must be DISTINGUISHABLE, not merely survivable — silently swallowing the crash
    would trade a loud failure for a quiet one, which is the fail-open class itself."""
    root = _root(tmp_path)
    monkeypatch.setattr(tw, "PREDICATES", {"P-boom": _crashing})
    r = tw.evaluate(root)[0]
    assert r["crashed"] is True and r["fired"] is True
    assert "PREDICATE CRASHED" in r["detail"] and "OSError" in r["detail"]


def test_crashed_predicates_are_excluded_from_the_fire_log(tmp_path, monkeypatch):
    """The fire-log feeds retire/graduate decisions. A crash is the ABSENCE of a
    measurement; counting it as a fire lets a broken predicate look busy in the statistics
    used to decide whether it earns its slot."""
    root = _root(tmp_path)
    monkeypatch.setattr(tw, "PREDICATES", {"P-boom": _crashing,
                                           "P-real": lambda r: (True, "genuinely fired")})
    tw.append_log(root, tw.evaluate(root))
    entry = json.loads((root / ".tessera" / "logs" / "watch.jsonl").read_text().strip())
    # Assert the KEY exists before its value: a missing key raises KeyError, which pytest
    # reports as an ERROR rather than a FAILURE — the contract violation then reads as test
    # noise instead of the omission it is (arbiter, 2026-08-09).
    assert "crashed" in entry, entry
    assert entry["fired"] == ["P-real"], entry
    assert entry["crashed"] == ["P-boom"], entry


def test_p16_survives_an_unreadable_log(tmp_path, monkeypatch):
    """The reported defect itself: an unguarded read_text() in p16_t2_receipts. Skipping
    UNDERCOUNTS, which can only hold the predicate quieter — never manufacture a bar-met."""
    root = _root(tmp_path)
    proj = tmp_path.parent / "downstream-probe"
    (proj / ".tessera" / "logs").mkdir(parents=True, exist_ok=True)
    bad = proj / ".tessera" / "logs" / "x.jsonl"
    bad.write_text("{}\n")
    monkeypatch.setattr(tw, "_downstream_projects", lambda r: [proj])

    # Patch NARROWLY. The first version replaced Path.read_text for every path, returning ""
    # for anything that was not the target — so any other file the predicate touched silently
    # read as empty and the test could pass for a reason it never stated (arbiter, 2026-08-09).
    # Delegating to the real implementation keeps the blast radius to the one file.
    real = Path.read_text
    monkeypatch.setattr(Path, "read_text", lambda self, **kw: (
        (_ for _ in ()).throw(OSError("gone")) if self == bad else real(self, **kw)))

    fired, detail = tw.p16_t2_receipts(root)
    assert "T2" in detail                      # returned a verdict rather than raising


def test_p16_under_bar_message_names_which_dimension_is_short(tmp_path, monkeypatch):
    """The second defect: the bars are AND-ed deliberately, so one can be met while the
    other is not — and the elapsed arm then said "under the 10/3 bar" while quoting a
    receipt count ABOVE 10. The AND is intended; the SENTENCE was wrong."""
    root = _root(tmp_path)
    projects = []
    for i in range(2):                          # 2 projects — under the 3-project bar
        p = tmp_path.parent / f"probe-{i}"
        (p / ".tessera" / "logs").mkdir(parents=True, exist_ok=True)
        (p / ".tessera" / "logs" / "a.jsonl").write_text(
            "\n".join(json.dumps({"type": "restore_receipt"}) for _ in range(9)) + "\n")
        projects.append(p)                      # 18 receipts — OVER the 10-receipt bar
    monkeypatch.setattr(tw, "_downstream_projects", lambda r: projects)
    late = tw.T2_SHIPPED + _dt.timedelta(days=tw.T2_PATIENCE_DAYS + 1)
    fired, detail = tw.p16_t2_receipts(root, now=late)
    assert fired
    assert "projects 2/3" in detail, detail
    assert "under the" not in detail, detail   # the self-contradicting phrasing is gone


def test_render_distinguishes_a_crash_from_a_fire(tmp_path, monkeypatch):
    """`crashed` was a first-class concept in the data model that render() could not see, so
    "0 fired, 2 crashed" rendered in the same shape as "2 fired" — missing coverage reading
    as findings (arbiter, 2026-08-09). Distinct from the exit-code fix, which taught the
    SURFACER the difference while the human-facing text still conflated them (#9)."""
    root = _root(tmp_path)
    monkeypatch.setattr(tw, "PREDICATES", {"P-boom": _crashing,
                                           "P-quiet": lambda r: (False, "nothing to report")})
    out = tw.render(tw.evaluate(root))
    assert "COULD NOT RUN" in out, out
    assert "Observatory triggers fired" not in out, out      # nothing actually fired
    assert "INCOMPLETE" in out and "not evidence of absence" in out, out


def test_render_keeps_crashes_out_of_the_fired_section(tmp_path, monkeypatch):
    root = _root(tmp_path)
    monkeypatch.setattr(tw, "PREDICATES", {"P-boom": _crashing,
                                           "P-real": lambda r: (True, "genuinely fired")})
    out = tw.render(tw.evaluate(root))
    fired_block = out.split("Observatory triggers fired")[1]
    assert "P-real" in fired_block and "P-boom" not in fired_block, out


def test_render_flags_incompleteness_even_when_something_fired(tmp_path, monkeypatch):
    """THE MIXED CASE, which the first version of the footer did not cover: with both fires
    and crashes it appended nothing, so the operator read the fired set as the whole picture
    — the same defect the crashed section exists to fix, surviving in the one shape it was
    not tested against (arbiter, 2026-08-09)."""
    root = _root(tmp_path)
    monkeypatch.setattr(tw, "PREDICATES", {"P-boom": _crashing,
                                           "P-real": lambda r: (True, "genuinely fired")})
    out = tw.render(tw.evaluate(root))
    assert "genuinely fired" in out and "INCOMPLETE" in out, out
    assert "not evidence of absence" in out, out


def test_snoozed_predicate_that_crashes_is_reported_not_silenced(tmp_path, monkeypatch):
    """A snooze says "I know this FIRES, quiet it", never "I accept it being BROKEN". The
    comment here previously claimed 💤 and was invalidated by a later edit to render()."""
    root = _root(tmp_path)
    monkeypatch.setattr(tw, "PREDICATES", {"P-boom": _crashing})
    monkeypatch.setattr(tw, "active_snooze_labels", lambda r, n: {"P-boom"})
    monkeypatch.setattr(tw, "_load_snoozes",
                        lambda r: {"P-boom": {"until": "2099-01-01", "reason": "x"}})
    results = tw.evaluate(root)
    assert results[0]["snoozed"] and results[0]["crashed"]
    assert "COULD NOT RUN" in tw.render(results)      # ⚠ section, not 💤


# ── Whole-file arbiter review, 2026-08-09. Five CONFIRMED findings, one guard each. ────────
# Every one of these was watched FAILING against the re-planted defect before being kept
# (standing pattern #10). Two other reported findings and one advisory were REJECTED on
# measurement and deliberately have no test: a test asserting a non-defect is a claim that
# the defect existed.


def test_p5_is_quiet_when_the_skills_mirror_is_absent(tmp_path):
    """F1. `.claude/skills` is GITIGNORED — absent on every fresh clone until ./install.sh.

    `iterdir()` raised FileNotFoundError there, evaluate() marked P5 crashed, main() exited
    2, and tessera-watch-surface.sh reported `runner-crashed` — a false alarm about the
    RUNNER on the one state install.sh exists to fix. Reproduced on a real `git clone`.
    """
    root = _root(tmp_path)
    (root / ".claude" / "skills").rmdir()
    assert tw.p5_skills(root) == (False, "no .claude/skills mirror (unbuilt or absent) "
                                         "— nothing to route")
    crashed = [r for r in tw.evaluate(root) if r["predicate"].startswith("P5")]
    assert crashed and not crashed[0]["crashed"], crashed


def test_p5_still_counts_when_the_mirror_is_there(tmp_path):
    """The guard must not have bought quiet by making P5 quiet everywhere."""
    root = _root(tmp_path)
    for i in range(tw.SKILL_MIN):
        (root / ".claude" / "skills" / f"s{i}").mkdir()
    fired, detail = tw.p5_skills(root)
    assert fired is True and f"{tw.SKILL_MIN} skills" in detail


def test_p8_stays_quiet_when_doccheck_is_simply_absent(tmp_path):
    """F3, half one: no doccheck to IMPORT is a legitimate state, not an alarm.

    IN A SUBPROCESS, and the first version of this test is why. In-process, pytest already
    has the real `scripts/` on sys.path, so `import doccheck` SUCCEEDS and the real checker
    runs against a tmp root — the absent branch is unreachable from inside this run. The
    test passed nothing and failed for a reason that had nothing to do with the code.
    """
    import subprocess
    import sys
    root = _root(tmp_path)
    (root / "scripts").mkdir()
    proc = subprocess.run(
        [sys.executable, "-c",
         "import sys;"
         "from importlib.machinery import SourceFileLoader;"
         "from importlib.util import module_from_spec, spec_from_loader;"
         f"l = SourceFileLoader('tw', {str(_path)!r});"
         "m = module_from_spec(spec_from_loader('tw', l)); l.exec_module(m);"
         "from pathlib import Path;"
         f"print(m.p8_doc_drift(Path({str(root)!r})))"],
        capture_output=True, text=True, cwd=str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert "False" in proc.stdout and "nothing to check" in proc.stdout, proc.stdout


def test_p8_lets_a_broken_doccheck_crash_instead_of_reporting_docs_honest(tmp_path,
                                                                          monkeypatch):
    """F3, half two — the defect. A doccheck that EXPLODES used to return fired=False, and
    render() prints only fired/snoozed/crashed, so 'doccheck unavailable' reached nobody:
    a doc-drift detector reporting a clean run on a checker that never ran (#2, #12).
    It must now propagate, so evaluate() marks it crashed and main() exits 2.
    """
    root = _root(tmp_path)
    (root / "scripts").mkdir()
    (root / "scripts" / "doccheck.py").write_text(
        "CHECKS = {}\n"
        "def run():\n"
        "    raise RuntimeError('the doc checker itself is broken')\n")
    import sys
    sys.modules.pop("doccheck", None)
    try:
        results = tw.evaluate(root)
    finally:
        sys.modules.pop("doccheck", None)
        while str(root / "scripts") in sys.path:
            sys.path.remove(str(root / "scripts"))
    p8 = [r for r in results if r["predicate"].startswith("P8")][0]
    assert p8["crashed"] is True, p8
    assert "COULD NOT RUN" in tw.render(results)


def test_every_globbed_log_read_survives_an_unreadable_file(tmp_path, monkeypatch):
    """F4 — the CLASS, not the reported row.

    arbiter named P7 and said it was the last unguarded reader. It was not: P3's compaction
    log, P13's degraded scan and `_read_firelog` had the identical hole, and P13 LOOKS
    guarded (its try covers stat() only; errors='replace' guards decoding, not OSError).
    Simulated by making read_text raise, which is what a vanished-between-glob-and-read or
    permission-denied file does — the real cases cannot be staged as root.
    """
    root = _root(tmp_path)
    (root / ".mnemos").mkdir()
    (root / ".mnemos" / "checkpoint-latest.json").write_text(
        json.dumps({"goal": "g", "active_constraints": [], "task_narrative": "n"}))
    (root / ".mnemos" / "compaction-log.jsonl").write_text('{"event":"compaction_fired"}\n')
    logs = root / ".tessera" / "logs"
    logs.mkdir(parents=True)
    (logs / "s.jsonl").write_text('{"type":"degraded","ts":"2099-01-01T00:00:00Z"}\n')
    (logs / "watch.jsonl").write_text('{"fired":["P1 hook-drift"]}\n')

    real_read_text = Path.read_text

    def boom(self, *a, **k):
        # ONLY the .jsonl logs. Patching every read would also hit P3's checkpoint, which is
        # a different read with a different right answer (it FIRES — see the test below), and
        # a test that cannot tell those two apart is not testing either.
        if self.suffix == ".jsonl":
            raise PermissionError(13, "Permission denied")
        return real_read_text(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", boom)
    # Each of the four sites must return a RESULT, not raise. Before the shared reader,
    # every one of these raised PermissionError.
    assert tw.p3_restore_integrity(root)[0] is False
    assert tw.p7_gate_labels(root)[0] is False
    assert tw.p13_degraded(root)[0] is False
    assert tw.p16_t2_receipts(root)[0] is False   # the fifth site, added after the verifier
    assert tw._read_firelog(root) == []           # noted this test asserted only four


def test_p3_reports_an_unreadable_checkpoint_instead_of_crashing(tmp_path, monkeypatch):
    """F4's sibling, and the one case where quiet would be WRONG.

    A checkpoint that exists and cannot be read is an UNDELIVERABLE payload — exactly the
    question T1 asks — so P3 must FIRE and say so, not return [] and read as deliverable,
    and not crash into a ⚠ that says nothing about the restore path.
    """
    root = _root(tmp_path)
    (root / ".mnemos").mkdir()
    ck = root / ".mnemos" / "checkpoint-latest.json"
    ck.write_text(json.dumps({"goal": "g", "active_constraints": [], "task_narrative": "n"}))
    real_read_text = Path.read_text

    def boom(self, *a, **k):
        if self.name == "checkpoint-latest.json":
            raise PermissionError(13, "Permission denied")
        return real_read_text(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", boom)
    fired, detail = tw.p3_restore_integrity(root)
    assert fired is True, detail
    assert "cannot be read" in detail


def test_p15_treats_an_empty_counter_file_as_no_counter(tmp_path):
    """F5. `touch` or a truncated write left this empty, and empty fell into the non-dict
    branch: "holds a legacy global counter ('')" — a report that the spend backstop had been
    permanently silenced. Inverted, not merely mis-worded: backstop._read_fires() returns {}
    for an empty file ON PURPOSE, so the backstop is fully enabled in exactly this state.
    """
    root = _root(tmp_path)
    (root / ".tessera").mkdir()
    (root / ".tessera" / ".spend-backstop-fires").write_text("   \n")
    fired, detail = tw.p15_spend_backstop_suppressed(root)
    assert fired is False, detail
    assert "legacy" not in detail


def test_p15_still_fires_on_a_real_legacy_counter(tmp_path):
    """The empty-file guard must not have swallowed the state P15 exists for."""
    root = _root(tmp_path)
    (root / ".tessera").mkdir()
    (root / ".tessera" / ".spend-backstop-fires").write_text("47")
    fired, detail = tw.p15_spend_backstop_suppressed(root)
    assert fired is True and "legacy global counter" in detail


def test_p12_compares_bytes_not_a_stat_signature(tmp_path):
    """M-2 (mine, not arbiter's). `filecmp.dircmp.diff_files` is a SHALLOW compare: same
    size + same mtime is declared identical without reading either file. Measured — this
    predicate returned "repo skills/ == global mirror" on 4 bytes vs 4 different bytes.
    `tessera-sync-skills` is `rsync -a`, which PRESERVES mtime, so the two sides routinely
    share one. p4_downstream's own docstring quotes the rule this broke: *a drift check that
    doesn't compare bytes isn't a drift check* (F-003).
    """
    import os
    root, mirror = tmp_path / "repo", tmp_path / "mirror"
    (root / "skills" / "base").mkdir(parents=True)
    (mirror / "base").mkdir(parents=True)
    a, b = root / "skills" / "base" / "SKILL.md", mirror / "base" / "SKILL.md"
    a.write_text("AAAA")
    b.write_text("BBBB")                     # same size, different bytes
    st = os.stat(a)
    os.utime(b, (st.st_atime, st.st_mtime))  # ...and now the same mtime
    fired, detail = tw.p12_skill_registry_drift(root, global_dir=mirror)
    assert fired is True, detail
    assert "differs: base/SKILL.md" in detail


def test_p12_stays_quiet_on_a_genuinely_identical_mirror(tmp_path):
    """The byte compare must not turn every mirror into drift."""
    root, mirror = tmp_path / "repo", tmp_path / "mirror"
    (root / "skills" / "base").mkdir(parents=True)
    (mirror / "base").mkdir(parents=True)
    (root / "skills" / "base" / "SKILL.md").write_text("same")
    (mirror / "base" / "SKILL.md").write_text("same")
    assert tw.p12_skill_registry_drift(root, global_dir=mirror)[0] is False


# ── Two more, found reading the file rather than in arbiter's list. Both need a foreign
#    writer to trigger — no producer emits either shape today — and both crash a predicate
#    on INPUT, which is the one thing the single reporter for P3/P4/P9/P11–P16 must not do.


def test_p13_survives_a_degraded_event_with_a_naive_timestamp(tmp_path):
    """A naive `ts` PARSES and then explodes on the aware-minus-naive subtraction, so the
    except around fromisoformat never sees it. `tessera-degraded` always writes Z — but
    P13 scans EVERY .jsonl in .tessera/logs, written by five producers, and a crash here
    silences the spec-11 channel: the predicate whose job is reporting that something else
    could not do its job.
    """
    root = _root(tmp_path)
    logs = root / ".tessera" / "logs"
    logs.mkdir(parents=True)
    now = _dt.datetime.now(_dt.timezone.utc)
    naive = now.replace(tzinfo=None).isoformat()          # no offset, otherwise identical
    (logs / "s.jsonl").write_text(json.dumps(
        {"type": "degraded", "ts": naive,
         "data": {"component": "hook", "reason": "toolchain-missing"}}) + "\n")
    fired, detail = tw.p13_degraded(root, now=now)
    assert fired is True, detail
    assert "hook/toolchain-missing" in detail


def test_p6_counts_a_malformed_status_as_needing_attention(tmp_path):
    """A non-string `status` crashed `.split`. The packet-level guard right above already
    decided that a packet P6 cannot understand counts as needs-attention rather than being
    dropped; this applies the same rule one line further down."""
    root = _root(tmp_path)
    esc = root / ".tessera" / "escalations"
    esc.mkdir(parents=True)
    (esc / "e.json").write_text(json.dumps({"status": 3, "summary": "x"}))
    fired, detail = tw.p6_escalations(root)
    assert fired is True and "1 open escalations" in detail


def test_p6_still_ignores_a_resolved_packet(tmp_path):
    """The malformed-status guard must not have made every packet count as open."""
    root = _root(tmp_path)
    esc = root / ".tessera" / "escalations"
    esc.mkdir(parents=True)
    (esc / "e.json").write_text(json.dumps({"status": "resolved:2026-08-09"}))
    assert tw.p6_escalations(root)[0] is False


# ── Returned as CAVEATS by bin/tessera-verify while CONFIRMING the fixes above. The
#    log-read fix was written to be the class and was still one row short of it: the globbed
#    *byte* comparisons (P1, P4, P14) and P11's globbed stat() were untouched. That is
#    standing pattern #11 aimed at the commit that cites #11.


def _unreadable(monkeypatch, predicate):
    """Make read_bytes raise for the *right-hand* side of every drift comparison."""
    real = Path.read_bytes

    def boom(self, *a, **k):
        if predicate(self):
            raise PermissionError(13, "Permission denied")
        return real(self, *a, **k)

    monkeypatch.setattr(Path, "read_bytes", boom)


def test_p1_reports_an_unreadable_template_as_drift_not_as_in_sync(tmp_path, monkeypatch):
    """Unreadable must be DRIFT. Quiet would mean a drift check reporting 'in sync' about a
    file it could not compare — the fail-open this watcher exists to catch, aimed at the
    watcher — and raising would crash the predicate."""
    root = _root(tmp_path)
    (root / ".claude" / "scripts" / "h.sh").write_text("same\n")
    (root / "templates" / "h.sh").write_text("same\n")
    assert tw.p1_hook_drift(root)[0] is False           # identical, and readable
    _unreadable(monkeypatch, lambda p: p.parent.name == "templates")
    fired, detail = tw.p1_hook_drift(root)
    assert fired is True and "h.sh" in detail


def test_p14_reports_an_unreadable_global_copy_as_stale(tmp_path, monkeypatch):
    root = _root(tmp_path)
    home = tmp_path / "home"
    tier3 = home / ".claude" / "templates"
    tier3.mkdir(parents=True)
    (root / ".claude" / "scripts" / "h.sh").write_text("same\n")
    (tier3 / "h.sh").write_text("same\n")
    (home / ".claude" / ".bootstrap-dir").write_text(str(root))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))
    assert tw.p14_global_tier_drift(root)[0] is False
    _unreadable(monkeypatch, lambda p: p.parent == tier3)
    fired, detail = tw.p14_global_tier_drift(root)
    assert fired is True and "STALE" in detail and "h.sh" in detail


def test_p11_skips_a_transcript_that_cannot_be_statted(tmp_path, monkeypatch):
    """A transcript vanishing between glob() and stat() crashed P11 — and it called stat()
    three times per file, so a rotation between two of them could judge one file on two
    different snapshots. Skipping UNDERCOUNTS, which can only hold P11 quieter; it can never
    manufacture a 'pipe is DEAD' alarm."""
    root = _root(tmp_path)
    tdir = tmp_path / "transcripts"
    _transcript(tdir, "ghost", age_h=24)
    _sessions_db(root, ["other"])
    assert tw.p11_ingest_pipe(root, tdir)[0] is True    # normally fires: never ingested
    real_stat = Path.stat

    def boom(self, *a, **k):
        if self.name == "ghost.jsonl":
            raise FileNotFoundError(2, "No such file or directory")
        return real_stat(self, *a, **k)

    monkeypatch.setattr(Path, "stat", boom)
    fired, detail = tw.p11_ingest_pipe(root, tdir)
    assert fired is False, detail                       # skipped, not crashed


def test_p15_legacy_message_states_the_shape_not_a_suppression(tmp_path):
    """A bare `0` is the same pre-fix SHAPE with nothing suppressed yet, and the message
    asserted a suppression had occurred. Over-claiming turns a correct alarm into a false
    report — which is P15's own subject (#12)."""
    root = _root(tmp_path)
    (root / ".tessera").mkdir()
    for raw in ("0", "not json", "47"):
        (root / ".tessera" / ".spend-backstop-fires").write_text(raw)
        fired, detail = tw.p15_spend_backstop_suppressed(root)
        assert fired is True, raw
        assert "legacy global counter" in detail
        assert "silences the spend backstop" in detail          # conditional...
        assert "silenced the spend backstop in EVERY" not in detail  # ...not asserted


def test_p14_owner_check_compares_the_directory_not_its_spelling(tmp_path, monkeypatch):
    """P14 WAS SILENCED BY THIS, LIVE, on 2026-08-09, by running ./install.sh.

    install.sh writes `$REPO` as `pwd` hands it over, and macOS's filesystem is
    CASE-INSENSITIVE: a run from `/Users/…/claude/tessera` recorded that spelling while
    ROOT resolves to `/Users/…/Claude/tessera`. Same directory. The old `owner != str(root)`
    read it as a foreign owner and returned quiet — and quiet is INDISTINGUISHABLE IN THE
    RENDER from "the global tier is in sync". The predicate whose whole subject is that
    uniform staleness reads as agreement was silenced by that shape one level up.

    TWO ALIASES, AND THE SECOND ONE IS THE LOAD-BEARING HALF. The first draft of this test
    used only a symlink — and re-planting `resolve()` in place of `samefile` made it PASS,
    because `resolve()` follows symlinks. It proved "not a raw string compare" and would
    have gone green on a fix that does not fix the bug that was actually observed. So the
    case-variant is tested too: it is the one `resolve()` cannot normalize, and it is the
    one that happened. Skipped, LOUDLY, where the filesystem makes it meaningless.
    """
    import pytest
    root = _root(tmp_path)
    home = tmp_path / "home"
    tier3 = home / ".claude" / "templates"
    tier3.mkdir(parents=True)
    (root / ".claude" / "scripts" / "h.sh").write_text("same\n")
    (tier3 / "h.sh").write_text("same\n")
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))

    # Alias 1 — a symlink. Works on every filesystem; catches a raw string compare, and on
    # its own catches NOTHING ELSE, since resolve() would satisfy it too.
    alias = tmp_path / "alias-to-root"
    alias.symlink_to(root)
    assert str(alias) != str(root)
    (home / ".claude" / ".bootstrap-dir").write_text(str(alias))
    _, detail = tw.p14_global_tier_drift(root)
    assert "not asserting on it" not in detail, detail
    assert "matches all" in detail, detail

    # Alias 2 — a CASE VARIANT, which is what install.sh actually wrote. resolve() does not
    # normalize case, so only a same-inode test passes this. Meaningless where the
    # filesystem is case-sensitive: there the variant is a genuinely different directory.
    probe = tmp_path / "CaseProbe"
    probe.mkdir()
    if not (tmp_path / "caseprobe").is_dir():
        pytest.skip("case-sensitive filesystem — the spelling that silenced P14 in the "
                    "wild cannot be reproduced here; the symlink half above still ran")
    swapped = str(root).swapcase() if str(root) != str(root).swapcase() else str(root).upper()
    assert Path(swapped).is_dir() and swapped != str(root)
    (home / ".claude" / ".bootstrap-dir").write_text(swapped)
    _, cased = tw.p14_global_tier_drift(root)
    assert "not asserting on it" not in cased, cased
    assert "matches all" in cased, cased

    # ...and a genuinely foreign owner must STILL silence it — that guard is the point of the
    # marker, and a fix that asserted on every machine would be worse than the bug.
    other = tmp_path / "some-other-checkout"
    other.mkdir()
    (home / ".claude" / ".bootstrap-dir").write_text(str(other))
    _, foreign = tw.p14_global_tier_drift(root)
    assert "not asserting on it" in foreign, foreign

    # A recorded owner that no longer exists is not this repo either — samefile raises there.
    (home / ".claude" / ".bootstrap-dir").write_text(str(tmp_path / "reaped-worktree"))
    _, gone = tw.p14_global_tier_drift(root)
    assert "not asserting on it" in gone, gone
