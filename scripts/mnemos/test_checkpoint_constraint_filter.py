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
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from .checkpoint import _fulfilled_post_contents, _select_constraints, write_checkpoint
from .models import MnemoNode
from .store import MnemosStore, post_constraint_content


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
    assert '53 file_exists constraint(s) omitted' in note, note
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
    shown, dropped, _ = _select_constraints(store.get_by_type('constraint'))
    after = len(json.dumps(shown))

    assert dropped == 61, dropped
    assert before > 5_000, f'premise broken — unfiltered payload only {before}b'
    assert after < 1_000, f'filter did not reclaim the payload: {after}b'


# --- Fulfilled-intent postconditions (P3 part 3, 2026-08-10) -----------------------


class _Reason:
    def __init__(self, goal, status, postconditions=(), invariants=()):
        self.goal = goal
        self.status = status
        self.postconditions = list(postconditions)
        self.invariants = list(invariants)


class _FakeICPG:
    """Minimal stand-in: `exists()` + `list_reasons()` is all the filter touches."""

    def __init__(self, reasons):
        self._reasons = reasons

    def exists(self):
        return True

    def list_reasons(self):
        return self._reasons


def test_fulfilled_postconditions_are_dropped_and_invariants_survive():
    """The semantic split: POST is 'true when fulfilled', INV is 'true after'."""
    store = _store()
    _add(store, 'POST: the receipt is written [from: Ship the T2 instrument]')
    _add(store, 'INV: the offer/receipt split holds [from: Ship the T2 instrument]')

    icpg = _FakeICPG([_Reason(
        'Ship the T2 instrument', 'fulfilled',
        postconditions=['the receipt is written'],
        invariants=['the offer/receipt split holds'])])

    cp = write_checkpoint(store, icpg_store=icpg)
    kept = [c for c in cp.active_constraints if not c.startswith('[')]
    assert kept == ['INV: the offer/receipt split holds [from: Ship the T2 instrument]'], kept


def test_an_open_intents_postcondition_is_NEVER_dropped():
    """Against the broken state: filtering on 'is a POST' rather than 'is fulfilled'
    would pass every other test here. Each of these three statuses must survive, and
    `drifted` most of all — it means the predicate is FAILING."""
    store = _store()
    for status in ('executing', 'proposed', 'drifted'):
        _add(store, post_constraint_content(f'Intent {status}', 'the thing holds'))

    icpg = _FakeICPG([
        _Reason(f'Intent {s}', s, postconditions=['the thing holds'])
        for s in ('executing', 'proposed', 'drifted')
    ])

    cp = write_checkpoint(store, icpg_store=icpg)
    kept = [c for c in cp.active_constraints if not c.startswith('[')]
    assert len(kept) == 3, kept
    assert not any('omitted' in c for c in cp.active_constraints), cp.active_constraints


def test_a_shared_postcondition_with_one_open_owner_survives():
    """The bridge dedups to ONE node, so a fulfilled owner must not drop a live one's.

    Both reasons share a goal PREFIX (the key truncates at 40 chars) and the same
    postcondition text, so they mint one identical content string.
    """
    prefix = 'Harden the checkpoint delivery channel so it'
    fulfilled = _Reason(prefix + ' fits', 'fulfilled', postconditions=['the payload fits'])
    live = _Reason(prefix + ' never spills', 'executing',
                   postconditions=['the payload fits'])
    assert (post_constraint_content(fulfilled.goal, 'the payload fits')
            == post_constraint_content(live.goal, 'the payload fits')), 'premise broken'

    assert _fulfilled_post_contents(_FakeICPG([fulfilled, live])) == set()
    assert _fulfilled_post_contents(_FakeICPG([fulfilled])) != set()


def test_no_icpg_store_drops_nothing():
    """Fail-safe: unable to determine status means keep, not guess."""
    store = _store()
    _add(store, 'POST: the receipt is written [from: Ship the T2 instrument]')
    cp = write_checkpoint(store)
    assert cp.active_constraints == [
        'POST: the receipt is written [from: Ship the T2 instrument]']


def test_an_orphaned_postcondition_is_kept():
    """A constraint whose intent was deleted from iCPG matches nothing — keep it."""
    store = _store()
    _add(store, 'POST: something from a deleted intent [from: Gone]')
    cp = write_checkpoint(store, icpg_store=_FakeICPG([]))
    assert cp.active_constraints == ['POST: something from a deleted intent [from: Gone]']


def test_the_POST_omission_is_STATED_never_silent():
    """Same load-bearing rule as the file_exists half, and for the same reason."""
    store = _store()
    posts = [f'postcondition number {i} holds' for i in range(39)]
    for p in posts:
        _add(store, post_constraint_content('Some fulfilled intent', p))

    icpg = _FakeICPG([_Reason('Some fulfilled intent', 'fulfilled', postconditions=posts)])
    cp = write_checkpoint(store, icpg_store=icpg)

    assert len(cp.active_constraints) == 1, cp.active_constraints
    note = cp.active_constraints[0]
    assert '39 postcondition(s) omitted' in note, note
    # It must say WHY they went and WHERE they still are, or it is a smaller silence.
    assert 'FULFILLED' in note and 'Still stored' in note, note
    assert 'mnemos nodes --type constraint' in note, note


def test_the_two_omission_notices_are_distinguishable():
    """Two different exclusions with two different justifications must not merge into
    one count — a reader cannot re-derive which class went missing from a total."""
    store = _store()
    _add(store, 'INV: file_exists("scripts/mnemos/checkpoint.py")')
    _add(store, post_constraint_content('A fulfilled intent', 'the thing shipped'))

    icpg = _FakeICPG([_Reason('A fulfilled intent', 'fulfilled',
                              postconditions=['the thing shipped'])])
    cp = write_checkpoint(store, icpg_store=icpg)

    notes = [c for c in cp.active_constraints if c.startswith('[')]
    assert len(notes) == 2, notes
    assert any('1 file_exists constraint(s) omitted' in n for n in notes), notes
    assert any('1 postcondition(s) omitted' in n for n in notes), notes


def test_every_command_the_notices_cite_actually_EXISTS():
    """The notice tells the agent where the dropped constraints went. If the command it
    names is not real, the note is worse than a silent drop — it is a silence with
    directions. Caught for real on 2026-08-10: the first draft cited `icpg show <id>`,
    which has never existed (the subcommands are init/create/record/fulfil/query/drift/
    bootstrap/status). Parsed out of the rendered note rather than hardcoded, so the
    check tracks whatever the note says instead of becoming a second copy of it.
    """
    store = _store()
    _add(store, 'INV: file_exists("scripts/mnemos/checkpoint.py")')
    _add(store, post_constraint_content('A fulfilled intent', 'the thing shipped'))
    icpg = _FakeICPG([_Reason('A fulfilled intent', 'fulfilled',
                              postconditions=['the thing shipped'])])
    cp = write_checkpoint(store, icpg_store=icpg)

    cited = set()
    for note in (c for c in cp.active_constraints if c.startswith('[')):
        for span in re.findall(r'`([^`]+)`', note):
            if span.split()[0] in ('icpg', 'mnemos'):
                cited.add(span)
    assert len(cited) >= 2, f'premise broken — no commands parsed out: {cited}'

    for command in sorted(cited):
        argv = [t for t in command.split() if not t.startswith('<')] + ['--help']
        proc = subprocess.run(
            [sys.executable, '-m', argv[0], *argv[1:]],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True, text=True)
        assert proc.returncode == 0, (
            f'checkpoint notice cites `{command}`, which the CLI rejects '
            f'(exit {proc.returncode}): {proc.stderr.strip()[-200:]}')


def test_a_fulfilled_POST_is_attributed_to_the_POSTCONDITION_notice():
    """Refuted by bin/tessera-verify 2026-08-10, and it survived the first test pass.

    A postcondition whose predicate text contains `file_exists(` was counted under the
    OTHER notice and announced as an *invariant*. The total omitted count was correct, so
    every count-based assertion passed — the ATTRIBUTION was wrong, in the one sentence
    whose job is telling the reader what went missing (#12: a report can be true and
    still mislead). The ordering question was noticed while writing and waved through as
    'preserves existing behaviour'.
    """
    store = _store()
    _add(store, post_constraint_content('A fulfilled intent', 'file_exists("z")'))
    icpg = _FakeICPG([_Reason('A fulfilled intent', 'fulfilled',
                              postconditions=['file_exists("z")'])])

    cp = write_checkpoint(store, icpg_store=icpg)
    notes = [c for c in cp.active_constraints if c.startswith('[')]
    assert len(notes) == 1, notes
    assert 'postcondition(s) omitted' in notes[0], notes[0]
    assert 'FULFILLED' in notes[0], notes[0]


def test_the_static_notice_never_calls_a_postcondition_an_invariant():
    """A POST from a STILL-OPEN intent can carry file_exists too — it belongs in the
    static notice (its intent is not fulfilled), but must not be labelled an invariant."""
    store = _store()
    _add(store, post_constraint_content('An open intent', 'file_exists("z")'))
    icpg = _FakeICPG([_Reason('An open intent', 'executing',
                              postconditions=['file_exists("z")'])])

    cp = write_checkpoint(store, icpg_store=icpg)
    notes = [c for c in cp.active_constraints if c.startswith('[')]
    assert len(notes) == 1, notes
    assert 'invariant' not in notes[0], notes[0]
    assert '1 file_exists constraint(s) omitted' in notes[0], notes[0]


def test_the_two_filters_interact_where_a_shared_POST_is_also_a_static_predicate():
    """Surfaced by bin/tessera-verify 2026-08-10 as a refuting case; kept as INTENDED.

    A POST shared by a fulfilled AND an executing intent survives
    `fulfilled - live` — but if its predicate text is `file_exists(...)` it then falls
    through to the static filter and is dropped anyway, so the shared-owner protection
    looks defeated. It is not a defect: the static policy has ALWAYS applied to open
    intents' constraints, and a `file_exists` predicate is asserted by doccheck
    `referenced-paths-exist` + pre-commit whoever owns it — strictly stronger than a
    line in this payload.

    The real finding was that the interaction of the two filters was never exercised:
    `test_a_shared_postcondition_with_one_open_owner_survives` uses 'the payload fits',
    so it could never reach the static branch. Pinned here so the behaviour is a
    decision rather than an accident, and so a future change to either filter has to
    confront it.
    """
    prefix = 'Harden the checkpoint delivery channel so it'
    store = _store()
    _add(store, post_constraint_content(prefix + ' fits', 'file_exists("b.py")'))

    icpg = _FakeICPG([
        _Reason(prefix + ' fits', 'fulfilled', postconditions=['file_exists("b.py")']),
        _Reason(prefix + ' never spills', 'executing',
                postconditions=['file_exists("b.py")']),
    ])
    cp = write_checkpoint(store, icpg_store=icpg)

    notes = [c for c in cp.active_constraints if c.startswith('[')]
    assert [c for c in cp.active_constraints if not c.startswith('[')] == []
    assert len(notes) == 1, notes
    # Static notice, NOT the postcondition notice — its intent is not fulfilled-only.
    assert '1 file_exists constraint(s) omitted' in notes[0], notes[0]
    # And the omission is still STATED, which is the property that must never lapse.
    assert 'mnemos nodes --type constraint' in notes[0], notes[0]


# --- Write-time budget warning (P3 part 3, 2026-08-10) ----------------------------


def test_an_over_budget_payload_says_so_AT_WRITE_TIME(capsys):
    """P3 reports a spill that already happened; this reports one as it is created.

    The checkpoint is rewritten mid-session, and `tessera-watch` runs at SessionStart
    only — so a payload that goes over at 13:15 is evaluated by nothing until the next
    session, where the warning arrives in the same breath as the truncated block it
    describes.
    """
    store = _store()
    for i in range(90):
        _add(store, f'INV: standing property {i} — ' + 'x' * 120)

    write_checkpoint(store)
    err = capsys.readouterr().err
    assert 'over the 8,000b delivery budget' in err, err
    assert 'Written anyway' in err, err


def test_an_under_budget_payload_is_SILENT():
    """A warner that always warns is a warner nobody reads."""
    store = _store()
    _add(store, 'INV: one small standing property')
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        write_checkpoint(store)
    assert buf.getvalue() == '', buf.getvalue()


def test_the_over_budget_checkpoint_is_STILL_WRITTEN():
    """A size guard that can refuse to save state is worse than the spill it guards."""
    store = _store()
    for i in range(90):
        _add(store, f'INV: standing property {i} — ' + 'x' * 120)

    cp = write_checkpoint(store)
    latest = store.mnemos_dir / 'checkpoint-latest.json'
    assert latest.exists(), 'checkpoint was not written'
    assert json.loads(latest.read_text())['id'] == cp.id


def demo() -> None:
    test_static_predicates_are_dropped_and_real_constraints_kept()
    test_the_omission_is_STATED_never_silent()
    test_no_constraints_produces_no_omission_notice()
    test_nothing_dropped_means_no_notice()
    test_the_real_shape_gets_under_the_measured_ceiling()
    test_fulfilled_postconditions_are_dropped_and_invariants_survive()
    test_an_open_intents_postcondition_is_NEVER_dropped()
    test_a_shared_postcondition_with_one_open_owner_survives()
    test_no_icpg_store_drops_nothing()
    test_an_orphaned_postcondition_is_kept()
    test_the_POST_omission_is_STATED_never_silent()
    test_the_two_omission_notices_are_distinguishable()
    test_every_command_the_notices_cite_actually_EXISTS()
    test_an_under_budget_payload_is_SILENT()
    test_the_over_budget_checkpoint_is_STILL_WRITTEN()
    print('ok')


if __name__ == '__main__':
    demo()
