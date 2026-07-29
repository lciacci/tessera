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
    """Build a fake `mnemos` whose shebang is THIS interpreter, so P9 clears the mnemos
    gates and actually reaches the icpg branch. Without this the test short-circuits on an
    unreadable shebang and asserts nothing — which is how a vacuous test looks."""
    import sys
    fake = tmp_path / "mnemos"
    fake.write_text(f"#!{sys.executable}\n")
    monkeypatch.setattr(tw.shutil, "which",
                        lambda n: icpg if n == "icpg" else str(fake))
    (root / ".python-version").write_text("3.13\n")
    (root / ".venv" / "bin" / "python").write_text("x")


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


def test_p9_icpg_branch_is_reachable_on_the_real_repo():
    """Non-vacuity: this repo HAS .icpg/reason.db, so the branch is live rather than
    dead code that would never have run."""
    assert (Path(__file__).resolve().parent.parent / ".icpg" / "reason.db").exists()
    fired, detail = tw.p9_interpreter_drift(Path(__file__).resolve().parent.parent)
    assert "icpg ok" in detail or "icpg" in detail, detail


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
