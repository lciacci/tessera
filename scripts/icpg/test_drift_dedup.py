"""Dedup on insert, and the report being adjudicable at all.

THE DEFECT: `create_drift_event` INSERTed unconditionally with a fresh UUID on every
scan, and `mnemos-pre-edit.sh` runs a scan on every Edit/Write. 700 rows were ~154
distinct drifts across 31 scans; one pair appeared 21 times. The report printed
`[0.65] Drift detected: test(0.30), usage(1.00)` with no symbol, no file, and no id —
so the top five events were byte-identical (they were the same drift, repeatedly) and
`icpg drift resolve`, which has existed since the module was written, could not be
invoked because nothing ever printed the argument it needs.

THE KEY IS A JUDGEMENT, and it is the part worth guarding: `(symbol_id, reason_id,
sorted(dimensions))`, NOT the description. The description embeds the scores, so
`usage(1.00)` -> `usage(0.90)` would mint a new row and the backlog would keep
creeping — the same defect wearing a smaller hat.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from icpg.models import DriftEvent
from icpg.store import ICPGStore


def _store() -> ICPGStore:
    store = ICPGStore(tempfile.mkdtemp())
    store.init_db()
    return store


def _event(dims=('usage',), severity=0.5, sym='sym-1', reason='r-1',
           at='2026-07-27T00:00:00+00:00') -> DriftEvent:
    return DriftEvent(
        id=f'evt-{sym}-{"-".join(dims)}-{at}-{severity}',
        symbol_id=sym, from_reason_id=reason,
        drift_dimensions=list(dims), severity=severity,
        description=f'Drift detected: {", ".join(dims)}', detected_at=at,
    )


def _open_rows(store: ICPGStore) -> list:
    return store.get_unresolved_drift()


# --- the insert path --------------------------------------------------------------


def test_the_same_drift_twice_is_one_row():
    store = _store()
    store.create_drift_event(_event())
    store.create_drift_event(_event(at='2026-07-27T01:00:00+00:00'))
    rows = _open_rows(store)
    assert len(rows) == 1
    assert rows[0].seen_count == 2


def test_a_repeat_returns_the_surviving_id_not_a_new_one():
    """Callers print what this returns; handing back an id that is not in the table
    would put an unusable argument in front of the user — the original defect."""
    store = _store()
    first = store.create_drift_event(_event())
    second = store.create_drift_event(_event(at='2026-07-27T02:00:00+00:00'))
    assert first == second


def test_a_severity_change_updates_in_place():
    """THE KEY CHOICE. Keying on the description would make this two rows, because the
    description carries the scores."""
    store = _store()
    store.create_drift_event(_event(severity=0.5))
    store.create_drift_event(_event(severity=0.9))
    rows = _open_rows(store)
    assert len(rows) == 1
    assert rows[0].severity == 0.9, "the refresh must carry the new severity"


def test_a_different_dimension_set_is_a_different_drift():
    store = _store()
    store.create_drift_event(_event(dims=('usage',)))
    store.create_drift_event(_event(dims=('usage', 'changed')))
    assert len(_open_rows(store)) == 2


def test_dimension_order_does_not_fork_the_key():
    store = _store()
    store.create_drift_event(_event(dims=('usage', 'changed')))
    store.create_drift_event(_event(dims=('changed', 'usage')))
    assert len(_open_rows(store)) == 1


def test_a_different_symbol_is_a_different_drift():
    store = _store()
    store.create_drift_event(_event(sym='sym-1'))
    store.create_drift_event(_event(sym='sym-2'))
    assert len(_open_rows(store)) == 2


def test_a_recurrence_after_resolution_is_news_not_a_merge():
    """A drift someone adjudicated and closed, recurring, must NOT be folded back into
    the closed row — that would silently resurrect a finding as though it never left."""
    store = _store()
    first = store.create_drift_event(_event())
    store.resolve_drift(first)
    store.create_drift_event(_event(at='2026-07-28T00:00:00+00:00'))
    assert len(_open_rows(store)) == 1
    assert _open_rows(store)[0].id != first


def test_detected_at_keeps_meaning_first_seen():
    store = _store()
    store.create_drift_event(_event(at='2026-07-01T00:00:00+00:00'))
    store.create_drift_event(_event(at='2026-07-27T00:00:00+00:00'))
    row = _open_rows(store)[0]
    assert row.detected_at.startswith('2026-07-01')
    assert (row.last_seen or '').startswith('2026-07-27')


# --- the migration, against a pre-dedup database ------------------------------------


def _legacy_db(path: Path, rows: list[tuple]) -> None:
    """A drift_events table in its pre-2026-07-27 shape, with duplicate rows."""
    conn = sqlite3.connect(str(path))
    conn.execute("""CREATE TABLE drift_events (
        id TEXT PRIMARY KEY, symbol_id TEXT NOT NULL, from_reason_id TEXT NOT NULL,
        drift_dimensions TEXT DEFAULT '[]', severity REAL DEFAULT 0.5,
        description TEXT, resolved INTEGER DEFAULT 0, detected_at TEXT NOT NULL)""")
    conn.executemany(
        'INSERT INTO drift_events (id, symbol_id, from_reason_id, drift_dimensions, '
        'severity, description, resolved, detected_at) VALUES (?,?,?,?,?,?,?,?)', rows)
    conn.commit()
    conn.close()


def test_migration_collapses_pre_existing_duplicates():
    """Dedup-on-insert alone would strand them: a later scan refreshes ONE copy and the
    rest sit unreachable forever. The backlog stops growing while staying unreadable."""
    project = Path(tempfile.mkdtemp())
    (project / '.icpg').mkdir()
    dims = json.dumps(['usage'])
    _legacy_db(project / '.icpg' / 'reason.db', [
        (f'old-{i}', 'sym-1', 'r-1', dims, 0.5, 'Drift detected: usage(0.50)', 0,
         f'2026-07-2{i}T00:00:00+00:00') for i in range(1, 4)
    ])
    rows = ICPGStore(str(project)).get_unresolved_drift()
    assert len(rows) == 1
    assert rows[0].id == 'old-1', "the survivor must be the OLDEST, so detected_at still means first-seen"
    assert rows[0].seen_count == 3, "the collapsed copies must be counted, not discarded"


def test_migration_leaves_resolved_rows_alone():
    """Merging into an adjudicated row would resurrect a closed finding."""
    project = Path(tempfile.mkdtemp())
    (project / '.icpg').mkdir()
    dims = json.dumps(['usage'])
    _legacy_db(project / '.icpg' / 'reason.db', [
        ('closed-1', 'sym-1', 'r-1', dims, 0.5, 'd', 1, '2026-07-21T00:00:00+00:00'),
        ('closed-2', 'sym-1', 'r-1', dims, 0.5, 'd', 1, '2026-07-22T00:00:00+00:00'),
    ])
    store = ICPGStore(str(project))
    assert store.get_unresolved_drift() == []
    conn = sqlite3.connect(str(project / '.icpg' / 'reason.db'))
    assert conn.execute('SELECT COUNT(*) FROM drift_events').fetchone()[0] == 2


def test_migration_is_idempotent():
    project = Path(tempfile.mkdtemp())
    (project / '.icpg').mkdir()
    dims = json.dumps(['usage'])
    _legacy_db(project / '.icpg' / 'reason.db', [
        ('old-1', 'sym-1', 'r-1', dims, 0.5, 'd', 0, '2026-07-21T00:00:00+00:00'),
        ('old-2', 'sym-1', 'r-1', dims, 0.5, 'd', 0, '2026-07-22T00:00:00+00:00'),
    ])
    assert len(ICPGStore(str(project)).get_unresolved_drift()) == 1
    assert len(ICPGStore(str(project)).get_unresolved_drift()) == 1



# ── ADR-0016: dismissed = the detector was wrong, and it stays quiet ───────────────────

def test_dismissed_is_not_resolved():
    """Two different facts. `resolved` = real drift, fixed. `dismissed` = never real.
    Merging them throws away the only signal that can retire a dimension."""
    store = _store()
    rid = store.create_drift_event(_event())
    store.dismiss_drift(rid, 'usage threshold is noise on a common name')
    assert _open_rows(store) == []
    assert store.dismissals_by_dimension() == {'usage': 1}


def test_a_resolved_drift_is_not_counted_as_a_dismissal():
    store = _store()
    rid = store.create_drift_event(_event())
    store.resolve_drift(rid, note='renamed the symbol')
    assert store.dismissals_by_dimension() == {}


def test_stats_headline_agrees_with_the_list_it_summarises():
    """FOUND 2026-07-27 by dismissing 165 events at once (ADR-0017's retirement).

    `get_stats()['unresolved_drift']` counted `resolved = 0` ALONE while
    `get_unresolved_drift()` filtered `resolved = 0 AND dismissed = 0`. So
    `icpg status` printed `Unresolved drift: 224` directly above
    `icpg drift list  # all 59`, and **dismissing a finding changed nothing in
    the number anyone looks at** — ADR-0016 built the verb, and the headline
    ignored it. That is ADR-0013's only-increments counter in a second function.

    Invisible while exactly one event had ever been dismissed. The bug needed a
    bulk disposition to become a gap big enough to notice, which is the argument
    for asserting the two agree rather than asserting either number.
    """
    store = _store()
    store.create_drift_event(_event(sym='sym-open'))
    rid_dismissed = store.create_drift_event(_event(sym='sym-dismissed'))
    rid_resolved = store.create_drift_event(_event(sym='sym-resolved'))
    store.dismiss_drift(rid_dismissed, 'detector was wrong')
    store.resolve_drift(rid_resolved, note='fixed')

    assert store.get_stats()['unresolved_drift'] == len(store.get_unresolved_drift()), (
        'the status headline and `drift list` must count the same set — a '
        'disposition that does not move the headline is not a disposition'
    )
    assert store.get_stats()['unresolved_drift'] == 1


def test_a_dismissed_drift_stays_suppressed_on_re_scan():
    """THE POINT of decision 4. Re-raising every scan re-litigates a closed ruling on every
    Stop — conclave F-001, which this repo already paid for once."""
    store = _store()
    rid = store.create_drift_event(_event(severity=0.5))
    store.dismiss_drift(rid, 'false positive')
    store.create_drift_event(_event(severity=0.5, at='2026-07-28T00:00:00+00:00'))
    assert _open_rows(store) == [], "a dismissed drift came back on an unchanged reading"


def test_a_severity_move_re_opens_a_dismissed_drift():
    """The dismissal was about a particular reading. New evidence, new question."""
    store = _store()
    rid = store.create_drift_event(_event(severity=0.5))
    store.dismiss_drift(rid, 'false positive at this level')
    store.create_drift_event(_event(severity=0.9))
    rows = _open_rows(store)
    assert len(rows) == 1
    assert rows[0].severity == 0.9


def test_re_opening_keeps_the_dismissal_note():
    """The same row is re-opened rather than a new one minted, so the record of why it was
    once dismissed travels with it."""
    store = _store()
    rid = store.create_drift_event(_event(severity=0.5))
    store.dismiss_drift(rid, 'thresholds are uncalibrated')
    store.create_drift_event(_event(severity=0.9))
    assert _open_rows(store)[0].id == rid


def test_a_new_dimension_is_a_new_question_not_a_suppressed_one():
    store = _store()
    rid = store.create_drift_event(_event(dims=('usage',)))
    store.dismiss_drift(rid, 'noise')
    store.create_drift_event(_event(dims=('usage', 'changed')))
    assert len(_open_rows(store)) == 1


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))


def test_a_malformed_dimensions_column_does_not_take_down_the_report():
    """FOUND BY REVIEW 2026-07-27, in this session's own code. Three places parse
    `drift_dimensions`; two guarded the parse and `_row_to_drift` did not, so ONE malformed
    row raised JSONDecodeError out of `get_unresolved_drift()` — taking down `icpg status`
    and `drift list`, and in the pre-edit hook path (stderr to /dev/null) taking down the
    drift surface SILENTLY. A bad row should cost that row's dimensions, not the report."""
    project = Path(tempfile.mkdtemp())
    (project / '.icpg').mkdir()
    _legacy_db(project / '.icpg' / 'reason.db', [
        ('bad', 's1', 'r1', 'NOT JSON', 0.5, 'd', 0, '2026-07-01T00:00:00+00:00'),
        ('good', 's2', 'r1', json.dumps(['usage']), 0.5, 'd', 0, '2026-07-02T00:00:00+00:00'),
    ])
    rows = ICPGStore(str(project)).get_unresolved_drift()
    assert len(rows) == 2, "a malformed row must not remove the readable ones"
    assert {r.id for r in rows} == {'bad', 'good'}
    assert next(r for r in rows if r.id == 'bad').drift_dimensions == []
