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

_ROOT = Path(os.environ.get("TESSERA_ROOT") or Path(__file__).resolve().parents[2])
CASES = _ROOT / "scripts" / "mnemos" / "fixtures" / "correction_cases.jsonl"

# Scored against `truth`. The other two are deliberately unscored: `allowed_boundary`
# permits either verdict by construction, and `outside_scope` rows are carrier turns
# that must never reach a detector at all.
SCORED = ("positive", "negative", "lucky_correct_negative")
UNSCORED = ("allowed_boundary", "outside_scope")
LAYERS = ("wording", "fixture", "judge", "telemetry", "policy")


def load_cases(path: Path | None = None) -> list[dict]:
    """Every fixture row, minus the `_readme` banner."""
    src = path or CASES
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
