"""Self-check for _correction_density low-N shrinkage in haziness.

Run from repo root: python3 -m scripts.mnemos.test_haziness

Guards finding #1's density half: one correction in a short session must not
saturate the dim, but the term must converge to the raw ratio as turns grow.
"""

from .haziness import unmeasured_reason, _correction_density, _CORRECTION_PRIOR, band


def _turn(correction: bool):
    # Minimal eligible-user-turn shape the function filters on.
    return {
        'role': 'user', 'event_type': 'user',
        'text_preview': 'x', 'tool_use_id': None,
        'correction_match': 1 if correction else 0,
    }


def _session(matches: int, eligible: int):
    return [_turn(i < matches) for i in range(eligible)]


def demo() -> None:
    K = _CORRECTION_PRIOR

    # No eligible turns → 0, no division.
    assert _correction_density([]) == 0.0

    # Low-N single match no longer spikes: raw 1/1=1.0 → 1/(1+K).
    assert _correction_density(_session(1, 1)) == 1 / (1 + K)
    assert _correction_density(_session(1, 3)) == 1 / (3 + K)

    # Shrinkage is monotone: same single match, more eligible turns → smaller
    # score is NOT what we want; more turns with no new matches should DILUTE.
    assert _correction_density(_session(1, 10)) < _correction_density(_session(1, 3))

    # Converges toward the raw ratio as N grows (half-strength at eligible==K).
    half = _correction_density(_session(K, K))   # raw 1.0, retained at K/(K+K)=0.5
    assert abs(half - 0.5) < 1e-9

    # A sustained-correction long session still reads high (not over-shrunk).
    big = _correction_density(_session(80, 100))  # raw 0.8
    assert big > 0.7

    # Bounded in [0, 1) by construction — never needs a clamp.
    assert 0.0 <= _correction_density(_session(5, 5)) < 1.0

    # Bands re-anchored 2026-07-20 (P10): distribution p50/p90/max, so the
    # label discriminates on real dogfood data instead of reading 'clear'
    # for every session ever ingested.
    assert band(0.0) == 'clear'
    assert band(0.05) == 'cloudy'
    assert band(0.11) == 'cloudy'   # the hand-labeled heavy session (0.11)
    assert band(0.12) == 'hazy'
    assert band(0.20) == 'lost'

    # ── B1: a budget-exhausted session's density is a FLOOR, not a measurement ──
    # CorrectionDetector runs on a 180s wall clock; past it every remaining turn returns
    # False, so those turns are UNMEASURED and RECORDED AS non-corrections. 13 real sessions
    # detect at 2.94% against a 17.1% baseline. This is P3's `unknown` lesson in another
    # organ: a verdict must not rest on what the instrument could not read.
    assert unmeasured_reason('budget-exhausted'), 'the defect this exists for'
    assert 'without being classified' in unmeasured_reason('budget-exhausted')
    assert unmeasured_reason('disabled-mid:consecutive-nulls')

    # Trustworthy: the classifier completed, or never ran but the REGEX covered every turn.
    # regex-only is a weaker detector over a COMPLETE pass — a recall problem (B2), not an
    # incomplete measurement. Conflating the two would mark half the corpus unusable.
    assert unmeasured_reason('ran') is None
    assert unmeasured_reason(None) is None
    assert unmeasured_reason('regex-only:ollama-down') is None, (
        'regex-only is a complete pass by a weaker detector, not an unmeasured session')

    print("ok")


if __name__ == "__main__":
    demo()
