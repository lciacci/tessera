"""Distinct goals must have visible boundaries in the checkpoint's Goal field.

2026-08-15. The field was `'; '.join(...)` under a heading reading "Goal", singular. A real
checkpoint rendered seven goals from seven different past sessions as one semicolon-joined
run-on. The boundaries were close to invisible, and combined with a mid-word truncation at
the ingest layer it produced

    ...drop POST for fulfilled intents from the checkpoin; Read the top section of...

which reads as one malformed sentence, not as two goals with the first one cut. Two
independent defects had to line up; this file covers the rendering half.

PRESENTATION ONLY. `_select_goals` still decides which goals appear and in what order —
these checks assert that it is UNCHANGED, because a rendering fix that quietly altered
selection would be reopening the payload budget adjudicated 2026-08-10.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mnemos.checkpoint import _render_goals


class _G:
    def __init__(self, content):
        self.content = content


def test_a_single_goal_gets_no_list_decoration():
    """The common downstream case. A bullet on a list of one is noise."""
    assert _render_goals([_G('ship the thing')]) == 'ship the thing'


def test_no_goals_is_unchanged():
    assert _render_goals([]) == 'No active goal'


def test_the_current_goal_still_leads_the_field():
    """Consumers and existing checks read the field as starting with the live goal —
    mnemos-pre-compact.sh and test_checkpoint_goal_cap both do. Rendering must not
    displace it behind a header."""
    out = _render_goals([_G('the live one'), _G('an older one')])
    assert out.startswith('the live one'), out


def test_a_truncated_goal_cannot_run_into_the_next_one():
    """THE REGRESSION, with the real strings. Under `'; '.join` these read as one
    sentence; on separate lines the cut is visible as a cut."""
    truncated = 'Pick up item 1: drop POST for fulfilled intents from the checkpoin'
    following = 'Read the top section of _project_specs/todos/active.md'
    out = _render_goals([_G(truncated), _G(following)])
    assert f'{truncated}; {following}' not in out
    lines = out.splitlines()
    assert any(line.strip().endswith('checkpoin') for line in lines), out
    assert any(line.strip().lstrip('- ').startswith('Read the top') for line in lines), out


def test_every_goal_survives_the_rendering():
    """Presentation must not drop content — that would be a selection change wearing a
    rendering fix, and selection is deliberately untouched here."""
    goals = [_G(f'goal-{i:03d}') for i in range(7)]
    out = _render_goals(goals)
    for g in goals:
        assert g.content in out, f'{g.content} lost'


def test_goals_are_on_separate_lines():
    goals = [_G('alpha'), _G('beta'), _G('gamma')]
    out = _render_goals(goals)
    for g in goals:
        assert any(line.strip().lstrip('- ') == g.content for line in out.splitlines()), out


def demo() -> None:
    """Run every test in this module.

    DERIVED, NOT HAND-MAINTAINED — the same runner as
    test_checkpoint_constraint_filter.demo(), for the same reason: a literal list of test
    names is a second definition of the module's contents, and the copy that drifts is
    always the one nobody runs. That file's list had silently fallen four behind before it
    was replaced (2026-08-10); these two files shipped 2026-08-15 with a fresh literal list
    each, which is the identical defect re-introduced five days later by someone who had
    read the fix. Review caught it.

    Fixture-needing tests are skipped BY NAME AND REPORTED, never silently dropped.
    """
    import inspect

    tests = [(name, fn) for name, fn in sorted(globals().items())
             if name.startswith('test_') and inspect.isfunction(fn)]
    assert tests, 'no tests discovered — the runner is broken, not the module empty'

    ran, skipped = 0, []
    for name, fn in tests:
        if inspect.signature(fn).parameters:
            skipped.append(name)
            continue
        fn()
        ran += 1

    # `ok (0 run)` is not ok — a green word over a runner that executed nothing.
    assert ran, f'demo() executed NOTHING — all {len(skipped)} tests read as fixture-needing'
    if skipped:
        print(f'ok ({ran} run; {len(skipped)} need pytest fixtures: {", ".join(skipped)})')
    else:
        print(f'ok ({ran} run)')


if __name__ == '__main__':
    demo()
