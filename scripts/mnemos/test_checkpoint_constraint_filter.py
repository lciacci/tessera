"""Self-checks for the checkpoint constraint filter (P3 remedy part 1, 2026-08-07).

Run: python3 -m mnemos.test_checkpoint_constraint_filter  (prints 'ok' on success)

Guards the defect measured on 2026-08-07: `file_exists("path")` invariants are bridged
from iCPG in bulk and DOMINATE the checkpoint's constraint payload — across 7 real
checkpoints they ran 53/53, 53/53, 56/56, 53/53, 61/77 and 62/80, four of them 100% — so
the constraint field was 5.3-8.7KB of a payload whose delivery channel caps at 10,000
characters. Constraints, Progress and Files were the fields that never arrived.

The subtle half is NOT the filtering, it is the ANNOUNCEMENT. A checkpoint whose
constraints silently vanished is indistinguishable from a project that has none, which is
this repo's signature failure (F-001: empty read as unused when it meant unreachable). So
the omitted COUNT is asserted here, not just the shrinkage.
"""

from __future__ import annotations

import json
import tempfile

from .checkpoint import _select_constraints, write_checkpoint
from .models import MnemoNode
from .store import MnemosStore


def _store() -> MnemosStore:
    store = MnemosStore(tempfile.mkdtemp())
    store.init_db()
    return store


def _add(store, content):
    store.create_node(MnemoNode(
        type='constraint', task_id='t', origin='session', content=content,
    ))


def test_static_predicates_are_dropped_and_real_constraints_kept():
    store = _store()
    _add(store, 'INV: file_exists("scripts/override/") [from: some intent]')
    _add(store, 'INV: file_exists("bin/tessera-watch")')
    _add(store, 'API backward compatibility must hold')

    cp = write_checkpoint(store)
    kept = [c for c in cp.active_constraints if not c.startswith('[')]
    assert kept == ['API backward compatibility must hold'], kept


def test_the_omission_is_STATED_never_silent():
    """The load-bearing assertion. A vanished constraint set must not read as 'none'."""
    store = _store()
    for i in range(53):
        _add(store, f'INV: file_exists("path/{i}")')

    cp = write_checkpoint(store)
    assert len(cp.active_constraints) == 1, cp.active_constraints
    note = cp.active_constraints[0]
    assert '53 file_exists invariant(s) omitted' in note, note
    # It must also say where they went, or the note is just a smaller silence.
    assert 'doccheck' in note and 'mnemos nodes --type constraint' in note, note


def test_no_constraints_produces_no_omission_notice():
    cp = write_checkpoint(_store())
    assert cp.active_constraints == [], cp.active_constraints


def test_nothing_dropped_means_no_notice():
    store = _store()
    _add(store, 'API backward compatibility must hold')
    cp = write_checkpoint(store)
    assert cp.active_constraints == ['API backward compatibility must hold']


def test_the_real_shape_gets_under_the_measured_ceiling():
    """Against the BROKEN state: the unfiltered payload must actually be over budget.

    Without this the filter could be a no-op on realistic input and every test above
    would still pass. 9,500 is `RESTORE_BUDGET_BYTES`; the derived ceiling is ~9,895.
    """
    store = _store()
    for i in range(61):
        _add(store, f'INV: file_exists("scripts/some/moderately/long/path/{i}.py") '
                    f'[from: Make Tessera\'s tooling (icpg, polyphony,]')
    for i in range(16):
        _add(store, f'real invariant {i}: the thing must hold')

    before = len(json.dumps([n.content for n in store.get_by_type('constraint')]))
    shown, dropped = _select_constraints(store.get_by_type('constraint'))
    after = len(json.dumps(shown))

    assert dropped == 61, dropped
    assert before > 5_000, f'premise broken — unfiltered payload only {before}b'
    assert after < 1_000, f'filter did not reclaim the payload: {after}b'


def demo() -> None:
    test_static_predicates_are_dropped_and_real_constraints_kept()
    test_the_omission_is_STATED_never_silent()
    test_no_constraints_produces_no_omission_notice()
    test_nothing_dropped_means_no_notice()
    test_the_real_shape_gets_under_the_measured_ceiling()
    print('ok')


if __name__ == '__main__':
    demo()
