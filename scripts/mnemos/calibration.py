"""ADR-0020's calibration fixture matrix — loader and scorer.

One home for the scoring rule so the deterministic test (`test_correction_fixtures.py`)
and the live eval (`eval_correction.py`) cannot drift apart. See
`scripts/mnemos/fixtures/README.md` for what the five case types mean and why the
fixtures are tracked rather than living in the gitignored silver set.

The load-bearing rule is `_pair_results`: a `lucky_correct_negative` PAIR is credited
only when BOTH members are correct. Getting the lucky member right on its own earns
nothing — that is what ADR-0020's "the lucky-correct negative stays negative" means for
a classifier.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

def _root() -> Path:
    """Repo root, TESSERA_ROOT overrides. **Read at CALL time, not import time**, matching
    `scripts/gate/paths.py:root()` — a module-level constant cannot be overridden by a test
    that imported this module first, which silently pins the fixture path. (arbiter
    2026-08-10; the sibling `eval_correction.py` still has the import-time form.)"""
    override = os.environ.get("TESSERA_ROOT")
    return Path(override) if override else Path(__file__).resolve().parents[2]


def cases_path() -> Path:
    return _root() / "scripts" / "mnemos" / "fixtures" / "correction_cases.jsonl"

# Scored against `truth`. The other two are deliberately unscored: `allowed_boundary`
# permits either verdict by construction, and `outside_scope` rows are carrier turns
# that must never reach a detector at all.
SCORED = ("positive", "negative", "lucky_correct_negative")
UNSCORED = ("allowed_boundary", "outside_scope")
LAYERS = ("wording", "fixture", "judge", "telemetry", "policy")

# A pair's SHAPE, declared per fixture and asserted against the members' truths. Two are
# legitimate and they expose the cue from opposite sides; the declaration exists so an
# ACCIDENTAL same-truth pair (a foil that stopped being a foil) cannot pass as the other.
SHAPES = {
    "opposite-truth": "cue fires on a turn that is not a correction",
    "same-truth": "cue is absent from an equivalent turn, so it is missed",
}


def load_cases(path: Path | None = None) -> list[dict]:
    """Every fixture row, minus the `_readme` banner."""
    src = path or cases_path()
    rows = [json.loads(line) for line in src.read_text().splitlines() if line.strip()]
    return [r for r in rows if "_readme" not in r]


def _verdicts(cases: list[dict], predict) -> list[tuple[dict, bool]]:
    """Pair each case with the detector's verdict. `predict` takes text, returns bool."""
    return [(c, bool(predict(c["text"]))) for c in cases]


def _flat_results(judged: list[tuple[dict, bool]], case: str) -> list[dict]:
    """Per-row correctness for a case type scored directly against `truth`."""
    return [{"text": c["text"], "truth": c["truth"], "got": v,
             "correct": v == c["truth"]}
            for c, v in judged if c["case"] == case]


def _pair_results(judged: list[tuple[dict, bool]]) -> list[dict]:
    """Per-PAIR correctness. Credited only when every member is right — the rule that
    makes a lucky-correct verdict worth nothing on its own."""
    pairs: dict[str, list] = {}
    for c, v in judged:
        if c["case"] == "lucky_correct_negative":
            pairs.setdefault(c["pair"], []).append((c, v))
    out = []
    for name, members in sorted(pairs.items()):
        detail = [{"role": c["role"], "text": c["text"], "truth": c["truth"],
                   "got": v, "correct": v == c["truth"]} for c, v in members]
        out.append({"pair": name, "cue": members[0][0]["cue"],
                    "credited": all(d["correct"] for d in detail),
                    "members": detail})
    return out


def score(cases: list[dict], predict) -> dict:
    """Run `predict` over the matrix. Returns per-case-type results plus the
    unscored rows' verdicts, which are reported and never counted as error."""
    judged = _verdicts(cases, predict)
    return {
        "positive": _flat_results(judged, "positive"),
        "negative": _flat_results(judged, "negative"),
        "pairs": _pair_results(judged),
        "unscored": [{"case": c["case"], "text": c["text"], "got": v}
                     for c, v in judged if c["case"] in UNSCORED],
    }


def summary(result: dict) -> str:
    """One block, safe to print from either caller."""
    lines = []
    for kind in ("positive", "negative"):
        rows = result[kind]
        hit = sum(r["correct"] for r in rows)
        lines.append(f"{kind:<26} {hit}/{len(rows)}")
    pairs = result["pairs"]
    credited = sum(p["credited"] for p in pairs)
    lines.append(f"{'lucky_correct_negative':<26} {credited}/{len(pairs)} pairs credited")
    for p in pairs:
        if not p["credited"]:
            got = ", ".join(f"{m['role']}={'ok' if m['correct'] else 'MISS'}"
                            for m in p["members"])
            lines.append(f"    - {p['pair']:<20} cue={p['cue']!r:<12} {got}")
    lines.append(f"{'unscored (reported only)':<26} {len(result['unscored'])}")
    return "\n".join(lines)
