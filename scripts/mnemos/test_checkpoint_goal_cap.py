"""Self-checks for the checkpoint goal-render cap.

Run: python3 -m mnemos.test_checkpoint_goal_cap  (prints 'ok' on success)

Guards the defect found 2026-07-26: goals are never-evict AND one is auto-minted
per ingested session, so `'; '.join(all goals)` grew to 10.9KB — 60% of the
checkpoint — and truncated the Layer-2 SessionStart delivery. The restore blob
outgrew its own delivery channel.

The subtle half is the ORDERING. Every goal in a real graph carries
activation_weight 1.0, so the store's `ORDER BY activation_weight DESC` is a
no-op and a naive head-slice keeps arbitrary rows. A cap that drops the live
goal to keep 'what is sqlfluffy' is worse than no cap, so recency is asserted
here, not just length.
"""

from __future__ import annotations

import tempfile

from .checkpoint import MAX_CHECKPOINT_GOALS, write_checkpoint
from .models import MnemoNode
from .store import MnemosStore


def _store() -> MnemosStore:
    store = MnemosStore(tempfile.mkdtemp())
    store.init_db()
    return store


def _add_goal(store, content, created_at):
    store.create_node(MnemoNode(
        type='goal', task_id=f'task-{content}', origin='session-goal',
        content=content, created_at=created_at,
    ))


def test_cap_limits_and_states_the_omission():
    store = _store()
    for i in range(MAX_CHECKPOINT_GOALS + 12):
        _add_goal(store, f'goal-{i:03d}', f'2026-07-{i + 1:02d}T00:00:00+00:00')

    cp = write_checkpoint(store)
    shown = [p for p in cp.goal.split('; ') if p.startswith('goal-')]

    assert len(shown) == MAX_CHECKPOINT_GOALS, f'kept {len(shown)}'
    # Silent truncation would read as a complete goal list. It must say so.
    assert '+12 older goal(s) omitted' in cp.goal, cp.goal


def test_cap_keeps_the_NEWEST_goals_not_arbitrary_rows():
    """The one that matters: equal activation_weight must not decide the cut."""
    store = _store()
    for i in range(MAX_CHECKPOINT_GOALS + 5):
        _add_goal(store, f'goal-{i:03d}', f'2026-07-{i + 1:02d}T00:00:00+00:00')

    weights = {n.activation_weight for n in store.get_by_type('goal')}
    assert weights == {1.0}, f'premise broken, weights vary: {weights}'

    cp = write_checkpoint(store)
    newest = f'goal-{MAX_CHECKPOINT_GOALS + 4:03d}'
    assert newest in cp.goal, f'dropped the newest goal: {cp.goal}'
    assert 'goal-000' not in cp.goal, f'kept the oldest goal: {cp.goal}'
    # task_id must follow the same recency rule, not an arbitrary row.
    assert cp.task_id == f'task-{newest}', cp.task_id


def test_no_goals_is_not_an_omission_notice():
    cp = write_checkpoint(_store())
    assert cp.goal == 'No active goal', cp.goal
    assert 'omitted' not in cp.goal


if __name__ == '__main__':
    test_cap_limits_and_states_the_omission()
    test_cap_keeps_the_NEWEST_goals_not_arbitrary_rows()
    test_no_goals_is_not_an_omission_notice()
    print('ok')
