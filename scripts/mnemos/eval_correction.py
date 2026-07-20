#!/usr/bin/env python3
"""Replay the correction classifier against the silver-label set.

The silver set (`.mnemos/silver-corrections.jsonl`, gitignored like all runtime
state) is 125 turns judged by Claude under the spec-13 rubric on 2026-07-20 —
25 qwen-positives + 100 qwen-negatives, tuning session excluded. This script
re-runs the LIVE classifier prompt over those previews and prints the confusion
matrix, so any rubric/model change ships with its own before/after numbers
(the should_fire stop-loss lesson: an eval with a thin class measures half a
classifier — this set has both classes).

Labels: yes / weak (borderline) / no; carrier rows (bash-stdout, interrupt
markers riding as user turns) are excluded. --lenient counts weak as yes.

Run from repo root: .venv/bin/python -m scripts.mnemos.eval_correction [--lenient]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SILVER = Path(".mnemos/silver-corrections.jsonl")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Eval correction classifier vs silver labels.")
    p.add_argument("--lenient", action="store_true", help="count weak (borderline) as yes")
    args = p.parse_args(argv)

    if not SILVER.exists():
        print(f"{SILVER} missing — the silver set lives per-machine; see docstring.",
              file=sys.stderr)
        return 1
    rows = [json.loads(l) for l in SILVER.read_text().splitlines()]
    rows = [r for r in rows if not r.get("meta") and not r.get("carrier")]

    from scripts.mnemos.correction_detect import classify
    from scripts.model_routing import _ollama_up, ollama_generate
    if not _ollama_up():
        print("Ollama down — cannot replay.", file=sys.stderr)
        return 1

    truthy = ("yes", "weak") if args.lenient else ("yes",)
    tp = fp = fn = tn = null = 0
    for r in rows:
        verdict = classify(r["preview"], generate=ollama_generate)
        if verdict is None:
            null += 1
            continue
        truth = r["silver_label"] in truthy
        tp += verdict and truth
        fp += verdict and not truth
        fn += (not verdict) and truth
        tn += (not verdict) and not truth

    mode = "lenient" if args.lenient else "strict"
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    print(f"n={len(rows)} ({mode}, {null} null)  TP={tp} FP={fp} FN={fn} TN={tn}")
    print(f"precision={prec:.2f} recall={rec:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
