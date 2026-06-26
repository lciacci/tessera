#!/usr/bin/env python3
"""Scan changed files for `tessera:*` override annotations and audit-log them.

Audit-only: this never changes pass/fail. It finds stated exceptions and emits
one `override` event per occurrence (docs/contracts/override-event.md). Non-
blocking by contract — always exits 0, so a host hook never fails on a scan error.

    scan.py                 # scan git-changed files, emit events
    scan.py --dry-run       # print findings, emit nothing
    scan.py FILE [FILE...]   # scan specific files
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

from emit import Override, append_event, build_event

# tessera:<rule>-<kind> with an optional ="reason" (present for skip-reason).
_ANNOTATION = re.compile(
    r'tessera:(?P<rule>tdd|quality-gates|security)-'
    r'(?P<kind>skip-reason|ignore-line)'
    r'(?:="(?P<reason>[^"]*)")?'
)


def find_overrides(text: str, filepath: str) -> list[Override]:
    """Pure: every override annotation in `text`, in line order."""
    out: list[Override] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        m = _ANNOTATION.search(line)
        if m:
            out.append(Override(m["rule"], m["kind"], filepath, lineno, m["reason"] or ""))
    return out


def _read_text(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def scan_files(files: list[str]) -> list[Override]:
    """Find overrides across many files."""
    found: list[Override] = []
    for f in files:
        found.extend(find_overrides(_read_text(f), f))
    return found


def changed_files() -> list[str]:
    """Tracked-but-modified + untracked files, per git. [] if not a repo."""
    try:
        out = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout
        extra = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            capture_output=True, text=True, check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return []
    names = {n for n in (out + extra).splitlines() if n}
    return sorted(n for n in names if Path(n).is_file())


def _emit_all(found: list[Override], session_id: str) -> None:
    for ov in found:
        append_event(build_event(ov, session_id=session_id), session_id)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Scan for tessera override annotations.")
    p.add_argument("files", nargs="*", help="files to scan (default: git-changed)")
    p.add_argument("--dry-run", action="store_true", help="print findings, emit nothing")
    args = p.parse_args(argv)

    found = scan_files(args.files or changed_files())
    if not found:
        return 0

    if args.dry_run:
        for ov in found:
            print(f"{ov.file}:{ov.line}: {ov.rule}/{ov.annotation_kind} {ov.reason}")
        return 0

    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if not session_id:
        print(f"{len(found)} override(s) found but CLAUDE_CODE_SESSION_ID unset; not logged",
              file=sys.stderr)
        return 0  # non-blocking

    _emit_all(found, session_id)
    print(f"{len(found)} override(s) audit-logged", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
