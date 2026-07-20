"""Self-check for correction_match detection in claude_log._preview.

Run from repo root: python3 -m scripts.mnemos.test_correction

Guards the finding #1 regression: a user turn that *references* the word
"Don't" as content (a CLAUDE.md section name) must NOT score as a
correction-of-Claude. Real corrections front-load the objection.
"""

from .claude_log import _emit_rows, _preview


def _match(text: str) -> int:
    # is_user=True, no redaction; we only care about the match flag.
    return _preview(text, False, is_user=True)[1]


class _FakeDetector:
    """Stands in for CorrectionDetector: never says a NEW correction (so regex
    drives match), always returns a fixed type for a known one."""

    def __init__(self, ctype):
        self.ctype = ctype

    def qwen_says_correction(self, cleaned):
        return False

    def correction_type(self, cleaned):
        return self.ctype


def _user_ev(text):
    return {'type': 'user', 'message': {'role': 'user', 'content': text}}


def _typing_wiring() -> None:
    # A regex-matched correction gets typed by the detector.
    rows = _emit_rows(_user_ev("No, undo that"), 1, 's', 't', False,
                      detector=_FakeDetector('defied'), eligible=True)
    row = rows[0]
    assert row['correction_match'] == 1
    assert row['correction_type'] == 'defied'

    # A non-correction turn is neither matched nor typed.
    rows = _emit_rows(_user_ev("Please add a timeout option"), 1, 's', 't',
                      False, detector=_FakeDetector('wrong'), eligible=True)
    assert rows[0]['correction_match'] == 0
    assert rows[0]['correction_type'] is None

    # Null type (Ollama down) never drops the correction.
    rows = _emit_rows(_user_ev("No, undo that"), 1, 's', 't', False,
                      detector=_FakeDetector(None), eligible=True)
    assert rows[0]['correction_match'] == 1
    assert rows[0]['correction_type'] is None


def _carrier_rows_excluded() -> None:
    # `!`-command output, slash-command wrappers, and interrupt markers ride
    # user role with no isMeta/promptSource flag. They emit as 'user-meta' so
    # the density denominator drops them (silver-label pass: ~11% dilution).
    for text in ('<bash-stdout>total 42</bash-stdout>',
                 '<local-command-stdout>Set model</local-command-stdout>',
                 '<command-name>/compact</command-name>',
                 '[Request interrupted by user for tool use]'):
        rows = _emit_rows(_user_ev(text), 1, 's', 't', False, eligible=True)
        assert rows[0]['event_type'] == 'user-meta', text
        assert rows[0]['correction_match'] == 0

    # A human turn that merely QUOTES output mid-text stays human.
    rows = _emit_rows(_user_ev("the run printed <bash-stdout> markers, why?"),
                      1, 's', 't', False, eligible=True)
    assert rows[0]['event_type'] == 'user'


def demo() -> None:
    # --- must NOT match (false positives the fix kills) ---
    assert _match("Change in the Don't Hardcode instructions") == 0, "finding #1 regression"
    assert _match("the Don't Hardcode section needs an update") == 0
    # 'instead' past the front window = fresh instruction, not a correction:
    assert _match(
        "Please add a config option for the timeout value here and wire it "
        "through the loader instead of hardcoding it"
    ) == 0

    # --- must match (real corrections preserved) ---
    assert _match("No, don't do that") == 1           # lead: no
    assert _match("Don't push that") == 1             # lead: don't
    assert _match("don't, revert it") == 1            # lead: don't
    assert _match("wait, that's wrong") == 1          # lead: wait
    assert _match("use the helper instead") == 1      # phrase early: instead
    assert _match("not that one, the other") == 1     # phrase early: not that

    # --- non-user turns never match ---
    assert _preview("No, don't do that", False, is_user=False)[1] == 0

    _typing_wiring()
    _carrier_rows_excluded()

    print("ok")


if __name__ == "__main__":
    demo()
