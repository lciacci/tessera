"""Step 0 and step 6 of the loop: authoring an intent, and closing it.

Added 2026-07-27 (ADR-0019). Before this, `create` opened an intent as `proposed`
and only `record` promoted it to `executing` — so the auto-recorder, which keys on
the executing intent, could never see a freshly stated one. Record needed an
executing intent and only record could make one.

Nothing here automates step 0. `create` is deliberately agent-invoked: a hook
authoring intent would answer "does the agent state intent?" by making the question
unanswerable, which is the proxy trap `hooks/icpg-record-intent`'s header names.
"""

from __future__ import annotations

import pytest

from .models import ReasonNode
from .store import ICPGStore


def _store(tmp_path) -> ICPGStore:
    store = ICPGStore(str(tmp_path))
    store.init_db()
    return store


class _Args:
    """argparse.Namespace stand-in — only the fields cmd_create/cmd_fulfil read."""

    def __init__(self, **kw):
        defaults = dict(
            goal='ship the widget', owner='test', decision_type='task',
            scope=['widget.py'], agent=None, task_id=None, parent=None,
            infer_contracts=False, invariants=[], preconditions=[],
            postconditions=[], project='.', note=None,
        )
        defaults.update(kw)
        self.__dict__.update(defaults)


def test_create_opens_the_intent_as_executing(tmp_path, monkeypatch):
    """The recorder keys on `executing`. `proposed` was unreachable-by-design:
    only `record` promoted, and `record` needs something already promoted."""
    from . import __main__ as m
    monkeypatch.setattr(m, 'VectorStore', lambda *a, **k: type(
        'V', (), {'add_reason': lambda *a, **k: None})())
    store = _store(tmp_path)
    assert m.cmd_create(store, _Args(project=str(tmp_path))) == 0
    reasons = store.list_reasons()
    assert len(reasons) == 1
    assert reasons[0].status == 'executing', reasons[0].status
    assert len(store.list_reasons(status='executing')) == 1


def test_hand_authored_contracts_persist_all_three_kinds(tmp_path, monkeypatch):
    """design-principles.md names hand-authoring as the FIRST tier; until now the
    CLI exposed only --infer-contracts, which needs an LLM key and silently
    degrades to the scope->file_exists heuristic. The top tier was unreachable."""
    from . import __main__ as m
    monkeypatch.setattr(m, 'VectorStore', lambda *a, **k: type(
        'V', (), {'add_reason': lambda *a, **k: None})())
    store = _store(tmp_path)
    m.cmd_create(store, _Args(
        project=str(tmp_path),
        invariants=['file_exists("a.py")'],
        preconditions=['test_exists("t.py")'],
        postconditions=['file_exists("b.py")'],
    ))
    r = store.list_reasons()[0]
    assert r.invariants == ['file_exists("a.py")']
    assert r.preconditions == ['test_exists("t.py")']
    assert r.postconditions == ['file_exists("b.py")']


def test_inference_does_not_erase_hand_authored_contracts(tmp_path, monkeypatch):
    """Union, not replace. Inference overwriting a deliberately stated predicate
    would silently discard the more trustworthy of the two."""
    from . import __main__ as m
    monkeypatch.setattr(m, 'VectorStore', lambda *a, **k: type(
        'V', (), {'add_reason': lambda *a, **k: None})())
    monkeypatch.setattr(m, 'infer_contracts', lambda *a, **k: {
        'preconditions': [], 'postconditions': [],
        'invariants': ['file_exists("inferred.py")'],
    })
    store = _store(tmp_path)
    m.cmd_create(store, _Args(
        project=str(tmp_path), infer_contracts=True,
        invariants=['file_exists("authored.py")'],
    ))
    inv = store.list_reasons()[0].invariants
    assert 'file_exists("authored.py")' in inv, 'hand-authored contract was erased'
    assert 'file_exists("inferred.py")' in inv, 'inferred contract was dropped'


def test_fulfil_closes_the_intent_and_frees_the_recorder(tmp_path):
    """The close verb (d). Without it `executing` only ever grows, and the
    recorder — which acts only on exactly ONE — goes permanently silent after the
    second intent."""
    from . import __main__ as m
    store = _store(tmp_path)
    a = ReasonNode(goal='first', owner='t', status='executing')
    b = ReasonNode(goal='second', owner='t', status='executing')
    store.create_reason(a)
    store.create_reason(b)
    assert len(store.list_reasons(status='executing')) == 2   # recorder is stuck

    assert m.cmd_fulfil(store, _Args(reason=a.id[:8])) == 0
    assert len(store.list_reasons(status='executing')) == 1   # unstuck
    assert store.get_reason(a.id).status == 'fulfilled'
    assert store.get_reason(a.id).fulfilled_at


def test_fulfil_fails_loud_on_an_unknown_id(tmp_path):
    """`update_reason_status` is an UPDATE ... WHERE id = ?, which reports success
    whether or not a row matched. A close verb that closes nothing while printing
    success leaves the intent open and the operator believing it shut — the same
    fail-open that scored an unknown session as 0.00 CLEAR."""
    from . import __main__ as m
    store = _store(tmp_path)
    store.create_reason(ReasonNode(goal='real', owner='t', status='executing'))
    assert m.cmd_fulfil(store, _Args(reason='deadbeef')) == 1
    assert len(store.list_reasons(status='executing')) == 1


def test_fulfil_refuses_an_ambiguous_prefix(tmp_path):
    """Two intents sharing a prefix must not silently close the first match."""
    from . import __main__ as m
    store = _store(tmp_path)
    for r in (ReasonNode(goal='a', owner='t', status='executing'),
              ReasonNode(goal='b', owner='t', status='executing')):
        store.create_reason(r)
    assert m.cmd_fulfil(store, _Args(reason='')) == 1        # '' prefixes everything
    assert len(store.list_reasons(status='executing')) == 2


def test_recording_the_same_symbols_twice_does_not_duplicate_edges(tmp_path):
    """FOUND BY REVIEW 2026-07-27, an hour after the Stop recorder was wired.

    `create_edge` uses `INSERT OR IGNORE`, which READS as deduplicating. It was
    not: the only UNIQUE column was `id`, a fresh uuid4 per call, so the conflict
    clause could never fire and every re-record appended a row. Harmless while
    `record` was manual and had never actually run — the recorder made it live,
    because Stop fires per TURN, so one session would append the same edges dozens
    of times. Measured on the live graph at 995 rows / 891 distinct after three
    runs.

    ADR-0013's drift-backlog defect (700 rows = 154 distinct x 31 scans) in a
    second table. The lesson is that the first fix was applied to the row it was
    found on rather than to the pattern, so the same bug shipped twice.
    """
    from .models import Edge
    store = _store(tmp_path)
    r = ReasonNode(goal='g', owner='t', status='executing')
    store.create_reason(r)
    edge = dict(from_id=r.id, to_id='sym-1', edge_type='CREATES')

    store.create_edge(Edge(**edge))
    after_first = len(store.get_edges_from(r.id, 'CREATES'))
    for _ in range(5):                      # five more Stops, same symbols
        store.create_edge(Edge(**edge))
    after_repeats = len(store.get_edges_from(r.id, 'CREATES'))

    assert after_first == 1
    assert after_repeats == 1, (
        f'{after_repeats} edges for one (from,to,type) — INSERT OR IGNORE is '
        'keying on the uuid again, so every Stop re-appends'
    )
    # A different edge type on the same pair is a DIFFERENT fact, not a duplicate.
    store.create_edge(Edge(from_id=r.id, to_id='sym-1', edge_type='MODIFIES'))
    assert len(store.get_edges_from(r.id)) == 2


def test_recording_does_not_reopen_a_fulfilled_intent_or_wipe_its_timestamp(tmp_path):
    """FOUND BY ULTRAREVIEW 2026-07-27 (bug_002).

    `update_reason_status` binds `fulfilled_at` UNCONDITIONALLY — omitting the
    kwarg writes SQL NULL. `cmd_record` called it as `(id, 'executing')`, so
    `icpg record --reason <fulfilled-id>` destroyed the fulfil timestamp AND
    silently reverted the intent to executing. A closed finding a peer verb can
    reopen without ceremony is what ADR-0016 s3 exists to prevent.

    Latent until this session: `cmd_fulfil` is the first writer of `fulfilled_at`,
    so the NULL write had always landed on an already-NULL column. Adding the close
    verb made the collision reachable.

    The auto-recorder filters to `executing` and could never hit it — only the
    manual CLI path was exposed. "Unreachable from the hook" is not "unreachable".
    """
    from . import __main__ as m
    store = _store(tmp_path)
    r = ReasonNode(goal='g', owner='t', status='executing')
    store.create_reason(r)
    m.cmd_fulfil(store, _Args(reason=r.id[:8]))

    closed = store.get_reason(r.id)
    stamp = closed.fulfilled_at
    assert closed.status == 'fulfilled' and stamp

    # Recording is BOOKKEEPING; status is JUDGEMENT (ADR-0019). Bookkeeping must
    # not mutate a judgement field — assert against the source, since a graph with
    # no changed files would pass vacuously.
    # Comments stripped first: the removal is documented IN cmd_record, so a raw
    # substring scan matches the explanation and fails on the fixed code. A guard
    # that cannot tell code from prose about the code is the `_check_`-prefix
    # mistake again, one file over.
    import inspect
    code = '\n'.join(
        line for line in inspect.getsource(m.cmd_record).splitlines()
        if not line.lstrip().startswith('#')
    )
    assert 'update_reason_status' not in code, (
        'cmd_record writes reason status again — it will NULL fulfilled_at and '
        'silently reopen a closed intent'
    )

    after = store.get_reason(r.id)
    assert after.status == 'fulfilled', 'a closed intent was reopened'
    assert after.fulfilled_at == stamp, 'the fulfil timestamp was destroyed'


def test_the_collapse_branch_keeps_the_earliest_row_per_triple(tmp_path):
    """FOUND BY REVIEW: the DELETE that collapses pre-existing duplicates never ran
    under the suite, because every test store gets the unique index on its first
    migration so `dupes` is always 0.

    That is the half that runs against REAL user graphs — the live 995->891 collapse
    was a one-shot hand run — and the half that depends on SQLite's
    bare-column-with-MIN() extension. A future edit keeping the wrong survivor, or
    deleting every row in a group, would have shipped green.
    """
    import sqlite3
    from .models import Edge

    store = _store(tmp_path)
    store.create_edge(Edge(from_id='r', to_id='s', edge_type='CREATES'))

    db = tmp_path / '.icpg' / 'reason.db'
    conn = sqlite3.connect(db)
    conn.execute('DROP INDEX idx_edges_triple')          # back to the old shape
    for i, ts in enumerate(['2026-07-03', '2026-07-01', '2026-07-02']):
        conn.execute(
            'INSERT INTO edges (id, from_id, to_id, edge_type, confidence, '
            'created_at) VALUES (?,?,?,?,?,?)',
            (f'dupe-{i}', 'r', 's', 'CREATES', 1.0, f'{ts}T00:00:00+00:00'))
    conn.commit()
    assert conn.execute('SELECT count(*) FROM edges').fetchone()[0] == 4
    conn.close()

    # A fresh store re-runs _migrate, which is where the collapse lives.
    with ICPGStore(str(tmp_path))._conn() as c:
        rows = c.execute('SELECT id, created_at FROM edges').fetchall()

    assert len(rows) == 1, f'collapse kept {len(rows)} rows, expected 1'
    assert rows[0]['created_at'].startswith('2026-07-01'), (
        f"kept {rows[0]['created_at']} — the collapse must keep the EARLIEST row, "
        'not an arbitrary one'
    )


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))


# --- _row_to_reason column guards (2026-08-10) ------------------------------------


def test_list_reasons_survives_null_and_malformed_contract_columns(tmp_path):
    """`_loads_list`'s docstring said "three call sites" while FOUR sat unguarded.

    `_row_to_reason` parsed scope/preconditions/postconditions/invariants with raw
    `json.loads`, so a NULL or malformed column raised out of `list_reasons()` — which is
    on the checkpoint path, the pre-edit hook path (stderr to /dev/null) and `icpg query`.
    That is the same silent-surface failure `_loads_list` was written for, in the reader
    next door. Verified load-bearing by re-planting the raw call: it raises TypeError.
    """
    import sqlite3

    from .models import ReasonNode
    from .store import ICPGStore

    store = ICPGStore(str(tmp_path))
    store.init_db()
    store.create_reason(ReasonNode(goal='g', owner='t', scope=['a/'],
                                   invariants=['i'], postconditions=['p']))
    with sqlite3.connect(tmp_path / '.icpg' / 'reason.db') as conn:
        conn.execute("UPDATE reasons SET postconditions=NULL, scope=NULL, "
                     "invariants='{not a list}'")

    reasons = ICPGStore(str(tmp_path)).list_reasons()
    assert len(reasons) == 1
    assert reasons[0].scope == [] and reasons[0].postconditions == []
    assert reasons[0].invariants == [], reasons[0].invariants
