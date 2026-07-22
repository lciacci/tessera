#!/usr/bin/env python3
"""Add the local→global fallback branch to a project's mnemos hook commands (ADR-0004).

ADR-0004 built the freeze/thaw switch but left one half unbuilt, and named the moment to build
it: *"first real thaw of a grandfathered repo (build the settings auto-patch then)."* That
trigger fired 2026-07-22 on tess-dashboard.

THE PROBLEM THIS SOLVES. Projects scaffolded before ADR-0004 carry LOCAL-ONLY hook commands:

    if [ -x ".claude/scripts/X.sh" ]; then exec ".claude/scripts/X.sh"; fi; exit 0

`tessera-hooks thaw` deletes those local copies. With no `elif` reaching the global templates,
every mnemos hook then resolves to nothing and exits 0 — **silently**. Not one error, and the
hooks look wired in settings.json. That is why `thaw` refuses without the fallback, and why
this patch has to exist before a grandfathered repo can thaw at all.

The statusline is patched too, and it is not an afterthought: statusline was LOCAL-ONLY when
every sibling hook already had the fallback, and the observatory calls that "the literal root
cause" of F-003's first sighting (commit eb21914 fixed it).

Stdlib-only on purpose (CLAUDE.md's interpreter split) so it runs under any python3.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

LOCAL = r'\.claude/scripts/(mnemos-[a-z-]+\.sh)'

# Matches the pre-ADR-0004 local-only form and captures the script name. Deliberately strict:
# a command already carrying `elif` must not be touched, and anything we do not recognise is
# reported rather than rewritten. A settings patcher that guesses is worse than one that stops.
LOCAL_ONLY = re.compile(
    r'^if \[ -x "' + LOCAL + r'" \]; then exec "\.claude/scripts/\1"; fi; exit 0$'
)


def patch_command(cmd: str) -> str | None:
    """Two-tier form, or None if the command needs no change."""
    if "templates/mnemos" in cmd:
        return None                      # already has the fallback
    m = LOCAL_ONLY.match(cmd.strip())
    if not m:
        return None
    name = m.group(1)
    return (f'if [ -x ".claude/scripts/{name}" ]; then exec ".claude/scripts/{name}"; '
            f'elif [ -x "$HOME/.claude/templates/{name}" ]; then '
            f'exec "$HOME/.claude/templates/{name}"; fi; exit 0')


def patch_statusline(cmd: str) -> str | None:
    """The statusline is a bare path in grandfathered repos, not an if/exec block."""
    if "templates/mnemos" in cmd:
        return None
    m = re.fullmatch(r'\.claude/scripts/(mnemos-statusline\.sh)', cmd.strip())
    if not m:
        return None
    name = m.group(1)
    return (f"sh -c 'if [ -x .claude/scripts/{name} ]; then exec .claude/scripts/{name}; "
            f'elif [ -x "$HOME/.claude/templates/{name}" ]; then '
            f'exec "$HOME/.claude/templates/{name}"; fi\'')


def patch(settings: dict) -> tuple[dict, list[str], list[str]]:
    """Returns (patched, changed_names, unrecognized_commands)."""
    changed: list[str] = []
    unknown: list[str] = []

    for groups in settings.get("hooks", {}).values():
        for group in groups:
            for hook in group.get("hooks", []):
                cmd = hook.get("command", "")
                if "mnemos" not in cmd:
                    continue
                new = patch_command(cmd)
                if new:
                    hook["command"] = new
                    changed.append(re.search(LOCAL, new).group(1))
                elif "templates/mnemos" not in cmd:
                    unknown.append(cmd)

    sl = settings.get("statusLine")
    if isinstance(sl, dict) and "mnemos" in sl.get("command", ""):
        new = patch_statusline(sl["command"])
        if new:
            sl["command"] = new
            changed.append("mnemos-statusline.sh (statusLine)")
        elif "templates/mnemos" not in sl["command"]:
            unknown.append(sl["command"])

    return settings, changed, unknown


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    dry = "--dry-run" in args
    args = [a for a in args if a != "--dry-run"]
    path = Path(args[0]) if args else Path(".claude/settings.json")

    try:
        settings = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        print(f"cannot read {path}: {e}", file=sys.stderr)
        return 2

    patched, changed, unknown = patch(settings)

    if unknown:
        print(f"REFUSING: {len(unknown)} mnemos command(s) in an unrecognised shape.",
              file=sys.stderr)
        print("A settings patcher that guesses is worse than one that stops. Patch by hand:",
              file=sys.stderr)
        for c in unknown:
            print(f"  {c[:120]}", file=sys.stderr)
        return 1

    if not changed:
        print("no change needed — every mnemos command already has the global fallback")
        return 0

    if dry:
        print(f"would patch {len(changed)}: {', '.join(changed)}")
        return 0

    path.write_text(json.dumps(patched, indent=2) + "\n")
    print(f"patched {len(changed)} command(s) with the global fallback: {', '.join(changed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
