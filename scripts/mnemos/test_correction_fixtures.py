"""ADR-0020's fixture matrix — deterministic half.

Runs against `regex_match` only: no Ollama, so it belongs in `tessera-test` and stays
green on a clean clone. The live-classifier half is
`eval_correction.py --fixtures`, which cannot be a CI gate because its judge is a model.

**What this file deliberately does NOT assert: that `regex_match` gets the positives
right.** It does not, by design — it is the high-precision/low-recall half of a two-
detector pipe. Asserting otherwise would mean editing fixtures until the weaker judge
passes, which is the eval-shaped form of standing pattern #1 and the exact failure
ADR-0020 adopted the five-layer diagnosis to prevent. Ground truth is authored from the
rubric; a detector scoring badly against it is a finding ABOUT THE DETECTOR.
"""
from __future__ import annotations

import pytest

from scripts.mnemos.calibration import LAYERS, SCORED, SHAPES, UNSCORED, load_cases, score
from scripts.mnemos.correction_detect import regex_match


@pytest.fixture(scope="module")
def cases():
    return load_cases()


def _regex(text: str) -> bool:
    return bool(regex_match(text))


def test_every_case_type_is_represented(cases):
    """A matrix missing a case type is not a matrix. Guards silent fixture deletion."""
    present = {c["case"] for c in cases}
    assert present == set(SCORED) | set(UNSCORED), present


def _pairs(cases) -> dict[str, list]:
    out: dict[str, list] = {}
    for c in cases:
        if c["case"] == "lucky_correct_negative":
            out.setdefault(c["pair"], []).append(c)
    return out


def test_lucky_pairs_are_well_formed(cases):
    """Each lucky-correct case is a PAIR sharing one cue: exactly one lucky, one foil."""
    pairs = _pairs(cases)
    assert pairs, "no lucky_correct_negative pairs — the load-bearing case type"
    for name, members in pairs.items():
        roles = sorted(m["role"] for m in members)
        assert roles == ["foil", "lucky"], f"{name}: {roles}"
        assert len({m["cue"] for m in members}) == 1, f"{name}: cue differs across pair"


def test_each_pair_declares_a_shape_that_matches_its_truths(cases):
    """The invariant that makes a pair a pair, which role+cue alone do NOT encode.

    Two shapes are legitimate — `opposite-truth` (the cue fires on a non-correction) and
    `same-truth` (the cue is absent from an equivalent turn). Without a declaration, a
    foil that accidentally stopped being a foil — both members true — reads as a valid
    opposite-truth pair and the matrix quietly loses a case. Found by arbiter 2026-08-10,
    whose premise (that every foil must be truth=false) was wrong and whose conclusion
    (that nothing asserts the property) was right."""
    for name, members in _pairs(cases).items():
        shape = {m["shape"] for m in members}
        assert len(shape) == 1, f"{name}: members disagree on shape: {shape}"
        declared = shape.pop()
        assert declared in SHAPES, f"{name}: unknown shape {declared!r}"
        truths = {m["role"]: m["truth"] for m in members}
        differ = truths["lucky"] != truths["foil"]
        assert differ == (declared == "opposite-truth"), (
            f"{name}: declared {declared} but truths are {truths}")


def test_at_least_one_pair_of_each_shape_exists(cases):
    """Both failure directions must stay represented. Losing every same-truth pair would
    leave the matrix blind to cue-ABSENCE misses, which is how the regex loses its
    hardest case ('do not merge that yet')."""
    shapes = {m["shape"] for members in _pairs(cases).values() for m in members}
    assert shapes == set(SHAPES), shapes


def test_fixture_text_never_leaks_its_case_label(cases):
    """ADR-0020's anti-gaming clause: the verdict must not be derivable from fixture
    labels or case-specific wording. The detector only ever receives `text`, so the
    check is that `text` cannot betray its own class.

    Scoped to the MULTI-WORD label forms only. An earlier version also matched bare
    words — 'positive', 'negative', 'fixture' — which are ordinary English a real turn
    may legitimately contain ('that's a negative result'), so the guard could fire on
    innocent fixture text while adding nothing: no plausible leak says 'negative'
    without saying which kind. (arbiter 2026-08-10, fragile-in-both-directions.)"""
    leaks = {lbl.replace("_", " ") for lbl in SCORED + UNSCORED if "_" in lbl}
    leaks |= {lbl for lbl in SCORED + UNSCORED if "_" in lbl}
    assert leaks, "no multi-word labels to check — the guard would be vacuous"
    for c in cases:
        low = c["text"].lower()
        for label in leaks:
            assert label not in low, f"{c['text']!r} leaks {label!r}"


def test_credit_requires_both_pair_members_not_just_the_lucky_one(cases):
    """The scoring rule itself, run against a KNOWN-shallow and a KNOWN-perfect judge.

    Testing it only against the real detector would prove nothing about the rule —
    standing pattern #10. A cue-keyed judge is right on every lucky member and must
    still earn ZERO; an oracle must earn every pair."""
    cue_keyed = score(cases, _regex)
    assert cue_keyed["pairs"], "no pairs to score"
    assert all(not p["credited"] for p in cue_keyed["pairs"])
    lucky_hits = [m for p in cue_keyed["pairs"] for m in p["members"]
                  if m["role"] == "lucky" and m["correct"]]
    assert lucky_hits, "expected the shallow judge to be RIGHT on lucky members"

    truth = {c["text"]: c["truth"] for c in cases}
    oracle = score(cases, lambda t: truth[t])
    assert all(p["credited"] for p in oracle["pairs"])


def test_regex_earns_no_pair_credit_and_misses_every_cue_free_positive(cases):
    """Characterization of the shipped surface heuristic, pinned so an improvement or a
    regression both show up as a failing test rather than a quiet number change.

    The finding this records: `regex_match` scores P=0.54 / R=0.54 / accuracy 0.50 over
    the 24 scored rows and earns 0/7 pair credit — and **all 7 of its true positives are
    lucky members**, so none is earned by meaning. Row metrics call it mediocre without
    saying why; the pair rule says exactly why.

    Drop the foils and the same fixtures report 12/17 ~ 70%, which is what a matrix
    without deliberately-constructed twins looks like."""
    result = score(cases, _regex)
    assert sum(p["credited"] for p in result["pairs"]) == 0
    assert sum(r["correct"] for r in result["positive"]) == 0
    assert sum(r["correct"] for r in result["negative"]) == len(result["negative"])


def test_unscored_rows_are_reported_and_never_counted(cases):
    """`allowed_boundary` and `outside_scope` must reach the report and no scoreboard —
    an unscorable case silently dropped is how coverage gaps hide."""
    result = score(cases, _regex)
    reported = {r["case"] for r in result["unscored"]}
    assert reported == set(UNSCORED), reported
    scored_texts = {r["text"] for r in result["positive"] + result["negative"]}
    scored_texts |= {m["text"] for p in result["pairs"] for m in p["members"]}
    assert not scored_texts & {r["text"] for r in result["unscored"]}


def test_disagreement_layers_are_a_closed_vocabulary():
    """The five-layer diagnosis is only useful if the layer names are fixed; an open
    string field would drift into free-text and stop being groupable."""
    assert LAYERS == ("wording", "fixture", "judge", "telemetry", "policy")
