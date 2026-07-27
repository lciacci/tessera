"""Tests for the shrunk drift detector — `scripts/icpg/`'s first tests, ever.

The module shipped with zero tests and stayed that way while its detector scored
five dimensions that could not fire. These guard the shrink itself, not just the
arithmetic: the first two would have gone red on the pre-2026-07-27 code, which is
the only thing that makes them evidence rather than decoration.

Runs in its OWN pytest process (`scripts/run-tests.sh`) — `scripts/icpg/` and
`scripts/polyphony/` both carry a `store.py` and a `models.py`, so joining the
top-level pool is a collection collision waiting for polyphony's first test.
Paired with doccheck's `ignored-test-suites-are-run`, which fails if the --ignore
is ever added without the matching run line.
"""

from __future__ import annotations

import subprocess

import pytest

from icpg.coverage import untested_intents
from icpg.drift import (
    _in_scope,
    _tracked_files_mentioning,
    check_symbol_drift,
)
from icpg.models import Edge, ReasonNode, Symbol
from icpg.store import ICPGStore
from icpg.symbols import extract_symbols

SOURCE = 'def widget_handler():\n    return 1\n'


def _store(tmp_path) -> ICPGStore:
    store = ICPGStore(str(tmp_path))
    store.init_db()
    return store


def _linked_symbol(store, tmp_path, *, invariants=None, postconditions=None,
                   scope=None, source=SOURCE):
    """A reason CREATES-linked to a real on-disk symbol, checksums matching."""
    path = tmp_path / 'widget.py'
    path.write_text(source)
    sym = next(s for s in extract_symbols(str(path)))
    store.upsert_symbol(sym)
    reason = ReasonNode(
        goal='ship the widget', owner='test',
        scope=scope if scope is not None else ['widget.py'],
        invariants=invariants or [], postconditions=postconditions or [],
    )
    store.create_reason(reason)
    store.create_edge(Edge(from_id=reason.id, to_id=sym.id, edge_type='CREATES'))
    return store, sym, reason, path


# --- the constant that was 712 of 712 events -----------------------------------


def test_no_test_dimension_is_ever_emitted(tmp_path):
    """`test(0.30)` was on 100% of stored events because nothing writes
    VALIDATED_BY. A dimension with one possible value is not a measurement."""
    store, sym, _, _ = _linked_symbol(tmp_path=tmp_path, store=_store(tmp_path))
    event = check_symbol_drift(store, sym.id)
    assert event is None or 'test' not in event.drift_dimensions


def test_a_clean_symbol_produces_no_event_at_all(tmp_path):
    """Pre-shrink this was impossible: every symbol scored at least test(0.30),
    so 'no drift' could not be expressed. Silence has to be reachable."""
    store, sym, _, _ = _linked_symbol(tmp_path=tmp_path, store=_store(tmp_path))
    assert check_symbol_drift(store, sym.id) is None


def test_dimension_vocabulary_is_exactly_the_fed_three(tmp_path):
    """Structural guard: re-adding a dimension without a producer trips here as
    well as in doccheck. Both, because doccheck reads source and this runs it."""
    store, sym, _, path = _linked_symbol(
        tmp_path=tmp_path, store=_store(tmp_path),
        invariants=['file_exists("gone.txt")'],
    )
    path.write_text('def widget_handler():\n    return 2\n')
    event = check_symbol_drift(store, sym.id)
    assert event is not None
    assert set(event.drift_dimensions) <= {'changed', 'decision', 'usage'}


# --- the producer/reader mismatch that made decision drift dead ----------------


def test_decision_drift_reads_invariants_not_only_postconditions(tmp_path):
    """THE BUG: `contracts.py` writes invariants (10/10 reasons here), the
    detector read postconditions (0/10). Both live, never connected."""
    store, sym, _, _ = _linked_symbol(
        tmp_path=tmp_path, store=_store(tmp_path),
        invariants=['file_exists("absent.txt")'], postconditions=[],
    )
    event = check_symbol_drift(store, sym.id)
    assert event is not None
    assert 'decision' in event.drift_dimensions


def test_decision_drift_is_silent_when_the_invariant_holds(tmp_path):
    """The other direction — otherwise the fix is just a new constant."""
    store = _store(tmp_path)
    (tmp_path / 'present.txt').write_text('here')
    store, sym, _, _ = _linked_symbol(
        tmp_path=tmp_path, store=store,
        invariants=['file_exists("present.txt")'],
    )
    event = check_symbol_drift(store, sym.id)
    assert event is None or 'decision' not in event.drift_dimensions


def test_decision_drift_still_reads_postconditions(tmp_path):
    """Widened, not swapped. A postcondition writer landing later must work."""
    store, sym, _, _ = _linked_symbol(
        tmp_path=tmp_path, store=_store(tmp_path),
        postconditions=['test_exists("tests/absent.py")'],
    )
    event = check_symbol_drift(store, sym.id)
    assert event is not None
    assert 'decision' in event.drift_dimensions


# --- usage drift, bounded to tracked files -------------------------------------


def _git_repo(tmp_path, tracked: dict[str, str]):
    subprocess.run(['git', 'init', '-q'], cwd=tmp_path, check=True)
    for name, body in tracked.items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body)
        subprocess.run(['git', 'add', name], cwd=tmp_path, check=True)


def test_usage_ignores_untracked_files(tmp_path):
    """`grep -rl <name> .` counted `.venv/`, `build/`, `__pycache__`. Any common
    name saturated the 0..1 score inside vendored code alone."""
    _git_repo(tmp_path, {'widget.py': SOURCE})
    vendored = tmp_path / '.venv' / 'lib'
    vendored.mkdir(parents=True)
    for i in range(20):
        (vendored / f'mod{i}.py').write_text('widget_handler\n')
    assert _tracked_files_mentioning('widget_handler', tmp_path) == ['widget.py']


def test_usage_counts_tracked_files_out_of_scope(tmp_path):
    _git_repo(tmp_path, {
        'widget.py': SOURCE,
        'a.py': 'widget_handler\n',
        'b.py': 'widget_handler\n',
        'c.py': 'widget_handler\n',
    })
    found = _tracked_files_mentioning('widget_handler', tmp_path)
    assert set(found) == {'widget.py', 'a.py', 'b.py', 'c.py'}
    out = [f for f in found if not _in_scope(f, ['widget.py'])]
    assert len(out) == 3


def test_no_answer_from_git_is_not_a_clean_scope(tmp_path):
    """None means 'could not measure'; [] means 'measured, nothing'. Collapsing
    them is the fail-open shape this repo keeps paying for."""
    assert _tracked_files_mentioning('widget_handler', tmp_path) is None


def test_no_matches_is_an_answer(tmp_path):
    """git grep exits 1 for 'no matches' — an answer, not a failure."""
    _git_repo(tmp_path, {'widget.py': SOURCE})
    assert _tracked_files_mentioning('nothing_matches_this', tmp_path) == []


# --- coverage, reported but never scored ---------------------------------------


def test_untested_intents_counts_intents_without_linked_tests(tmp_path):
    store, _, _, _ = _linked_symbol(tmp_path=tmp_path, store=_store(tmp_path))
    assert untested_intents(store) == (1, 1)


def test_untested_intents_excludes_abandoned_intents(tmp_path):
    store = _store(tmp_path)
    store.create_reason(
        ReasonNode(goal='dropped', owner='test', status='abandoned')
    )
    assert untested_intents(store) == (0, 0)


def test_untested_intents_clears_when_a_validated_by_edge_exists(tmp_path):
    """It cannot move today — nothing writes VALIDATED_BY — but it must be able
    to. A counter that can only report one value is what we just removed."""
    store, sym, reason, _ = _linked_symbol(
        tmp_path=tmp_path, store=_store(tmp_path)
    )
    test_sym = Symbol(
        name='test_widget', file_path='test_widget.py',
        symbol_type='function', language='python',
    )
    store.upsert_symbol(test_sym)
    store.create_edge(
        Edge(from_id=reason.id, to_id=test_sym.id, edge_type='VALIDATED_BY')
    )
    assert untested_intents(store) == (0, 1)


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))
