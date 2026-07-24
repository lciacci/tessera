#!/usr/bin/env python3
"""Anchor cwd-relative hook paths in a project's .claude/settings.json.

WHY. A hook command inherits the SESSION cwd (the Bash tool keeps cwd across calls), so a
`cd` into another repo retargets every relative `.claude/scripts/X` path. In Tessera (source
tier, no global fallback) that silently killed twelve hooks (2026-07-24, fixed there).

Downstream severity is NOT uniform, and this module says so honestly:
  - The 7 mnemos hooks carry the ADR-0004 `elif $HOME/.claude/templates/X` fallback, which
    MASKS the bug: a mis-resolved local branch falls through to the absolute global copy.
    Anchoring them is defense-in-depth, not a live fix.
  - The Tessera hooks (tessera-gate-scan, tessera-spend-guard, tessera-spend-backstop) are
    LOCAL-ONLY (no fallback). On a wrong cwd in a cross-repo session they silently exit 0 —
    dead, exactly like Tessera's were. These are the live-vulnerable ones.
Anchoring the local branch to ${CLAUDE_PROJECT_DIR:-.}/ fixes both and matches what Tessera
already ships.

tessera-sync-harness cannot deliver this on its own: it only ADDS missing hooks, never
rewrites an existing command. This module is that missing rewrite; --patch-settings wires it.

CONSISTENCY GUARD (the ship-both-halves trap, avoided). The DETECTOR of unanchored paths is
doccheck._bare_hook_paths; this is the FIXER. If they drift, one flags what the other cannot
fix. test_anchor_settings asserts every fixer output is clean under the detector — so they
cannot disagree.

statusLine is deliberately out of scope: downstreams use the `sh -c '… .claude/scripts/X …'`
form with UNQUOTED local paths, which doccheck also does not flag (unquoted is indistinguishable
from a string mention). Same boundary on both sides; recorded as a follow-up, not a silent miss.

Stdlib-only (CLAUDE.md interpreter split), so a bare python3 runs it anywhere.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ANCHOR = "${CLAUDE_PROJECT_DIR:-.}"
# A path as its OWN quoted token, tolerating a leading ./. The ${CLAUDE_PROJECT_DIR:-.}/ anchor
# and the absolute $HOME/.claude/templates/ branch both sit between the " and .claude, so
# neither already-anchored form matches — only a bare local path does. Mirrors, on purpose,
# doccheck._HOOK_PATH_QUOTED; the shared test keeps them in lockstep.
_QUOTED = re.compile(r'"(?:\./)?((?:\.claude/scripts|hooks)/[A-Za-z0-9._-]+)"')


def anchor_command(cmd: str) -> str | None:
    """The anchored command, or None if there was nothing to change (idempotent)."""
    new = _QUOTED.sub(lambda m: f'"{ANCHOR}/{m.group(1)}"', cmd)
    return new if new != cmd else None


def anchor(settings: dict) -> tuple[dict, list[str]]:
    """Anchor every hook command in place. Returns (settings, changed-event-labels)."""
    changed: list[str] = []
    for event, groups in (settings.get("hooks") or {}).items():
        for group in groups:
            for hook in group.get("hooks", []):
                new = anchor_command(hook.get("command", ""))
                if new is not None:
                    hook["command"] = new
                    changed.append(event)
    return settings, changed


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    dry = "--dry-run" in args
    args = [a for a in args if a != "--dry-run"]
    path = Path(args[0]) if args else Path(".claude/settings.json")
    try:
        settings = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        print(f"cannot read {path}: {exc}", file=sys.stderr)
        return 2
    patched, changed = anchor(settings)
    if not changed:
        print(f"no change needed — {path} hook paths already anchored")
        return 0
    if dry:
        print(f"would anchor {len(changed)} command(s): {', '.join(sorted(set(changed)))}")
        return 0
    path.write_text(json.dumps(patched, indent=2) + "\n")
    print(f"anchored {len(changed)} command(s): {', '.join(sorted(set(changed)))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
