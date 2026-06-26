"""Self-checks for the idempotent goal/constraint capture paths.

Run: python3 -m mnemos.test_bridge_goals  (prints 'ok' on success)

Guards the two flood-prevention invariants: re-running the iCPG bridge or the
session-goal extractor must NOT duplicate nodes, since both run every session.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace

from .store import MnemosStore


def _store() -> MnemosStore:
    tmp = tempfile.mkdtemp()
    store = MnemosStore(tmp)
    store.init_db()
    return store


def _add_turn(store, sid, idx, role, preview):
    with store._conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO claude_sessions "
            "(id, project_path, started_at, source_path, last_ingested_at) "
            "VALUES (?,?,?,?,?)",
            (sid, '/p', 't', '/p/x.jsonl', 't'),
        )
        conn.execute(
            "INSERT INTO claude_turns "
            "(session_id, idx, role, event_type, text_preview, ts) "
            "VALUES (?,?,?,?,?,?)",
            (sid, idx, role, 'message', preview, 't'),
        )


def _fake_icpg(reasons):
    return SimpleNamespace(list_reasons=lambda: reasons)


def _reason(rid, goal):
    return SimpleNamespace(
        id=rid, goal=goal, status='active', scope=['src/'],
        invariants=['x > 0'], postconditions=['returns y'],
    )


def demo() -> None:
    # --- session-goal extraction ---
    s = _store()
    _add_turn(s, 'sess1', 0, 'user', 'build the auth flow')
    _add_turn(s, 'sess1', 1, 'assistant', 'ok')
    _add_turn(s, 'tool1', 0, 'user', 'Given these git commit messages, infer')
    _add_turn(s, 'cmd1', 0, 'user', '<local-command-caveat>Caveat: ...')

    assert s.extract_session_goals() == 1, 'one real goal, tooling skipped'
    assert s.extract_session_goals() == 0, 'idempotent: no re-create'
    goals = s.get_by_type('goal')
    assert len(goals) == 1 and goals[0].content == 'build the auth flow'
    assert goals[0].task_id == 'sess1'

    # --- iCPG bridge ---
    b = _store()
    icpg = _fake_icpg([_reason('r1abcdef', 'make X safe')])
    st = b.load_from_icpg(icpg)
    assert st == {'goals_imported': 1, 'constraints_imported': 2}, st
    st2 = b.load_from_icpg(icpg)
    assert st2 == {'goals_imported': 0, 'constraints_imported': 0}, st2
    assert len(b.get_by_type('goal')) == 1
    assert len(b.get_by_type('constraint')) == 2

    # rejected reasons are skipped
    c = _store()
    rej = _reason('r2', 'dead')
    rej.status = 'abandoned'
    assert c.load_from_icpg(_fake_icpg([rej]))['goals_imported'] == 0

    print('ok')


if __name__ == '__main__':
    demo()
