#!/usr/bin/env python3
"""Precision spot-check for should_fire passive labels — the P10 gate, made runnable.

Read-only. Replays the should_fire classifier over gates a HUMAN already labeled
(the P7 ground truth on disk), feeding each stored `should_fire_basis` — the
verbatim disposition the human judged on — back to the classifier, and reports
the confusion matrix. This is the sample `tessera-watch` P10 wants before any
dashboard trusts classifier labels. It is how the recall-0.08 rubric bug in the
first cut (#34) was caught: n=3 backtest called it ~0.5; n=26 ground truth showed
it near-always-No, because terse option-picks ("1a 2a", "commit") read as
dismissals. After the rubric fix, recall 0.08 → 0.76 on the same set.

Ground truth is per-machine gitignored runtime state (.tessera/logs), so this is
a local dev/ops tool, not CI. Needs Ollama up. `--session <id>` scopes to one.

    python3 -m scripts.gate.eval_should_fire
"""
from __future__ import annotations

import argparse
import glob
import json
import sys

try:  # -m scripts.gate.eval_should_fire (package context)
    from .label import classify_should_fire
except ImportError:  # flat import in the gate test process (sys.path=scripts/gate)
    from label import classify_should_fire


def human_labeled_gates(session: str | None = None) -> list[dict]:
    """Gate `data` dicts a human labeled: should_fire set, no classifier stamp,
    and a basis to replay. The verbatim basis is what the human judged on, so
    the classifier gets exactly the same input — a fair comparison."""
    pattern = f".tessera/logs/{session}.jsonl" if session else ".tessera/logs/*.jsonl"
    out: list[dict] = []
    for path in glob.glob(pattern):
        for line in open(path, encoding="utf-8", errors="replace"):
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("type") != "suggestion_gate":
                continue
            d = ev.get("data") or {}
            if (d.get("should_fire") is not None and not d.get("labeled_by")
                    and d.get("should_fire_basis")):
                out.append(d)
    return out


def evaluate(gates: list[dict], *, generate) -> dict:
    """Confusion matrix of classifier-vs-human on should_fire. Positive = True."""
    m = {"tp": 0, "fp": 0, "tn": 0, "fn": 0, "skipped": 0, "mismatches": []}
    for d in gates:
        v = classify_should_fire(d.get("note"), d["should_fire_basis"], generate=generate)
        if v is None:
            m["skipped"] += 1
            continue
        h = bool(d["should_fire"])
        key = {(True, True): "tp", (True, False): "fp",
               (False, False): "tn", (False, True): "fn"}[(v, h)]
        m[key] += 1
        if v != h:
            m["mismatches"].append((h, v, d["should_fire_basis"][:70]))
    return m


def _report(m: dict) -> None:
    n = m["tp"] + m["fp"] + m["tn"] + m["fn"]
    if not n:
        print("no human-labeled gates with a basis to evaluate")
        return
    print(f"n={n} (skipped {m['skipped']} junk)  "
          f"human-pos={m['tp'] + m['fn']} human-neg={m['tn'] + m['fp']}")
    print(f"confusion: TP={m['tp']} FP={m['fp']} TN={m['tn']} FN={m['fn']}")
    if m["tp"] + m["fp"]:
        print(f"precision={m['tp'] / (m['tp'] + m['fp']):.2f}")
    if m["tp"] + m["fn"]:
        print(f"recall   ={m['tp'] / (m['tp'] + m['fn']):.2f}")
    print(f"accuracy ={(m['tp'] + m['tn']) / n:.2f}")
    if m["mismatches"]:
        print("--- mismatches (human→classifier) ---")
        for h, v, b in m["mismatches"]:
            print(f"  {h}→{v}: {b}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Eval should_fire classifier vs human labels.")
    p.add_argument("--session", help="scope to one session id")
    args = p.parse_args(argv)
    gates = human_labeled_gates(args.session)
    if not gates:
        print("no human-labeled gates found on disk (.tessera/logs)", file=sys.stderr)
        return 0
    from scripts.model_routing import _ollama_up, ollama_generate
    if not _ollama_up():
        print("Ollama down — cannot evaluate.", file=sys.stderr)
        return 0
    _report(evaluate(gates, generate=ollama_generate))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
