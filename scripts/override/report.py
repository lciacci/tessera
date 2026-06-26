#!/usr/bin/env python3
"""Tabulate recent `override` events — the periodic review of design-principles §554.

    report.py                 # all overrides in the last week
    report.py --since 30d      # custom window: <N>{h,d,w}
    report.py --logs DIR       # point at a logs dir (default: .tessera/logs)

Stands in for the deferred `tess overrides report` front-end.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

_UNITS = {"h": "hours", "d": "days", "w": "weeks"}


def parse_since(s: str) -> timedelta:
    """'1w' / '30d' / '24h' -> timedelta. Raises ValueError on junk."""
    m = re.fullmatch(r"(\d+)([hdw])", s.strip())
    if not m:
        raise ValueError(f"bad --since {s!r}; use <N>h|d|w, e.g. 1w")
    return timedelta(**{_UNITS[m[2]]: int(m[1])})


def _parse_ts(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def load_overrides(logs_dir: Path, cutoff: datetime) -> list[dict]:
    """Override events at/after cutoff, newest first. Skips malformed lines."""
    rows: list[dict] = []
    for log in sorted(logs_dir.glob("*.jsonl")):
        for line in log.read_text(encoding="utf-8").splitlines():
            row = _row_if_recent(line, cutoff)
            if row:
                rows.append(row)
    return sorted(rows, key=lambda r: r["ts"], reverse=True)


def _row_if_recent(line: str, cutoff: datetime) -> dict | None:
    try:
        ev = json.loads(line)
    except ValueError:
        return None
    if ev.get("type") != "override":
        return None
    ts = _parse_ts(ev.get("ts", ""))
    if not ts or ts < cutoff:
        return None
    return {"ts": ev["ts"], **ev.get("data", {})}


def format_table(rows: list[dict]) -> str:
    """One line per override: ts  rule/kind  file:line  reason."""
    if not rows:
        return "No overrides in window."
    lines = [f"{len(rows)} override(s):"]
    for r in rows:
        loc = f"{r.get('file','?')}:{r.get('line','?')}"
        tag = f"{r.get('rule','?')}/{r.get('annotation_kind','?')}"
        lines.append(f"  {r['ts']}  {tag:24}  {loc:32}  {r.get('reason','')}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Report recent override events.")
    p.add_argument("--since", default="1w", help="window: <N>h|d|w (default 1w)")
    p.add_argument("--logs", default=".tessera/logs", help="logs dir")
    args = p.parse_args(argv)

    cutoff = datetime.now(timezone.utc) - parse_since(args.since)
    logs_dir = Path(args.logs)
    rows = load_overrides(logs_dir, cutoff) if logs_dir.is_dir() else []
    print(format_table(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
