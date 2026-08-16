"""A truncated preview must not read as complete text.

2026-08-15. `_preview` cut turn text with a bare `cleaned[:200]`. The cut landed wherever
200 characters happened to fall, so a shortened preview was indistinguishable from a whole
one. The live instance: a session checkpoint carried the goal

    ...Pick up item 1: drop POST for fulfilled intents from the checkpoin

which does not look truncated — it looks like a typo — and reached the model that way,
because MnemosStore turns each session's first prompt into a GoalNode from this preview.

The 200-char cap itself is a storage/privacy decision and is NOT changed here; full turn
content is still never persisted. Only the shape of the cut changed.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mnemos.claude_log import PREVIEW_CHARS, _truncate_preview


def test_the_live_regression_no_longer_ends_mid_word():
    """The exact string from the checkpoint that motivated this."""
    goal = ("Read the top section of _project_specs/todos/active.md — ignore the Mnemos "
            "resume block, it's truncated — then run bin/tessera-watch. Pick up item 1: "
            "drop POST for fulfilled intents from the checkpoint payload")
    assert len(goal) > PREVIEW_CHARS
    out = _truncate_preview(goal)
    assert not out.endswith("checkpoin")
    assert out.endswith("…")
    assert " ".join(out[:-1].split()) in " ".join(goal.split())


def test_short_text_is_returned_untouched_and_unmarked():
    """An unmarked preview must mean 'this is the whole turn'. That is the entire signal."""
    for text in ("hi", "a" * (PREVIEW_CHARS - 1), "a" * PREVIEW_CHARS):
        assert _truncate_preview(text) == text
        assert not _truncate_preview(text).endswith("…")


def test_never_exceeds_the_storage_cap_including_the_ellipsis():
    """MnemosStore slices to 200 AGAIN downstream and would eat an overhanging marker."""
    for n in range(PREVIEW_CHARS - 5, PREVIEW_CHARS + 60):
        assert len(_truncate_preview("word " * n)) <= PREVIEW_CHARS


def test_a_long_unbroken_token_keeps_the_hard_cut():
    """No space to back off to — a URL or base64 blob. Backing off would destroy the
    preview to tidy it, so the ragged edge is the better trade and the cut is still
    marked."""
    blob = "https://example.com/" + "x" * 400
    out = _truncate_preview(blob)
    assert len(out) <= PREVIEW_CHARS
    assert out.endswith("…")
    assert out.startswith("https://example.com/xxx")


def test_the_cut_lands_on_whitespace_not_inside_a_word():
    text = " ".join(f"word{i:03d}" for i in range(200))
    out = _truncate_preview(text)
    assert out.endswith("…")
    assert text.startswith(out[:-1])
    # the character right after the kept text is a space -> nothing was sliced mid-word
    assert text[len(out) - 1] == " "


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
