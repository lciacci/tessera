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


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))
