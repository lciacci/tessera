"""Self-check for the qwen correction classifier (correction_detect).

Mocks the Ollama call — no network, no model needed. Guards the recall fix:
a substantive redirect with no keyword IS caught, agreement/neutral is NOT,
and every failure mode falls open to the regex verdict (never worse than today).

Run from repo root: python3 -m scripts.mnemos.test_correction_detect
"""

from .correction_detect import (
    TYPES,
    CorrectionDetector,
    classify,
    classify_type,
    regex_match,
)


def _gen(reply):
    """A fake Ollama that always returns `reply`."""
    return lambda prompt, **kw: reply


def _regex_unchanged() -> None:
    # Single home for the old heuristic; behavior identical to pre-refactor.
    assert regex_match("No, don't do that") == 1
    assert regex_match("not that one, the other") == 1
    assert regex_match("the Don't Hardcode section needs an update") == 0
    # The recall gap the classifier exists to close — regex misses this:
    assert regex_match("but that would require rewriting the whole loader") == 0


def _classify_parses_token() -> None:
    assert classify("x", generate=_gen("yes")) is True
    assert classify("x", generate=_gen("No.")) is False
    assert classify("x", generate=_gen("Yes, it does.")) is True
    assert classify("x", generate=_gen("")) is None        # unreachable
    assert classify("x", generate=_gen("maybe?")) is None  # junk → no signal


def _detector_behavior() -> None:
    # The redirect regex missed, now caught.
    d = CorrectionDetector(generate=_gen("yes"), enabled=True)
    assert d.qwen_says_correction("but that would require rewriting the loader")

    # Agreement stays negative.
    d = CorrectionDetector(generate=_gen("no"), enabled=True)
    assert d.qwen_says_correction("ok, go ahead") is False

    # Fail-open: model down → False (regex verdict stands). One blip is
    # tolerated; only sustained failure disables (protects --reclassify --all).
    d = CorrectionDetector(generate=_gen(""), enabled=True)
    assert d.qwen_says_correction("whatever") is False
    assert d.enabled is True                       # one failure tolerated
    for _ in range(CorrectionDetector._MAX_CONSECUTIVE_FAILS):
        d.qwen_says_correction("whatever")
    assert d.enabled is False                      # sustained failure disables

    # A success between failures resets the counter.
    d = CorrectionDetector(generate=lambda p, **kw: "" , enabled=True)
    d.qwen_says_correction("x"); d.qwen_says_correction("x")
    d.generate = lambda p, **kw: "yes"
    assert d.qwen_says_correction("x") is True and d.enabled is True

    # Disabled detector never calls the model.
    calls = []
    d = CorrectionDetector(
        generate=lambda p, **kw: calls.append(1) or "yes", enabled=False)
    assert d.qwen_says_correction("x") is False
    assert calls == []


def _classify_type_parses() -> None:
    for t in TYPES:
        assert classify_type("x", generate=_gen(t)) == t
    # Word embedded in a sentence still parses.
    assert classify_type("x", generate=_gen("This was overreached.")) == "overreached"
    # None on unreachable or a word not in TYPES.
    assert classify_type("x", generate=_gen("")) is None
    assert classify_type("x", generate=_gen("dunno")) is None


def _detector_type_behavior() -> None:
    # Types within budget.
    d = CorrectionDetector(generate=_gen("defied"), enabled=True)
    assert d.correction_type("you ignored the instruction") == "defied"

    # Null type never crashes; shares budget → disabled/over-budget yields None.
    d = CorrectionDetector(generate=_gen("wrong"), enabled=False)
    assert d.correction_type("x") is None

    d = CorrectionDetector(generate=_gen("wrong"), enabled=True, budget_s=0.0)
    assert d.correction_type("x") is None       # budget already spent


def demo() -> None:
    _regex_unchanged()
    _classify_parses_token()
    _detector_behavior()
    _classify_type_parses()
    _detector_type_behavior()
    print("ok")


if __name__ == "__main__":
    demo()
