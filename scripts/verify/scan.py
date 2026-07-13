#!/usr/bin/env python3
"""Stop-hook verify-scan — an unverified "done" on a safety path must not pass quietly.

Spec 12: the most effective mechanism on 2026-07-12 (independent adversarial
verification, 3-for-3 refutations) rode on a human remembering to ask. This makes
the harness the trigger: if the session touched a safety path AND an assistant turn
claimed done/fixed/closed AND no `verification` event is logged, exit non-zero so
the model must state its claims and run `bin/tessera-verify` before finishing.

Detection is a recall net, like scripts/gate/scan.py — the model is the precision
filter, and `tessera-verify skip --reason` is the auditable escape hatch.

UNLIKE every other Tessera hook, this one fails LOUD: an internal error exits 1
("verify-scan broken") instead of 0. A silent scan on a safety-path session is the
exact fail-open class this spec exists to end (ADR-0006 tier 4). The fire cap
bounds the noise; it cannot be wedged into an unbounded nag.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

LOGS = Path(".tessera/logs")
MAX_FIRES_PER_SESSION = 3

# Spec 12's five safety paths, plus the verifier itself — machinery that guards
# the machinery is a safety path by definition.
SAFETY_PATHS = (
    "scripts/spend/",
    ".claude/scripts/",
    "hooks/",
    "install.sh",
    "scripts/doccheck.py",
    "scripts/verify/",
)

DONE_CLAIM = re.compile(
    r"\b(fixed|done|closed|resolved|complete|completed|shipped|green|passing)\b",
    re.IGNORECASE,
)


def iter_entries(path: str):
    """Transcript JSONL, main-thread only. Bad lines skipped; missing file raises."""
    with open(path) as f:
        for line in f:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not d.get("isSidechain"):
                yield d


def _tool_uses(entry: dict):
    content = (entry.get("message") or {}).get("content")
    if not isinstance(content, list):
        return
    for block in content:
        if block.get("type") == "tool_use":
            yield block.get("name", ""), block.get("input") or {}


def touched_safety_paths(transcript: str) -> list[str]:
    """Safety paths this session's tool calls touched (substring match — recall net)."""
    hit: list[str] = []
    for entry in iter_entries(transcript):
        for name, tool_input in _tool_uses(entry):
            haystack = tool_input.get("file_path", "") if name != "Bash" else ""
            if name == "Bash":
                haystack = tool_input.get("command", "")
            for sp in SAFETY_PATHS:
                if sp in haystack and sp not in hit:
                    hit.append(sp)
    return hit


def made_done_claim(transcript: str) -> bool:
    for entry in iter_entries(transcript):
        if entry.get("type") != "assistant":
            continue
        content = (entry.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if block.get("type") == "text" and DONE_CLAIM.search(block.get("text", "")):
                return True
    return False


def verification_logged(session_id: str) -> bool:
    """Any verification event counts — including a recorded skip. Skips are audited
    in `tessera-verify stats`, not re-nagged here."""
    path = LOGS / f"{session_id}.jsonl"
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return False
    for line in lines:
        try:
            if json.loads(line).get("type") == "verification":
                return True
        except json.JSONDecodeError:
            continue
    return False


def _fire_count(session_id: str) -> int:
    try:
        return int((LOGS / f".verify-scan-fires-{session_id}").read_text().strip())
    except (OSError, ValueError):
        return 0


def _bump_fires(session_id: str) -> None:
    try:
        LOGS.mkdir(parents=True, exist_ok=True)
        (LOGS / f".verify-scan-fires-{session_id}").write_text(str(_fire_count(session_id) + 1))
    except OSError:
        pass


def report(paths: list[str]) -> str:
    return "\n".join(
        [
            "VERIFY-SCAN: this session touched safety path(s) and claimed done/fixed,",
            "but no verification event is logged (spec 12).",
            "",
            "Safety paths touched: " + ", ".join(paths),
            "",
            "State the claims you are making, explicitly, and falsify them:",
            '  bin/tessera-verify --claim "<exact claim 1>" --claim "<exact claim 2>"',
            "",
            "If the detector over-counted (no fix/done claim was actually made, or the",
            "touch was trivial), record that instead — a skip is auditable, silence is not:",
            '  bin/tessera-verify skip --reason "<why no verification is needed>"',
        ]
    )


def _broken(session_id: str, why: str) -> int:
    """Fail LOUD, bounded: the scan itself broke, and that must reach the model."""
    if session_id and _fire_count(session_id) >= MAX_FIRES_PER_SESSION:
        return 0
    if session_id:
        _bump_fires(session_id)
    print(
        f"VERIFY-SCAN BROKEN: {why}\n"
        "The verify backstop cannot run, so an unverified safety change could pass\n"
        "silently. Verify manually (bin/tessera-verify) or fix the scan before finishing.",
        file=sys.stderr,
    )
    return 1


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        return _broken(argv[1] if len(argv) > 1 else "", "called without transcript/session args")
    transcript, session_id = argv[0], argv[1]
    if _fire_count(session_id) >= MAX_FIRES_PER_SESSION:
        return 0
    try:
        paths = touched_safety_paths(transcript)
        if not paths or not made_done_claim(transcript):
            return 0
        if verification_logged(session_id):
            return 0
    except Exception as e:  # noqa: BLE001 — loud, not open (spec 12)
        return _broken(session_id, f"{type(e).__name__}: {e}")
    _bump_fires(session_id)
    print(report(paths), file=sys.stderr)
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as e:  # noqa: BLE001
        print(f"VERIFY-SCAN BROKEN: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
