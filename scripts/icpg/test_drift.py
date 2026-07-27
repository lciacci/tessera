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

import inspect
import re

import pytest

from icpg.coverage import untested_intents
from icpg.drift import check_symbol_drift
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


def test_emitted_dimensions_stay_inside_the_fed_three(tmp_path):
    """Observational guard — it only catches a dimension that actually FIRES.

    REFUTED AS ORIGINALLY DOCUMENTED (tessera-verify, 2026-07-27). This test used
    to claim "re-adding a dimension without a producer trips here as well as in
    doccheck". False. It trips only for an ABSENCE-shaped dimension like the old
    `test(0.30)`, which fired on every symbol. Re-adding `dependency` (scores the
    PRESENCE of never-written REQUIRES edges) left all 13 tests green, because it
    returns None on every symbol and never reaches the output at all. So this is
    kept for what it does prove, and the declared-vocabulary test below covers
    what it cannot.
    """
    store, sym, _, path = _linked_symbol(
        tmp_path=tmp_path, store=_store(tmp_path),
        invariants=['file_exists("gone.txt")'],
    )
    path.write_text('def widget_handler():\n    return 2\n')
    event = check_symbol_drift(store, sym.id)
    assert event is not None
    assert set(event.drift_dimensions) <= {'changed', 'decision'}


def test_declared_dimension_vocabulary_is_exactly_the_fed_two():
    """Reads what `check_symbol_drift` SCORES, not what it happened to emit.

    The gap this closes was found by falsifying the test above: a dimension whose
    edge type is never written returns None forever, so nothing observational can
    see it come back. `ownership` was worse still — it read edges UNTYPED, so it
    tripped neither this suite nor doccheck. Source is the only place a dead
    dimension is visible on the day it is re-added rather than never.

    THE PATTERN MUST NOT KEY ON THE SCORER'S NAME (fixed 2026-07-27, found by
    `bin/tessera-verify` the same hour this test was written). It used to require a
    `_check_` prefix — `r"\\(\\s*'(\\w+)',\\s*_check_"` — so the falsifier re-added
    `('usage', _usage_score(store, sym))` returning None and **34 tests stayed
    green**. Renaming one function walked past the only guard that can see a
    silent dimension, which is precisely the failure class this test exists for.
    doccheck's `drift-dimensions-have-producers` is no backstop: it scans EDGE
    TYPES read by `drift.py`, and `usage` never read one.

    A live re-add under any name is still caught observationally (the falsifier
    confirmed: a scorer returning 1.0 trips two other tests here). This guard is
    for the always-`None` case, which is the one nothing else can see.
    """
    # Match ANY callable in the scored tuple, not one naming convention.
    declared = set(re.findall(
        r"\(\s*'(\w+)',\s*[\w.]+\(", inspect.getsource(check_symbol_drift)
    ))
    assert declared == {'changed', 'decision'}, (
        f"scored dimensions changed: {sorted(declared)}. Adding one means adding "
        f"its producer first — see docs/observatory.md on the detector shrink."
    )
    assert 'usage' not in declared, (
        "`usage` was RETIRED by ADR-0017 on measurement, not deferred: it shelled "
        "out to `git grep` for a SUBSTRING, so it scored name commonness (`ok` "
        "matched 'hook'), and the word-boundary repair was tried and failed. "
        "Re-adding it needs a new decision that supersedes ADR-0017, not a patch."
    )


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


# The four `usage` tests that stood here were removed with the dimension
# (ADR-0017, 2026-07-27). They were good tests of a question that should not have
# been asked: they proved `git grep` was bounded to tracked files and that "could
# not measure" stayed distinct from "measured nothing" — both true, and neither
# able to see that the thing being counted was substring collisions on short
# names. Passing tests over a mis-posed predicate is the shape worth remembering.
# The None-vs-[] discipline they encoded is standing pattern #2 and outlives them.


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
