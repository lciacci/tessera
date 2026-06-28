#!/usr/bin/env python3
"""Gate-logging ratio report — read-only over existing logs, no hook, no state.

Surfaces the dogfood finding that gate logging under-captures (the model forgets
to call emit.py mid-flow). For each session's gate log it counts gates logged and
the edit-activity inside the session's gate-span window, so a low gates / high
edits row reads as under-logging.

Limits (printed in the footer too): 0-gate sessions are invisible (they leave no
log file); activity windows are bounded by first/last gate, so they undercount
work before the first gate and after the last. It's a trend tool, not a precise
miss-rate — that would need the deferred transcript scan.
"""
import glob
import json
import os
from datetime import datetime, timezone

LOGS = ".tessera/logs"
SIGNALS = ".mnemos/signals.jsonl"
EDIT_TOOLS = {"Edit", "Write", "NotebookEdit"}


def _iso_to_epoch(s):
    dt = datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")
    return dt.replace(tzinfo=timezone.utc).timestamp()


def load_edit_timestamps():
    """Epoch ts of every successful Edit/Write, sorted. Empty if no signals log."""
    out = []
    try:
        with open(SIGNALS) as f:
            for line in f:
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if d.get("tool") in EDIT_TOOLS and d.get("event") == "post" and d.get("success"):
                    out.append(d.get("ts", 0))
    except FileNotFoundError:
        pass
    return sorted(out)


def _gate_timestamps(path):
    ts = []
    with open(path) as f:
        for line in f:
            try:
                ts.append(_iso_to_epoch(json.loads(line)["ts"]))
            except (json.JSONDecodeError, KeyError, ValueError):
                pass
    return ts


def _activity(ts, edits):
    if len(ts) < 2:
        return "n/a (single gate — no span)"
    lo, hi = min(ts), max(ts)
    n = sum(1 for e in edits if lo <= e <= hi)
    return f"{n} edits in gate-span"


def session_rows(edits):
    rows = []
    for path in sorted(glob.glob(f"{LOGS}/*.jsonl")):
        ts = _gate_timestamps(path)
        rows.append((os.path.basename(path)[:8], len(ts), _activity(ts, edits)))
    return rows


def main():
    edits = load_edit_timestamps()
    rows = session_rows(edits)
    print(f"{'session':10} {'gates':>5}  activity-in-gate-span")
    for sid, gates, activity in rows:
        print(f"{sid:10} {gates:>5}  {activity}")
    total = sum(g for _, g, _ in rows)
    print(f"\n{len(rows)} sessions, {total} gates logged, {len(edits)} total edits on disk.")
    print("Caveat: 0-gate sessions absent (no log); spans undercount (bounded by gates).")


if __name__ == "__main__":
    main()
