"""Self-check for the qwen correction classifier (correction_detect).

Mocks the Ollama call — no network, no model needed. Guards the recall fix:
a substantive redirect with no keyword IS caught, agreement/neutral is NOT,
and every failure mode falls open to the regex verdict (never worse than today).

Run from repo root: python3 -m scripts.mnemos.test_correction_detect
"""

from .correction_detect import CorrectionDetector, classify, regex_match


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

    # Fail-open: model down → False (regex verdict stands) AND stop trying.
    d = CorrectionDetector(generate=_gen(""), enabled=True)
    assert d.qwen_says_correction("whatever") is False
    assert d.enabled is False

    # Disabled detector never calls the model.
    calls = []
    d = CorrectionDetector(
        generate=lambda p, **kw: calls.append(1) or "yes", enabled=False)
    assert d.qwen_says_correction("x") is False
    assert calls == []


def demo() -> None:
    _regex_unchanged()
    _classify_parses_token()
    _detector_behavior()
    print("ok")


if __name__ == "__main__":
    demo()
