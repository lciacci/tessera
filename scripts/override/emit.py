#!/usr/bin/env python3
"""Append an `override` event to the structured log.

Sibling to scripts/gate/emit.py. Records that a rule exception was stated in
code via a `tessera:*` annotation — audit-only, see docs/contracts/override-event.md.

CLI (mainly for manual/testing use; scan.py calls build_event/append directly):
    emit.py --rule tdd --kind skip-reason --file a.py --line 42 --reason "scaffolding"
    emit.py ... --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

RULES = ("tdd", "quality-gates", "security")
KINDS = ("skip-reason", "ignore-line")


@dataclass
class Override:
    """One stated exception found in code."""
    rule: str
    annotation_kind: str
    file: str
    line: int
    reason: str = ""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def build_event(ov: Override, *, session_id: str, ts: str | None = None) -> dict:
    """The contract-shaped override event."""
    return {
        "type": "override",
        "ts": ts or _utc_now_iso(),
        "session_id": session_id,
        "source": "override-scanner",
        "data": {
            "rule": ov.rule,
            "annotation_kind": ov.annotation_kind,
            "file": ov.file,
            "line": ov.line,
            "reason": ov.reason,
        },
    }


def log_path(session_id: str) -> Path:
    return Path(".tessera/logs") / f"{session_id}.jsonl"


def append_event(event: dict, session_id: str) -> Path:
    """Append one JSON line to the session log; create the dir if needed."""
    path = log_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    return path


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Append an override event.")
    p.add_argument("--rule", required=True, choices=RULES)
    p.add_argument("--kind", required=True, choices=KINDS, dest="annotation_kind")
    p.add_argument("--file", required=True)
    p.add_argument("--line", required=True, type=int)
    p.add_argument("--reason", default="")
    p.add_argument("--dry-run", action="store_true", help="print event, do not append")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if not session_id:
        print("CLAUDE_CODE_SESSION_ID not set; cannot key the event", file=sys.stderr)
        return 2

    ov = Override(args.rule, args.annotation_kind, args.file, args.line, args.reason)
    event = build_event(ov, session_id=session_id)

    if args.dry_run:
        print(json.dumps(event, ensure_ascii=False))
        return 0

    path = append_event(event, session_id)
    print(f"override event appended → {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
